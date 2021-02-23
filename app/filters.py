from aiogram.dispatcher.filters import Filter
from aiogram.types import CallbackQuery

from .ui.inline_markup import buttons


class StartPollFilter(Filter):

    async def check(self, query: CallbackQuery) -> bool:
        return query.data == buttons.START_POLL.callback_data


class NextQuestionFilter(Filter):
    async def check(self, query: CallbackQuery) -> bool:
        return query.data == buttons.NEXT.callback_data


class EndPollFilter(Filter):
    async def check(self, query: CallbackQuery) -> bool:
        return query.data == buttons.END.callback_data
