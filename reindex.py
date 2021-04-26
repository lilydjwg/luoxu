#!/usr/bin/python3

import psycopg2

from luoxu.indexing import text_to_vector

def main():
  with psycopg2.connect('postgresql:///tgindexer') as conn:
    last_id = 0
    while True:
      with conn.cursor() as cur:
        print('\r%s' % last_id, end='', flush=True)
        cur.execute('select id, text from messages where id > %s limit 50', (last_id,))
        rows = cur.fetchall()
        for id, text in rows:
          cur.execute('''update messages
            set textvector = to_tsvector('english', %s)
            where id = %s''', (text_to_vector(text), id))
      if not rows:
        break
      else:
        last_id = rows[-1][0]

if __name__ == '__main__':
  main()
