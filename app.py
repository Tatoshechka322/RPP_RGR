import os
import random
import string
from datetime import datetime
from flask import Flask, request, redirect, render_template, flash, url_for
from flask_login import login_user, LoginManager, logout_user, current_user, login_required
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash
from flask_caching import Cache
from flask_limiter import Limiter

# Импорт собственных модулей
from db import db  # Импорт объекта базы данных
from db.models import users, ShortenedLink  # Импорт моделей пользователей и коротких ссылок


# --- Инициализация приложения и компонентов ---
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Генерация секретного ключа для Flask

# Настройка подключения к базе данных PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://ershtrub:postgres@127.0.0.1:5432/BokovLarionov'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Отключение отслеживания изменений в SQLAlchemy

# Настройка кэша
app.config['CACHE_TYPE'] = 'SimpleCache'

# Инициализация базы данных, кэша и limitera
db.init_app(app)
cache = Cache(app)
limiter = Limiter(app, default_limits=["10/day", "100/day"])  # Лимитирование запросов


# --- Инициализация менеджера логинов ---
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Настройка представления для входа


# --- Функция загрузки пользователя по ID ---
@login_manager.user_loader
def load_user(user_id):
    """Загружает пользователя из базы данных по его ID."""
    return users.query.get(int(user_id))


# --- Функция генерации короткого ID ---
def generate_short_id(length=6):
    """Генерирует случайный короткий ID заданной длины."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


# --- Маршрут главной страницы ---
@app.route('/', methods=['GET', 'POST'])
@limiter.limit("10/day", key_func=lambda: current_user.id if current_user.is_authenticated else None,
               error_message="Превышен лимит на создание ссылок.")
@login_required  # Требуется авторизация
def index():
    """Обрабатывает запросы главной страницы (создание коротких ссылок)."""
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

        # Проверка лимита на создание ссылок за день
        today = datetime.utcnow().date()
        links_created_today = ShortenedLink.query.filter(
            ShortenedLink.user_id == current_user.id,
            func.date(ShortenedLink.created_at) == today
        ).count()
        if links_created_today >= 10:
            flash("Превышен лимит на создание ссылок.", "error")
            return redirect(url_for('index'))

        new_link = ShortenedLink(user_id=current_user.id, original_url=original_url, short_id=short_id)
        db.session.add(new_link)
        db.session.commit()
        flash(f'Ваш короткий URL: {url_for("redirect_to_original", short_id=short_id, _external=True)}', 'success')
        return redirect(url_for('index'))
    return render_template('index.html')


# --- Маршрут перенаправления по короткому URL ---
@app.route('/<short_id>')
@limiter.limit("100/day")
def redirect_to_original(short_id):
    """Перенаправляет пользователя по короткому URL на оригинальный URL."""
    cached_url = cache.get(short_id)
    if cached_url:
        return redirect(cached_url)

    link = ShortenedLink.query.filter_by(short_id=short_id).first()
    if link:
        link.click_count += 1
        db.session.add(link)
        db.session.commit()
        cache.set(short_id, link.original_url, timeout=3600)  # Кэширование на 1 час
        return redirect(link.original_url)
    else:
        return "URL не найден", 404


# --- Маршрут для получения статистики по короткому URL ---
@app.route('/stats/<short_id>')
@login_required
def stats(short_id):
    """Возвращает статистику по короткому URL (количество кликов)."""
    link = ShortenedLink.query.filter_by(short_id=short_id).first_or_404()
    return {'click_count': link.click_count}


# --- Маршрут для входа ---
@app.route('/signin', methods=['GET', 'POST'])
def login():
    """Обрабатывает запросы страницы входа."""
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


# --- Маршрут для регистрации ---
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Обрабатывает запросы страницы регистрации."""
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
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            errors.append(f"Ошибка при регистрации: {e}") #Добавил вывод ошибки

    return render_template('signup.html', errors=errors, login=login, password='', password_check='')


# --- Маршрут для выхода ---
@app.route('/logout')
def logout():
    """Выполняет выход пользователя из системы."""
    logout_user()
    return redirect(url_for('index'))


# --- Запуск приложения ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Создание таблиц базы данных
    app.run(debug=True)
    
