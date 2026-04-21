import asyncio
import inspect
import logging

from telethon.tl import types

from .lib.expiringdict import ExpiringDict
from .ctxvars import group_title

logger = logging.getLogger(__name__)

class MediaMgr:
  def __init__(self, client):
    self.client = client
    self._media_cache = ExpiringDict(3600)
    self._media_cache_lock = asyncio.Lock()

  async def get_media(self, media):
    if isinstance(media, types.MessageMediaPhoto):
      key = media.photo.id
    else:
      key = media.document.id

    async with self._media_cache_lock:
      cached = self._media_cache.get(key)
      if cached is None:
        # coroutine cannot be awaited twice, but task can
        fu = asyncio.create_task(self._download_media(media))
        self._media_cache[key] = fu

    if cached is None:
      return await fu
    else:
      if inspect.isawaitable(cached):
        return await cached
      else:
        return cached

  async def _download_media(self, media):
    if isinstance(media, types.MessageMediaPhoto):
      key = media.photo.id
    else:
      key = media.document.id
    logger.info('<%s> Downloading media %s...', group_title.get(), key)
    return await self.client.download_media(media, file=bytes)
