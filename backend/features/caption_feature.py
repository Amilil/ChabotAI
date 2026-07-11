import backend.ai_services as ai_services
from backend.services.session_service import user_states
from backend.whatsapp_service import send_text
from backend.handlers.error_handler import handle_ai_error
from backend.messages import MSG_CAPTION_REVISION


async def handle_caption_generation(sender_number: str, prompt: str) -> dict:
    """Generate a caption and transition to revision state."""
    user_state = user_states[sender_number]
    user_state["step"] = "generating"

    await send_text(sender_number, "✏️ Membuat caption...")
    try:
        caption = await ai_services.generate_text(
            f"Create a professional, engaging social media caption (max 3 sentences) in Indonesian language for: {prompt}"
        )
    except Exception as e:
        return await handle_ai_error(sender_number, e)

    user_states[sender_number] = {
        "step": "waiting_caption_revision",
        "original_prompt": prompt,
        "last_caption": caption
    }
    await send_text(sender_number, MSG_CAPTION_REVISION.format(caption=caption))
    return {"status": "caption_done"}
