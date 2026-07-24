import asyncio
import os
from backend.google_drive_service import upload_file_to_drive
from backend.whatsapp_service import send_text
from backend.services.session_service import user_states
from backend.messages import MSG_ERROR_UPLOAD


async def upload_to_drive(sender_number: str, file_path: str, mime_type: str) -> str | None:
    try:
        drive_number = user_states[sender_number].get("drive_user_number", sender_number)
        drive_link = await asyncio.to_thread(upload_file_to_drive, file_path, mime_type, drive_number)

        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"[CLEANUP] Local file deleted: {file_path}")
        except OSError as e:
            print(f"[CLEANUP] Failed to delete {file_path}: {e}")

        return drive_link
    except Exception as e:
        print("DRIVE ERROR:", e)
        import traceback
        traceback.print_exc()
        await send_text(sender_number, MSG_ERROR_UPLOAD)
        user_states[sender_number] = {"step": "waiting_prompt"}
        return None
