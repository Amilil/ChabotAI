import asyncio

from backend.constants import SESSION_TIMEOUT
from backend.messages import MSG_SESSION_TIMEOUT
from backend.whatsapp_service import send_text
from backend.services.session_service import user_states, user_timeout_tasks


def cancel_timeout(sender_number: str) -> None:
    """Cancel the timeout task for a user if one exists."""
    task = user_timeout_tasks.pop(sender_number, None)
    if task and not task.done():
        task.cancel()


async def _timeout_worker(sender_number: str) -> None:
    """Wait for SESSION_TIMEOUT then reset the user state if still idle."""
    try:
        await asyncio.sleep(SESSION_TIMEOUT)
    except asyncio.CancelledError:
        return

    state = user_states.get(sender_number)
    if state and state.get("step") != "generating":
        print(f"[TIMEOUT] Reset sesi user {sender_number} karena idle {SESSION_TIMEOUT}s")
        user_states.pop(sender_number, None)
        user_timeout_tasks.pop(sender_number, None)
        await send_text(sender_number, MSG_SESSION_TIMEOUT)


def reset_timeout(sender_number: str) -> None:
    """Cancel any existing timeout and start a fresh one for the user."""
    cancel_timeout(sender_number)
    task = asyncio.create_task(_timeout_worker(sender_number))
    user_timeout_tasks[sender_number] = task
