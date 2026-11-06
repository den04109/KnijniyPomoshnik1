import sqlalchemy
from sqlalchemy import orm
from .db_session import SqlAlchemyBase


class Query(SqlAlchemyBase):
    __tablename__ = 'queries'

    id = sqlalchemy.Column(sqlalchemy.Integer,
                           primary_key=True, autoincrement=True)
    question = sqlalchemy.Column(sqlalchemy.String,)
    answer = sqlalchemy.Column(sqlalchemy.String,
                               nullable=True)
    user_id = sqlalchemy.Column(sqlalchemy.Integer,
                                sqlalchemy.ForeignKey("users.id"))
    user = orm.relationship('User')