# Import all models here so Alembic can discover them for autogenerate.
# The order matters for foreign key resolution during table creation.
from app.models.user import User
from app.models.telegram_link import TelegramLink
from app.models.category import Category
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.transaction_item import TransactionItem
from app.models.audit_log import AuditLog

__all__ = [
    "User",
    "TelegramLink",
    "Category",
    "Account",
    "Transaction",
    "TransactionItem",
    "AuditLog",
]
