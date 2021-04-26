from aiohttp import web

from . import util
from .types import SearchQuery, GroupNotFound

class SearchHandler:
  def __init__(self, dbconn):
    self.dbconn = dbconn

  async def get(self, request):
    try:
      q = self._parse_query(request.query)
    except Exception:
      raise web.HTTPBadRequest
    try:
      group_name, messages = await self.dbconn.search(q)
    except GroupNotFound:
      raise web.HTTPNotFound

    return web.json_response({
      'group_name': group_name,
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

def setup_app(dbconn, prefix=''):
  app = web.Application()
  handler = SearchHandler(dbconn)
  app.router.add_get(f'{prefix}/search', handler.get)
  return app
