from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Shared declarative base for all SQLAlchemy models.
    Import this in every model file and inherit from it.
    Alembic reads this base to discover models for autogenerate.
    """

    pass
