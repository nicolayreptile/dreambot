from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from collections import namedtuple


from . import emoji


__InlineButton = namedtuple('InlineButton',
                            ['START_POLL', 'NEXT', 'SITE', 'END', 'PREVIOUS', 'SUBMIT', 'POLL_NEXT', 'POLL_PREVIOUS'])
__InlineKeyboard = namedtuple('InlineKeyboard',
                              ['START_POLL', 'END', 'FULL_NAV', 'FORWARD_NAV', 'BACK_NAV', 'NAV', 'POLL_NAV' ])

buttons = __InlineButton(
    START_POLL=InlineKeyboardButton(f'{emoji.writing_hand} Рассказать сон', callback_data='_start_poll'),
    NEXT=InlineKeyboardButton(f'{emoji.arrow_right} Следующий вопрос', callback_data='_next'),
    PREVIOUS=InlineKeyboardButton('Предыдущий вопрос', callback_data='_previous'),
    SITE=InlineKeyboardButton('Перейти на сайт проекта', url='http://systemofdreams.tilda.ws'),
    END=InlineKeyboardButton('Отправить ответы', callback_data='_end_poll'),
    SUBMIT=InlineKeyboardButton('Отправить', callback_data='_submit'),
    POLL_NEXT=InlineKeyboardButton(emoji.rightwards_arrow, callback_data='_poll_next'),
    POLL_PREVIOUS=InlineKeyboardButton(emoji.leftwards_arrow, callback_data='_poll_previous'),
)

full_nav = [buttons.PREVIOUS, buttons.NEXT]
back_nav = [buttons.PREVIOUS]
forward_nav = [buttons.NEXT]

keyboards = __InlineKeyboard(
    START_POLL=InlineKeyboardMarkup(2, [[buttons.START_POLL, buttons.SITE]]),
    FULL_NAV=InlineKeyboardMarkup(2, [[buttons.PREVIOUS, buttons.NEXT]]),
    FORWARD_NAV=InlineKeyboardMarkup(1, [[buttons.NEXT]]),
    BACK_NAV=InlineKeyboardMarkup(1, [[buttons.PREVIOUS]]),
    END=InlineKeyboardMarkup(1, [[buttons.END]]),
    NAV=InlineKeyboardMarkup(2, [[buttons.PREVIOUS, buttons.NEXT]]),
    POLL_NAV=InlineKeyboardMarkup(2, [[buttons.POLL_NEXT, buttons.POLL_PREVIOUS]]),
)
