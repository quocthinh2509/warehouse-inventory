# erp_the20/services/local_gate_service.py
import json, time, hmac, hashlib, jwt
from typing import Dict, Optional
from django.conf import settings
from django.core.exceptions import ValidationError

# ===== Crypto helpers =====
def _canonical_json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()

def _hmac_hex(secret: str, payload: dict) -> str:
    return hmac.new(secret.encode(), _canonical_json_bytes(payload), hashlib.sha256).hexdigest()

# ===== Selectors (đơn giản: lấy agent config từ settings) =====
def get_agent_config(agent_code: str) -> Optional[Dict]:
    # Có thể đổi sang DB sau này nếu muốn (Agent model)
    agents = getattr(settings, "AGENTS", {})
    return agents.get(agent_code)

# ===== Core services =====
def verify_attestation_and_issue_token(attestation: dict, sig: str) -> str:
    """
    - Xác minh attestation từ Agent (HMAC + purpose + exp).
    - Nếu OK: trả về local_access_token (JWT TTL ngắn).
    """
    now = int(time.time())
    agent_code = attestation.get("agent_code")
    exp = int(attestation.get("exp", 0))
    purpose = attestation.get("purpose")

    if not agent_code or not sig:
        raise ValidationError("bad request")
    if exp < now:
        raise ValidationError("attestation expired")
    if purpose != "wifi_local_presence":
        raise ValidationError("wrong purpose")

    agent = get_agent_config(agent_code)
    if not agent:
        raise ValidationError("unknown agent")

    expected = _hmac_hex(agent["hmac_secret"], attestation)
    if not hmac.compare_digest(expected, sig):
        raise ValidationError("invalid signature")

    # (tuỳ chọn) chống replay bằng Redis: lưu nonce trong TTL ngắn

    payload = {
        "purpose": "local_gate",
        "agent_code": agent_code,
        "iat": now,
        "exp": now + int(getattr(settings, "LOCAL_ACCESS_TTL", 60)),
        # (tuỳ chọn) "client_ip": attestation.get("client_ip"),
        # (tuỳ chọn) "nonce": attestation.get("nonce"),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGO)
    return token

def require_local_access_token(token: str) -> Dict:
    """
    - Giải mã & kiểm tra local_access_token từ header X-Local-Access.
    - Trả claims (dict) nếu hợp lệ; ném ValidationError nếu không.
    """
    if not token:
        raise ValidationError("missing local access")

    try:
        data = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise ValidationError("local access expired")
    except jwt.InvalidTokenError:
        raise ValidationError("invalid token")

    if data.get("purpose") != "local_gate":
        raise ValidationError("wrong purpose")

    # (tuỳ chọn) validate agent_code mapping, CIDR, v.v. ở đây
    return data
