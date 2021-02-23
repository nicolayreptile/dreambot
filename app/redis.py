import typing
import json
import asyncio
import aioredis


class Redis:
    STATE_KEY = 'state'
    DATA_KEY = 'data'
    POLL_KEY = 'poll'

    def __init__(self, host: str, port: int = 6379, db: int = 0, key_prefix: typing.Optional[str] = None):
        self._host = host
        self._port = port
        self._db = db

        self._prefix = (key_prefix, )
        self._loop = asyncio.get_event_loop()
        self._redis: typing.Optional[aioredis.RedisConnection] = None
        self._connection_lock = asyncio.Lock(loop=self._loop)
        self._ttl = 3600

    def get_key(self, *parts):
        return ':'.join(self._prefix + tuple(map(str, parts)))

    async def redis(self):
        async with self._connection_lock:
            if self._redis is None or self._redis.closed:
                self._redis = await aioredis.create_redis_pool(self._host,
                                                               db=self._db,
                                                               encoding='utf-8')
        return self._redis

    async def close(self):
        async with self._connection_lock:
            if self._redis and not self._redis.closed:
                self._redis.close()

    async def wait_closed(self):
        async with self._connection_lock:
            if self._redis:
                return await self._redis.wait_closed()
            return True

    async def get_current(self, user: int, chat: int) -> typing.Optional[int]:
        key = self.get_key(user, chat, self.STATE_KEY)
        redis = await self.redis()
        current = await redis.get(key, encoding='utf-8')
        if current is not None:
            current = int(current)
        return current

    async def set_current(self, user: int, chat: int, current: int):
        key = self.get_key(user, chat, self.STATE_KEY)
        redis = await self.redis()
        return await redis.set(key, current, expire=self._ttl)

    async def get_data(self, user: int, chat: int) -> dict:
        key = self.get_key(user, chat, self.DATA_KEY)
        redis = await self.redis()
        raw_result = await redis.get(key, encoding='utf-8')
        if raw_result:
            return json.loads(raw_result)
        return {}

    async def set_data(self, user: int, chat: int, data: dict):
        """
        Data stored as:
        {
            "name1": ["ans1", "ans2", ...],
            "name2": ["ans1", ...]
        }
        """
        key = self.get_key(user, chat, self.DATA_KEY)
        data = json.dumps(data)
        redis = await self.redis()
        return await redis.set(key, data, expire=self._ttl)

    async def update_data(self, user: int, chat: int, new_data: dict):
        key = self.get_key(user, chat, self.DATA_KEY)
        redis = await self.redis()
        data = await redis.get(key, encoding='utf-8')
        data = json.loads(data) if data else {}
        data.update(new_data)
        data = json.dumps(data)
        return await redis.set(key, data, expire=self._ttl)

    async def get_poll_info(self, poll: int):
        key = self.get_key(poll, self.POLL_KEY)
        redis = await self.redis()
        data = await redis.get(key, encoding='utf-8')
        data = json.loads(data) if data else {}
        return data

    async def set_poll_info(self, poll: int, data: dict):
        key = self.get_key(poll, self.POLL_KEY)
        data = json.dumps(data)
        redis = await self.redis()
        await redis.set(key, data, expire=self._ttl)

    async def delete(self, user: int, chat: int):
        key_state = self.get_key(user, chat, self.STATE_KEY)
        key_data = self.get_key(user, chat, self.DATA_KEY)
        redis = await self.redis()
        return await redis.delete(key_state, key_data)

    async def reset_all(self):
        redis = await self.redis()
        return await redis.flushall()

    async def set_from(self, form: dict):
        data = json.dumps(form)
        redis = await self.redis()
        await redis.set('form', data)

    async def get_form(self):
        redis = await self.redis()
        data = await redis.get('form', encoding='utf-8')
        if data:
            return json.loads(data)
        return data


