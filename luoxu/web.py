from asyncio import Lock
import os
import logging

from aiohttp import web
from telethon.tl.types import User

from . import util
from .types import SearchQuery, GroupNotFound

logger = logging.getLogger(__name__)

class BaseHandler:
  def __init__(self, dbconn):
    self.dbconn = dbconn

class SearchHandler(BaseHandler):
  async def get(self, request):
    try:
      q = self._parse_query(request.query)
    except Exception:
      raise web.HTTPBadRequest
    try:
      group_pub_id, messages = await self.dbconn.search(q)
    except GroupNotFound:
      raise web.HTTPNotFound

    return web.json_response({
      'group_pub_id': group_pub_id,
      'group_id': q.group,
      'has_more': len(messages) == self.dbconn.SEARCH_LIMIT,
      'messages': [{
        'id': m['msgid'],
        'from_id': m['from_user'],
        'from_name': m['from_user_name'],
        'text': m['text'],
        'html': m.get('html'),
        't': m['created_at'].timestamp(),
        'edited': m['updated_at'] and m['updated_at'].timestamp() or None,
      } for m in messages],
    }, headers = {
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'public, max-age=0',
    })

  def _parse_query(self, query):
    group = int(query['g'])
    terms = query.get('q')
    sender = int(query.get('sender', 0))
    start = query.get('start')
    if start:
      start = util.fromtimestamp(int(start))
    end = query.get('end')
    if end:
      end = util.fromtimestamp(int(end))
    return SearchQuery(group, terms, sender, start, end)

class GroupsHandler(BaseHandler):
  async def get(self, request):
    groups = await self.dbconn.get_groups()
    return web.json_response({
      'groups': [{
        'group_id': g['group_id'],
        'name': g['name'],
        'pub_id': g['pub_id'],
      } for g in groups],
    }, headers = {
      'Access-Control-Allow-Origin': '*',
    })

class NamesHandler(BaseHandler):
  async def get(self, request):
    group = int(request.query['g'])
    q = request.query['q']
    names = await self.dbconn.find_names(group, q)
    return web.json_response({
      'names': names,
    }, headers = {
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'public, max-age=86400',
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
    if not os.path.exists(file):
      logger.info('downloading photo for %s: %s', u.id, filename)
      with open(file, 'wb') as f:
        await self.client.download_profile_photo(u, file=f)
    return file

  async def get(self, request) -> web.FileResponse:
    if uid_str := request.match_info.get('uid'):
      uid = int(uid_str)
      u = await self.client.get_entity(uid)
      if u.deleted:
        name = 'ghost'
        file = None
      elif not u.photo:
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
    elif name := request.match_info.get('name'):
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
      'Cache-Control': 'public, max-age=14400',
      'Content-Disposition': f'inline; filename="avatar-{name}.jpg"',
    })

def setup_app(dbconn, client, cache_dir, default_avatar, ghost_avatar, prefix=''):
  app = web.Application()
  app.router.add_get(f'{prefix}/search', SearchHandler(dbconn).get)
  app.router.add_get(f'{prefix}/groups', GroupsHandler(dbconn).get)
  app.router.add_get(f'{prefix}/names', NamesHandler(dbconn).get)

  ah = AvatarHandler(client, cache_dir, default_avatar, ghost_avatar)
  app.router.add_get(fr'{prefix}/avatar/{{uid:\d+}}.jpg', ah.get)
  app.router.add_get(fr'{prefix}/avatar/{{name:\w+}}.jpg', ah.get)

  return app
