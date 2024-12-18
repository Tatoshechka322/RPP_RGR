from flask import Flask, request, jsonify, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timedelta
import hashlib

app = Flask(__name__)

# Конфигурация базы данных
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://ershtrub:postgres@127.0.0.1:5432/RPP_RGR'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация компонентов
db = SQLAlchemy(app)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
limiter = Limiter(app, key_func=get_remote_address)

# Модели для базы данных
class ShortenedLink(db.Model):
    __tablename__ = 'shortened_links'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(80), nullable=True)
    original_url = db.Column(db.String(255), nullable=False)
    short_id = db.Column(db.String(6), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    click_count = db.Column(db.Integer, default=0)
    ip_addresses = db.Column(db.PickleType, default=[])

# Эндпоинт для создания короткой ссылки
@app.route('/shorten', methods=['POST'])
@limiter.limit("10 per day")  # Ограничение на 10 запросов в день
def shorten():
    data = request.get_json()
    original_url = data.get('original_url')
    user_id = data.get('user_id')

    if not original_url:
        return jsonify({"error": "Original URL is required"}), 400

    # Генерация уникального идентификатора
    short_id = hashlib.md5(original_url.encode()).hexdigest()[:6]

    # Сохранение в базе данных
    new_link = ShortenedLink(original_url=original_url, user_id=user_id, short_id=short_id)
    db.session.add(new_link)
    db.session.commit()

    return jsonify({"shortened_url": f"http://127.0.0.1:5000/{short_id}"}), 201

# Эндпоинт для перенаправления
@app.route('/<short_id>', methods=['GET'])
@cache.cached(timeout=3600, key_prefix='short_url_')  # Кэширование на 1 час
@limiter.limit("100 per day")  # Ограничение на 100 кликов по ссылке с одного IP
def redirect_to_url(short_id):
    # Проверка кэша
    cached_url = cache.get(short_id)
    if cached_url:
        return redirect(cached_url)

    # Получение оригинальной ссылки из базы данных
    link = ShortenedLink.query.filter_by(short_id=short_id).first()
    if not link:
        return jsonify({"error": "Shortened link not found"}), 404

    # Обновление статистики
    link.click_count += 1
    ip_address = get_remote_address()
    if ip_address not in link.ip_addresses:
        link.ip_addresses.append(ip_address)
    db.session.commit()

    # Кэширование оригинального URL
    cache.set(short_id, link.original_url, timeout=3600)

    return redirect(link.original_url)

# Эндпоинт для просмотра статистики
@app.route('/stats/<short_id>', methods=['GET'])
def get_stats(short_id):
    link = ShortenedLink.query.filter_by(short_id=short_id).first()
    if not link:
        return jsonify({"error": "Shortened link not found"}), 404

    return jsonify({
        "click_count": link.click_count,
        "unique_ips": len(link.ip_addresses),
        "ip_addresses": link.ip_addresses
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)