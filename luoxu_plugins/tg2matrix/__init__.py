import logging
import os
import sqlite3
from typing import Optional

from telethon import events

from . import utils

logger = logging.getLogger('luoxu_plugins.tg2matrix')

class DB:
  def __init__(self) -> None:
    self.dbfile = os.path.join(os.path.dirname(__file__), 'tg2matrix.db')
    self.db = sqlite3.connect(self.dbfile, autocommit=False)
    self._may_init()

  def _may_init(self) -> None:
    with self.db:
      try:
        c = self.db.execute('select version from metadata')
        row = c.fetchone()
        if row:
          if row[0] == 1:
            return
          else:
            raise RuntimeError('unknown database version %s' % row[0])
      except sqlite3.OperationalError:
        pass

      self.db.autocommit = True
      try:
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
          CREATE TABLE metadata (version integer primary key);
          INSERT INTO metadata (version) VALUES (1);
          CREATE TABLE msg_mapping (
            channel_id integer NOT NULL,
            msg_id integer NOT NULL,
            event_id text NOT NULL,
            replied_to text,
            PRIMARY KEY (channel_id, msg_id)
          )''')
      finally:
        self.db.autocommit = False

  def get_matrix_event_id(
    self, channel_id: int, msg_id: int,
  ) -> Optional[str]:
    with self.db:
      c = self.db.execute('''
        SELECT event_id FROM msg_mapping
        WHERE channel_id = ? AND msg_id = ?
      ''', (channel_id, msg_id))
      row = c.fetchone()
      if row:
        return row[0]
      else:
        return None

  def save_matrix_event_id(
    self, channel_id: int, msg_id: int,
    event_id: str, replied_to: str | None,
  ) -> None:
    with self.db:
      try:
        self.db.execute('''
          INSERT INTO msg_mapping
            (channel_id, msg_id, event_id, replied_to)
          VALUES (?, ?, ?, ?)''',
          (channel_id, msg_id, event_id, replied_to))
      except sqlite3.IntegrityError:
        pass

class TgChannelWatcher:
  def __init__(self, client, socket_path, channels):
    self.socket_path = socket_path
    self.channels = channels
    self.channel_ids = {}
    self.client = client
    self.db = DB()

  async def on_event(self, event):
    if not self.channel_ids and self.channels:
      for g, m in self.channels.items():
        if isinstance(g, int):
          self.channel_ids[g] = m
        else:
          e = await self.client.get_entity(g)
          self.channel_ids[e.id] = m

    msg = event.message
    if getattr(msg.peer_id, 'channel_id', None) in self.channel_ids:
      await self.process_message(msg)

  async def process_message(self, msg):
    channel_id = msg.peer_id.channel_id
    event_id = self.db.get_matrix_event_id(channel_id, msg.id)
    if msg.reply_to and (replied_to := msg.reply_to.reply_to_msg_id):
      reply_to = self.db.get_matrix_event_id(channel_id, replied_to)
    else:
      reply_to = None

    text = msg.message
    html = utils.tg_message_to_html(msg)
    mmsg = {
      'cmd': 'send_message',
      'target': self.channel_ids[channel_id],
      'content': text,
      'html_content': html,
      'return_id': True,
    }
    if event_id:
      mmsg['replaces'] = event_id
    if reply_to:
      mmsg['reply_to'] = reply_to

    event_id = utils.send_message(self.socket_path, mmsg)
    self.db.save_matrix_event_id(channel_id, msg.id, event_id, reply_to)

def register(indexer, client):
  config = indexer.config['plugin']['tg2matrix']
  channels = config['channels']
  socket_path = config['socket_path']
  w = TgChannelWatcher(client, socket_path, channels)
  client.add_event_handler(w.on_event, events.NewMessage())
  client.add_event_handler(w.on_event, events.MessageEdited())
