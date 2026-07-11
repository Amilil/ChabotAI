import backend.ai_services as ai_services
from backend.services.session_service import user_states
from backend.services.timeout_service import cancel_timeout
from backend.whatsapp_service import send_text
from backend.handlers.error_handler import handle_ai_error
from backend.messages import MSG_CAPTION_DONE, MSG_CAPTION_REVISED


async def handle_caption_revision(sender_number: str, incoming_msg: str, user_state: dict) -> dict:
    if incoming_msg.upper() == "SELESAI":
        cancel_timeout(sender_number)
        user_states[sender_number] = {"step": "waiting_prompt"}
        await send_text(sender_number, MSG_CAPTION_DONE)
        return {"status": "revision_finished"}

    await send_text(sender_number, "✏️ Merevisi caption...")

    try:
        new_caption = await ai_services.generate_text(
            f"""You are a professional copywriter. Write all output in Indonesian language.

Original topic: {user_state['original_prompt']}

Current caption:
{user_state['last_caption']}

Revision instruction: {incoming_msg}

Task: Revise the caption according to the instruction. Keep the original context, stay on topic. Output in Indonesian."""
        )
    except Exception as e:
        return await handle_ai_error(sender_number, e)

    user_state["last_caption"] = new_caption
    await send_text(sender_number, MSG_CAPTION_REVISED.format(caption=new_caption))
    return {"status": "caption_revised"}
