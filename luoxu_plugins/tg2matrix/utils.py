import socket
import json
import html
import struct
from typing import Literal, Any

def recv_n(sock, n):
  data = b''
  while (remaining := n - len(data)) > 0:
    data += sock.recv(remaining)
  return data

def send_message(socket_path, msg):
  s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
  s.connect(socket_path)
  m = json.dumps(msg, ensure_ascii=False).encode()
  size = struct.pack('>I', len(m))
  s.sendall(size)
  s.sendall(m)

  size = recv_n(s, 4)
  n = struct.unpack('>I', size)[0]
  ret = recv_n(s, n)
  s.close()
  return json.loads(ret)['id']

def tg_message_to_html(msg):
  ret = []
  for x in segment_tgmsg(msg):
    if isinstance(x, str):
      ret.append(html.escape(x, quote=False).replace('\n', '<br>'))
      continue

    match x.kind, x.action:
      case 'bold', 'start':
        ret.append('<b>')
      case 'bold', 'end':
        ret.append('</b>')
      case 'code', 'start':
        ret.append('<code>')
      case 'code', 'end':
        ret.append('</code>')
      case 'italic', 'start':
        ret.append('<i>')
      case 'italic', 'end':
        ret.append('</i>')
      case 'pre', 'start':
        ret.append(f'<pre class="language-{x.value}">')
      case 'pre', 'end':
        ret.append('</pre>')
      case 'spoiler', 'start':
        ret.append('<span data-mx-spoiler>')
      case 'spoiler', 'end':
        ret.append('</span>')
      case 'strike', 'start':
        ret.append('<s>')
      case 'strike', 'end':
        ret.append('</s>')
      case 'texturl', 'start':
        ret.append(f'<a href="{x.value}">')
      case 'texturl', 'end':
        ret.append('</a>')
      case 'underline', 'start':
        ret.append('<u>')
      case 'underline', 'end':
        ret.append('</u>')
      case 'url', 'start':
        url = msg.message[x.offset:x.offset + x.value]
        ret.append(f'<a href="{url}">')
      case 'url', 'end':
        ret.append('</a>')

  return ''.join(ret)

def segment_tgmsg(msg):
  m = msg.message

  my_entities = [TgEntity(x, True) for x in msg.entities]
  my_entities.extend(reversed([TgEntity(x, False) for x in msg.entities]))
  # sort by offset, but end precedes start
  # or else we'd get an empty element
  my_entities.sort(
    key = lambda e: (e.offset, ['end', 'start'].index(e.action)))

  last_end = 0
  for e in my_entities:
    if e.offset > last_end:
      yield m[last_end:e.offset]
    yield e

    last_end = e.offset

  if last_end < len(m):
    yield m[last_end:]

class TgEntity:
  kind: str
  value: Any
  action: Literal['start', 'end']
  offset: int

  def __init__(self, entity, is_start):
    e = entity
    kind = e.__class__.__name__.removeprefix('MessageEntity').lower()
    if kind == 'texturl':
      value = e.url
    elif kind == 'pre':
      value = e.language
    elif kind == 'url':
      value = e.length
    else:
      value = None

    self.kind = kind
    self.value = value
    self.action = 'start' if is_start else 'end'
    self.offset = e.offset if is_start else e.offset + e.length

  def __repr__(self):
    return f'<TgEntity: kind={self.kind}, value={self.value}, action={self.action}, offset={self.offset}>'
