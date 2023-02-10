import logging
import asyncio
from typing import Optional

import telethon
from telethon.tl import types

import querytrans

logger = logging.getLogger(__name__)

def text_to_query(s):
  return querytrans.transform(s)

async def format_msg(msg, ocrsvc=None) -> Optional[str]:
  try:
    return await asyncio.wait_for(_format_msg(msg, ocrsvc=ocrsvc), 60)
  except asyncio.TimeoutError:
    logger.error('timed out formatting a message: %r', msg.to_dict())

async def _format_msg(msg, ocrsvc=None) -> str:
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

  if ocrsvc and (media := msg.media):
    if isinstance(media, types.MessageMediaPhoto) \
       or (isinstance(media, types.MessageMediaDocument)
           and msg.media.document.mime_type.startswith('image/')):
      if ocr_text := await ocrsvc.ocr_img(msg.client, media, msg.chat.title):
        text.append('[image]')
        text.extend(ocr_text)

  text = '\n'.join(x for x in text if x)

  return text
