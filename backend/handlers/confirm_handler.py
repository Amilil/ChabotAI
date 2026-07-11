from backend.services.session_service import user_states
from backend.services.timeout_service import cancel_timeout
from backend.whatsapp_service import send_text
from backend.messages import MSG_CANCELLED


async def handle_waiting_konfirmasi(sender_number: str, incoming_msg: str, user_state: dict):
    if incoming_msg.lower() in ["batal", "tidak", "no"]:
        cancel_timeout(sender_number)
        user_states.pop(sender_number, None)
        await send_text(sender_number, MSG_CANCELLED)
        return {"status": "cancelled"}

    if incoming_msg.lower() not in ["ya", "yes", "iya"]:
        await send_text(sender_number, "Ketik YA untuk lanjut atau BATAL untuk membatalkan.")
        return {"status": "invalid_konfirmasi"}

    user_state["step"] = "generating"
    cancel_timeout(sender_number)
    return {
        "status": "confirmed",
        "prompt": user_state.get("prompt", ""),
        "menu": user_state.get("menu", ""),
        "rasio": user_state.get("rasio", "1:1"),
        "resolusi": user_state.get("resolusi", "720p"),
    }
