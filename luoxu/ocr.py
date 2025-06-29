import logging
import inspect
import asyncio
import time

import aiohttp
from telethon.tl import types

from .lib.expiringdict import ExpiringDict

logger = logging.getLogger(__name__)

class OCRService:
  def __init__(self, ocr_url, ocr_socket=None):
    self._ocr_cache = ExpiringDict(3600)
    self._ocr_cache_lock = asyncio.Lock()
    self.ocr_url = ocr_url

    if ocr_socket:
      conn = aiohttp.UnixConnector(path=ocr_socket)
      session = aiohttp.ClientSession(connector=conn)
    else:
      session = aiohttp.ClientSession()

    self._aiosession = session

  async def ocr_img(self, client, media, group_title):
    if isinstance(media, types.MessageMediaPhoto):
      key = media.photo.id
    else:
      key = media.document.id

    async with self._ocr_cache_lock:
      cached = self._ocr_cache.get(key)
      if cached is None:
        # coroutine cannot be awaited twice, but task can
        fu = asyncio.create_task(self._ocr_img_no_cache(client, media, group_title))
        self._ocr_cache[key] = fu

    if cached is None:
      return await fu
    else:
      if inspect.isawaitable(cached):
        return await cached
      else:
        return cached

  async def _ocr_img_no_cache(self, client, media, group_title):
    if isinstance(media, types.MessageMediaPhoto):
      key = media.photo.id
      mime_type = 'image/jpeg'
    else:
      key = media.document.id
      mime_type = media.document.mime_type

    logger.info('<%s> Downloading media %d...', group_title, key)
    imgdata = await client.download_media(media, file=bytes)

    formdata = aiohttp.FormData()
    formdata.add_field(
      'file', imgdata,
      filename = 'image', content_type = mime_type,
    )
    formdata.add_field('lang', 'zh-Hans')
    logger.info('<%s> Uploading media %d to OCR service...', group_title, key)
    try:
      st = time.time()
      res = await self._aiosession.post(self.ocr_url, data=formdata)
      j = await res.json()
      elaped = time.time() - st
    except Exception as e:
      logger.error('OCR failed with %r', e)
      return []

    logger.info('OCR %d done in %.3fs.', key, elaped)
    ret = [r['text'] for r in j['result']] if j['result'] else []
    self._ocr_cache[key] = ret
    self._ocr_cache.expire()
    return ret
