from typing import Optional

from telegram import User as TgUser

from core.db.models import User
from core.utils.dict_ import dict_pick_only


def from_tg_user(user: TgUser) -> User:
    return User(
        **dict_pick_only(user.to_dict(), ["username", "first_name", "last_name"]),
        telegram_id=user.id
    )
