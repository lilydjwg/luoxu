create table tg_groups (
  group_id bigint unique not null primary key,
  name text not null,
  pub_id text,
  loaded_first_id bigint,
  loaded_last_id bigint
);

create table messages (
  group_id bigint not null references tg_groups (group_id),
  msgid bigint not null,
  from_user bigint,
  from_user_name text not null,
  text text not null,
  created_at timestamp with time zone not null,
  updated_at timestamp with time zone
) PARTITION BY RANGE (created_at);

CREATE TABLE messages_y2016 PARTITION OF messages
    FOR VALUES FROM ('2016-01-01') TO ('2017-01-01');

CREATE TABLE messages_y2017 PARTITION OF messages
    FOR VALUES FROM ('2017-01-01') TO ('2018-01-01');

CREATE TABLE messages_y2018 PARTITION OF messages
    FOR VALUES FROM ('2018-01-01') TO ('2019-01-01');

CREATE TABLE messages_y2019 PARTITION OF messages
    FOR VALUES FROM ('2019-01-01') TO ('2020-01-01');

CREATE TABLE messages_y2020 PARTITION OF messages
    FOR VALUES FROM ('2020-01-01') TO ('2021-01-01');

CREATE TABLE messages_y2021 PARTITION OF messages
    FOR VALUES FROM ('2021-01-01') TO ('2022-01-01');

CREATE TABLE messages_y2022 PARTITION OF messages
    FOR VALUES FROM ('2022-01-01') TO ('2023-01-01');

CREATE TABLE messages_y2023 PARTITION OF messages
    FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');

CREATE TABLE messages_y2024 PARTITION OF messages
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

-- for dedupe and cutwords:
--
-- explain analyze SELECT msgid, text FROM messages
-- WHERE msgid < 9223372036854775807
-- and group_id = 1031857103
-- and created_at > '2022-05-23 14:24'
-- ORDER BY msgid DESC LIMIT 1000;
create unique index messages_msgid_idx on messages (group_id, msgid, created_at DESC);

-- fulltext search
-- explain analyze
-- select msgid, group_id, from_user, from_user_name, created_at, updated_at, pgroonga_highlight_html(text, pgroonga_query_extract_keywords('街角 魔族 1080p CHS'), 'message_idx') as html
-- from (select msgid, group_id, from_user, from_user_name, created_at, updated_at, text from messages where 1 = 1 and group_id = 1216816802 and text &@~ '街角 魔族 1080p CHS' order by created_at desc limit 50) as t;
--
-- using message_idx
-- Subquery Scan on t  (cost=171490.23..171490.25 rows=1 width=87) (actual time=29.750..31.542 rows=50 loops=1)
--   ->  Limit  (cost=171490.23..171490.24 rows=1 width=104) (actual time=29.633..29.646 rows=50 loops=1)
--         ->  Sort  (cost=171490.23..171490.24 rows=1 width=104) (actual time=20.844..20.849 rows=50 loops=1)
--               Sort Key: messages.created_at DESC
--               Sort Method: quicksort  Memory: 54kB
--               ->  Bitmap Heap Scan on messages  (cost=0.00..171490.22 rows=1 width=104) (actual time=20.485..20.778 rows=88 loops=1)
--                     Recheck Cond: (text &@~ '街角 魔族 1080p CHS'::text)
--                     Filter: (group_id = 1216816802)
--                     Rows Removed by Filter: 1
--                     Heap Blocks: exact=76
--                     ->  Bitmap Index Scan on message_idx  (cost=0.00..0.00 rows=73234 width=0) (actual time=20.431..20.431 rows=90 loops=1)
--                           Index Cond: (text &@~ '街角 魔族 1080p CHS'::text)
-- Planning Time: 0.910 ms
-- JIT:
--   Functions: 9
--   Options: Inlining false, Optimization false, Expressions true, Deforming true
--   Timing: Generation 0.896 ms, Inlining 0.000 ms, Optimization 0.536 ms, Emission 8.271 ms, Total 9.703 ms
-- Execution Time: 68.963 ms
CREATE INDEX message_idx ON messages USING pgroonga (text) WITH (tokenizer='TokenNgram("report_source_location", true, "loose_blank", true)');

-- message by sender without search terms
--
-- explain analyze select msgid, group_id, from_user, from_user_name, created_at, updated_at, text from messages where 1 = 1 and from_user = 694598748 order by created_at desc limit 50;
-- explain analyze select msgid, group_id, from_user, from_user_name, created_at, updated_at, text from messages where 1 = 1 and group_id = 1031857103 and from_user = 694598748 order by created_at desc limit 50;
-- CREATE INDEX message_sender_idx ON public.messages USING btree (from_user, created_at DESC);

create table usernames (
  name text not null,
  uid bigint[] not null,
  group_id bigint[] not null,
  last_seen timestamp with time zone not null
);

CREATE UNIQUE INDEX usernames_uidx ON usernames (name);
CREATE INDEX usernames_idx ON usernames USING pgroonga (name) WITH (tokenizer='TokenBigramSplitSymbolAlphaDigit');

CREATE FUNCTION array_distinct(anyarray) RETURNS anyarray AS $f$
  SELECT array_agg(DISTINCT x) FROM unnest($1) t(x);
$f$ LANGUAGE SQL IMMUTABLE;

CREATE OR REPLACE FUNCTION update_usernames()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO usernames (name, uid, group_id, last_seen)
    VALUES (NEW.from_user_name, ARRAY[NEW.from_user], ARRAY[NEW.group_id], NEW.created_at)
    ON CONFLICT (name) DO UPDATE
      SET last_seen = CASE WHEN usernames.last_seen > NEW.created_at THEN usernames.last_seen ELSE NEW.created_at END,
          uid = array_distinct(usernames.uid || NEW.from_user),
          group_id = array_distinct(usernames.group_id || NEW.group_id);
  RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';

CREATE TRIGGER table_updated AFTER INSERT
  ON messages FOR EACH ROW EXECUTE PROCEDURE update_usernames();
