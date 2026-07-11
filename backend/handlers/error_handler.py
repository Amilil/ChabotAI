from backend.services.session_service import user_states
from backend.services.timeout_service import cancel_timeout, reset_timeout
from backend.whatsapp_service import send_text
from backend.messages import MSG_ERROR_BUDGET, MSG_ERROR_CONTENT_FILTER, MSG_ERROR_GENERAL
from backend.ai_services import BudgetExceededError


async def handle_ai_error(sender_number: str, e: Exception) -> dict:
    if isinstance(e, BudgetExceededError):
        print(f"[BUDGET ERROR] {e}")
        await send_text(sender_number, MSG_ERROR_BUDGET)
        cancel_timeout(sender_number)
    elif "di-block" in str(e).lower() or "content filter" in str(e).lower() or "blocked" in str(e).lower():
        print(f"[CONTENT FILTER] {e}")
        await send_text(sender_number, MSG_ERROR_CONTENT_FILTER)
    else:
        print("AI ERROR:", e)
        await send_text(sender_number, MSG_ERROR_GENERAL)
    user_states[sender_number] = {"step": "waiting_prompt"}
    reset_timeout(sender_number)
    return {"status": "ai_error"}
