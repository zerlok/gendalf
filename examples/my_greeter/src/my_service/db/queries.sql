-- !sqlcast
-- dialect: postgres

-- name: create_users_table
create table if not exists users
(
    id         serial primary key,
    name       varchar(256)             not null,
    created_at timestamp with time zone not null default current_timestamp
);

-- name: create_user :one
insert into users (id, name)
values (:user_id, :user_name)
returning id, name, created_at;

-- name: get_user_by_id :one
select id, name, created_at
from users
where id = :user_id
limit 1;

-- name: search_users_by_name_ilike
select id, name, created_at
from users
where name ilike :user_name_pattern
limit :limit;
