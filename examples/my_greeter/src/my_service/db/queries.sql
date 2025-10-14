-- !sqlcast

-- name: create_users_table
create table if not exists users
(
    id         serial primary key,
    name       varchar(256)             not null,
    created_at timestamp with time zone not null default current_timestamp
);

-- name: create_user :one
insert into users (id, name)
values (:user_id::integer, :user_name::varchar(256))
returning users.id, name, created_at;

-- name: get_user_by_id :one
select id, name, created_at
from users
where id = :user_id::integer
limit 1;

-- name: search_users_by_name_ilike
select id, name, created_at
from users
where name ilike :user_name_pattern::varchar(256)
limit :limit::integer;
