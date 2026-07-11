import asyncio
import backend.ai_services as ai_services
from backend.google_drive_service import upload_file_to_drive
from backend.whatsapp_service import send_text
from backend.services.session_service import user_states
from backend.services.timeout_service import reset_timeout
from backend.handlers.error_handler import handle_ai_error
from backend.messages import MSG_FEATURE_WIP, MSG_ERROR_UPLOAD, MSG_CAPTION_REVISION


async def handle_image_caption_generation(sender_number: str, prompt: str, rasio: str, resolusi: str) -> dict:
    await send_text(sender_number, f"🎨✏️ Membuat gambar dan caption... ({rasio} / {resolusi})")
    try:
        result = await ai_services.generate_image_with_caption(prompt, rasio=rasio, resolusi=resolusi)
    except Exception as e:
        return await handle_ai_error(sender_number, e)

    if not result:
        await send_text(sender_number, MSG_FEATURE_WIP.format(fitur="Gambar + Caption"))
        user_states[sender_number] = {"step": "waiting_prompt"}
        return {"status": "feature_wip"}

    try:
        drive_link = await asyncio.to_thread(upload_file_to_drive, result["image"], "image/png")
    except Exception as e:
        print("DRIVE ERROR:", e)
        await send_text(sender_number, MSG_ERROR_UPLOAD)
        user_states[sender_number] = {"step": "waiting_prompt"}
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
