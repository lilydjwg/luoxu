from asyncio import Lock

from aiohttp import web

from . import util
from .types import SearchQuery, GroupNotFound
from .lib.expiringdict import ExpiringDict

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
      'messages': [{
        'id': m['msgid'],
        'from_id': m['from_user'],
        'from_name': m['from_user_name'],
        'text': m['text'],
        't': m['datetime'].timestamp(),
      } for m in messages],
    }, headers = {
      'Access-Control-Allow-Origin': '*',
    })

  def _parse_query(self, query):
    group = int(query['g'])
    terms = query.get('q')
    sender = query.get('sender')
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

class AvatarHandler:
  def __init__(self, client) -> None:
    self.client = client
    self.cache = ExpiringDict(14400, maxsize=50)
    self.cache_count = 0
    self.lock = Lock()

  async def _get_avatar(self, uid: int) -> bytes:
    cache = self.cache
    if (data := cache.get(uid)) is not None:
      return data

    data = await self._get_avatar_real(uid)
    cache[uid] = data
    if self.cache_count > 10:
      self.cache_count = 0
      cache.expire()
    else:
      self.cache_count += 1
    return data

  async def _get_avatar_real(self, uid: int) -> bytes:
    return await self.client.download_profile_photo(uid, file=bytes)

  async def get(self, request):
    uid = int(request.match_info['uid'])
    async with self.lock:
      data = await self._get_avatar(uid)
    return web.Response(body=data, headers = {
      'Content-Type': 'image/jpeg',
      'Cache-Control': 'public, max-age=14400',
      'Content-Disposition': f'inline; filename="avatar-{uid}.jpg"',
    })

def setup_app(dbconn, client, prefix=''):
  app = web.Application()
  app.router.add_get(f'{prefix}/search', SearchHandler(dbconn).get)
  app.router.add_get(f'{prefix}/groups', GroupsHandler(dbconn).get)

  ah = AvatarHandler(client)
  app.router.add_get(fr'{prefix}/avatar/{{uid:\d+}}', ah.get)
  app.router.add_get(fr'{prefix}/avatar/{{uid:\d+}}.jpg', ah.get)

  return app
