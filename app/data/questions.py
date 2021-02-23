from collections import OrderedDict
from typing import List, Optional, Union, Dict
from aiogram import Bot, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from . import consts


Response = Union[types.Message, types.PollAnswer, types.InlineQuery, types.CallbackQuery]


class Question:
    template = '<b>{0}</b>\n{1}'

    def __init__(self, text: str, help_text: str, index: int):
        self.name = 'QUESTION_{0}'.format(index)
        self.text = self.template.format(text, help_text)

    async def action(self, bot: Bot, chat_id: int) -> types.Message:
        return await bot.send_message(
            chat_id=chat_id,
            text=self.text
        )


class Poll:
    template = '<b>{}</b>'
    min_poll_size = 2
    max_poll_size = 10

    def __init__(self, text: str, help_text: str, options: List[str],
                 has_other: bool = False,
                 index: int = 0):
        self.name = 'POLL_{0}'.format(index)
        self.text = self.template.format(text)
        self.help_text = help_text
        self.options = []
        if has_other:
            options.append(consts.OTHER)
        sub_option = []
        while options:
            if len(sub_option) == self.max_poll_size:
                self.options.append(sub_option)
                sub_option = []
            sub_option.append(options.pop(0))
        if sub_option:
            self.options.append(sub_option)
        if len(self.options[-1]) < self.min_poll_size:
            self.options[-1].append(self.options[-2].pop())
        self.help_text = help_text
        if not self.help_text:
            self.help_text = 'Выберите один или несколько вариантов ответа'

    def __len__(self):
        return len(self.options)

    async def action(self, bot: Bot, chat_id: int, offset: int = 0) -> types.Message:
        await bot.send_message(
            chat_id=chat_id,
            text=self.text,
        )
        return await bot.send_poll(
            chat_id=chat_id,
            question=self.help_text,
            options=self.options[offset],
            allows_multiple_answers=True
        )


class ButtonPoll:
    template = '<b>{0}</b>\n{1}'

    def __init__(self, text: str, help_text: str, options: List[str],
                 has_other: bool = False,
                 index: int = 0):
        self.text = self.template.format(text, help_text or '')
        self.name = 'POLL_{0}'.format(index)
        self.options = {}
        buttons = []
        if has_other:
            options.append(consts.OTHER)
        for i, option in enumerate(options):
            key = 'option_{0}'.format(i)
            btn = InlineKeyboardButton(text=option, callback_data=key)
            self.options[key] = option
            buttons.append([btn])
        self.keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    async def action(self, bot: Bot, chat_id: int) -> types.Message:
        return await bot.send_message(
            chat_id=chat_id,
            text=self.text,
            reply_markup=self.keyboard,
        )


class Pool:
    pool: OrderedDict[int, Union[Poll, Question]] = OrderedDict()
    start: int = 0
    end: int

    def __init__(self, response: dict):
        items = response['items']
        for index, item in enumerate(items):
            elem = None
            type_ = item.get('type')
            text = item.get('value')
            options = item.get('choices')
            help_text = item.get('help_text', '')
            has_other = item.get('has_other_option')
            if type_ in ('PARAGRAPH_TEXT', 'TEXT', ):
                elem = Question(text, help_text, index)
            elif type_ == 'CHECKBOX':
                elem = Poll(text, help_text, options, has_other, index)
            elif type_ == 'MULTIPLE_CHOICE':
                elem = ButtonPoll(text, help_text, options, has_other, index)
            self.pool[index] = elem

        self.end = len(self) - 1

    def __getitem__(self, index: int):
        return self.pool.get(index)

    def __len__(self):
        return len(self.pool)
