import hashlib
import hmac
from ipaddress import ip_address

from django.conf import settings


def _hmac(value: str, secret: str) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def hash_session_key(session_key: str) -> str:
    return _hmac(session_key, settings.SESSION_HASH_SECRET)


def get_client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
    candidate = forwarded or request.META.get("REMOTE_ADDR", "0.0.0.0")
    try:
        return str(ip_address(candidate))
    except ValueError:
        return "0.0.0.0"


def hash_client_ip(request) -> str:
    return _hmac(get_client_ip(request), settings.IP_HASH_SECRET)


def ensure_session_owner(request) -> str:
    if not request.session.session_key:
        request.session.create()
    return hash_session_key(request.session.session_key)
