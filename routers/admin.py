"""
后台管理 API
提供用户、角色、权限、功能开关、系统配置管理
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from database.mysql_client import mysql_client
from services.auth_service import get_current_user, require_permission, get_password_hash
from config import settings

router = APIRouter(tags=["后台管理"])


# ========== 用户管理 ==========

class UserCreateRequest(BaseModel):
    username: str
    password: str
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    role_codes: List[str] = []
    status: int = 1


class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    role_codes: Optional[List[str]] = None
    status: Optional[int] = None


@router.get("/users")
async def list_users(user=Depends(require_permission("user:view"))):
    rows = mysql_client.execute(
        """
        SELECT u.id, u.username, u.name, u.phone, u.email, u.department, u.status,
               GROUP_CONCAT(r.role_code) as roles
        FROM users u
        LEFT JOIN user_roles ur ON u.id = ur.user_id
        LEFT JOIN roles r ON ur.role_id = r.id
        GROUP BY u.id
        ORDER BY u.id DESC
        """
    )
    return [
        {
            "id": row[0],
            "username": row[1],
            "name": row[2],
            "phone": row[3],
            "email": row[4],
            "department": row[5],
            "status": row[6],
            "roles": row[7].split(",") if row[7] else [],
        }
        for row in rows
    ]


@router.post("/users")
async def create_user(req: UserCreateRequest, user=Depends(require_permission("user:create"))):
    existing = mysql_client.execute(
        "SELECT id FROM users WHERE username = :username", {"username": req.username}
    )
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    result = mysql_client.execute(
        """
        INSERT INTO users (username, password_hash, name, phone, email, department, status)
        VALUES (:username, :password_hash, :name, :phone, :email, :department, :status)
        """,
        {
            "username": req.username,
            "password_hash": get_password_hash(req.password),
            "name": req.name,
            "phone": req.phone,
            "email": req.email,
            "department": req.department,
            "status": req.status,
        },
    )
    new_user_id = result.lastrowid

    if req.role_codes:
        _bind_user_roles(new_user_id, req.role_codes)

    return {"status": "ok", "id": new_user_id}


@router.put("/users/{user_id}")
async def update_user(user_id: int, req: UserUpdateRequest, user=Depends(require_permission("user:update"))):
    update_fields = []
    params = {"user_id": user_id}
    if req.name is not None:
        update_fields.append("name = :name")
        params["name"] = req.name
    if req.phone is not None:
        update_fields.append("phone = :phone")
        params["phone"] = req.phone
    if req.email is not None:
        update_fields.append("email = :email")
        params["email"] = req.email
    if req.department is not None:
        update_fields.append("department = :department")
        params["department"] = req.department
    if req.status is not None:
        update_fields.append("status = :status")
        params["status"] = req.status

    if update_fields:
        mysql_client.execute(
            f"UPDATE users SET {', '.join(update_fields)} WHERE id = :user_id",
            params,
        )

    if req.role_codes is not None:
        _bind_user_roles(user_id, req.role_codes)

    return {"status": "ok"}


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, user=Depends(require_permission("user:delete"))):
    mysql_client.execute("DELETE FROM users WHERE id = :id", {"id": user_id})
    return {"status": "ok"}


def _bind_user_roles(user_id: int, role_codes: List[str]):
    mysql_client.execute("DELETE FROM user_roles WHERE user_id = :user_id", {"user_id": user_id})
    if not role_codes:
        return
    placeholders = ", ".join([f"'{code}'" for code in role_codes])
    mysql_client.execute(
        f"""
        INSERT INTO user_roles (user_id, role_id)
        SELECT :user_id, id FROM roles WHERE role_code IN ({placeholders})
        """,
        {"user_id": user_id},
    )


# ========== 角色与权限 ==========

@router.get("/roles")
async def list_roles(user=Depends(require_permission("role:view"))):
    rows = mysql_client.execute(
        """
        SELECT r.id, r.role_code, r.role_name, r.description, r.status,
               GROUP_CONCAT(p.permission_code) as permissions
        FROM roles r
        LEFT JOIN role_permissions rp ON r.id = rp.role_id
        LEFT JOIN permissions p ON rp.permission_id = p.id
        GROUP BY r.id
        """
    )
    return [
        {
            "id": row[0],
            "role_code": row[1],
            "role_name": row[2],
            "description": row[3],
            "status": row[4],
            "permissions": row[5].split(",") if row[5] else [],
        }
        for row in rows
    ]


@router.get("/permissions")
async def list_permissions(user=Depends(require_permission("role:view"))):
    rows = mysql_client.execute("SELECT id, permission_code, permission_name, resource, action, description FROM permissions")
    return [
        {
            "id": row[0],
            "permission_code": row[1],
            "permission_name": row[2],
            "resource": row[3],
            "action": row[4],
            "description": row[5],
        }
        for row in rows
    ]


class RolePermissionUpdateRequest(BaseModel):
    permission_codes: List[str]


@router.put("/roles/{role_id}/permissions")
async def update_role_permissions(
    role_id: int,
    req: RolePermissionUpdateRequest,
    user=Depends(require_permission("role:update")),
):
    mysql_client.execute("DELETE FROM role_permissions WHERE role_id = :role_id", {"role_id": role_id})
    if not req.permission_codes:
        return {"status": "ok"}
    placeholders = ", ".join([f"'{code}'" for code in req.permission_codes])
    mysql_client.execute(
        f"""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT :role_id, id FROM permissions WHERE permission_code IN ({placeholders})
        """,
        {"role_id": role_id},
    )
    return {"status": "ok"}


# ========== 功能开关 ==========

@router.get("/features")
async def list_features(user=Depends(get_current_user)):
    rows = mysql_client.execute("SELECT feature_code, feature_name, enabled, description FROM feature_switches")
    return {row[0]: bool(row[2]) for row in rows}


@router.put("/features")
async def update_features(req: dict, user=Depends(require_permission("feature:update"))):
    for code, enabled in req.items():
        mysql_client.execute(
            "UPDATE feature_switches SET enabled = :enabled WHERE feature_code = :code",
            {"code": code, "enabled": 1 if enabled else 0},
        )
    return {"status": "ok"}


# ========== 系统配置 ==========

@router.get("/config")
async def get_config(user=Depends(get_current_user)):
    rows = mysql_client.execute(
        "SELECT config_key, config_value, description FROM system_configs WHERE is_public = 1"
    )
    result = {row[0]: row[1] for row in rows}
    if settings.simulation_date:
        result["simulation_date"] = settings.simulation_date
    return result


@router.put("/config")
async def update_config(req: dict, user=Depends(require_permission("config:update"))):
    for key, value in req.items():
        mysql_client.execute(
            "UPDATE system_configs SET config_value = :value WHERE config_key = :key",
            {"key": key, "value": str(value)},
        )
    return {"status": "ok"}
