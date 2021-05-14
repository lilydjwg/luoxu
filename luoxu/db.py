import logging
from typing import List

import asyncpg
import telethon

from .util import format_name
from .indexing import text_to_vector, text_to_query
from .types import SearchQuery, GroupNotFound

logger = logging.getLogger(__name__)

class PostgreStore:
  def __init__(self, address: str) -> None:
    self.address = address
    self.conn = None

  async def clone(self):
    new = self.__class__(self.address)
    await new.setup()
    return new

  async def setup(self) -> None:
    self.conn = await asyncpg.connect(self.address)

  async def last_id(self, group_id: int) -> int:
    row = await self.conn.fetchrow(
      '''select msgid from messages
        where group_id = $1
        order by msgid desc limit 1''', group_id)
    if not row:
      return 0
    return row['msgid']

  async def first_id(self, group_id: int) -> int:
    row = await self.conn.fetchrow(
      '''select msgid from messages
        where group_id = $1
        order by msgid asc limit 1''', group_id)
    if not row:
      return 0
    return row['msgid']

  async def insert_message(self, msg):
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

    sql = '''\
        insert into messages
        (group_id, msgid, from_user, from_user_name, text, textvector, datetime) values
        ($1,       $2,    $3,        $4,             $5,   to_tsvector('english', $6), $7)
        '''
    logger.debug('inserting [%s] %s', msg.id, text)
    await self.conn.execute(
      sql,
      msg.peer_id.channel_id,
      msg.id,
      u.id if u else None,
      format_name(u),
      text,
      text_to_vector(text),
      msg.date,
    )

  async def get_group(self, group_id: int):
    sql = '''\
        select * from tg_groups
        where group_id = $1'''
    return await self.conn.fetchrow(sql, group_id)

  async def get_groups(self):
    sql = '''select * from tg_groups'''
    return await self.conn.fetch(sql)

  async def insert_group(self, group):
    sql = '''\
        insert into tg_groups
        (group_id, name, pub_id) values
        ($1,       $2,  $3)'''
    await self.conn.execute(
      sql,
      group.id,
      group.title,
      group.username,
    )

  async def updated(self, group_id: int) -> None:
    sql = '''\
        update tg_groups
        set last_sync_dt = current_timestamp
        where group_id = $1'''
    await self.conn.execute(sql, group_id)

  async def group_done(self, group_id: int) -> None:
    sql = '''\
        update tg_groups
        set start_reached = true
        where group_id = $1'''
    await self.conn.execute(sql, group_id)

  def transaction(self):
    return self.conn.transaction()

  async def search(self, q: SearchQuery) -> List[dict]:
    group = await self.get_group(q.group)
    if not group:
      raise GroupNotFound(q.group)

    sql = '''
      select
        msgid, from_user, from_user_name, text, datetime
      from messages where
      group_id = $1
    '''
    params = [q.group]
    if q.terms:
      sql += f''' and textvector @@ websearch_to_tsquery('english', ${len(params)+1})'''
      params.append(text_to_query(q.terms))
    if q.sender:
      sql += f''' and from_user = ${len(params)+1}'''
      params.append(q.sender)
    if q.start:
      sql += f''' and datetime > ${len(params)+1}'''
      params.append(q.start)
    if q.end:
      sql += f''' and datetime < ${len(params)+1}'''
      params.append(q.end)

    sql += ' order by datetime desc limit 50'
    logger.debug('searching: %s: %s', sql, params)
    rows = await self.conn.fetch(sql, *params)
    return group['pub_id'], rows

