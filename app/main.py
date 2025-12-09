from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db import Base, engine, get_db
from app import crud, schemas, auth, models

app = FastAPI(title="FastAPI Finance - Admin/User System")

# Allow all CORS for local development (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# create tables if missing
Base.metadata.create_all(bind=engine)

# ensure unique constraint for (user_id, date) (Postgres-friendly)
create_constraint_sql = text("""
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'unique_user_date'
  ) THEN
    ALTER TABLE daily_financials
    ADD CONSTRAINT unique_user_date UNIQUE (user_id, date);
  END IF;
END
$$;
""")
with engine.connect() as conn:
    conn.execute(create_constraint_sql)
    conn.commit()


# -------------------------
# AUTH
# -------------------------
@app.post("/auth/login", response_model=schemas.Token)
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = crud.authenticate_user(db, data.userid, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token_data = {"id": user.id, "userid": user.userid, "is_admin": user.is_admin}
    access_token = auth.create_access_token(token_data)
    db.add(models.AuditLog(actor_user_id=user.id, action="login", details={"userid": user.userid}))
    db.commit()
    return {"access_token": access_token, "token_type": "bearer"}


# -------------------------
# ADMIN endpoints
# -------------------------
@app.post("/admin/users", response_model=schemas.UserOut, status_code=201)
def admin_create_user(user_in: schemas.UserCreate, admin: models.User = Depends(auth.require_admin), db: Session = Depends(get_db)):
    existing = crud.get_user_by_userid(db, user_in.userid)
    if existing:
        raise HTTPException(status_code=400, detail="userid already exists")
    created = crud.create_user(db, user_in, actor_id=admin.id)
    return created


@app.get("/admin/users", response_model=list[schemas.UserOut])
def admin_list_users(admin: models.User = Depends(auth.require_admin), db: Session = Depends(get_db)):
    return crud.list_users(db)


# *** Updated: admin_get_user_daily returns JSON-serializable primitives including is_deleted ***
@app.get("/admin/user/{userid}/daily", response_model=list[schemas.DailyOut])
def admin_get_user_daily(userid: str, admin: models.User = Depends(auth.require_admin), db: Session = Depends(get_db)):
    rows = crud.get_user_daily_by_userid(db, userid)
    if rows is None:
        raise HTTPException(status_code=404, detail="User not found")
    out = []
    for r in rows:
        out.append({
            "id": int(r.id),
            "user_id": int(r.user_id),
            "date": str(r.date),
            "total_deposit": float(r.total_deposit),
            "total_withdraw": float(r.total_withdraw),
            "created_at": str(r.created_at),
            "is_deleted": bool(r.is_deleted)
        })
    return out


@app.get("/admin/logs", response_model=list[schemas.AuditOut])
def admin_get_logs(admin: models.User = Depends(auth.require_admin), db: Session = Depends(get_db)):
    return crud.list_logs(db)


# --- Admin edit/delete/restore daily ---
@app.put("/admin/daily/{daily_id}", response_model=schemas.DailyOut)
def admin_update_daily(daily_id: int, payload: schemas.DailyIn, admin: models.User = Depends(auth.require_admin), db: Session = Depends(get_db)):
    updated = crud.update_daily(db, daily_id, payload.total_deposit, payload.total_withdraw, actor_id=admin.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Daily record not found")
    # serialize for response
    return {
        "id": int(updated.id),
        "user_id": int(updated.user_id),
        "date": str(updated.date),
        "total_deposit": float(updated.total_deposit),
        "total_withdraw": float(updated.total_withdraw),
        "created_at": str(updated.created_at),
        "is_deleted": bool(updated.is_deleted)
    }


@app.delete("/admin/daily/{daily_id}")
def admin_delete_daily(daily_id: int, admin: models.User = Depends(auth.require_admin), db: Session = Depends(get_db)):
    row = crud.soft_delete_daily(db, daily_id, actor_id=admin.id)
    if not row:
        raise HTTPException(status_code=404, detail="Daily record not found")
    return {"detail": "deleted"}


@app.post("/admin/daily/{daily_id}/restore")
def admin_restore_daily(daily_id: int, admin: models.User = Depends(auth.require_admin), db: Session = Depends(get_db)):
    row = crud.restore_daily(db, daily_id, actor_id=admin.id)
    if not row:
        raise HTTPException(status_code=404, detail="Daily record not found")
    return {"detail": "restored"}


# --- Admin user management endpoints ---
@app.post("/admin/user/{userid}/deactivate")
def admin_deactivate_user(userid: str, admin: models.User = Depends(auth.require_admin), db: Session = Depends(get_db)):
    u = crud.deactivate_user(db, userid, actor_id=admin.id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return {"detail": "deactivated", "userid": userid}


@app.post("/admin/user/{userid}/restore")
def admin_restore_user(userid: str, admin: models.User = Depends(auth.require_admin), db: Session = Depends(get_db)):
    u = crud.restore_user(db, userid, actor_id=admin.id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return {"detail": "restored", "userid": userid}


@app.delete("/admin/user/{userid}")
def admin_delete_user(userid: str, admin: models.User = Depends(auth.require_admin), db: Session = Depends(get_db)):
    ok = crud.hard_delete_user(db, userid, actor_id=admin.id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    return {"detail": "deleted", "userid": userid}


# -------------------------
# USER endpoints
# -------------------------
@app.post("/user/daily", response_model=schemas.DailyOut)
def user_post_daily(daily: schemas.DailyIn, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    q = text("""
    INSERT INTO daily_financials (user_id, date, total_deposit, total_withdraw, created_at, is_deleted)
    VALUES (:uid, :date, :dep, :wit, now(), false)
    ON CONFLICT (user_id, date) DO UPDATE
      SET total_deposit = EXCLUDED.total_deposit,
          total_withdraw = EXCLUDED.total_withdraw,
          created_at = now(),
          is_deleted = false
    RETURNING id, user_id, date, total_deposit, total_withdraw, created_at, is_deleted;
    """)
    result = db.execute(q, {"uid": user.id, "date": daily.date, "dep": daily.total_deposit, "wit": daily.total_withdraw})
    db.commit()
    row = result.fetchone()
    db.add(models.AuditLog(actor_user_id=user.id, action="submit_daily", details={"date": str(daily.date), "deposit": daily.total_deposit, "withdraw": daily.total_withdraw}))
    db.commit()
    resp = {
        "id": int(row.id),
        "user_id": int(row.user_id),
        "date": str(row.date),
        "total_deposit": float(row.total_deposit),
        "total_withdraw": float(row.total_withdraw),
        "created_at": str(row.created_at),
        "is_deleted": bool(row.is_deleted)
    }
    return resp


# *** Updated: user_get_daily returns primitives so frontend can display history reliably ***
@app.get("/user/daily", response_model=list[schemas.DailyOut])
def user_get_daily(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    rows = db.query(models.DailyFinancial).filter(models.DailyFinancial.user_id == user.id, models.DailyFinancial.is_deleted == False).order_by(models.DailyFinancial.date.desc()).all()
    out = []
    for r in rows:
        out.append({
            "id": int(r.id),
            "user_id": int(r.user_id),
            "date": str(r.date),
            "total_deposit": float(r.total_deposit),
            "total_withdraw": float(r.total_withdraw),
            "created_at": str(r.created_at),
            "is_deleted": bool(r.is_deleted)
        })
    return out
