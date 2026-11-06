import sqlalchemy
from .db_session import SqlAlchemyBase
from sqlalchemy import orm


class Book(SqlAlchemyBase):
    __tablename__ = 'books'

    id = sqlalchemy.Column(sqlalchemy.Integer,
                           primary_key=True, autoincrement=True)
    title = sqlalchemy.Column(sqlalchemy.String,
                            unique=True, nullable=True)
    filepath = sqlalchemy.Column(sqlalchemy.String,
                                 nullable=True)