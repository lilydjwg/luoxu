import asyncio
import tempfile
import sys

from .. import wordcloud
from . import parse_args, generate_wordcloud

async def reply(text, file=None):
  print(text)
  if file:
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
      f.write(file)
      print(f'image saved as {f.name}')

async def main():
  dbstring, chat_id, *args = sys.argv[1:]
  wordcloud.DBSTRING = dbstring
  chat_id = int(chat_id)
  r = parse_args(args)
  if r is None:
    sys.exit('bad args.')
  else:
    endtime, is_full = r
    await generate_wordcloud(chat_id, '(n/a)', None, endtime, reply)

if __name__ == '__main__':
  try:
    import nicelogger
    nicelogger.enable_pretty_logging('INFO')
  except ImportError:
    pass
  loop = asyncio.get_event_loop()
  loop.run_until_complete(main())

