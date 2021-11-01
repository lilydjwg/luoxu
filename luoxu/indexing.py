from opencc import OpenCC
import telethon

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

def format_msg(msg):
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
  text = '\n'.join(x for x in text if x)

  return text
