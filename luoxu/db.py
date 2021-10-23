import logging
import contextlib
from typing import Literal

import asyncpg
import telethon

from .util import format_name
from .indexing import text_to_query
from .types import SearchQuery, GroupNotFound

logger = logging.getLogger(__name__)

class PostgreStore:
  SEARCH_LIMIT = 50

  def __init__(self, address: str) -> None:
    self.address = address
    self.pool = None

  async def setup(self) -> None:
    self.pool = await asyncpg.create_pool(self.address)

  async def insert_message(self, conn, msg):
    if isinstance(msg, telethon.tl.patched.MessageService):
      # pinning messages
      return

    u = msg.sender
    text = []
    if m := msg.message:
      text.append(m)
    if p := msg.poll:
      poll_text = "\n".join(a.text for a in p.poll.answers)
      text.append(f'[poll] {p.poll.question}\n{poll_text}')
    if w := msg.web_preview:
      text.extend((
        '[webpage]',
        w.url,
        w.site_name,
        w.title,
        w.description,
      ))
    if d := msg.document:
      for a in d.attributes:
        if hasattr(a, 'file_name'):
          text.append(f'[file] {a.file_name}')
        if getattr(a, 'performer', None) and getattr(a, 'title', None):
          text.append(f'[audio] {a.title} - {a.performer}')
    text = '\n'.join(x for x in text if x)

    r = await conn.fetchrow(
      '''update messages set text = $1, updated_at = $2
         where msgid = $3 and group_id = $4 returning id''',
      text, msg.edit_date, msg.id, msg.chat.id)
    if r is None: # non-existent
      await conn.execute(
        '''insert into messages
          (group_id, msgid, from_user, from_user_name, text, created_at, updated_at) values
          ($1,       $2,    $3,        $4,             $5,   $6, $7) ''',
        msg.peer_id.channel_id,
        msg.id,
        u.id if u else None,
        format_name(u),
        text,
        msg.date,
        msg.edit_date,
      )
      logger.info('inserted <%s> [%s] %s', msg.chat.title, msg.id, text)
    else:
      logger.info('updated <%s> [%s] %s', msg.chat.title, msg.id, text)

  async def get_group(self, conn, group_id: int):
    sql = '''\
        select * from tg_groups
        where group_id = $1'''
    return await conn.fetchrow(sql, group_id)

  async def insert_group(self, conn, group):
    g = await self.get_group(conn, group.id)
    if g:
      return g

    sql = '''\
        insert into tg_groups
        (group_id, name, pub_id) values
        ($1,       $2,  $3)
        returning *'''
    return await conn.fetchrow(
      sql,
      group.id,
      group.title,
      group.username,
    )

  async def loaded_upto(
    self, conn, group_id: int,
    direction: Literal[1, -1], msgid: int,
  ) -> None:
    sql = '''update tg_groups set %s = $1 where group_id = $2''' % ({
      1: 'loaded_last_id', -1: 'loaded_first_id',
    }[direction])
    await conn.execute(sql, msgid, group_id)

  @contextlib.asynccontextmanager
  async def get_conn(self):
    async with self.pool.acquire() as conn, conn.transaction():
      yield conn

  async def search(self, q: SearchQuery) -> list[dict]:
    async with self.get_conn() as conn:
      if q.group:
        group = await self.get_group(conn, q.group)
        if not group:
          raise GroupNotFound(q.group)
        groupinfo = {
          q.group: [group['pub_id'], group['name']],
        }
      else:
        sql = '''select group_id, pub_id, name from tg_groups'''
        rows = await conn.fetch(sql)
        groupinfo = {row['group_id']: [row['pub_id'], row['name']] for row in rows}

      # run a subquery to highlight because it would highlight all
      # matched rows (ignoring limits) otherwise
      common_cols = 'msgid, group_id, from_user, from_user_name, created_at, updated_at'
      sql = '''select {0}, text from messages where 1 = 1'''
      highlight = None
      params = []
      if q.group:
        sql += f''' and group_id = ${len(params)+1}'''
        params.append(q.group)
      if q.terms:
        query = text_to_query(q.terms.strip())
        if not query:
          raise ValueError
        sql += f''' and text &@~ ${len(params)+1}'''
        params.append(query)
        highlight = f'''pgroonga_highlight_html(text, pgroonga_query_extract_keywords(${len(params)+1}), 'message_idx') as html'''
        params.append(query)
      if q.sender:
        sql += f''' and from_user = ${len(params)+1}'''
        params.append(q.sender)
      if q.start:
        sql += f''' and created_at > ${len(params)+1}'''
        params.append(q.start)
      if q.end:
        sql += f''' and created_at < ${len(params)+1}'''
        params.append(q.end)

      sql += f' order by created_at desc limit {self.SEARCH_LIMIT}'
      if highlight:
        sql = f'select {{0}}, {highlight} from ({sql}) as t'
      sql = sql.format(common_cols)
      logger.debug('searching: %s: %s', sql, params)
      rows = await conn.fetch(sql, *params)
      return groupinfo, rows

  async def get_groups(self):
    async with self.get_conn() as conn:
      sql = '''select * from tg_groups'''
      return await conn.fetch(sql)

  async def find_names(self, group: int, q: str) -> list[tuple[str, str]]:
    q = q.strip()
    if not q:
      raise ValueError
    async with self.get_conn() as conn:
      if group:
        gq = ' and group_id = $2'
        args = (q, group)
      else:
        gq = ''
        args = (q,)
      sql = f'''\
          with cte as (
            select row_number() over
                (partition by from_user, from_user_name order by id desc) as rn,
              from_user, from_user_name
            from messages
            where from_user_name &@ $1{gq}
            order by id desc)
          select * from cte
          where rn = 1 limit 10'''
      return [(r['from_user'], r['from_user_name'])
              for r in await conn.fetch(sql, *args)]

