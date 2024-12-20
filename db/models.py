from datetime import datetime

from . import db
from flask_login import UserMixin

class users(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(30), nullable=False, unique=True)
    password = db.Column(db.String(1024))

    def __repr__(self):
        return f'id:{self.id}, login:{self.login}'

class ShortenedLink(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
  original_url = db.Column(db.String(255), nullable=False)
  short_id = db.Column(db.String(6), unique=True, nullable=False)
  click_count = db.Column(db.Integer, default=0)
  created_at = db.Column(db.DateTime, default=datetime.utcnow)

def __repr__(self):
    return f'<ShortenedLink {self.short_id}>'
