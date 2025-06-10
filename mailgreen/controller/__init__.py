from .auth_controller import router as auth_router
from .mail_controller import router as mail_router
from .sender_controller import router as sender_router
from .keyword_controller import router as keyword_router
from .trash_controller import router as trash_router
from .star_lable_controller import router as star_router
from .carbon_controller import router as carbon_router
from .subscription_controller import router as subscription_router

__all__ = [
    "auth_router",
    "mail_router",
    "sender_router",
    "keyword_router",
    "trash_router",
    "star_router",
    "carbon_router",
    "subscription_router",
]
