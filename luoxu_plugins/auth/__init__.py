import logging
import asyncio

logger = logging.getLogger('luoxu_plugins.auth')


async def register(indexer, client):
    luoxu_web_url = indexer.config['plugin']['auth']['web_url']
    enable_groups_ids = indexer.auth_enable_group_ids
    ttl = int(indexer.config['telegram'].get('auth_expire', 3600))

    async def auth(event):
        chat = await event.get_chat()
        if chat.id not in enable_groups_ids:
            return
        token = indexer.token_manager.add_token(chat.id)
        url_message = await event.reply(f"{luoxu_web_url}?token={token}#g={chat.id}")
        await asyncio.sleep(ttl)
        try:
            await url_message.delete()
        except:
            logger.warning('删除 url 消息失败')

    indexer.add_msg_handler(auth, pattern='.*/luoxuurl$')
