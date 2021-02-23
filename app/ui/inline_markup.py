from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from collections import namedtuple


from . import emoji


__InlineButton = namedtuple('InlineButton', ['START_POLL', 'NEXT', 'SITE', 'END'])
__InlineKeyboard = namedtuple('InlineKeyboard', ['START_POLL', 'NEXT', 'END'])

buttons = __InlineButton(
    START_POLL=InlineKeyboardButton(f'{emoji.writing_hand} Рассказать сон', callback_data='start_poll'),
    NEXT=InlineKeyboardButton(f'{emoji.arrow_right} Дальше', callback_data='next'),
    SITE=InlineKeyboardButton('Перейти на сайт проекта', url='http://systemofdreams.tilda.ws'),
    END=InlineKeyboardButton('Отправить ответы', callback_data='end_poll'),
)

keyboards = __InlineKeyboard(
    START_POLL=InlineKeyboardMarkup(2, [[buttons.START_POLL, buttons.SITE]]),
    NEXT=InlineKeyboardMarkup(1, [[buttons.NEXT]]),
    END=InlineKeyboardMarkup(1, [[buttons.END]])
)
