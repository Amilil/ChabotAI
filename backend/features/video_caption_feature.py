import asyncio
import backend.ai_services as ai_services
from backend.google_drive_service import upload_file_to_drive
from backend.whatsapp_service import send_text
from backend.services.session_service import user_states
from backend.services.timeout_service import reset_timeout
from backend.handlers.error_handler import handle_ai_error
from backend.messages import MSG_FEATURE_WIP, MSG_ERROR_UPLOAD


async def handle_video_caption_generation(sender_number: str, prompt: str, rasio: str, resolusi: str) -> dict:
    """Generate video and caption, upload video to Drive, and present caption for revision."""
    await send_text(sender_number, f"🎬✏️ Membuat video dan caption... ({rasio} / {resolusi})")
    try:
        result = await ai_services.generate_video_with_caption(prompt, rasio=rasio, resolusi=resolusi)
    except Exception as e:
        return await handle_ai_error(sender_number, e)

    if not result:
        await send_text(sender_number, MSG_FEATURE_WIP.format(fitur="Video + Caption"))
        user_states[sender_number] = {"step": "waiting_prompt"}
        return {"status": "feature_wip"}

    print("[VIDEO] Generate success")

    try:
        drive_number = user_states[sender_number].get("drive_user_number", sender_number)
        drive_link = await asyncio.to_thread(upload_file_to_drive, result["video"], "video/mp4", drive_number)
    except Exception as e:
        print("DRIVE ERROR:", e)
        import traceback
        traceback.print_exc()
        await send_text(sender_number, MSG_ERROR_UPLOAD)
        user_states[sender_number] = {"step": "waiting_prompt"}
        return {"status": "drive_error"}

    print("[VIDEO] Upload Drive success")

    if result["caption"]:
        user_states[sender_number] = {
            "step": "waiting_caption_revision",
            "original_prompt": prompt,
            "last_caption": result["caption"]
        }
        reset_timeout(sender_number)
        full_msg = (
            f"✅ Video berhasil dibuat!\n\n"
            f"🔗 Link Video\n{drive_link}\n\n"
            f"📝 Caption\n{result['caption']}\n\n"
            f"---\n"
            f"Silakan ketik revisi caption jika ingin mengubah caption.\n"
            f"Ketik SELESAI jika sudah sesuai."
        )
    else:
        user_states[sender_number] = {"step": "waiting_prompt"}
        reset_timeout(sender_number)
        full_msg = (
            f"✅ Video berhasil dibuat!\n\n"
            f"🔗 Link Video\n{drive_link}\n\n"
            f"⚠️ Caption gagal dibuat.\n"
            f"Silakan pilih menu Caption jika ingin membuat caption secara terpisah."
        )

    await send_text(sender_number, full_msg)
    print("[WHATSAPP] Final response sent")
    return {"status": "video_caption_done"}
