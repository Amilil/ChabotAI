import time

LID_TTL = 86400

_cache = {}


def get_cached_phone(lid: str) -> str | None:
    entry = _cache.get(lid)
    if entry is None:
        return None
    if time.monotonic() > entry["expires_at"]:
        _cache.pop(lid, None)
        return None
    return entry["phone"]


def set_cached_phone(lid: str, phone: str) -> None:
    _cache[lid] = {
        "phone": phone,
        "expires_at": time.monotonic() + LID_TTL,
    }
