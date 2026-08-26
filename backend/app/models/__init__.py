# Import all models here so Alembic can discover them for autogenerate.
# The order matters for foreign key resolution during table creation.
from app.models.account import Account
from app.models.audit_log import AuditLog
from app.models.category import Category
from app.models.pending_transaction import PendingTransaction
from app.models.profile import Profile
from app.models.telegram_link import TelegramLink
from app.models.transaction import Transaction
from app.models.transaction_item import TransactionItem

__all__ = [
    "Profile",
    "TelegramLink",
    "Category",
    "Account",
    "Transaction",
    "TransactionItem",
    "AuditLog",
    "PendingTransaction",
]
