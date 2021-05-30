import asyncio
import json
import typing

import aioredis


class Redis:
    STATE_KEY = 'state'
    DATA_KEY = 'data'
    POLL_KEY = 'poll'
    MSG_KEY = 'message'
    TABLE_ROW_KEY = 'row'
    USERS_KEY = 'user'

    def __init__(self, redis_url: str, db: int = 0, key_prefix: typing.Optional[str] = None):
        self._address = redis_url
        self._db = db

        self._prefix = (key_prefix,)
        self._loop = asyncio.get_event_loop()
        self._redis: typing.Optional[aioredis.RedisConnection] = None
        self._connection_lock = asyncio.Lock(loop=self._loop)
        self._ttl = 3600

    def get_key(self, *parts):
        return ':'.join(self._prefix + tuple(map(str, parts)))

    async def redis(self):
        async with self._connection_lock:
            if self._redis is None or self._redis.closed:
                self._redis = await aioredis.create_redis_pool(self._address, db=self._db, encoding='utf-8')
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

    async def get_current(self, user: int, chat: int
                          ) -> typing.Tuple[typing.Optional[int], typing.Optional[int]]:
        key = self.get_key(user, chat, self.STATE_KEY)
        redis = await self.redis()
        data = await redis.get(key, encoding='utf-8')
        index = msg_id = None
        if data:
            index, msg_id = list(map(int, json.loads(data)))
        return index, msg_id

    async def get_current_msg_id(self, user: int, chat: int) -> typing.Optional[int]:
        key = self.get_key(user, chat, self.STATE_KEY)
        redis = await self.redis()
        data = await redis.get(key, encoding='utf-8')
        msg_id = None
        if data:
            msg_id = json.loads(data)[1]
            msg_id = int(msg_id)
        return msg_id

    async def remove_current(self, user: int, chat: int):
        key = self.get_key(user, chat, self.STATE_KEY)
        redis = await self.redis()
        return await redis.delete(key)

    async def set_current(self, user: int, chat: int, current: int, msg_id: int):
        key = self.get_key(user, chat, self.STATE_KEY)
        data = json.dumps([current, msg_id])
        redis = await self.redis()
        return await redis.set(key, data, expire=self._ttl)

    async def get_data(self, user: int, chat: int) -> dict:
        key = self.get_key(user, chat, self.DATA_KEY)
        redis = await self.redis()
        raw_result = await redis.get(key, encoding='utf-8')
        if raw_result:
            return json.loads(raw_result)
        return {}

    async def set_data(self, user: int, chat: int, data: typing.Dict):
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

    async def get_poll_info(self, user: int, chat: int, current: int, ):
        key = self.get_key(user, chat, current, self.POLL_KEY)
        redis = await self.redis()
        data = await redis.get(key, encoding='utf-8')
        data = json.loads(data) if data else {}
        return data

    async def set_poll_info(self, user: int, chat: int, current: int, data: typing.Dict):
        key = self.get_key(user, chat, current, self.POLL_KEY)
        data = json.dumps(data)
        redis = await self.redis()
        await redis.set(key, data, expire=self._ttl)

    async def update_msg_history(self, user: int, chat: int, msg_id: int):
        key = self.get_key(user, chat, self.MSG_KEY)
        redis = await self.redis()
        data = await redis.get(key)
        history = json.loads(data) if data else []
        history.append(msg_id)
        data = json.dumps(history)
        await redis.set(key, data)

    async def get_msg_history(self, user: int, chat: int):
        key = self.get_key(user, chat, self.MSG_KEY)
        redis = await self.redis()
        data = await redis.get(key)
        history = json.loads(data) if data else []
        history = list(map(int, history))
        await redis.delete(key)
        return history

    async def delete(self, user: int, chat: int) -> str:
        key_state = self.get_key(user, chat, self.STATE_KEY)
        key_data = self.get_key(user, chat, self.DATA_KEY)
        redis = await self.redis()
        data = await redis.get(key_data, encoding='utf-8')
        await redis.delete(key_state, key_data)
        return data

    async def reset_all(self):
        redis = await self.redis()
        return await redis.flushall()

    async def get_row_for_user(self, user: int):
        key = self.get_key(user, self.TABLE_ROW_KEY)
        redis = await self.redis()
        data = await redis.get(key)
        return int(data)

    async def set_row_for_user(self, user: int, row: int):
        key = self.get_key(user, self.TABLE_ROW_KEY)
        redis = await self.redis()
        await redis.set(key, row, expire=self._ttl)

    async def set_from(self, form: typing.Dict):
        data = json.dumps(form)
        redis = await self.redis()
        await redis.set('form', data, expire=self._ttl)

    async def get_form(self):
        redis = await self.redis()
        data = await redis.get('form', encoding='utf-8')
        if data:
            return json.loads(data)
        return data

    async def get_token(self) -> typing.Optional[bytes]:
        redis = await self.redis()
        data = await redis.get('token_', encoding=None)
        return data

    async def set_token(self, token: bytes):
        redis = await self.redis()
        return await redis.set('token_', token)

    async def set_user(self, user: int, value: int = 1):
        redis = await self.redis()
        key = self.get_key(user, self.USERS_KEY)
        await redis.set(key, value)

    async def user_exists(self, user):
        redis = await self.redis()
        key = self.get_key(user, self.USERS_KEY)
        result = await redis.get(key)
        return bool(result)
