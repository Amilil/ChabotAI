from backend.constants import RESOLUSI_OPTIONS
from backend.whatsapp_service import send_text
from backend.messages import MSG_INVALID_RESOLUSI, MSG_KONFIRMASI_GENERATE


async def handle_waiting_resolusi(sender_number: str, incoming_msg: str, user_state: dict) -> dict:
    """Validate resolution selection and transition to confirmation."""
    if incoming_msg not in RESOLUSI_OPTIONS:
        await send_text(sender_number, MSG_INVALID_RESOLUSI)
        return {"status": "invalid_resolusi"}

    resolusi_data = RESOLUSI_OPTIONS[incoming_msg]
    user_state["resolusi"] = resolusi_data["label"]
    user_state["step"] = "waiting_konfirmasi"

    await send_text(
        sender_number,
        MSG_KONFIRMASI_GENERATE.format(
            prompt=user_state["prompt"],
            rasio=user_state["rasio"],
            desc_rasio=user_state["rasio_desc"],
            resolusi=resolusi_data["label"]
        )
    )
    return {"status": "konfirmasi_asked"}
