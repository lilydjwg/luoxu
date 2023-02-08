from asyncio import Lock
import os
import logging
from html import escape as htmlescape
import re
import time

from aiohttp import web
from telethon.tl.types import User, ChatPhotoEmpty
from telethon.errors.rpcerrorlist import ChannelPrivateError

from . import util
from .types import SearchQuery, GroupNotFound

logger = logging.getLogger(__name__)

class BaseHandler:
  def __init__(self, dbconn):
    self.dbconn = dbconn

  async def get(self, request):
    origin = request.headers.get('Origin')
    if origin and origin not in request.config_dict['origins']:
      raise web.HTTPBadRequest

    st = time.time()
    res = await self._get(request)
    logger.info('request took %.3fs', time.time() - st)
    if origin:
      res.headers.setdefault(
        'Access-Control-Allow-Origin', origin
      )
      res.headers.setdefault(
        'Vary', 'Origin'
      )

    return res

def html_or_text(m):
  if r := m.get('html'):
    return re.sub(r'<span class="keyword">(\s+)', r'\1<span class="keyword">', r)
  if r := m.get('text'):
    return htmlescape(r)
  return ' '

class SearchHandler(BaseHandler):
  def __init__(self, dbconn, auth_enable_groups, token_manager):
    super().__init__(dbconn)
    self.auth_enable_groups = auth_enable_groups
    self.token_manager = token_manager

  async def _get(self, request):
    try:
      q = self._parse_query(request.query)
    except Exception:
      raise web.HTTPBadRequest
    if q.group in self.auth_enable_groups:
      if not q.token:
        raise web.HTTPUnauthorized
      if not self.token_manager.is_valid(q.group, q.token):
        raise web.HTTPForbidden
    try:
      groupinfo, messages = await self.dbconn.search(q)
    except GroupNotFound:
      raise web.HTTPNotFound

    return web.json_response({
      'groupinfo': groupinfo,
      'has_more': len(messages) == self.dbconn.SEARCH_LIMIT,
      'messages': [{
        'id': m['msgid'],
        'from_id': m['from_user'],
        'from_name': m['from_user_name'],
        'group_id': m['group_id'],
        'html': html_or_text(m),
        't': m['created_at'].timestamp(),
        'edited': m['updated_at'] and m['updated_at'].timestamp() or None,
      } for m in messages],
    }, headers = {
      'Cache-Control': 'max-age=0',
    })

  def _parse_query(self, query):
    group = int(query.get('g', 0))
    terms = query.get('q')
    sender = int(query.get('sender', 0))
    start = query.get('start')
    token = query.get('token', '')
    if start:
      start = util.fromtimestamp(int(start))
    end = query.get('end')
    if end:
      end = util.fromtimestamp(int(end))
    return SearchQuery(group, terms, sender, start, end, token)

class GroupsHandler(BaseHandler):
  async def _get(self, request):
    groups = await self.dbconn.get_groups()
    gs = [{
      'group_id': str(g['group_id']),
      'name': g['name'],
      'pub_id': g['pub_id'],
    } for g in groups]
    gs.sort(key=lambda g: g['name'])
    return web.json_response({
      'groups': gs,
    })

class NamesHandler(BaseHandler):
  async def _get(self, request):
    group = int(request.query.get('g') or 0)
    q = request.query['q']
    names = await self.dbconn.find_names(group, q)
    return web.json_response({
      'names': names,
    }, headers = {
      'Cache-Control': 's-maxage=0, max-age=86400',
    })

class AvatarHandler:
  def __init__(self, client, cache_dir, default_avatar: str, ghost_avatar: str) -> None:
    self.client = client
    self.cache_dir = cache_dir
    self.default_avatar = default_avatar
    self.ghost_avatar = ghost_avatar
    self.lock = Lock()

  async def _get_avatar(self, u: User) -> str:
    filename = f'{u.photo.photo_id}.jpg'
    file = os.path.join(self.cache_dir, filename)
    tmpfile = os.path.join(self.cache_dir, 'tmp.jpg')
    if not os.path.exists(file):
      logger.info('downloading photo for %s: %s', u.id, filename)
      with open(tmpfile, 'wb') as f:
        await self.client.download_profile_photo(u, file=f)
      os.rename(tmpfile, file)
    return file

  async def get(self, request) -> web.FileResponse:
    if uid_str := request.match_info.get('uid'):
      uid = int(uid_str)
      try:
        u = await self.client.get_entity(uid)
      except ChannelPrivateError:
        raise web.HTTPForbidden(headers = {
          'Cache-Control': 'public, max-age=86400',
        })

      if getattr(u, 'deleted', False):
        name = 'ghost'
        file = None
      elif not u.photo or isinstance(u.photo, ChatPhotoEmpty):
        name = 'nobody'
        file = None
      else:
        async with self.lock:
          file = await self._get_avatar(u)
        logger.debug('avatar for %s is at %s', uid, file)
        name = u.username or uid_str
      if not file:
        raise web.HTTPTemporaryRedirect(f'{name}.jpg', headers = {
          'Cache-Control': 'public, max-age=14400',
        })
      max_age = 14400
    elif name := request.match_info.get('name'):
      max_age = 86400 * 365
      if name == 'ghost':
        file = self.ghost_avatar
      elif name == 'nobody':
        file = self.default_avatar
      else:
        raise web.HTTPNotFound
    else:
      raise web.HTTPNotFound

    return web.FileResponse(path=file, headers = {
      'Content-Type': 'image/jpeg',
      'Cache-Control': f'public, max-age={max_age}',
      'Content-Disposition': f'inline; filename="avatar-{name}.jpg"',
    })

def setup_app(
  dbconn, client, cache_dir,
  default_avatar, ghost_avatar,
  *,
  prefix = '',
  origins = (),
  auth_enable_groups = (),
  token_manager = None,
):
  app = web.Application()
  app['origins'] = origins
  app.router.add_get(f'{prefix}/search', SearchHandler(dbconn, auth_enable_groups, token_manager).get)
  app.router.add_get(f'{prefix}/groups', GroupsHandler(dbconn).get)
  app.router.add_get(f'{prefix}/names', NamesHandler(dbconn).get)

  if client:
    ah = AvatarHandler(client, cache_dir, default_avatar, ghost_avatar)
    app.router.add_get(fr'{prefix}/avatar/{{uid:\d+}}.jpg', ah.get)
    app.router.add_get(fr'{prefix}/avatar/{{name:\w+}}.jpg', ah.get)

  return app

async def run_web(config, port):
  import asyncio
  from .db import PostgreStore
  db = PostgreStore(config['database'])
  await db.setup()

  web_config = config['web']
  cache_dir = web_config['cache_dir']
  os.makedirs(cache_dir, exist_ok=True)
  app = setup_app(
    db, None,
    os.path.abspath(cache_dir),
    os.path.abspath(web_config['default_avatar']),
    os.path.abspath(web_config['ghost_avatar']),
    prefix = web_config['prefix'],
    origins = web_config['origins'],
  )
  runner = web.AppRunner(app)
  await runner.setup()
  site = web.TCPSite(
    runner,
    web_config['listen_host'], port,
  )
  await site.start()
  while True:
    await asyncio.sleep(3600)

if __name__ == '__main__':
  from .lib.nicelogger import enable_pretty_logging
  enable_pretty_logging('DEBUG')

  from .util import run_until_sigint, load_config

  import argparse

  parser = argparse.ArgumentParser()
  parser.add_argument('--config', default='config.toml',
                      help='config file path')
  parser.add_argument('--port', type=int,
                      help='listen on this TCP port')
  args = parser.parse_args()

  config = load_config(args.config)
  run_until_sigint(run_web(config, args.port))
