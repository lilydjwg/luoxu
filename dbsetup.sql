create table tg_groups (
  group_id bigint unique not null primary key,
  name text not null,
  pub_id text,
  loaded_first_id bigint,
  loaded_last_id bigint
);

create table messages (
  id serial primary key,
  group_id bigint not null references tg_groups (group_id),
  msgid bigint not null,
  from_user bigint,
  from_user_name text not null,
  text text not null,
  created_at timestamp with time zone not null,
  updated_at timestamp with time zone
);

create unique index messages_msgid_idx on messages (msgid, group_id);

CREATE INDEX message_idx ON messages USING pgroonga (text) WITH (tokenizer='TokenNgram("report_source_location", true, "loose_blank", true)');

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
