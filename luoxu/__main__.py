import os
import re
import asyncio
import logging
import operator
from functools import partial
import importlib
import inspect

from telethon import events
from aiohttp import web

from .db import PostgreStore
from .group import GroupHistoryIndexer
from .util import load_config, UpdateLoaded, create_client
from .auth import TokenManager
from . import web as myweb
from .ctxvars import msg_source

logger = logging.getLogger(__name__)

class Indexer:
  def __init__(self, config):
    self.config = config
    self.mark_as_read = config['telegram'].get('mark_as_read', True)
    self.dbstore = None
    self.msg_handlers = []

  async def load_plugins(self, client):
    for plugin, conf in self.config.get('plugin', {}).items():
      if not conf.get('enabled', True):
        continue

      logger.info('loading plugin %s', plugin)
      mod = importlib.import_module(f'luoxu_plugins.{plugin}')
      ret = mod.register(self, client)
      if inspect.isawaitable(ret):
        await ret

  def add_msg_handler(self, handler, pattern='.*'):
    self.msg_handlers.append((handler, re.compile(pattern)))

  async def on_message(self, event):
    if isinstance(event, events.MessageEdited.Event):
      msg_source.set('editmsg')
    else:
      msg_source.set('newmsg')
    msg = event.message
    use_ocr = msg.peer_id.channel_id not in self.ocr_ignore_group_ids
    dbstore = self.dbstore

    if self.group_forward_history_done.get(msg.peer_id.channel_id, False):
      update_loaded = UpdateLoaded.update_last
    else:
      update_loaded = UpdateLoaded.update_none
    await dbstore.insert_messages([msg], update_loaded, use_ocr)

    if self.mark_as_read:
      try:
        await msg.mark_read()
      except ConnectionError as e:
        logger.warning('cannot mark as read: %r', e)

    for handler, pattern in self.msg_handlers:
      logger.debug('message: %s, pattern: %s', msg.text, pattern)
      if pattern.fullmatch(msg.text):
        asyncio.create_task(handler(event))

  async def run(self):
    config = self.config
    tg_config = config['telegram']
    client = create_client(tg_config)

    db = PostgreStore(config['database'])
    await db.setup()
    self.dbstore = db

    ttl = int(tg_config.get('auth_expire', 3600))
    self.token_manager = TokenManager(ttl)

    await client.start(tg_config['account'])
    index_group_ids = []
    ocr_ignore_group_ids = []
    auth_enable_group_ids = []
    group_entities = []
    dialogs = None
    for g in tg_config['index_groups']:
      if g.startswith('@'):
        group = await client.get_entity(g)
      else:
        g2 = int(g)
        try:
          group = await client.get_entity(g2)
        except ValueError:
          if dialogs is None:
            dialogs = await client.get_dialogs()
          group = [d.entity for d in dialogs if d.entity.id == g2][0]

      if g in tg_config.get('ocr_ignore_groups', ()):
        ocr_ignore_group_ids.append(group.id)

      if g in tg_config.get('auth_enable_groups', ()):
        auth_enable_group_ids.append(group.id)

      index_group_ids.append(group.id)
      group_entities.append(group)

    self.ocr_ignore_group_ids = ocr_ignore_group_ids
    self.auth_enable_group_ids = auth_enable_group_ids
    client.add_event_handler(self.on_message, events.NewMessage(chats=index_group_ids))
    client.add_event_handler(self.on_message, events.MessageEdited(chats=index_group_ids))

    await self.load_plugins(client)

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
      auth_enable_groups = auth_enable_group_ids,
      token_manager = self.token_manager,
    )
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(
      runner,
      web_config['listen_host'], web_config['listen_port'],
    )
    await site.start()

    try:
      while True:
        try:
          await self.run_on_connected(client, db, group_entities)
          logger.warning('disconnected, reconnecting in 1s')
          await asyncio.sleep(1)
        except (
          ConnectionError,
          asyncio.CancelledError,
          asyncio.exceptions.IncompleteReadError,
        ) as e:
          if isinstance(e.__context__, KeyboardInterrupt):
            break
          else:
            logger.exception('connection error, retry in 5s')
            await asyncio.sleep(5)
    finally:
      await runner.cleanup()

  async def run_on_connected(self, client, db, group_entities):
    self.group_forward_history_done = {}
    runnables = []
    for group in group_entities:
      ginfo = await self.init_group(group)
      use_ocr = group.id not in self.ocr_ignore_group_ids
      gi = GroupHistoryIndexer(group, ginfo, use_ocr)
      runnables.append(gi.run(
        client, db,
        partial(operator.setitem, self.group_forward_history_done, group.id, True)
      ))

    if not client.is_connected():
      await client.start(self.config['telegram']['account'])
      # reset last ping to avoid reconnecting every 60s
      logger.info('resetting client._sender._ping')
      client._sender._ping = None

    # we do need to fetch history on startup because telethon doesn't
    # record group's pts in database.
    #
    # we also need to fetch history on reconnect because sometimes we still
    # don't see some missed updates (I don't know why).
    #
    # we may still miss edits that happen while we're offline and missed
    # the updates.
    gis = asyncio.gather(*runnables)
    # await client.catch_up()
    try:
      await client.run_until_disconnected()
    finally:
      gis.cancel()
      try:
        await gis
      except asyncio.CancelledError:
        pass

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
