"""
认证相关 API
"""
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from services.auth_service import (
    authenticate_user,
    create_access_token,
    get_current_user,
    get_password_hash,
    get_user_by_username,
    get_user_permissions,
    get_user_roles,
)
from database.mysql_client import mysql_client

router = APIRouter(tags=["认证"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserProfileResponse(BaseModel):
    id: int
    username: str
    name: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    department: Optional[str]
    roles: list
    permissions: list


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    access_token = create_access_token(data={"sub": user["username"], "user_id": user["id"]})
    roles = get_user_roles(user["id"])
    permissions = get_user_permissions(user["id"])

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "name": user["name"],
            "department": user["department"],
            "roles": roles,
            "permissions": [p["permission_code"] for p in permissions],
        },
    }


@router.get("/me", response_model=UserProfileResponse)
async def get_me(user: dict = Depends(get_current_user)):
    return {
        "id": user["id"],
        "username": user["username"],
        "name": user["name"],
        "phone": user["phone"],
        "email": user["email"],
        "department": user["department"],
        "roles": user["roles"],
        "permissions": user["permissions"],
    }


@router.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    user: dict = Depends(get_current_user),
):
    from services.auth_service import verify_password, get_password_hash

    db_user = get_user_by_username(user["username"])
    if not verify_password(old_password, db_user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")

    mysql_client.execute(
        "UPDATE users SET password_hash = :hash WHERE id = :id",
        {"hash": get_password_hash(new_password), "id": user["id"]},
    )
    return {"status": "ok", "message": "密码修改成功"}
