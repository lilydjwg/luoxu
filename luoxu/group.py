import logging

logger = logging.getLogger(__name__)

class GroupHistoryIndexer:
  entity = None

  def __init__(self, entity, group_info):
    self.group_id = entity.id
    self.entity = entity
    self.group_info = group_info

  async def run(self, client, dbstore, callback):
    group_info = self.group_info
    if group_info['loaded_last_id'] is None:
      first_id = 0
      msg = await client.get_messages(self.entity, limit=1)
      last_id = msg.id
    else:
      first_id = self.group_info['loaded_first_id']
      last_id = self.group_info['loaded_last_id']

    # going forward
    while True:
      msgs = await client.get_messages(
        self.entity,
        limit = 50,
        # from current to newer (or latest)
        reverse = True,
        min_id = last_id,
      )
      if not msgs:
        break

      async with dbstore.get_conn() as conn:
        for msg in msgs:
          await dbstore.insert_message(conn, msg)
        last_id = msgs[-1].id
        await dbstore.loaded_upto(conn, self.group_id, 1, last_id)
        if not first_id:
          first_id = msgs[0].id
          await dbstore.loaded_upto(conn, self.group_id, -1, first_id)

    callback()

    # going backward
    last_id = first_id
    if last_id == 1:
      return

    while True:
      msgs = await client.get_messages(
        self.entity,
        limit = 50,
        # from current (or latest) to older
        max_id = last_id,
      )
      if not msgs:
        break

      async with dbstore.get_conn() as conn:
        for msg in msgs:
          await dbstore.insert_message(conn, msg)

        last_id = msgs[-1].id
        await dbstore.loaded_upto(conn, self.group_id, -1, last_id)
