from backend.constants import RASIO_OPTIONS
from backend.whatsapp_service import send_text
from backend.messages import MSG_INVALID_RASIO, MSG_RESOLUSI


async def handle_waiting_rasio(sender_number: str, incoming_msg: str, user_state: dict) -> dict:
    """Validate aspect ratio selection and transition to resolution choice."""
    if incoming_msg not in RASIO_OPTIONS:
        await send_text(sender_number, MSG_INVALID_RASIO)
        return {"status": "invalid_rasio"}

    rasio_data = RASIO_OPTIONS[incoming_msg]
    user_state["rasio"] = rasio_data["label"]
    user_state["rasio_desc"] = rasio_data["desc"]
    user_state["step"] = "waiting_resolusi"

    await send_text(
        sender_number,
        MSG_RESOLUSI.format(rasio=rasio_data["label"], desc_rasio=rasio_data["desc"])
    )
    return {"status": "resolusi_asked"}
