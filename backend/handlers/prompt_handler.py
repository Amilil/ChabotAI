from backend.services.session_service import user_states
from backend.services.timeout_service import cancel_timeout, reset_timeout
from backend.whatsapp_service import send_text
from backend.messages import MSG_WELCOME, MSG_MENU


async def handle_global_commands(sender_number: str, incoming_msg: str):
    if incoming_msg.lower() in ["reset", "mulai", "restart", "/start"]:
        cancel_timeout(sender_number)
        user_states.pop(sender_number, None)
        await send_text(sender_number, MSG_WELCOME)
        return {"status": "reset"}

    if incoming_msg.lower() in ["help", "bantuan", "/help"]:
        reset_timeout(sender_number)
        await send_text(sender_number, MSG_WELCOME)
        return {"status": "help"}

    return None


async def handle_new_user(sender_number: str):
    user_states[sender_number] = {"step": "waiting_prompt"}
    reset_timeout(sender_number)
    await send_text(sender_number, MSG_WELCOME)
    return {"status": "welcome_sent"}


async def handle_waiting_prompt(sender_number: str, incoming_msg: str, user_state: dict):
    user_state["prompt"] = incoming_msg
    user_state["step"] = "waiting_menu"
    await send_text(sender_number, MSG_MENU.format(prompt=incoming_msg))
    return {"status": "menu_sent"}
