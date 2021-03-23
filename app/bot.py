from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram import filters
from .ui.inline_markup import keyboards
from .filters import (
    EndPollFilter,
    PollNavFilter,
    StartPollFilter,
    SkipFilter,
    NextQuestionFilter,
    SubmitFilter)
from .redis import Redis
from .data.docs import Doc
from .data.questions import Poll, Pool, Question, ButtonPoll
from .data import consts
from .ui.inline_markup import buttons


class DreamBot:
    def __init__(self, token: str, redis: Redis):
        self.doc = Doc()
        self.bot = Bot(token, parse_mode=types.ParseMode.HTML)
        self.dispatcher = Dispatcher(self.bot)
        self.storage = redis
        self.pool = None

    async def start(self):
        #self.pool = Pool(await self.doc.form(self.storage))
        self.pool = Pool(await self.doc.get_data())
        self.dispatcher.register_message_handler(self.welcome, commands=['start'])
        self.dispatcher.register_message_handler(self.message_handler)
        self.dispatcher.register_callback_query_handler(self.start_poll, StartPollFilter())
        self.dispatcher.register_callback_query_handler(self.next_question, NextQuestionFilter())
        self.dispatcher.register_callback_query_handler(self.skip, SkipFilter())
        self.dispatcher.register_callback_query_handler(self.submit, SubmitFilter())
        self.dispatcher.register_callback_query_handler(self.end_poll, EndPollFilter())
        self.dispatcher.register_callback_query_handler(self.poll_nav, PollNavFilter())
        self.dispatcher.register_callback_query_handler(self.button_poll_handler, filters.Regexp(Poll.r_pattern_option))
        self.dispatcher.register_callback_query_handler(self.checkbox_poll_handler, filters.Regexp(Poll.r_pattern_main))
        #self.dispatcher.register_errors_handler(self.error_handler)

        # self.dispatcher.register_poll_handler(self.poll_handler)
        await self.dispatcher.skip_updates()
        await self.dispatcher.start_polling()

    @staticmethod
    async def welcome(msg: types.Message):
        user = msg.from_user.full_name or msg.forward_from.username
        text = 'Привет, <b>{0}!</b>'.format(user)
        await msg.answer(
            text=text,
            reply_markup=keyboards.START_POLL
        )

    async def start_poll(self, msg: types.CallbackQuery):
        user, chat, bot = msg.from_user.id, msg.message.chat.id, msg.bot
        await msg.answer(text='Отвечайте на вопросы')
        await self.storage.set_current(user, chat, Pool.start)
        await self.storage.update_data(user, chat, {'datetime': [datetime.today().strftime('%Y.%m.%d %H:%M:%S')]})
        await self.pool[Pool.start].action(bot, chat)

    async def end_poll(self, query: types.CallbackQuery):
        user, chat = query.from_user.id, query.message.chat.id
        data = await self.storage.get_data(user, chat)
        msg_history = await self.storage.get_msg_history(user, chat)
        await self.storage.delete(user, chat)
        values = [', '.join(value) for value in list(data.values())]
        for msg_id in msg_history:
            await query.bot.delete_message(chat, msg_id)
        await query.bot.send_message(
            chat_id=chat,
            text='Вы можете поделиться еще одним сноведением',
            reply_markup=keyboards.START_POLL
        )
        self.doc.write(values)

    async def submit(self, msg: types.CallbackQuery):
        user, chat = msg.from_user.id, msg.message.chat.id
        current = await self.storage.get_current(user, chat)
        poll = self.pool[current]
        await self.storage.set_current(user, chat, current + 1)
        await msg.bot.edit_message_reply_markup(
            chat_id=chat,
            message_id=msg.message.message_id,
            reply_markup=poll.delete_submit(msg)
        )
        await self.next_question(msg)

    async def next_question(self, query: types.CallbackQuery):
        user, chat, bot = query.from_user.id, query.message.chat.id, query.bot
        current = await self.storage.get_current(user, chat)
        q = self.pool[current]
        msg = None
        if isinstance(q, ButtonPoll):
            msg = await q.action(bot, chat)
        elif isinstance(q, Poll):
            msg = await q.action(bot, chat, 0)
            data = q.poll_data(current, user, chat, msg.message_id, 0, {})
            await self.storage.set_poll_info(user, chat, current, data)
        elif isinstance(q, Question):
            msg = await q.action(bot, chat)
        await self.storage.update_msg_history(user, chat, msg.message_id)
        if current == self.pool.end:
            return await self.send_end_keyboard(bot, chat)

    async def poll_nav(self, query: types.CallbackQuery):
        user, chat, bot = query.from_user.id, query.message.chat.id, query.bot
        current = await self.storage.get_current(user, chat)
        q: Poll = self.pool[current]
        poll_info = await self.storage.get_poll_info(user, chat, current)
        offset = q.get_offset(query, poll_info['offset'])
        msg_id = poll_info['msg_id']
        poll_info['offset'] = offset
        options_status = poll_info['options_status']
        await self.storage.set_poll_info(user, chat, current, poll_info)
        new_msg = await q.action(bot, chat, offset, msg_id, options_status)
        print(new_msg)

    async def previous_question(self, query: types.CallbackQuery):
        user, chat, bot = query.from_user.id, query.message.chat.id, query.bot
        current = await self.storage.get_current(user, chat)
        await self.storage.set_current(user, chat, current - 1)
        await self.next_question(query)

    async def send_other(self, chat: int, bot: Bot):
        await bot.send_message(
            chat_id=chat,
            text='<b>Напишите ответ в свободной форме...</b>',
        )

    async def checkbox_poll_handler(self, msg: types.CallbackQuery):
        user, chat = msg.from_user.id, msg.message.chat.id
        current = await self.storage.get_current(user, chat)
        poll = self.pool[current]
        if not isinstance(poll, Poll):
            return
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
        if answer == consts.OTHER:
            return await self.send_other(chat, msg.bot)
        data = await self.storage.get_data(user, chat)
        data = data.get(poll.name, [])
        if answer in data:
            data.remove(answer)
        else:
            data.append(answer)
        await self.storage.update_data(user, chat, {poll.name: data})

    # async def poll_handler(self, msg: types.Poll):
    #     poll_info = await self.storage.get_poll_info(msg.id)
    #     user, chat = poll_info['user'], poll_info['chat']
    #     poll, offset = poll_info['poll'], int(poll_info['offset']) + 1
    #     options = []
    #     has_other = False
    #     for option in msg.options:
    #         if option.voter_count > 0:
    #             if option.text == consts.OTHER:
    #                 has_other = True
    #                 continue
    #             options.append(option.text)
    #     data = await self.storage.get_data(user, chat)
    #     answer = data.get(self.pool[poll].name, [])
    #     answer.extend(options)
    #     data[self.pool[poll].name] = answer
    #     await self.storage.update_data(user, chat, data)
    #     if len(self.pool[poll]) > offset:
    #         msg = await self.pool[poll].action(msg.bot, chat, offset)
    #         data = dict(poll=poll, user=user, chat=chat, offset=offset)
    #         return await self.storage.set_poll_info(msg.poll.id, data)
    #     if has_other:
    #         return await self.send_other(chat, msg.bot)
    #     await self.storage.set_current(user, chat, poll + 1)
    #     await self.send_next_keyboard(msg.bot, chat)

    async def skip(self, msg: types.CallbackQuery):
        user, chat = msg.from_user.id, msg.message.chat.id
        current = await self.storage.get_current(user, chat)
        await self.storage.set_current(user, chat, current + 1)
        await self.next_question(msg)

    async def button_poll_handler(self, msg: types.CallbackQuery):
        user, chat = msg.from_user.id, msg.message.chat.id
        current = await self.storage.get_current(user, chat)
        answer = self.pool[current].options[msg.data]
        if answer == consts.OTHER:
            return await self.send_other(chat, msg.bot)
        data = {self.pool[current].name: [answer]}
        await self.storage.update_data(user, chat, data)
        await self.storage.set_current(user, chat, current + 1)
        await self.send_next_keyboard(msg.bot, chat, current)

    async def message_handler(self, msg: types.Message):
        user, chat = msg.from_user.id, msg.chat.id
        current = await self.storage.get_current(user, chat)
        data = await self.storage.get_data(user, chat)
        answer = data.get(self.pool[current].name, [])
        answer.append(msg.text)
        data[self.pool[current].name] = answer
        await self.storage.update_data(user, chat, data)
        await self.storage.set_current(user, chat, current + 1)
        await self.send_next_keyboard(msg.bot, chat, current)

    async def send_next_keyboard(self, bot: Bot, chat: int, current: int):
        return await bot.send_message(
            chat_id=chat,
            text='Нажмите <b>"Дальше"</b>, чтобы перейти к следующему вопросу',
            reply_markup=keyboards.NAV if current else keyboards.NEXT
        )

    async def send_end_keyboard(self, bot: Bot, chat: int):
        return await bot.send_message(
            chat_id=chat,
            text='Нажмите "Отправить", чтобы завершить опрос',
            reply_markup=keyboards.END
        )

    async def error_handler(self, exp: Exception):
        import logging
        logging.error(exp)
