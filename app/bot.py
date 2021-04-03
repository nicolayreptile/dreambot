from datetime import datetime
from typing import Union

from aiogram import Bot, Dispatcher, types
from aiogram import filters

from .data import consts
from .data.docs import Doc, GoogleApi
from .data.db import Db, Users
from .data.questions import Poll, Pool, Question, ButtonPoll
from .filters import (
    EndPollFilter,
    PollNavFilter,
    StartPollFilter,
    NextQuestionFilter,
    PreviousQuestionFilter,
    SubmitFilter)
from .redis import Redis
from .ui.inline_markup import keyboards


class DreamBot:
    def __init__(self, token: str, redis: Redis):
        self.doc = Doc()
        self.bot = Bot(token, parse_mode=types.ParseMode.HTML)
        self.dispatcher = Dispatcher(self.bot)
        self.storage = redis
        self.writer = GoogleApi(redis)
        self.users = Users(redis)
        self.pool = None

    async def start(self):
        self.pool = Pool(await self.doc.get_data())
        await self.users.initialize()
        self.dispatcher.register_message_handler(self.welcome, commands=['start'])
        self.dispatcher.register_message_handler(self.message_handler)
        self.dispatcher.register_callback_query_handler(self.start_poll, StartPollFilter())
        self.dispatcher.register_callback_query_handler(self.next_question, NextQuestionFilter())
        self.dispatcher.register_callback_query_handler(self.previous_question, PreviousQuestionFilter())
        self.dispatcher.register_callback_query_handler(self.submit, SubmitFilter())
        self.dispatcher.register_callback_query_handler(self.end_poll, EndPollFilter())
        self.dispatcher.register_callback_query_handler(self.poll_nav, PollNavFilter())
        self.dispatcher.register_callback_query_handler(self.button_poll_handler, filters.Regexp(Poll.r_pattern_option))
        self.dispatcher.register_callback_query_handler(self.checkbox_poll_handler, filters.Regexp(Poll.r_pattern_main))

        await self.dispatcher.skip_updates()
        await self.dispatcher.start_polling()

    async def welcome(self, msg: types.Message):
        user = msg.from_user.full_name or msg.forward_from.username
        text = 'Привет, <b>{0}!</b>'.format(user)
        reply_msg = await msg.answer(
            text=text,
            reply_markup=keyboards.START_POLL
        )
        await self.storage.update_msg_history(msg.from_user.id, msg.chat.id, reply_msg.message_id)

    async def start_poll(self, msg: types.CallbackQuery):
        user, chat = msg.from_user.id, msg.message.chat.id
        await msg.answer(text='Отвечайте на вопросы')
        await self.storage.remove_current(user, chat)
        await self.writer.initialize(user)
        await self.storage.update_data(user, chat, {'datetime': [datetime.today().strftime('%Y.%m.%d %H:%M:%S')]})
        await self.next_question(msg)

    async def end_poll(self, query: types.CallbackQuery):
        user, chat = query.from_user.id, query.message.chat.id
        await self.storage.set_user(user)
        msg_history = await self.storage.get_msg_history(user, chat)
        data = await self.storage.delete(user, chat)
        for msg_id in msg_history:
            await query.bot.delete_message(chat, msg_id)
        await query.bot.send_message(
            chat_id=chat,
            text='Вы можете поделиться еще одним сноведением',
            reply_markup=keyboards.START_POLL
        )
        await self.users.create(user, data)
        await query.answer()

    async def submit(self, msg: types.CallbackQuery):
        user, chat = msg.from_user.id, msg.message.chat.id
        current, msg_id = await self.storage.get_current(user, chat)
        poll = self.pool[current]
        if not msg_id == msg.message.message_id:
            return await msg.answer('Вы уже утвечали на этот вопрос')
        data = await self.storage.get_data(user, chat)
        poll_options = data.get(poll.name, [])
        if consts.OTHER in poll_options:
            await msg.answer()
            return await self.send_other(chat, msg.bot)
        return await self.next_question(msg)

    async def next_question(self, msg: Union[types.Message, types.CallbackQuery], forward=True):
        if isinstance(msg, types.Message):
            user, chat, bot = msg.from_user.id, msg.chat.id, msg.bot
        elif isinstance(msg, types.CallbackQuery):
            user, chat, bot = msg.from_user.id, msg.message.chat.id, msg.bot
            await msg.answer()
        else:
            raise ValueError()

        current, msg_id = await self.storage.get_current(user, chat)
        user_exists = await self.storage.user_exists(user)

        if current is None:
            current = Pool.start
        elif forward:
            await self.write_answer(user, chat, current)
            current += 1
            if current > self.pool.end:
                return await msg.answer('Это последний вопрос')
        else:
            current -= 1

        q = self.pool[current]
        if user_exists:
            while q and q.is_first_only and self.pool.end > current >= Pool.start:
                current = current + 1 if forward else current - 1
                q = self.pool[current]

        reply_msg = None
        if isinstance(q, ButtonPoll):
            reply_msg = await q.action(bot, chat)
        elif isinstance(q, Poll):
            reply_msg = await q.action(bot, chat, 0)
            data = q.poll_data(current, user, chat, reply_msg.message_id, 0, {})
            await self.storage.set_poll_info(user, chat, current, data)
        elif isinstance(q, Question):
            reply_msg = await q.action(bot, chat)

        await self.storage.set_current(user, chat, current, reply_msg.message_id)
        await self.storage.update_msg_history(user, chat, reply_msg.message_id)

        if current == self.pool.end:
            return await self.send_end_keyboard(bot, user, chat)

    async def write_answer(self, user: int, chat: int, index: int):
        raw_data = await self.storage.get_data(user, chat)
        data = raw_data.get(self.pool[index].name, [])
        if data:
            await self.writer.write_cell(user, index, data)

    async def poll_nav(self, query: types.CallbackQuery):
        user, chat, bot = query.from_user.id, query.message.chat.id, query.bot
        current, msg_id = await self.storage.get_current(user, chat)
        if not msg_id == query.message.message_id:
            return await query.answer('Вы уже отвечали на этот вопрос')
        q: Poll = self.pool[current]
        poll_info = await self.storage.get_poll_info(user, chat, current)
        offset = q.get_offset(query, poll_info['offset'])
        msg_id = poll_info['msg_id']
        poll_info['offset'] = offset
        options_status = poll_info['options_status']
        await self.storage.set_poll_info(user, chat, current, poll_info)
        await q.action(bot, chat, offset, msg_id, options_status)
        return await query.answer()

    async def previous_question(self, query: types.CallbackQuery):
        await query.answer()
        await self.next_question(query, forward=False)

    @staticmethod
    async def send_other(chat: int, bot: Bot):
        return await bot.send_message(
            chat_id=chat,
            text='<i>Напишите ответ в свободной форме...</i>',
        )

    async def checkbox_poll_handler(self, msg: types.CallbackQuery):
        user, chat = msg.from_user.id, msg.message.chat.id
        current, msg_id = await self.storage.get_current(user, chat)
        poll = self.pool[current]
        if not isinstance(poll, Poll) or not msg_id == msg.message.message_id:
            return await msg.answer('Вы уже отвечали на этот вопрос')
        answer = poll.options[msg.data]
        poll_info = await self.storage.get_poll_info(user, chat, current)
        options_status = poll_info['options_status']
        status = options_status.get(msg.data, False)
        status = not status
        options_status[msg.data] = status
        poll_info['options_status'] = options_status
        await self.storage.set_poll_info(user, chat, current, poll_info)
        await msg.bot.edit_message_reply_markup(
            chat_id=chat,
            message_id=msg.message.message_id,
            reply_markup=poll.change_option_state(msg, msg.data, status)
        )
        data = await self.storage.get_data(user, chat)
        data = data.get(poll.name, [])
        if answer in data:
            data.remove(answer)
        else:
            data.append(answer)
        await self.storage.update_data(user, chat, {poll.name: data})
        return await msg.answer()

    async def button_poll_handler(self, msg: types.CallbackQuery):
        user, chat = msg.from_user.id, msg.message.chat.id
        current, msg_id = await self.storage.get_current(user, chat)
        if not msg.message.message_id == msg_id:
            return await msg.answer('Вы уже отвечали на этот вопрос')
        answer = self.pool[current].options[msg.data]
        if answer == consts.OTHER:
            reply_msg = await self.send_other(chat, msg.bot)
            return await self.storage.update_msg_history(user, chat, reply_msg.message_id)
        data = {self.pool[current].name: [answer]}
        await self.storage.update_data(user, chat, data)
        await self.next_question(msg)
        await msg.answer()

    async def message_handler(self, msg: types.Message):
        user, chat = msg.from_user.id, msg.chat.id
        current, msg_id = await self.storage.get_current(user, chat)
        data = await self.storage.get_data(user, chat)
        answer = data.get(self.pool[current].name, [])
        answer.append(msg.text)
        data[self.pool[current].name] = answer
        await self.storage.update_data(user, chat, data)
        await self.storage.update_msg_history(user, chat, msg.message_id)
        await self.next_question(msg)

    async def send_end_keyboard(self, bot: Bot, user: int, chat: int):
        msg = await bot.send_message(
            chat_id=chat,
            text='Нажмите "Отправить", чтобы завершить опрос',
            reply_markup=keyboards.END
        )
        await self.storage.update_msg_history(user, chat, msg.message_id)
