import os

from eventlet.wsgi import server
#from mistralai import Mistral
from flask import Flask, render_template, redirect, abort
from pyexpat.errors import messages
from sqlalchemy.dialects.oracle.dictionary import all_users
from sqlalchemy.testing.suite.test_reflection import users

from ai import test_answer
from data import db_session
from data.books import Book
from data.queries import Query
from data.users import User
from forms.add_book import AddBookForm
from forms.login import LoginForm
from forms.register import RegisterForm
from flask_login import current_user, LoginManager, login_user, login_required, logout_user


from flask import request
from flask_socketio import SocketIO, emit
import time

#from our_functions import open_file_to_research_origin

from our_functions import open_file_to_research_origin

app = Flask(__name__)
app.config['SECRET_KEY'] = '1234'

socketio = SocketIO(app, async_mode='eventlet')


login_manager = LoginManager()
login_manager.init_app(app)

def get_all_books():
    db_sess = db_session.create_session()
    all_books = db_sess.query(Book).all()
    return all_books

def get_all_queries(id):
    db_sess = db_session.create_session()
    queries = db_sess.query(Query).filter(Query.user_id == id).all()
    return queries

def get_all_titles():
    db_sess = db_session.create_session()
    books = db_sess.query(Book).all()
    res = [i.title for i in books]
    return res

def get_all_book_filepathes():
    db_sess = db_session.create_session()
    books = db_sess.query(Book).all()
    res = [i.filepath for i in books]
    return res

@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.query(User).get(user_id)


@socketio.on('connect')
def test_connect():
    print('Client connected:', request.sid)
    '''if not messages:
    # Опционально: приветствие для нового клиента
        emit('message', {'user': 'Server', 'msg': 'Привет! Добро пожаловать в чат.', 'type': 'server'}, room=request.sid)
        messages.append({'user': 'Server', 'msg': 'Привет! Добро пожаловать в чат.', 'type': 'server'})'''


@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected:', request.sid)


@socketio.on('message')
def handle_message(data):
    """Обработчик события 'message' от клиента."""
    print('received message: ' + str(data))

    user = data.get('user', 'Anonymous')
    msg = data.get('msg', '')

    if msg:
        # 1. Обработка исходного сообщения пользователя
        user_message_data = {'user': current_user.username, 'msg': msg, 'type': 'user'}

        # Отправляем сообщение всем, включая отправителя
        emit('message', user_message_data, broadcast=True)


        #Запрос к ИИ
        titles_list = get_all_titles()
        server_answer = test_answer(msg, titles_list)

        # 2. Отправка ответного сообщения ТОЛЬКО отправителю
        #answer = test_answer(user_message_data)
        server_reply_data = {'user': 'Server', 'msg': server_answer, 'type': 'server'}
        time.sleep(0.1) # Раскомментируйте для имитации задержки


        # Отправляем ответное сообщение ТОЛЬКО текущему клиенту (отправителю)
        emit('message', server_reply_data, room=request.sid)
        db_sess = db_session.create_session()
        query = Query(question=user_message_data['msg'],
                      answer=server_reply_data['msg'])
        current_user.queries.append(query)
        db_sess.merge(current_user)
        db_sess.commit()



@app.route('/')
def index_with_chat():
    """Главная страница чата."""
    initial_messages = []
    # При загрузке страницы, нужно имитировать, что все сообщения - это
    # либо пользовательские, либо серверные, для корректной отрисовки.
    # Предполагаем, что сообщения от 'Server' - это ответы сервера.
    initial_messages.append({'user': 'Server', 'msg': 'Привет! Добро пожаловать в чат.', 'type': 'server'})
    if current_user.is_authenticated:
        messages = get_all_queries(current_user.id)
        for msg in messages:
            initial_messages.append({'user': current_user.username, 'msg': msg.question, 'type': 'user'})
            initial_messages.append({'user': 'Server', 'msg': msg.answer, 'type': 'server'})



    return render_template('index_with_chat.html', messages=initial_messages)



@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def reqister():
    form = RegisterForm()
    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            return render_template('register.html', title='Регистрация',
                                   form=form,
                                   message="Пароли не совпадают")
        db_sess = db_session.create_session()
        if db_sess.query(User).filter(User.email == form.email.data).first():
            return render_template('register.html', title='Регистрация',
                                   form=form,
                                   message="Такой пользователь уже есть")
        user = User(
            username=form.username.data,
            email=form.email.data
        )
        user.set_password(form.password.data)
        db_sess.add(user)
        db_sess.commit()
        return redirect('/login')
    return render_template('register.html', title='Регистрация', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        user = db_sess.query(User).filter(User.email == form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            return redirect("/")
        return render_template('login.html',
                               message="Неправильный логин или пароль",
                               form=form)
    return render_template('login.html', title='Авторизация', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")

@app.route('/library')
def library():
    db_sess = db_session.create_session()
    books = db_sess.query(Book).all()
    books.sort(key=lambda x: x.title)
    return render_template('library.html', books=books)

@app.route('/add_book', methods=['GET', 'POST'])
def add_book():
    form = AddBookForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()

        file = form.file.data

        # Сохраняем во временную папку
        temp_path = os.path.join('local_file_storage', file.filename)
        file.save(temp_path)

        new_title = file.filename

        # Автоопределение названия
        if form.auto_name.data:
            new_title = open_file_to_research_origin(temp_path)[:-1]+".txt"
            if new_title.startswith('Информации о'):
                new_title = file.filename

        # Проверка на дубликат
        if db_sess.query(Book).filter(Book.title == new_title).first():
            return render_template(
                'add_book.html',
                form=form,
                message='Книга с таким названием уже есть'
            )

        # ВАЖНО: возвращаем указатель файла в начало
        file.stream.seek(0)

        # Сохраняем уже в основную папку
        final_path = os.path.join('files', new_title)
        file.save(final_path)
        os.remove(f"local_file_storage/{file.filename}")

        # Запись в БД
        book = Book(
            title=new_title,
            filepath=final_path
        )
        db_sess.add(book)
        db_sess.commit()

        return redirect('/library')

    return render_template('add_book.html', form=form)

def search_or_create_admin():
    db_sess = db_session.create_session()
    users = db_sess.query(User).all()
    if not users:
        user = User(
            username='admin',
            email='admin@admin'
        )
        user.set_password('admin')
        db_sess.add(user)
        db_sess.commit()

@app.route('/book_delete/<int:id>', methods=['GET', 'POST'])
@login_required
def book_delete(id):
    db_sess = db_session.create_session()
    book = db_sess.query(Book).filter(Book.id == id).first()
    print(book.id)
    if book:
        db_sess.delete(book)
        db_sess.commit()
    else:
        abort(404)
    return redirect('/')

@app.route('/watch_book/<int:id>')
def watch_book(id):
    db_sess = db_session.create_session()
    book = db_sess.query(Book).filter(Book.id == id).first()
    if book:
        f = open(book.filepath, encoding='utf-8')
        text = f.read()
    return render_template('watch_book.html', book=book, text=text)

if __name__ == '__main__':
    db_session.global_init("db/knigniypomoschnik.db")
    search_or_create_admin()
    socketio.run(app, host='127.0.0.1', port=8804, debug=True)