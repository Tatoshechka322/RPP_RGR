import pickle
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import ARRAY


db = SQLAlchemy()

class users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

    def __repr__(self):
        return f'<users {self.login}>'

class ShortenedLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    original_url = db.Column(db.String(255), nullable=False)
    short_id = db.Column(db.String(6), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    click_count = db.Column(db.Integer, default=0)
    ip_addresses = db.Column(ARRAY(db.String(15)), default=[]) #Use ARRAY for better efficiency.

    user = db.relationship('User', backref=db.backref('shortened_links', lazy=True))

    def __repr__(self):
        return f'<ShortenedLink {self.short_id}>'
