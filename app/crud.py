from sqlalchemy.orm import Session
from app import models, schemas, utils
from typing import Optional, List
from datetime import date
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import func

# ---------- Users ----------
def get_user_by_userid(db: Session, userid: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.userid == userid).first()

def create_user(db: Session, user_in: schemas.UserCreate, actor_id: Optional[int] = None) -> models.User:
    hashed = utils.hash_password(user_in.password)
    user = models.User(
        userid=user_in.userid,
        full_name=user_in.full_name,
        password_hash=hashed,
        is_admin=user_in.is_admin,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(models.AuditLog(actor_user_id=actor_id, action="create_user", details={"created_user": user.userid}))
    db.commit()
    return user

def authenticate_user(db: Session, userid: str, password: str) -> Optional[models.User]:
    user = get_user_by_userid(db, userid)
    if not user:
        return None
    # block inactive users
    if getattr(user, "is_active", True) is False:
        return None
    if not utils.verify_password(password, user.password_hash):
        return None
    return user

def list_users(db: Session) -> List[models.User]:
    return db.query(models.User).order_by(models.User.id).all()

# ---------- Daily financials ----------
def upsert_daily(db: Session, user_id: int, date_val: date, deposit: float, withdraw: float):
    stmt = insert(models.DailyFinancial).values(
        user_id=user_id, date=date_val, total_deposit=deposit, total_withdraw=withdraw
    ).on_conflict_do_update(
        index_elements=['user_id', 'date'],
        set_={
            "total_deposit": deposit,
            "total_withdraw": withdraw,
            "created_at": func.now(),
            "is_deleted": False  # un-delete on upsert
        }
    ).returning(
        models.DailyFinancial.id,
        models.DailyFinancial.user_id,
        models.DailyFinancial.date,
        models.DailyFinancial.total_deposit,
        models.DailyFinancial.total_withdraw,
        models.DailyFinancial.created_at,
        models.DailyFinancial.is_deleted
    )
    res = db.execute(stmt)
    db.commit()
    return res.fetchone()

def list_user_daily(db: Session, user_id: int):
    return db.query(models.DailyFinancial).filter(
        models.DailyFinancial.user_id == user_id,
        models.DailyFinancial.is_deleted == False
    ).order_by(models.DailyFinancial.date.desc()).all()

def get_user_daily_by_userid(db: Session, userid: str):
    user = get_user_by_userid(db, userid)
    if not user:
        return None
    return list_user_daily(db, user.id)

# ---------- Logs ----------
def list_logs(db: Session, limit: int = 1000):
    return db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(limit).all()

# ---------- Admin / edit / soft-delete ----------
def get_daily_by_id(db: Session, daily_id: int):
    return db.query(models.DailyFinancial).filter(models.DailyFinancial.id == daily_id).first()

def update_daily(db: Session, daily_id: int, deposit: float, withdraw: float, actor_id: Optional[int] = None):
    row = db.query(models.DailyFinancial).filter(models.DailyFinancial.id == daily_id).first()
    if not row:
        return None
    before = {"total_deposit": float(row.total_deposit), "total_withdraw": float(row.total_withdraw)}
    row.total_deposit = deposit
    row.total_withdraw = withdraw
    # if editing a previously deleted record, leave is_deleted as-is (admin may explicitly restore)
    db.add(models.AuditLog(actor_user_id=actor_id, action="update_daily", details={"daily_id": daily_id, "before": before, "after": {"total_deposit": deposit, "total_withdraw": withdraw}}))
    db.commit()
    db.refresh(row)
    return row

def soft_delete_daily(db: Session, daily_id: int, actor_id: Optional[int] = None):
    row = db.query(models.DailyFinancial).filter(models.DailyFinancial.id == daily_id).first()
    if not row:
        return None
    row.is_deleted = True
    db.add(models.AuditLog(actor_user_id=actor_id, action="delete_daily", details={"daily_id": daily_id}))
    db.commit()
    db.refresh(row)
    return row

def restore_daily(db: Session, daily_id: int, actor_id: Optional[int] = None):
    row = db.query(models.DailyFinancial).filter(models.DailyFinancial.id == daily_id).first()
    if not row:
        return None
    row.is_deleted = False
    db.add(models.AuditLog(actor_user_id=actor_id, action="restore_daily", details={"daily_id": daily_id}))
    db.commit()
    db.refresh(row)
    return row

# ---------- User management: deactivate / restore / hard delete ----------
def deactivate_user(db: Session, userid: str, actor_id: Optional[int] = None):
    user = db.query(models.User).filter(models.User.userid == userid).first()
    if not user:
        return None
    user.is_active = False
    db.add(models.AuditLog(actor_user_id=actor_id, action="deactivate_user", details={"userid": userid}))
    db.commit()
    db.refresh(user)
    return user

def restore_user(db: Session, userid: str, actor_id: Optional[int] = None):
    user = db.query(models.User).filter(models.User.userid == userid).first()
    if not user:
        return None
    user.is_active = True
    db.add(models.AuditLog(actor_user_id=actor_id, action="restore_user", details={"userid": userid}))
    db.commit()
    db.refresh(user)
    return user

def hard_delete_user(db: Session, userid: str, actor_id: Optional[int] = None):
    user = db.query(models.User).filter(models.User.userid == userid).first()
    if not user:
        return None
    db.add(models.AuditLog(actor_user_id=actor_id, action="delete_user", details={"userid": userid}))
    db.delete(user)
    db.commit()
    return True
