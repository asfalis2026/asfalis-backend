from app.extensions import db
from datetime import datetime


class RevokedToken(db.Model):
    """Stores JTIs of refresh tokens that have been revoked (via logout or rotation).

    Access tokens are short-lived (15 min) so they are not tracked here.
    Only refresh tokens are blacklisted to keep every protected-endpoint
    database hit away from the hot path.
    """

    __tablename__ = 'revoked_tokens'

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, unique=True, index=True)
    token_type = db.Column(db.String(20), nullable=False, default='refresh')
    revoked_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<RevokedToken jti={self.jti} type={self.token_type}>'
