import backend.ai_services as ai_services
from backend.whatsapp_service import send_text
from backend.services.session_service import user_states
from backend.services.timeout_service import reset_timeout
from backend.services.drive_helper import upload_to_drive
from backend.handlers.error_handler import handle_ai_error
from backend.messages import MSG_FEATURE_WIP, MSG_CAPTION_REVISION


async def handle_image_caption_generation(sender_number: str, prompt: str, rasio: str, resolusi: str) -> dict:
    """Generate image and caption, upload image to Drive, and present caption for revision."""
    await send_text(sender_number, f"🎨✏️ Membuat gambar dan caption... ({rasio} / {resolusi})")
    try:
        result = await ai_services.generate_image_with_caption(prompt, rasio=rasio, resolusi=resolusi)
    except Exception as e:
        return await handle_ai_error(sender_number, e)

    if not result:
        await send_text(sender_number, MSG_FEATURE_WIP.format(fitur="Gambar + Caption"))
        user_states[sender_number] = {"step": "waiting_prompt"}
        return {"status": "feature_wip"}

    drive_link = await upload_to_drive(sender_number, result["image"], "image/png")
    if drive_link is None:
        return {"status": "drive_error"}

    user_states[sender_number] = {
        "step": "waiting_caption_revision",
        "original_prompt": prompt,
        "last_caption": result["caption"]
    }
    reset_timeout(sender_number)
    await send_text(sender_number, f"✅ Gambar selesai! ({rasio} / {resolusi})\n{drive_link}")
    await send_text(sender_number, MSG_CAPTION_REVISION.format(caption=result["caption"]))
    return {"status": "image_caption_done"}
