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

create index messages_msgid_idx on messages (msgid);

CREATE INDEX user_name_idx ON messages USING pgroonga (from_user_name) WITH (tokenizer='TokenBigramSplitSymbolAlphaDigit');
CREATE INDEX message_idx ON messages USING pgroonga (text) WITH (tokenizer='TokenNgram("report_source_location", true, "loose_blank", true)');
