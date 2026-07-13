"""
JWT 认证与权限。

用法 — api.py 直接声明依赖即可：
    from .auth import get_current_user, require_admin

    @router.get("/entities")
    def list_entities(user=Depends(get_current_user)):           # 登录即可
        ...

    @router.post("/entities")
    def create_entity(payload, user=Depends(require_admin)):    # 需管理员
        ...
"""
import re
from datetime import datetime, timedelta

import jwt
from fastapi import Depends, Header, HTTPException
from passlib.context import CryptContext

try:
    from .config import JWT_ALGORITHM, JWT_EXPIRE_HOURS, JWT_SECRET
except ImportError:
    from config import JWT_ALGORITHM, JWT_EXPIRE_HOURS, JWT_SECRET

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 角色层级
ROLE_LEVEL = {"admin": 2, "user": 1}


# ---------- 密码 ----------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------- JWT ----------
def create_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的 Token")


# ---------- FastAPI 依赖 ----------
def get_current_user(authorization: str = Header(None)) -> dict:
    """登录即可：从 Authorization header 解析用户，未登录 401。"""
    if not authorization:
        raise HTTPException(status_code=401, detail="请先登录")
    match = re.match(r"^Bearer\s+(.+)$", authorization)
    if not match:
        raise HTTPException(status_code=401, detail="Authorization 格式应为 Bearer <token>")
    return decode_token(match.group(1))


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """管理员权限：未登录 401，非 admin 403。"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="权限不足，需要管理员")
    return user
