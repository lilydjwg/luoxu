import os
import re
import asyncio
import logging
import operator
from functools import partial
import importlib

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
    self.mark_as_read = config['telegram'].get('mark_as_read', True)
    self.dbstore = None
    self.msg_handlers = []

  def load_plugins(self):
    for plugin, conf in self.config.get('plugin', {}).items():
      if not conf.get('enabled', True):
        continue

      logger.info('loading plugin %s', plugin)
      mod = importlib.import_module(f'luoxu_plugins.{plugin}')
      mod.register(self)

  def add_msg_handler(self, handler, pattern='.*'):
    self.msg_handlers.append((handler, re.compile(pattern)))

  async def on_message(self, event):
    msg = event.message
    dbstore = self.dbstore
    async with dbstore.get_conn() as conn:
      await dbstore.insert_message(conn, msg)
      if self.group_forward_history_done.get(msg.peer_id.channel_id, False):
        await dbstore.loaded_upto(conn, msg.peer_id.channel_id, 1, msg.id)

    if self.mark_as_read:
      await msg.mark_read()

    for handler, pattern in self.msg_handlers:
      logger.debug('message: %s, pattern: %s', msg.text, pattern)
      if pattern.fullmatch(msg.text):
        asyncio.create_task(handler(event))

  async def run(self):
    config = self.config
    tg_config = config['telegram']

    client = TelegramClient(
      tg_config['session_db'],
      tg_config['api_id'],
      tg_config['api_hash'],
      auto_reconnect = False, # we would miss updates between connections
    )
    if proxy := tg_config.get('proxy'):
      import socks
      client.set_proxy((socks.SOCKS5, proxy[0], int(proxy[1])))

    db = PostgreStore(config['database']['url'])
    await db.setup()
    self.dbstore = db

    web_config = config['web']
    cache_dir = web_config['cache_dir']
    os.makedirs(cache_dir, exist_ok=True)
    app = myweb.setup_app(
      db, client,
      os.path.abspath(cache_dir),
      os.path.abspath(web_config['default_avatar']),
      os.path.abspath(web_config['ghost_avatar']),
      prefix = web_config['prefix'],
      origins = web_config['origins'],
    )
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(
      runner,
      web_config['listen_host'], web_config['listen_port'],
    )
    await site.start()

    await client.start(tg_config['account'])
    index_group_ids = []
    group_entities = []
    for g in tg_config['index_groups']:
      if not g.startswith('@'):
        g = int(g)
      group = await client.get_entity(g)
      index_group_ids.append(group.id)
      group_entities.append(group)

    client.add_event_handler(self.on_message, events.NewMessage(chats=index_group_ids))
    client.add_event_handler(self.on_message, events.MessageEdited(chats=index_group_ids))

    self.load_plugins()

    try:
      while True:
        await self.run_on_connected(client, db, group_entities)
        logger.warning('disconnected, reconnecting in 1s')
        await asyncio.sleep(1)
    finally:
      await runner.cleanup()

  async def run_on_connected(self, client, db, group_entities):
    self.group_forward_history_done = {}
    runnables = []
    for group in group_entities:
      ginfo = await self.init_group(group)
      gi = GroupHistoryIndexer(group, ginfo)
      runnables.append(gi.run(
        client, db,
        partial(operator.setitem, self.group_forward_history_done, group.id, True)
      ))

    if not client.is_connected():
      await client.start(self.config['telegram']['account'])

    gis = asyncio.gather(*runnables)
    try:
      await client.run_until_disconnected()
    except ConnectionError:
      gis.cancel()

  async def init_group(self, group):
    logger.info('init_group: %r', group.title)
    async with self.dbstore.get_conn() as conn:
      return await self.dbstore.insert_group(conn, group)

if __name__ == '__main__':
  from .lib.nicelogger import enable_pretty_logging
  # enable_pretty_logging('DEBUG')
  enable_pretty_logging('INFO')

  from .util import run_until_sigint

  import argparse

  parser = argparse.ArgumentParser()
  parser.add_argument('--config', default='config.toml',
                      help='config file path')
  args = parser.parse_args()

  config = load_config(args.config)
  indexer = Indexer(config)
  run_until_sigint(indexer.run())
