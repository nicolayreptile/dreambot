from collections import OrderedDict
from typing import List, Optional, Union, Dict

from aiogram import Bot, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.ui import emoji
from app.ui import inline_markup
from . import consts

Response = Union[types.Message, types.PollAnswer, types.InlineQuery, types.CallbackQuery]


class Base:
    is_first_only = False
    template: str
    is_last = False

    def __init__(self, index: int, required: bool = True, first_time_only: bool = False):
        self.index = index
        self.required = required
        self.first_time_only = first_time_only

    async def action(self, bot: Bot, chat_id: int):
        raise NotImplementedError()

    @property
    def nav_panel(self):
        if not self.is_last:
            if not self.required:
                if self.index:
                    return inline_markup.full_nav
                else:
                    return inline_markup.forward_nav
            elif self.index:
                return inline_markup.back_nav


class Question(Base):
    template = '{0}\n{1}'

    def __init__(self, text: str, help_text: str, *args):
        super().__init__(*args)
        self.name = 'QUESTION_{0}'.format(self.index)
        self.text = self.template.format(text, help_text)

    async def action(self, bot: Bot, chat_id: int) -> types.Message:
        reply_markup = None
        if self.nav_panel:
            reply_markup = InlineKeyboardMarkup(self.nav_panel)
        return await bot.send_message(
            chat_id=chat_id,
            text=self.text,
            reply_markup=reply_markup
        )


class Poll(Base):
    template = '{}'
    callback_data_template = '{0}:{1}'
    text_template = '{0} {1}'
    min_poll_size = 2
    max_poll_size = 10
    row_width = 4
    max_len = 18
    r_pattern_main = r'POLL_([0-9]*)'
    r_pattern_option = r'OPTION_([0-9]*)'

    def __init__(self, text: str, help_text: str, options: List[str],
                 has_other: bool = False, *args):
        super(Poll, self).__init__(*args)
        self.name = 'POLL_{0}'.format(self.index)
        self.text = self.template.format(text)
        self.help_text = help_text
        self.options = {}
        self.flat_options = {}

        for idx, option in enumerate(options):
            callback_data = self.callback_data_template.format(self.name, idx)
            self.options[callback_data] = idx + 1
            self.flat_options[callback_data] = option
            self.text = f'{self.text}\n {idx + 1}. {option}'
        if has_other:
            callback_data = self.callback_data_template.format(self.name, len(options))
            self.options[callback_data] = self.flat_options[callback_data] = consts.OTHER
            options.append(consts.OTHER)
        self.limit = len(options) // 2
        self.help_text = help_text
        if not self.help_text:
            self.help_text = 'Выберите один или несколько вариантов ответа'

    def __len__(self):
        return len(self.options)

    def keyboard(self, offset: int = 0, options_status: Optional[Dict] = None) -> InlineKeyboardMarkup:
        options_status = options_status or {}
        buttons = []
        options = list(self.options.items())
        for i in range(offset, offset + self.limit, self.row_width):
            last = i + self.row_width
            row_options = options[i:last] if last < len(options) else options[i:]
            row = []
            for callback_data, option in row_options:
                status = emoji.green_circle if options_status.get(callback_data) else emoji.white_circle
                text = self.text_template.format(status, str(option))
                row += [InlineKeyboardButton(text=text, callback_data=callback_data)]
            buttons.append(row)
        nav_buttons = []
        if offset:
            nav_buttons.append(inline_markup.buttons.POLL_PREVIOUS)
        if len(self) > offset + self.limit + 1:
            nav_buttons.append(inline_markup.buttons.POLL_NEXT)
        if nav_buttons:
            buttons.append(nav_buttons)
        buttons.append([inline_markup.buttons.SUBMIT])
        if self.nav_panel:
            buttons.append(self.nav_panel)

        return InlineKeyboardMarkup(row_width=self.row_width, inline_keyboard=buttons)

    def change_option_state(self, msg: types.CallbackQuery, callback_data_checked: str,
                            status: bool) -> InlineKeyboardMarkup:
        keyboard = msg.message.values['reply_markup']
        buttons: List[List[InlineKeyboardButton]] = keyboard.inline_keyboard
        for group in buttons:
            for button in group:
                if button.callback_data == callback_data_checked:
                    option = self.options[callback_data_checked]
                    checked = self.text_template.format(emoji.green_circle, option)
                    unchecked = self.text_template.format(emoji.white_circle, option)
                    button.text = checked if status else unchecked
                    break
        return InlineKeyboardMarkup(row_width=self.row_width, inline_keyboard=buttons)

    def get_offset(self, msg: types.CallbackQuery, offset: int):
        if msg.data == inline_markup.buttons.POLL_NEXT.callback_data:
            offset = offset + self.limit
        elif msg.data == inline_markup.buttons.POLL_PREVIOUS.callback_data:
            offset = offset - self.limit
        return offset

    def delete_submit(self, msg: types.CallbackQuery) -> InlineKeyboardMarkup:
        keyboard = msg.message.values['reply_markup']
        buttons: List[List[InlineKeyboardButton]] = keyboard.inline_keyboard
        buttons.pop()
        return InlineKeyboardMarkup(row_width=self.row_width, inline_keyboard=buttons)

    @staticmethod
    def poll_data(index: int, user: int, chat: int,
                  msg_id: int, offset: int, options_status: dict) -> dict:
        return {
            'index': index,
            'user': user,
            'chat': chat,
            'msg_id': msg_id,
            'offset': offset,
            'options_status': options_status,
        }

    async def action(self, bot: Bot,
                     chat_id: int,
                     offset: int = 0,
                     msg_id: Optional[int] = None,
                     options_status: Optional[dict] = None) -> types.Message:
        if msg_id:
            return await bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=self.keyboard(offset, options_status),
            )
        return await bot.send_message(
            chat_id=chat_id,
            text=self.text,
            reply_markup=self.keyboard(offset),
        )


class ButtonPoll(Base):
    template = '{0}\n{1}'

    def __init__(self, text: str, help_text: str, options: list[str],
                 has_other: bool = False, *args):
        super(ButtonPoll, self).__init__(*args)
        self.text = self.template.format(text, help_text or '')
        self.name = 'POLL_{0}'.format(self.index)
        self.options = {}
        self.flat_options = {}
        buttons = [[]]
        for i, option in enumerate(options):
            key = 'option_{0}'.format(i + 1)
            btn = InlineKeyboardButton(text=str(i + 1) if len(options) > 5 else option, callback_data=key)
            self.options[key] = i
            self.flat_options[key] = option
            self.text = f'{self.text}\n {i}. {option}'
            if len(buttons[-1]) > 4:
                buttons.append([btn])
            else:
                buttons[-1].append(btn)
        if has_other:
            key = 'option_{0}'.format(len(options) + 2)
            btn = InlineKeyboardButton(text=consts.OTHER, callback_data=key)
            if len(buttons[-1]) > 4:
                buttons.append([btn])
            else:
                buttons[-1].append(btn)
            options.append(consts.OTHER)
        if self.nav_panel:
            buttons.append(self.nav_panel)
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
            required = item.get('required', True)
            first_time_only = item.get('first_time_only', False)
            if type_ in ('PARAGRAPH_TEXT', 'TEXT',):
                elem = Question(text, help_text, index, required, first_time_only)
            elif type_ == 'CHECKBOX':
                elem = Poll(text, help_text, options, has_other, index, required, first_time_only)
            elif type_ == 'MULTIPLE_CHOICE':
                elem = ButtonPoll(text, help_text, options, has_other, index, required, first_time_only)
            self.pool[index] = elem
        self.end = len(self) - 1
        self[self.end].is_last = True

    def __getitem__(self, index: int) -> Optional[Union[ButtonPoll, Poll, Question]]:
        return self.pool.get(index)

    def __len__(self) -> int:
        return len(self.pool)
