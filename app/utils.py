# Use pbkdf2_sha256 to avoid bcrypt binary dependency issues on Windows
from passlib.context import CryptContext

# pbkdf2_sha256 is pure-python (provided by passlib), stable and secure enough for typical apps
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
