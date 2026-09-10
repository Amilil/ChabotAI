from fastapi import FastAPI, Request
import asyncio
import time
from backend.services.rate_limiter import check_rate_limit

from backend.whatsapp_service import send_text, resolve_lid
from backend.messages import MSG_RATE_LIMITED
from backend.services.session_service import user_states, user_locks, add_processed, get_msg_id
from backend.services.timeout_service import reset_timeout
from backend.handlers.prompt_handler import handle_global_commands, handle_new_user, handle_waiting_prompt
from backend.handlers.menu_handler import handle_waiting_menu
from backend.handlers.aspect_handler import handle_waiting_rasio
from backend.handlers.resolution_handler import handle_waiting_resolusi
from backend.handlers.confirm_handler import handle_waiting_konfirmasi
from backend.features.image_feature import handle_image_generation
from backend.features.video_feature import handle_video_generation
from backend.features.image_caption_feature import handle_image_caption_generation
from backend.features.video_caption_feature import handle_video_caption_generation
from backend.features.revision_feature import handle_caption_revision

app = FastAPI()

BOT_START_TIME = int(time.time())


async def handle_message(sender_number: str, incoming_msg: str):
    """Core message handler — runs inside per-user lock."""

    result = await handle_global_commands(sender_number, incoming_msg)
    if result:
        return result

    drive_user_number = await resolve_lid(sender_number)

    if sender_number not in user_states:
        result = await handle_new_user(sender_number)
        user_states[sender_number]["drive_user_number"] = drive_user_number
        return result

    user_states[sender_number]["drive_user_number"] = drive_user_number

    reset_timeout(sender_number)

    if not check_rate_limit(sender_number):
        await send_text(sender_number, MSG_RATE_LIMITED)
        return {"status": "rate_limited"}

    user_state = user_states[sender_number]
    print(f"STEP: {user_state['step']}")

    if user_state["step"] == "waiting_prompt":
        return await handle_waiting_prompt(sender_number, incoming_msg, user_state)

    if user_state["step"] == "waiting_menu":
        return await handle_waiting_menu(sender_number, incoming_msg, user_state)

    if user_state["step"] == "waiting_rasio":
        return await handle_waiting_rasio(sender_number, incoming_msg, user_state)

    if user_state["step"] == "waiting_resolusi":
        return await handle_waiting_resolusi(sender_number, incoming_msg, user_state)

    if user_state["step"] == "waiting_konfirmasi":
        result = await handle_waiting_konfirmasi(sender_number, incoming_msg, user_state)
        if result["status"] != "confirmed":
            return result

        prompt = result["prompt"]
        menu = result["menu"]
        rasio = result["rasio"]
        resolusi = result["resolusi"]

        if menu == "1":
            return await handle_image_generation(sender_number, prompt, rasio, resolusi)
        if menu == "2":
            return await handle_video_generation(sender_number, prompt, rasio, resolusi)
        if menu == "3":
            return await handle_image_caption_generation(sender_number, prompt, rasio, resolusi)
        if menu == "4":
            return await handle_video_caption_generation(sender_number, prompt, rasio, resolusi)

    if user_state["step"] == "waiting_caption_revision":
        return await handle_caption_revision(sender_number, incoming_msg, user_state)

    user_states[sender_number] = {"step": "waiting_prompt"}
    await send_text(
        sender_number,
        "⚠️ Terjadi kesalahan. Silakan mulai dari awal.\n\nKirim ide atau deskripsi konten Anda."
    )
    return {"status": "fallback_reset"}


# =====================================
# ROUTES
# =====================================

@app.get("/")
async def home() -> dict:
    """Health check endpoint."""
    return {"status": "online", "bot": "AI Content Generator"}


@app.post("/webhook")
async def whatsapp_webhook(request: Request) -> dict:
    """Receive WhatsApp webhook, validate payload, and dispatch to message handler."""

    print("WEBHOOK HIT")

    try:
        data = await request.json()

        payload = data.get("payload", {})

        # --- Anti duplikat ---
        msg_id = get_msg_id(payload)
        print("MSG ID:", msg_id)

        if not msg_id:
            return {"status": "ignored", "reason": "no_msg_id"}

        if not add_processed(msg_id):
            print("DUPLICATE DETECTED:", msg_id)
            return {"status": "duplicate"}

        # --- Filter event ---
        event = data.get("event")
        if event != "message":
            return {"status": "ignored", "reason": "not_message_event"}

        # --- Filter tipe pesan ---
        message_type = (payload.get("_data", {}) or {}).get("type")
        if message_type not in ["chat", "text"]:
            return {"status": "ignored", "reason": "unsupported_type"}

        # --- Filter pesan dari bot sendiri ---
        from_me = payload.get("fromMe", False)
        if from_me:
            return {"status": "ignored", "reason": "from_me"}

        # --- Filter pesan lama ---
        message_timestamp = payload.get("timestamp")
        if message_timestamp and int(message_timestamp) < BOT_START_TIME:
            print("SKIP OLD MESSAGE")
            return {"status": "ignored", "reason": "old_message"}

        # --- Filter grup ---
        sender_number = payload.get("from")
        if not sender_number:
            return {"status": "ignored", "reason": "no_sender"}
        if "@g.us" in sender_number:
            return {"status": "ignored", "reason": "group_message"}

        # --- Ambil isi pesan ---
        incoming_msg = (payload.get("body") or payload.get("text") or "").strip()
        if not incoming_msg:
            return {"status": "ignored", "reason": "empty_message"}

        print(f"DARI: {sender_number}")
        print(f"TEXT: {incoming_msg}")

        # --- Per-user lock: cegah race condition duplicate webhook ---
        if sender_number not in user_locks:
            user_locks[sender_number] = asyncio.Lock()

        if user_locks[sender_number].locked():
            print(f"SKIP: user {sender_number} sedang diproses")
            return {"status": "ignored", "reason": "user_locked"}

        async with user_locks[sender_number]:
            return await handle_message(sender_number, incoming_msg)

    except Exception as e:
        print(f"\nWEBHOOK ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": str(e)
        }


@app.post("/webhook-test")
async def webhook_test(request: Request):
    """Minimal webhook endpoint for testing - only prints payload to terminal."""
    data = await request.json()
    payload = data.get("payload", {})
    sender = payload.get("from", "unknown")
    text = (payload.get("body") or payload.get("text") or "").strip()
    print(f"\n=== WEBHOOK TEST RECEIVED ===")
    print(f"FROM: {sender}")
    print(f"TEXT: {text}")
    print(f"FULL PAYLOAD: {data}")
    print(f"=============================\n")
    return {"status": "received"}
