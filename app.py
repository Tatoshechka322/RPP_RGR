import os
import random
import string
from flask import Flask, request, redirect, render_template, flash, url_for
from flask_login import login_user, LoginManager, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from db import db
from db.models import users, ShortenedLink

# Инициализация компонентов
app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://ershtrub:postgres@127.0.0.1:5432/BokovLarionov'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


# Инициализация LoginManager
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# Загрузка пользователя по ID
@login_manager.user_loader
def load_users(user_id):
    return users.query.get(int(user_id))


@login_manager.user_loader
def load_user(user_id):
    return users.query.get(int(user_id))

def generate_short_id(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        original_url = request.form['original_url']
        custom_short_id = request.form.get('custom_short_id')

        if not original_url:
            flash('Пожалуйста, введите URL', 'error')
            return redirect(url_for('index'))

        short_id = custom_short_id or generate_short_id()
        existing_link = ShortenedLink.query.filter_by(short_id=short_id).first()
        if existing_link:
            flash('Этот короткий URL уже используется.', 'error')
            return redirect(url_for('index'))

        new_link = ShortenedLink(user_id=current_user.id if current_user.is_authenticated else None, original_url=original_url, short_id=short_id)
        db.session.add(new_link)
        db.session.commit()
        flash(f'Ваш короткий URL: {url_for("redirect_to_original", short_id=short_id, _external=True)}', 'success')
        return redirect(url_for('index'))
    return render_template('index.html')


@app.route('/<short_id>')
def redirect_to_original(short_id):
    link = ShortenedLink.query.filter_by(short_id=short_id).first_or_404()
    link.click_count += 1
    db.session.commit()
    return redirect(link.original_url)


## Страница Входа
@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'GET':
        return render_template('signin.html')

    errors = []
    login = request.form.get('login')
    password = request.form.get('password')
    user = users.query.filter_by(login=login).first()

    # Ошибка: поля не заполнены
    if not login or not password:
        errors.append('Пожалуйста, заполните все поля')
    elif user is None:
        errors.append('Такой пользователь отсутствует')
    elif not check_password_hash(user.password, password):
        errors.append('Неверный пароль')
    else:
        login_user(user)
        flash('Вы успешно вошли!', 'success')
        return redirect(url_for('main'))

    return render_template('signin.html', errors=errors, login=login, password='')

## Страница Регистрации
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')

    errors = []
    login = request.form.get('login')
    password = request.form.get('password')
    password_check = request.form.get('password_check')

    if not login or not password or not password_check:
        errors.append("Все поля должны быть заполнены")

    elif password != password_check:
        errors.append("Пароли не совпадают")

    user = users.query.filter_by(login=login).first()
    if user:
        errors.append("Пользователь с таким логином уже существует")

    if not errors:
        try:
            hashed_password = generate_password_hash(password)
            new_user = users(login=login, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            flash('Вы успешно зарегистрировались!', 'success')  # Добавить flash сообщение об успехе
            return redirect(url_for('signin'))
        except Exception as e:
            db.session.rollback()
    return render_template('signin.html', errors=errors, login=login, password='', password_check='')



## Выход пользователя
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
