import datetime
from enum import Enum, auto

import tomli
from telethon import TelegramClient
import copy
import os

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

  loop = asyncio.new_event_loop()
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

config_schema = {
    'telegram': {
        'api_id': 'int',
        'api_hash': 'str',
        'account': 'str',
        'session_db': 'str',
        'ipv6': 'str',
        'proxy': 'strs',
        'mark_as_read': 'bool',
        'index_groups': 'strs',
        'ocr_ignore_groups': 'strs',
    },
    'database': {
        'url': 'str',
        'first_year': 'int',
        'ocr_url': 'str',
        'ocr_socket': 'str',
    },
    'web': {
        'listen_host': 'str',
        'listen_port': 'int',
        'cache_dir': 'str',
        'default_avatar': 'str',
        'ghost_avatar': 'str',
        'prefix': 'str',
        'origins': 'strs',
    },
    'plugin': {
        'wordcloud': {
            'enabled': 'bool',
            'url': 'bool'
        },
        'adminapi': {
            'enabled': 'bool',
            'port': 'int'
        }
    }
}

def load_config(file):
  def merge_env(origin: dict[str, any]) -> dict[str, any]:
    def get_env(name: str, typ: str) -> any:
      if name not in os.environ:
        return None
      v = os.environ[name]
      if typ == 'str':
        return v
      if typ == 'int':
        return int(v)
      if typ == 'bool':
        return v.lower() == 'true'
      if typ == 'strs':
        return v.split(',')
      raise ValueError(f'unknown type {typ}')
    def f(x: any, ctx: list[str]) -> any:
      if isinstance(x, dict):
        return {k: y for k, v in x.items() if (y := f(v, ctx + [k.upper()]))}
      if isinstance(x, str):
        return get_env('_'.join(ctx), x)
      raise ValueError(f'unknown value {x}')

    def g(a: dict[str, any], b: dict[str, any]) -> dict[str, any]:
      r = copy.deepcopy(a)
      for k, v in b.items():
        old = a.get(k)
        if isinstance(old, dict) and isinstance(v, dict):
          r[k] = g(old, v)
        else:
          r[k] = copy.deepcopy(v)
      return r
    new = f(config_schema, [])
    return g(origin, new)
  if os.path.isfile(file):
    with open(file, 'rb') as f:
      return merge_env(tomli.load(f))
  else:
    print(f'{file} does not exist, using env vars only')
    return merge_env({})

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
