import logging
import inspect
import asyncio

from opencc import OpenCC
import telethon
import aiohttp
from telethon.tl import types

from .lib.expiringdict import ExpiringDict

logger = logging.getLogger(__name__)

CONVERTERS = [
  OpenCC('s2tw'),
  OpenCC('tw2s'),
  OpenCC('s2twp'),
  OpenCC('tw2sp'),
]

def text_to_query(s):
  variants = {c.convert(s) for c in CONVERTERS}
  if len(variants) > 1:
    s = ' OR '.join(f'({x})' for x in variants)
  else:
    s = variants.pop()

  return s

_ocr_cache = ExpiringDict(3600)
_ocr_cache_lock = asyncio.Lock()
_aiosession = None
async def _ocr_img(client, media, ocr_url):
  if isinstance(media, types.MessageMediaPhoto):
    key = media.photo.id
  else:
    key = media.document.id

  async with _ocr_cache_lock:
    cached = _ocr_cache.get(key)
    if cached is None:
      # coroutine cannot be awaited twice, but task can
      fu = asyncio.create_task(_ocr_img_no_cache(client, media, ocr_url))
      _ocr_cache[key] = fu

  if cached is None:
    return await fu
  else:
    if inspect.isawaitable(cached):
      return await cached
    else:
      return cached

async def _ocr_img_no_cache(client, media, ocr_url):
  if isinstance(media, types.MessageMediaPhoto):
    key = media.photo.id
    mime_type = 'image/jpeg'
  else:
    key = media.document.id
    mime_type = media.document.mime_type

  logger.info('Downloading media %d...', key)
  imgdata = await client.download_media(media, file=bytes)

  global _aiosession
  if _aiosession is None:
    _aiosession = aiohttp.ClientSession()

  formdata = aiohttp.FormData()
  formdata.add_field(
    'file', imgdata,
    filename = 'image', content_type = mime_type,
  )
  formdata.add_field('lang', 'zh-Hans')
  logger.info('Uploading media %d to OCR service...', key)
  try:
    res = await _aiosession.post(ocr_url, data=formdata)
    j = await res.json()
  except Exception as e:
    logger.error('OCR failed with %r', e)
    return []

  logger.info('OCR done.')
  ret = [r[1][0] for r in j['result']]
  _ocr_cache[key] = ret
  _ocr_cache.expire()
  return ret

async def format_msg(msg, ocr_url=None):
  if isinstance(msg, telethon.tl.patched.MessageService):
    # pinning messages
    return

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

  if ocr_url and (media := msg.media):
    if isinstance(media, types.MessageMediaPhoto) \
       or (isinstance(media, types.MessageMediaDocument)
           and msg.media.document.mime_type.startswith('image/')):
      if ocr_text := await _ocr_img(msg.client, media, ocr_url):
        text.append('[image]')
        text.extend(ocr_text)

  text = '\n'.join(x for x in text if x)

  return text
