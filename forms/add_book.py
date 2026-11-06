from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import SubmitField
from wtforms.fields.simple import BooleanField
from wtforms.validators import DataRequired

class AddBookForm(FlaskForm):
    file = FileField('Выберите файл в формате ".txt"', validators=[DataRequired()])
    submit = SubmitField('Загрузить')
    auto_name = BooleanField('автоматически определить название книги', default=True)