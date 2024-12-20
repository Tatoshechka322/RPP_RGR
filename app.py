import os
import random
import string
from datetime import datetime, timedelta

from flask import Flask, request, redirect, render_template, flash, url_for
from flask_login import login_user, LoginManager, logout_user, current_user, login_required
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from db import db
from db.models import users, ShortenedLink

# Инициализация компонентов
app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://ershtrub:postgres@127.0.0.1:5432/BokovLarionov'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['CACHE_TYPE'] = 'SimpleCache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 3600

db.init_app(app)
cache = Cache(app)
limiter = Limiter(app, default_limits=["10/day", "100/day"])

# Инициализация LoginManager
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# Загрузка пользователя по ID
@login_manager.user_loader
def load_user(user_id):
    return users.query.get(int(user_id))


def generate_short_id(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


##
@app.route('/', methods=['GET', 'POST'])
@limiter.limit("10/day", key_func=lambda: current_user.id if current_user.is_authenticated else None,
               error_message="Превышен лимит на создание ссылок.")

@login_required
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

            # Проверка лимита на создание ссылок
        today = datetime.utcnow().date()
        links_created_today = ShortenedLink.query.filter(
            ShortenedLink.user_id == current_user.id,
            func.date(ShortenedLink.created_at) == today
        ).count()
        if links_created_today >= 10:
            flash("Превышен лимит на создание ссылок.", "error")
            return redirect(url_for('index'))

        new_link = ShortenedLink(user_id=current_user.id if current_user.is_authenticated else None, original_url=original_url, short_id=short_id)
        db.session.add(new_link)
        db.session.commit()
        flash(f'Ваш короткий URL: {url_for("redirect_to_original", short_id=short_id, _external=True)}', 'success')
        return redirect(url_for('index'))
    return render_template('index.html')


##
@app.route('/<short_id>')
# @limiter.limit("100/day", error_message="Превышен лимит кликов по этой ссылке.")
@limiter.limit("100/day", key_func=lambda: request.remote_addr, error_message="Превышен лимит кликов по этой ссылке.")
def redirect_to_original(short_id):
    link = cache.get(short_id)
    if link and (datetime.utcnow() - link['created_at']) < timedelta(hours=1):
        link['click_count'] += 1
        cache.set(short_id, link)
        return redirect(link['original_url'])
    else:
        link = ShortenedLink.query.filter_by(short_id=short_id).first_or_404()
        link.click_count += 1
        db.session.commit()
        cache.set(short_id, {'original_url': link.original_url, 'click_count': link.click_count, 'created_at': datetime.utcnow()}) #Добавление времени создания в кэш
        return redirect(link.original_url)


##
@app.route('/stats/<short_id>')
@login_required
def stats(short_id):
    link = ShortenedLink.query.filter_by(short_id=short_id).first_or_404()
    return {'click_count': link.click_count}


## Страница Входа
@app.route('/signin', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('signin.html')

    errors = []
    login = request.form.get('login')
    password = request.form.get('password')
    user = users.query.filter_by(login=login).first()

    if not login or not password:
        errors.append('Пожалуйста, заполните все поля')
    elif user is None:
        errors.append('Такой пользователь отсутствует')
    elif not check_password_hash(user.password, password):
        errors.append('Неверный пароль')
    else:
        login_user(user)
        flash('Вы успешно вошли!', 'success')
        return redirect(url_for('index'))

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
            flash('Вы успешно зарегистрировались!', 'success')
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
