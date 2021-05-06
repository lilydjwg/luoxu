import asyncio

from telethon import TelegramClient
from aiohttp import web

from .db import PostgreStore
from .group import GroupIndexer
from .util import load_config
from . import web as myweb

async def main():
  config = load_config('config.toml')
  tg_config = config['telegram']

  client = TelegramClient(
    tg_config['session_db'],
    tg_config['api_id'],
    tg_config['api_hash'])
  await client.start(tg_config['account'])

  db = PostgreStore(config['database']['url'])
  await db.setup()

  web_config = config['web']
  app = myweb.setup_app(db, client, web_config['prefix'])
  runner = web.AppRunner(app)
  await runner.setup()
  site = web.TCPSite(
    runner,
    web_config['listen_host'], web_config['listen_port'],
  )
  await site.start()

  group1 = await client.get_entity('@archlinuxcn_group')
  group2 = await client.get_entity('@archlinuxcn_offtopic')
  g1 = GroupIndexer(group1)
  g2 = GroupIndexer(group2)
  try:
    await asyncio.gather(
      g1.run(client, await db.clone()),
      g2.run(client, await db.clone()),
    )
  finally:
    await runner.cleanup()

if __name__ == '__main__':
  from .lib.nicelogger import enable_pretty_logging
  enable_pretty_logging('DEBUG')
  # enable_pretty_logging('INFO')

  from .util import run_until_sigint
  run_until_sigint(main())
