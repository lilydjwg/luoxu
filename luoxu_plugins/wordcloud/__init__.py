import time
import asyncio
import io
import datetime
import math
import subprocess
import logging

from telethon import utils
from wordcloud import WordCloud

logger = logging.getLogger('luoxu_plugins.wordcloud')

CUTWORDS_EXE = 'luoxu-cutwords'
FONT = '/usr/share/fonts/adobe-source-han-sans/SourceHanSansCN-Normal.otf'
TIMEZONE = datetime.timezone(datetime.timedelta(hours=8))
DBSTRING: str

def gen_image(words, stream):
  image = WordCloud(
    font_path = FONT, width = 800, height = 400,
  ).generate_from_frequencies(words).to_image()
  image.save(stream, 'PNG')

async def generate_wordcloud(chat, target_user, endtime, msg):
  logger.info(
    '生成词云，群组 %s，用户 %s, 结束时间 %s',
    chat.title,
    utils.get_display_name(target_user),
    endtime.strftime('%Y-%m-%d %H:%M:%S%z'),
  )
  st = datetime.datetime.now().astimezone(TIMEZONE)
  cmd = [
    CUTWORDS_EXE,
    DBSTRING,
    chat.id,
    int(endtime.timestamp()),
    target_user.id if target_user else 0,
  ]
  cmd = [str(x) for x in cmd]
  p = await asyncio.create_subprocess_exec(
    *cmd,
    stdout=subprocess.PIPE,
  )
  data = await p.stdout.read()
  lines = data.decode().splitlines()
  it = iter(lines)
  total_messages = int(next(it))
  words = {}
  for line in it:
    w, n = line.split(None, 1)
    words[w] = int(n)
  st2 = time.time()
  logger.info('分析完成，用时 %.3fs', st2 - st.timestamp())

  if not words:
    await msg.reply('落絮词云未找到符合条件的消息。')
    return

  stream = io.BytesIO()
  loop = asyncio.get_event_loop()
  await loop.run_in_executor(None, gen_image, words, stream)
  st3 = time.time()
  logger.info('生成完成，用时 %.3fs', st3 - st2)

  await msg.reply(
    f'落絮词云为您生成消息词云\n'
    f'{chat.title} 群组 {utils.get_display_name(target_user)}\n'
    f'从 {endtime:%Y-%m-%d %H:%M:%S}\n'
    f'到 {st:%Y-%m-%d %H:%M:%S}\n'
    f'共 {total_messages} 条消息',
    file = (stream.getvalue() if words else None),
  )
  logger.info('回复完成，用时 %.3fs', time.time() - st3)

async def send_help(event):
  '''send /luoxucloud command help.'''
  help_message = await event.reply(
    '发送 /luoxucloud + 天数，查看自己的消息词云。\n'
    '回复 /luoxucloud + 天数，查看别人的消息词云。\n'
    '发送 /luoxucloud + 天数 + full，查看所有人的消息词云。\n'
    '\n'
    '天数必须是 float 类型。\n'
    '数字较大时，生成可能需要较长时间，请耐心等待。\n'
    '\n'
    '例如： /luoxucloud 7\n'
    '\n'
    '项目源码： https://github.com/lilydjwg/luoxu/tree/master/luoxu_plugins/wordcloud'
  )

  await asyncio.sleep(60)
  try:
    await help_message.delete()
  except:
    logger.warn('删除帮助消息失败')

async def wordcloud(event):
  logger.debug('wordcloud on event: %r', event)
  msg = event.message
  _, *args = msg.text.split()

  is_wrong_usage = False
  is_full = False
  if not args or len(args) > 2:
    is_wrong_usage = True
  else:
    try:
      days = float(args[0])
    except ValueError:
      is_wrong_usage = True
    else:
      if math.isnan(days) or math.isinf(days):
        is_wrong_usage = True
      if len(args) == 2:
        if args[1] == 'full':
          is_full = True
        else:
          is_wrong_usage = True
      days = min(365 * 30, days)
      endtime = datetime.datetime.now().astimezone(TIMEZONE) - datetime.timedelta(days=days)

  if is_wrong_usage:
    await send_help(event)
    return

  if is_full:
    target_user = None
  else:
    if msg.is_reply:
      reply = await msg.get_reply_message()
      target_user = await reply.get_sender()
    else:
      target_user = await msg.get_sender()

  chat = await event.get_chat()
  await generate_wordcloud(
    chat, target_user, endtime, msg,
  )

def register(indexer):
  global DBSTRING
  DBSTRING = indexer.config['plugin']['wordcloud']['url']
  indexer.add_msg_handler(wordcloud, pattern='/luoxucloud(?: .*)?')
