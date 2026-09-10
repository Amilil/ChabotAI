from collections import deque

user_states = {}
user_locks = {}
user_timeout_tasks = {}

processed_queue: deque[str] = deque(maxlen=1000)
processed_set: set[str] = set()


def add_processed(msg_id: str) -> bool:
    if msg_id in processed_set:
        return False

    if len(processed_queue) == processed_queue.maxlen:
        oldest = processed_queue.popleft()
        processed_set.discard(oldest)

    processed_queue.append(msg_id)
    processed_set.add(msg_id)

    return True


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
