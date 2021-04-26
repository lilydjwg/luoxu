create table tg_groups (
  group_id integer unique not null primary key,
  name text not null,
  pub_id text,
  start_reached boolean not null default false,
  last_sync_dt timestamp with time zone
);

create table messages (
  id serial primary key,
  group_id integer not null references tg_groups (group_id),
  msgid integer not null,
  from_user integer,
  from_user_name text not null,
  text text not null,
  textvector tsvector not null,
  datetime timestamp with time zone not null
);

create index messages_datetime_idx on messages (datetime);
create index messages_msgid_idx on messages (msgid);
