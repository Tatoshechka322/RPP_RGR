import os

class Config:
    SQLALCHEMY_DATABASE_URI = 'postgresql://ershtrub:postgres@127.0.0.1:5432/BokovLarionov'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.urandom(24)  # Для безопасных форм
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 3600  # 1 час