import datetime
from enum import Enum, auto

import tomli
from telethon import TelegramClient

def format_name(user) -> str:
  if user is None:
    return '(null)'

  try:
    l = [user.first_name, user.last_name]
  except AttributeError:
    return user.title # channel
  return ' '.join(x for x in l if x)

def fromtimestamp(ts: int) -> datetime.datetime:
  return datetime.datetime.fromtimestamp(ts).astimezone()

def run_until_sigint(fu):
  import asyncio

  loop = asyncio.get_event_loop()
  fu = loop.create_task(fu)

  try:
    loop.run_until_complete(fu)
  except KeyboardInterrupt:
    fu.cancel()
    try:
      loop.run_until_complete(fu)
    except asyncio.CancelledError:
      pass
    print('Cancelled.')

def load_config(file):
  with open(file, 'rb') as f:
    return tomli.load(f)

class UpdateLoaded(Enum):
  update_none = auto()
  update_first = auto()
  update_last = auto()
  update_both = auto()

def create_client(tg_config):
  client = TelegramClient(
    tg_config['session_db'],
    tg_config['api_id'],
    tg_config['api_hash'],
    use_ipv6 = tg_config.get('ipv6', False),
    auto_reconnect = False, # we would miss updates between connections
  )
  if proxy := tg_config.get('proxy'):
    import socks
    client.set_proxy((socks.SOCKS5, proxy[0], int(proxy[1])))
  return client
