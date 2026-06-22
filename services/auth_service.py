"""
用户认证与权限服务
基于 MySQL 的 users / roles / permissions 表
"""
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import settings
from database.mysql_client import mysql_client

# 使用 HTTPBearer 从请求头提取 token
security = HTTPBearer(auto_error=False)

SECRET_KEY = getattr(settings, "secret_key", "hospital-narrative-assistant-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def get_user_by_username(username: str) -> Optional[dict]:
    rows = mysql_client.execute(
        "SELECT id, username, password_hash, name, phone, email, department, status FROM users WHERE username = :username",
        {"username": username},
    )
    if not rows:
        return None
    row = rows[0]
    return {
        "id": row[0],
        "username": row[1],
        "password_hash": row[2],
        "name": row[3],
        "phone": row[4],
        "email": row[5],
        "department": row[6],
        "status": row[7],
    }


def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        return None
    if not user["status"]:
        return None
    return user


def get_user_roles(user_id: int) -> list:
    rows = mysql_client.execute(
        """
        SELECT r.role_code, r.role_name FROM roles r
        JOIN user_roles ur ON r.id = ur.role_id
        WHERE ur.user_id = :user_id AND r.status = 1
        """,
        {"user_id": user_id},
    )
    return [{"role_code": row[0], "role_name": row[1]} for row in rows]


def get_user_permissions(user_id: int) -> list:
    rows = mysql_client.execute(
        """
        SELECT DISTINCT p.permission_code, p.permission_name, p.resource, p.action
        FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        JOIN user_roles ur ON rp.role_id = ur.role_id
        WHERE ur.user_id = :user_id
        """,
        {"user_id": user_id},
    )
    return [{"permission_code": row[0], "permission_name": row[1], "resource": row[2], "action": row[3]} for row in rows]


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证信息")
    payload = decode_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或已过期")
    user = get_user_by_username(payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    if not user["status"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已禁用")
    user["roles"] = get_user_roles(user["id"])
    user["permissions"] = [p["permission_code"] for p in get_user_permissions(user["id"])]
    return user


def require_permission(permission_code: str):
    def checker(user: dict = Depends(get_current_user)):
        if permission_code not in user.get("permissions", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"缺少权限: {permission_code}")
        return user
    return checker
