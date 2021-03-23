from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from collections import namedtuple


from . import emoji


__InlineButton = namedtuple('InlineButton',
                            ['START_POLL', 'NEXT', 'SITE', 'END', 'SKIP',
                             'PREVIOUS', 'SUBMIT', 'POLL_NEXT', 'POLL_PREVIOUS'])
__InlineKeyboard = namedtuple('InlineKeyboard',
                              ['START_POLL', 'NEXT', 'END', 'SKIP', 'PREVIOUS', 'NAV', 'POLL_NAV'])

buttons = __InlineButton(
    START_POLL=InlineKeyboardButton(f'{emoji.writing_hand} Рассказать сон', callback_data='_start_poll'),
    NEXT=InlineKeyboardButton(f'{emoji.arrow_right} Дальше', callback_data='_next'),
    SITE=InlineKeyboardButton('Перейти на сайт проекта', url='http://systemofdreams.tilda.ws'),
    END=InlineKeyboardButton('Отправить ответы', callback_data='_end_poll'),
    SKIP=InlineKeyboardButton('Нет подходящего ответа', callback_data='_skip'),
    PREVIOUS=InlineKeyboardButton('Предыдущий вопрос', callback_data='_previous'),
    SUBMIT=InlineKeyboardButton('Отправить', callback_data='_submit'),
    POLL_NEXT=InlineKeyboardButton(emoji.rightwards_arrow, callback_data='_poll_next'),
    POLL_PREVIOUS=InlineKeyboardButton(emoji.leftwards_arrow, callback_data='_poll_previous'),
)

keyboards = __InlineKeyboard(
    START_POLL=InlineKeyboardMarkup(2, [[buttons.START_POLL, buttons.SITE]]),
    NEXT=InlineKeyboardMarkup(1, [[buttons.NEXT]]),
    END=InlineKeyboardMarkup(1, [[buttons.END]]),
    SKIP=InlineKeyboardMarkup(1, [[buttons.SKIP]]),
    PREVIOUS=InlineKeyboardMarkup(1, [[buttons.PREVIOUS]]),
    NAV=InlineKeyboardMarkup(2, [[buttons.PREVIOUS, buttons.NEXT]]),
    POLL_NAV=InlineKeyboardMarkup(2, [[buttons.POLL_NEXT, buttons.POLL_PREVIOUS]]),
)
