import os
from app.db import engine, Base, SessionLocal
from app import models, utils
from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()

def create_db_and_admin(admin_userid: str, admin_password: str, full_name: str = "Administrator"):
    # create tables (SQLAlchemy)
    Base.metadata.create_all(bind=engine)

    # Create the unique constraint only if it doesn't already exist (works across Postgres versions)
    create_constraint_sql = text("""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'unique_user_date'
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

    db = SessionLocal()
    try:
        existing = db.query(models.User).filter(models.User.userid == admin_userid).first()
        if existing:
            print("Admin user already exists:", admin_userid)
            return
        hashed = utils.hash_password(admin_password)
        admin = models.User(userid=admin_userid, full_name=full_name, password_hash=hashed, is_admin=True, is_active=True)
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print("Created admin:", admin.userid)
    finally:
        db.close()

if __name__ == "__main__":
    import getpass
    userid = input("Admin userid to create (e.g. admin): ").strip() or "admin"
    pwd = getpass.getpass("Admin password: ")
    create_db_and_admin(userid, pwd)
