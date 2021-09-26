import asyncio
import logging
import operator
from functools import partial

from telethon import TelegramClient, events
from aiohttp import web

from .db import PostgreStore
from .group import GroupHistoryIndexer
from .util import load_config
from . import web as myweb

logger = logging.getLogger(__name__)

class Indexer:
  def __init__(self, config):
    self.config = config
    self.group_forward_history_done = {}
    self.dbstore = None

  async def on_message(self, event):
    msg = event.message
    dbstore = self.dbstore
    async with dbstore.get_conn() as conn:
      await dbstore.insert_message(conn, msg)
      if self.group_forward_history_done[msg.peer_id.channel_id]:
        await dbstore.loaded_upto(conn, msg.peer_id.channel_id, 1, msg.id)

  async def run(self):
    config = self.config
    tg_config = config['telegram']

    client = TelegramClient(
      tg_config['session_db'],
      tg_config['api_id'],
      tg_config['api_hash'])
    if proxy := tg_config.get('proxy'):
      import socks
      client.set_proxy((socks.SOCKS5, proxy[0], int(proxy[1])))
    await client.start(tg_config['account'])

    db = PostgreStore(config['database']['url'])
    await db.setup()
    self.dbstore = db

    web_config = config['web']
    app = myweb.setup_app(db, client, web_config['prefix'])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(
      runner,
      web_config['listen_host'], web_config['listen_port'],
    )
    await site.start()

    runnables = []
    index_group_ids = []
    for g in tg_config['index_groups']:
      if not g.startswith('@'):
        g = int(g)
      group = await client.get_entity(g)
      index_group_ids.append(group.id)
      self.group_forward_history_done[group.id] = False

      ginfo = await self.init_group(group)
      gi = GroupHistoryIndexer(group, ginfo)
      runnables.append(gi.run(
        client, db,
        partial(operator.setitem, self.group_forward_history_done, group.id, True)
      ))

    client.add_event_handler(self.on_message, events.NewMessage(chats=index_group_ids))
    client.add_event_handler(self.on_message, events.MessageEdited(chats=index_group_ids))

    try:
      await asyncio.gather(*runnables)
      await client.run_until_disconnected()
    finally:
      await runner.cleanup()

  async def init_group(self, group):
    logger.info('init_group: %r', group.title)
    async with self.dbstore.get_conn() as conn:
      return await self.dbstore.insert_group(conn, group)

if __name__ == '__main__':
  from .lib.nicelogger import enable_pretty_logging
  enable_pretty_logging('DEBUG')
  # enable_pretty_logging('INFO')

  from .util import run_until_sigint

  config = load_config('config.toml')
  indexer = Indexer(config)
  run_until_sigint(indexer.run())
