import asyncpg

from db.model import UsersRow
import typing


class AsyncQuerier:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.__pool = pool

    async def create_users_table(self) -> None:
        async with self.__pool.acquire() as conn:
            await conn.execute("""
                create table if not exists users
                (
                    id         serial primary key,
                    name       varchar(256)             not null,
                    created_at timestamp with time zone not null default current_timestamp
                );
            """)

    async def create_user(self, user_id: int, name: str) -> typing.Optional[UsersRow]:
        async with self.__pool.acquire() as conn:
            row = await conn.fetchrow("""
                insert into users (id, name)
                values ($1, $2)
                returning id, name, created_at;
            """, user_id, name)

        return UsersRow(id=row[0], name=row[1], created_at=row[2]) if row is not None else None

    async def get_user_by_id(self, user_id: int) -> typing.Optional[UsersRow]:
        async with self.__pool.acquire() as conn:
            row = await conn.fetchrow("""
                                         select id, name, created_at
                                         from users
                                         where id = $1;
                                         """, user_id)

        return UsersRow(id=row[0], name=row[1], created_at=row[2]) if row is not None else None

    async def search_users_by_name_ilike(self, user_name_pattern: str, limit: int) -> typing.Sequence[UsersRow]:
        async with self.__pool.acquire() as conn:
            rows = await conn.fetch("""
                                         select id, name, created_at
                                         from users
                                         where name ilike $1
                                         limit $2;
                                         """, user_name_pattern, limit)

        return [UsersRow(id=row[0], name=row[1], created_at=row[2]) for row in rows]
