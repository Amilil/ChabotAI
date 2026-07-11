user_states = {}
user_locks = {}
user_timeout_tasks = {}
processed_messages = set()


def get_msg_id(payload: dict) -> str:
    """Extract message ID from payload or generate a fallback from sender, timestamp, and body."""
    msg_id = (
        payload.get("id")
        or payload.get("messageId")
        or payload.get("_data", {}).get("id", {}).get("_serialized")
    )
    if not msg_id:
        sender = payload.get("from", "")
        body = payload.get("body") or payload.get("text") or ""
        timestamp = payload.get("timestamp", "")
        msg_id = f"{sender}_{timestamp}_{body[:30]}"
    return msg_id
