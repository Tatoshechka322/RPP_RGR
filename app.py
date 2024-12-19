import os
import secrets
from sqlite3 import IntegrityError
from flask import Flask, request, redirect, jsonify, render_template, flash, url_for, abort
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import login_user, LoginManager, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from models import db, ShortenedLink, users
from config import Config

app = Flask(__name__)

# Инициализация компонентов
db.init_app(app)

# Инициализация LoginManager
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Загрузка пользователя по ID
@login_manager.user_loader
def load_users(user_id):
    return users.query.get(int(user_id))

@app.route('/', methods=['GET'])
def main():
    return render_template('index.html')

## Страница Входа
@app.route('/signin', methods=['GET', 'POST'])
def login():
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
        return redirect(url_for('index'))

    return render_template('login.html', errors=errors, login=login, password='')

## Страница Регистрации
@app.route('/signup', methods=['GET', 'POST'])
def register():
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
    return render_template('signup.html', errors=errors, login=login, password='', password_check='')



## Выход пользователя
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create tables if they don't exist
    app.run(debug=True)



