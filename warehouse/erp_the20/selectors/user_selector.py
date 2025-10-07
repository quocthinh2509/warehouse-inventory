# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Set, Dict, List
import logging

from django.db import connections, DatabaseError

logger = logging.getLogger(__name__)

# ====== CONFIG ======
ECOM_DB_ALIAS   = "ecom_platform"  # alias trong settings.DATABASES
ECOM_SCHEMA     = "public"
ECOM_USER_TABLE = "user"           # đúng như ảnh

# role nào coi là manager (để lowercase)
MANAGER_ROLES = {"admin", "system admin"}

@dataclass(frozen=True)
class ExternalUser:
    id: int
    fullname: str
    role: str
    mail: str

def _table_ref() -> str:
    # "public"."user" (quote vì 'user' là từ khóa)
    return f'"{ECOM_SCHEMA}"."{ECOM_USER_TABLE}"'

def _quote_ident(name: str) -> str:
    """
    Quote identifier nếu có ký tự hoa hoặc không phải dạng safe (a-z0-9_).
    """
    safe = name.islower() and all(c.isalnum() or c == "_" for c in name)
    return name if safe else f'"{name}"'

def _list_columns() -> Set[str]:
    sql = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
    """
    with connections[ECOM_DB_ALIAS].cursor() as cur:
        cur.execute(sql, (ECOM_SCHEMA, ECOM_USER_TABLE))
        return {r[0] for r in cur.fetchall()}

def _pick(colnames: Set[str], candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in colnames:
            return c
    return None

# ========= SINGLE READ =========

def get_external_user(employee_id: int) -> Optional[ExternalUser]:
    """
    Đọc (id, fullname, role, mail) từ ecom-platform (public.user),
    tự dò tên cột phù hợp (fullname vs "FullName", role vs "Role", id vs "Id"/"ID", mail vs email/Gmail...).
    """
    try:
        cols = _list_columns()

        id_col       = _pick(cols, ["id", "Id", "ID"])
        fullname_col = _pick(cols, ["fullname", "FullName", "full_name", "Full_Name", "name", "Name"])
        role_col     = _pick(cols, ["role", "Role"])
        mail_col     = _pick(cols, ["email", "Email", "EMAIL", "mail", "Mail", "MAIL", "gmail", "Gmail", "GMAIL", "user_email", "UserEmail", "userMail"])

        if not id_col:
            logger.error("Cannot resolve ID column in external user table.")
            return None

        if not fullname_col:
            logger.warning("Fullname column not found, default to first available column.")
            fullname_col = "fullname" if "fullname" in cols else next(iter(cols))

        if not role_col:
            logger.warning("Role column not found, default to first available column.")
            role_col = "role" if "role" in cols else next(iter(cols))

        if not mail_col:
            logger.warning("Mail column not found, default to first available column.")
            mail_col = "email" if "email" in cols else next(iter(cols))

        q_id       = _quote_ident(id_col)
        q_fullname = _quote_ident(fullname_col)
        q_role     = _quote_ident(role_col)
        q_mail     = _quote_ident(mail_col)

        sql = f"""
            SELECT {q_id} AS id, {q_fullname} AS fullname, {q_role} AS role, {q_mail} AS mail
            FROM {_table_ref()}
            WHERE {q_id} = %s
            LIMIT 1
        """
        with connections[ECOM_DB_ALIAS].cursor() as cur:
            cur.execute(sql, (employee_id,))
            row = cur.fetchone()
            if not row:
                return None
            _id, fullname, role, mail = row
            return ExternalUser(
                id=int(_id),
                fullname=str(fullname or ""),
                role=str(role or ""),
                mail=str(mail or ""),
            )
    except DatabaseError as e:
        logger.exception("Query external user failed: %s", e)
        return None

def get_employee_role(employee_id: int) -> Optional[str]:
    u = get_external_user(employee_id)
    if not u or not u.role:
        return None
    return u.role.strip().lower()

def get_employee_fullname(employee_id: int) -> Optional[str]:
    u = get_external_user(employee_id)
    return u.fullname if u else None

def get_employee_email(employee_id: int) -> Optional[str]:
    """
    Lấy email (mail) của user theo employee_id.
    """
    u = get_external_user(employee_id)
    mail = (u.mail or "").strip() if u else ""
    return mail or None

def is_employee_manager(employee_id: int) -> bool:
    role = get_employee_role(employee_id)
    return bool(role and role in MANAGER_ROLES)

# ========= BATCH READ =========

def get_external_users_map(employee_ids: List[int]) -> Dict[int, ExternalUser]:
    """
    Trả về dict {employee_id: ExternalUser}. Bỏ qua id không tồn tại.
    Tối ưu 1 query thay vì gọi get_external_user() N lần.
    """
    ids = [int(i) for i in set(employee_ids or []) if str(i).isdigit()]
    if not ids:
        return {}

    try:
        cols = _list_columns()
        id_col       = _pick(cols, ["id", "Id", "ID"]) or "id"
        fullname_col = _pick(cols, ["fullname", "FullName", "full_name", "Full_Name", "name", "Name"]) or "fullname"
        role_col     = _pick(cols, ["role", "Role"]) or "role"
        mail_col     = _pick(cols, ["email", "Email", "EMAIL", "mail", "Mail", "MAIL", "gmail", "Gmail", "GMAIL", "user_email", "UserEmail", "userMail"]) or "email"

        q_id       = _quote_ident(id_col)
        q_fullname = _quote_ident(fullname_col)
        q_role     = _quote_ident(role_col)
        q_mail     = _quote_ident(mail_col)

        placeholders = ",".join(["%s"] * len(ids))
        sql = f"""
            SELECT {q_id} AS id, {q_fullname} AS fullname, {q_role} AS role, {q_mail} AS mail
            FROM {_table_ref()}
            WHERE {q_id} IN ({placeholders})
        """

        out: Dict[int, ExternalUser] = {}
        with connections[ECOM_DB_ALIAS].cursor() as cur:
            cur.execute(sql, tuple(ids))
            for row in cur.fetchall():
                _id, fullname, role, mail = row
                out[int(_id)] = ExternalUser(
                    id=int(_id),
                    fullname=str(fullname or ""),
                    role=str(role or ""),
                    mail=str(mail or ""),
                )
        return out
    except DatabaseError as e:
        logger.warning("Batch external user query failed: %s", e)
        return {}
