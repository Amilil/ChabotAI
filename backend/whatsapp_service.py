import httpx
import backend.config as config


def format_number(wa_id: str) -> str | None:
    """Normalize WhatsApp ID by appending @c.us suffix if needed."""
    if not wa_id:
        return None

    wa_id = str(wa_id).strip()

    if "@g.us" in wa_id:
        return wa_id
    if "@c.us" in wa_id:
        return wa_id
    if "@lid" in wa_id:
        return wa_id
    if wa_id.isdigit():
        return wa_id + "@c.us"

    return wa_id


async def send_text(to, text) -> dict | None:
    """Send a text message via WAHA API."""
    if not text:
        print("[WAHA] Empty text blocked")
        return None

    to = format_number(to)

    payload = {
        "session": config.WAHA_SESSION,
        "chatId": to,
        "text": text
    }

    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if config.WAHA_API_KEY:
        headers["X-Api-Key"] = config.WAHA_API_KEY

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                f"{config.WAHA_URL}/api/sendText",
                headers=headers,
                json=payload
            )

        print(f"\n=== SEND TEXT ===")
        print(f"STATUS: {res.status_code}")
        print(f"TO: {to}")
        print(f"TEXT: {text[:50]}...")

        # WAHA bisa return 200 atau 201, keduanya sukses
        if res.status_code not in [200, 201]:
            print("[WAHA ERROR SEND TEXT]", res.text)
            return None

        try:
            return res.json()
        except:
            return {"raw": res.text}

    except Exception as e:
        print("[SEND TEXT ERROR]", type(e).__name__, repr(e))
        return None


# ==========================================
# LID → Phone Number resolution
# ==========================================

async def resolve_lid(sender: str) -> str:
    """Resolve @lid to real phone number via WAHA API.

    Returns the real MSISDN (e.g. 62813xx@c.us) if sender is @lid,
    otherwise returns sender unchanged.

    Cache hit → immediate return.
    HTTP 500   → warm-up + retry once.
    All failures → fallback to original sender.
    """
    if "@lid" not in sender:
        return sender

    from backend.services.lid_cache import get_cached_phone, set_cached_phone

    cached = get_cached_phone(sender)
    if cached:
        print(f"[LID] Cache hit: {sender} → {cached}")
        return cached

    lid = sender.replace("@lid", "")
    url = f"{config.WAHA_URL}/api/{config.WAHA_SESSION}/lids/{lid}"

    print(f"[LID] Resolving: {sender}")

    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if config.WAHA_API_KEY:
        headers["X-Api-Key"] = config.WAHA_API_KEY

    async def _do_request() -> httpx.Response | None:
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                return await c.get(url, headers=headers)
        except Exception as e:
            print(f"[LID] Request error: {e}")
            return None

    resp = await _do_request()

    # ── HTTP 500: warm-up + retry sekali ──
    if resp and resp.status_code == 500:
        print("[LID] HTTP 500 — warmup + retry")
        try:
            warmup_url = f"{config.WAHA_URL}/api/{config.WAHA_SESSION}/lids?limit=1"
            async with httpx.AsyncClient(timeout=10) as c:
                await c.get(warmup_url, headers=headers)
        except Exception:
            pass
        resp = await _do_request()

    # ── Parse sukses ──
    if resp and resp.status_code == 200:
        try:
            body = resp.json()
            pn = body.get("pn")
            if pn:
                set_cached_phone(sender, pn)
                print(f"[LID] Resolved: {sender} → {pn}")
                return pn
        except Exception as e:
            print(f"[LID] Parse response gagal: {e}")

    # ── Fallback ──
    print(f"[LID] Fallback: gunakan sender asli ({sender})")
    return sender