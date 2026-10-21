from app.db.base import Base, TimestampMixin

# Los modelos de dominio se importarán aquí para que Alembic y SQLAlchemy conozcan su metadata
__all__ = ["Base", "TimestampMixin"]
