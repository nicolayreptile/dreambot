from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram import filters
from .ui.inline_markup import keyboards
from .filters import EndPollFilter, StartPollFilter, NextQuestionFilter
from .redis import Redis
from .data.docs import Doc
from .data.questions import Poll, Pool, Question, ButtonPoll
from .data import consts


class DreamBot:
    def __init__(self, token: str):
        self.doc = Doc()
        self.bot = Bot(token, parse_mode=types.ParseMode.HTML)
        self.dispatcher = Dispatcher(self.bot)
        self.storage = Redis('redis://localhost', key_prefix='dream_bot')
        self.pool = None

    async def start(self):
        self.pool = Pool(await self.doc.form(self.storage))
        self.dispatcher.register_message_handler(self.welcome, commands=['start'])
        self.dispatcher.register_message_handler(self.message_handler)
        self.dispatcher.register_callback_query_handler(self.start_poll, StartPollFilter())
        self.dispatcher.register_callback_query_handler(self.next_question, NextQuestionFilter())
        self.dispatcher.register_callback_query_handler(self.end_poll, EndPollFilter())
        self.dispatcher.register_callback_query_handler(self.button_poll_handler, filters.Regexp('option_([0-9]*)'))
        self.dispatcher.register_poll_handler(self.poll_handler)
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
        await self.storage.delete(user, chat)
        values = [','.join(value) for value in list(data.values())]
        self.doc.write(values)
        await query.bot.send_message(
            chat_id=chat,
            text='Вы можете поделиться еще одним сноведением',
            reply_markup=keyboards.START_POLL
        )

    async def next_question(self, query: types.CallbackQuery):
        user, chat, bot = query.from_user.id, query.message.chat.id, query.bot
        current = await self.storage.get_current(user, chat)
        q = self.pool[current]
        if isinstance(q, ButtonPoll):
            await q.action(bot, chat)
        elif isinstance(q, Poll):
            msg = await q.action(bot, chat, 0)
            data = dict(poll=current, user=user, chat=chat, offset=0)
            await self.storage.set_poll_info(msg.poll.id, data)
        elif isinstance(q, Question):
            await q.action(bot, chat)

        if current == self.pool.end:
            return await self.send_end_keyboard(bot, chat)

    async def send_other(self, chat: int, bot: Bot):
        await bot.send_message(
            chat_id=chat,
            text='<b>Напишите ответ в свободной форме...</b>',
        )

    async def poll_handler(self, msg: types.Poll):
        poll_info = await self.storage.get_poll_info(msg.id)
        user, chat = poll_info['user'], poll_info['chat']
        poll, offset = poll_info['poll'], int(poll_info['offset']) + 1
        options = []
        has_other = False
        for option in msg.options:
            if option.voter_count > 0:
                if option.text == consts.OTHER:
                    has_other = True
                    continue
                options.append(option.text)
        data = await self.storage.get_data(user, chat)
        answer = data.get(self.pool[poll].name, [])
        answer.extend(options)
        data[self.pool[poll].name] = answer
        await self.storage.update_data(user, chat, data)
        if len(self.pool[poll]) > offset:
            msg = await self.pool[poll].action(msg.bot, chat, offset)
            data = dict(poll=poll, user=user, chat=chat, offset=offset)
            return await self.storage.set_poll_info(msg.poll.id, data)
        if has_other:
            return await self.send_other(chat, msg.bot)
        await self.storage.set_current(user, chat, poll + 1)
        await self.send_next_keyboard(msg.bot, chat)

    async def button_poll_handler(self, msg: types.CallbackQuery):
        user, chat = msg.from_user.id, msg.message.chat.id
        current = await self.storage.get_current(user, chat)
        answer = self.pool[current].options[msg.data]
        if answer == consts.OTHER:
            return await self.send_other(chat, msg.bot)
        data = {self.pool[current].name: [answer]}
        await self.storage.update_data(user, chat, data)
        await self.storage.set_current(user, chat, current + 1)
        await self.send_next_keyboard(msg.bot, chat)

    async def message_handler(self, msg: types.Message):
        user, chat = msg.from_user.id, msg.chat.id
        current = await self.storage.get_current(user, chat)
        data = await self.storage.get_data(user, chat)
        answer = data.get(self.pool[current].name, [])
        answer.append(msg.text)
        data[self.pool[current].name] = answer
        await self.storage.update_data(user, chat, data)
        await self.storage.set_current(user, chat, current + 1)
        await self.send_next_keyboard(msg.bot, chat)

    async def send_next_keyboard(self, bot: Bot, chat: int):
        return await bot.send_message(
            chat_id=chat,
            text='Нажмите <b>"Дальше"</b>, чтобы перейти к следующему вопросу',
            reply_markup=keyboards.NEXT
        )

    async def send_end_keyboard(self, bot: Bot, chat: int):
        return await bot.send_message(
            chat_id=chat,
            text='Нажмите "Отправить", чтобы завершить опрос',
            reply_markup=keyboards.END
        )
