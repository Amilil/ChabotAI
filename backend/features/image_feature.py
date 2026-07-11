import asyncio
import backend.ai_services as ai_services
from backend.google_drive_service import upload_file_to_drive
from backend.whatsapp_service import send_text
from backend.services.session_service import user_states
from backend.services.timeout_service import reset_timeout
from backend.handlers.error_handler import handle_ai_error
from backend.messages import MSG_FEATURE_WIP, MSG_ERROR_UPLOAD


async def handle_image_generation(sender_number: str, prompt: str, rasio: str, resolusi: str) -> dict:
    await send_text(sender_number, f"🎨 Membuat gambar... ({rasio} / {resolusi})")
    try:
        image_result = await ai_services.generate_image(prompt, rasio=rasio, resolusi=resolusi)
    except Exception as e:
        return await handle_ai_error(sender_number, e)

    if not image_result:
        await send_text(sender_number, MSG_FEATURE_WIP.format(fitur="Gambar"))
        user_states[sender_number] = {"step": "waiting_prompt"}
        return {"status": "feature_wip"}

    try:
        drive_link = await asyncio.to_thread(upload_file_to_drive, image_result, "image/png")
    except Exception as e:
        print("DRIVE ERROR:", e)
        await send_text(sender_number, MSG_ERROR_UPLOAD)
        user_states[sender_number] = {"step": "waiting_prompt"}
        return {"status": "drive_error"}

    user_states[sender_number] = {"step": "waiting_prompt"}
    reset_timeout(sender_number)
    await send_text(
        sender_number,
        f"✅ Gambar berhasil dibuat!\nRasio: {rasio} | Resolusi: {resolusi}\n\n{drive_link}\n\nSilakan kirim ide baru untuk membuat konten berikutnya."
    )
    return {"status": "image_done"}
