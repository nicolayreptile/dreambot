import typing
import os
import asyncpg
import dotenv

from ..redis import Redis


dotenv.load_dotenv()


class Db:

    def __init__(self):
        self.dsn = os.environ.get('DATABASE_URL')
        self.pool = None

    async def select(self, table_name: str, columns: list[str], condition: typing.Optional[str] = None):
        columns = ', '.join(columns)
        stmt = f'SELECT {columns} FROM {table_name}'
        if condition:
            stmt += f' WHERE {condition}'
        async with asyncpg.create_pool(self.dsn) as pool:
            result = await pool.fetch(stmt)
            return result

    async def insert(self, table_name: str, columns: list[str], values: list[typing.Union[str, int]]):
        columns = ', '.join(columns)
        values = ', '.join(list(map(self.prepare_args, values)))
        stmt = f'INSERT INTO {table_name}({columns}) VALUES({values})'
        async with asyncpg.create_pool(self.dsn) as pool:
            await pool.execute(stmt)

    async def table_exists(self, table_name: str) -> bool:
        stmt = f'SELECT EXISTS(SELECT FROM information_schema.tables where table_name=$1)'
        async with asyncpg.create_pool(self.dsn) as pool:
            result = await pool.fetchrow(stmt, table_name)
            return result['exists']

    async def table_create(self, table_name: str, columns: list[tuple[str, str]]):
        stmt = 'CREATE TABLE {0} (id serial PRIMARY KEY, {1})'.format(
            table_name, ', '.join(list(map(lambda x: f'{x[0]} {x[1]}', columns)))
        )
        async with asyncpg.create_pool(self.dsn) as pool:
            await pool.execute(stmt)

    def prepare_args(self, string: typing.Any):
        return f'\'{str(string)}\''


class Users:
    table_name = 'users'
    columns = [('user_id', 'int'), ('data', 'text')]

    def __init__(self, redis: Redis):
        self.db = Db()
        self.redis = redis

    async def initialize_table(self):
        if not await self.db.table_exists(self.table_name):
            await self.db.table_create(self.table_name, self.columns)
        return True

    async def initialize(self):
        if await self.initialize_table():
            users = await self.db.select(self.table_name, ['user_id'])
            map(lambda x: self.redis.set_user(x['user_id']), users)

    async def exists(self, user_id: int):
        rows = await self.db.select(self.table_name, ['*'], f'$user_id={user_id}')
        return True if len(rows) else False

    async def create(self, user_id: int, data: str):
        return await self.db.insert(self.table_name, ['user_id', 'data'], [user_id, data])
