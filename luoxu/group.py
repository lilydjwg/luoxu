import logging
import asyncio

from .ctxvars import msg_source
from .util import UpdateLoaded

logger = logging.getLogger(__name__)

async def timed_get_messages(client, *args, **kwargs):
  while True:
    try:
      return await asyncio.wait_for(client.get_messages(*args, **kwargs), 60)
    except asyncio.TimeoutError:
      logger.error('timed out formatting a message, retrying: %r, %r', args, kwargs)
      await asyncio.sleep(1)
    except Exception:
      logger.exception('error in get_messages')
      await asyncio.sleep(1)

class GroupHistoryIndexer:
  entity = None

  def __init__(self, entity, group_info, use_ocr):
    self.group_id = entity.id
    self.entity = entity
    self.group_info = group_info
    self.use_ocr = use_ocr

  async def run(self, client, dbstore, callback):
    msg_source.set('history')
    group_info = self.group_info
    if group_info['loaded_last_id'] is None:
      first_id = 0
      msgs = await timed_get_messages(client, self.entity, limit=2)
      last_id = msgs[-1].id
    else:
      first_id = self.group_info['loaded_first_id']
      last_id = self.group_info['loaded_last_id']

    # going forward
    while True:
      msgs = await timed_get_messages(
        client,
        self.entity,
        limit = 50,
        # from current to newer (or latest)
        reverse = True,
        min_id = last_id,
      )
      if not msgs:
        break

      if not first_id:
        update_loaded = UpdateLoaded.update_both
        first_id = msgs[0].id
      else:
        update_loaded = UpdateLoaded.update_last
        last_id = msgs[-1].id
      await dbstore.insert_messages(msgs, update_loaded, use_ocr = self.use_ocr)

    logger.info('forward history index done for group %s', self.group_info['name'])
    callback()

    # going backward
    if first_id == 1:
      return

    while True:
      msgs = await timed_get_messages(
        client,
        self.entity,
        limit = 50,
        # from current (or latest) to older
        max_id = first_id,
      )
      if not msgs:
        break

      msgs = msgs[::-1]
      first_id = msgs[0].id
      await dbstore.insert_messages(msgs, UpdateLoaded.update_first, use_ocr = self.use_ocr)

    logger.info('backward history index done for group %s', self.group_info['name'])
