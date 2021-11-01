import datetime
from enum import Enum, auto

import toml

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
  with open(file) as f:
    return toml.load(f)

class UpdateLoaded(Enum):
  update_none = auto()
  update_first = auto()
  update_last = auto()
  update_both = auto()
