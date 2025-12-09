from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, Any

class Token(BaseModel):
    access_token: str
    token_type: str

class LoginRequest(BaseModel):
    userid: str
    password: str

class UserCreate(BaseModel):
    userid: str
    password: str
    full_name: Optional[str] = None
    is_admin: Optional[bool] = False

class UserOut(BaseModel):
    id: int
    userid: str
    full_name: Optional[str] = None
    is_admin: bool
    # now ensures the API can show whether account is active
    is_active: Optional[bool] = True

    class Config:
        orm_mode = True

class DailyIn(BaseModel):
    date: date
    total_deposit: float
    total_withdraw: float

class DailyOut(BaseModel):
    id: int
    user_id: int
    date: date
    total_deposit: float
    total_withdraw: float
    created_at: datetime
    # NEW: expose deletion state to frontend so UI can show Restore/Delete
    is_deleted: bool

    class Config:
        orm_mode = True

class AuditOut(BaseModel):
    id: int
    actor_user_id: Optional[int]
    action: str
    details: Any
    created_at: datetime

    class Config:
        orm_mode = True
