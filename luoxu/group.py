import asyncio
import logging

logger = logging.getLogger(__name__)

# TODO: fetch messages [1, 1000000)

class GroupIndexer:
  entity = None

  def __init__(self, entity):
    self.group_id = entity.id
    self.entity = entity

  async def run(self, client, dbstore):
    group_info = await dbstore.get_group(self.group_id)
    if group_info is None:
      await self.new_group(dbstore)
      start_reached = False
      last_id = 0
    else:
      start_reached = group_info['start_reached']
      last_id = await dbstore.last_id(self.group_id)
      self.username = group_info['pub_id']

    while True:
      async with dbstore.transaction():
        logger.info('Fetching messages starting at %s', last_id + 1)
        msgs = await client.get_messages(
          self.entity,
          add_offset = -20,
          limit = 20,
          offset_id = last_id + 1,
        )
        for msg in reversed(msgs):
          await dbstore.insert_message(msg)
      if not msgs:
        if start_reached:
          await asyncio.sleep(10)
        else:
          ret = await self.run_history(client, dbstore)
          if ret:
            start_reached = True
      else:
        await dbstore.updated(self.group_id)
        last_id = msgs[0].id

  async def run_history(self, client, dbstore):
    first_id = await dbstore.first_id(self.group_id)
    if first_id == 0:
      return

    async with dbstore.transaction():
      msgs = await client.get_messages(
        self.entity,
        limit = 50,
        max_id = first_id,
      )
      if not msgs:
        await dbstore.group_done(self.group_id)
        return True

      for msg in msgs:
        await dbstore.insert_message(msg)

  async def new_group(self, dbstore):
    logger.info('new_group: %r', self.entity)
    await dbstore.insert_group(self.entity)

