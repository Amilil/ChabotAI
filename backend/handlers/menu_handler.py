from backend.services.session_service import user_states
from backend.services.timeout_service import cancel_timeout
from backend.whatsapp_service import send_text
from backend.messages import MSG_INVALID_MENU, MSG_CANCELLED, MSG_RASIO
from backend.features.caption_feature import handle_caption_generation


async def handle_waiting_menu(sender_number: str, incoming_msg: str, user_state: dict):
    if incoming_msg not in ["0", "1", "2", "3", "4", "5"]:
        await send_text(sender_number, MSG_INVALID_MENU)
        return {"status": "invalid_menu"}

    if incoming_msg == "0":
        cancel_timeout(sender_number)
        user_states.pop(sender_number, None)
        await send_text(sender_number, MSG_CANCELLED)
        return {"status": "cancelled"}

    user_state["menu"] = incoming_msg

    if incoming_msg == "5":
        prompt = user_state.get("prompt", "")
        return await handle_caption_generation(sender_number, prompt)

    user_state["step"] = "waiting_rasio"
    await send_text(sender_number, MSG_RASIO)
    return {"status": "rasio_asked"}
