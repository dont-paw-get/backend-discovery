"""SQLAlchemy 선언적 베이스. 모든 ORM 모델은 이 Base를 상속한다."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
