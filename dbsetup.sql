create table tg_groups (
  group_id integer unique not null primary key,
  name text not null,
  pub_id text,
  loaded_first_id integer,
  loaded_last_id integer
);

create table messages (
  id serial primary key,
  group_id integer not null references tg_groups (group_id),
  msgid integer not null,
  from_user integer,
  from_user_name text not null,
  text text not null,
  textvector tsvector not null,
  created_at timestamp with time zone not null,
  updated_at timestamp with time zone
);

create index messages_datetime_idx on messages (created_at);
create index messages_msgid_idx on messages (msgid);
