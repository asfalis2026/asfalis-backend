from sqlalchemy import Column, Integer, String, DateTime, Index
from datetime import datetime

from app.database import Base


class RevokedToken(Base):
    """Stores JTIs of refresh tokens that have been revoked (via logout or rotation)."""

    __tablename__ = 'revoked_tokens'

    id = Column(Integer, primary_key=True)
    jti = Column(String(36), nullable=False, unique=True, index=True)
    token_type = Column(String(20), nullable=False, default='refresh')
    revoked_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<RevokedToken jti={self.jti} type={self.token_type}>'
