from sqlalchemy import Column, Integer, Text, Boolean, Date, Numeric, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.db import Base
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    userid = Column(Text, unique=True, nullable=False, index=True)
    full_name = Column(Text)
    password_hash = Column(Text, nullable=False)
    is_admin = Column(Boolean, default=False)
    # NEW: track whether user can log in / is active
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # cascade deletes daily entries when user is hard-deleted
    daily = relationship("DailyFinancial", back_populates="user", cascade="all, delete-orphan")
    logs = relationship("AuditLog", back_populates="actor")


class DailyFinancial(Base):
    __tablename__ = "daily_financials"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    total_deposit = Column(Numeric(14, 2), default=0)
    total_withdraw = Column(Numeric(14, 2), default=0)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    # NEW: soft-delete flag so records can be restored
    is_deleted = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="daily")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(Text, nullable=False)
    details = Column(JSONB)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    actor = relationship("User", back_populates="logs")
