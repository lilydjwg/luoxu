import logging

from aiohttp import web

logger = logging.getLogger('luoxu_plugins.adminapi')

class IsAdminHandler():
  def __init__(self, client):
    self.client = client

  async def post(self, request):
    params = await request.post()
    group_id = params['group']
    msg_id = int(params['msgid'])
    if not group_id.startswith('@'):
      group_id = int(group_id)

    client = self.client
    msgs = await client.get_messages(group_id, ids=[msg_id])
    msg = msgs[0]
    perms = await client.get_permissions(msg.chat, msg.sender)
    ret = {
      'ban_users': perms.ban_users,
    }
    return web.json_response(ret)

async def register(indexer, client):
  port = indexer.config['plugin']['adminapi']['port']

  handler = IsAdminHandler(client)

  app = web.Application()
  app.router.add_post('/api/isadmin', handler.post)

  runner = web.AppRunner(app)
  await runner.setup()
  site = web.TCPSite(
    runner,
    '127.0.0.1', port,
  )
  await site.start()
