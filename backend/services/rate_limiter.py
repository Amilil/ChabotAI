import time


class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()

    def consume(self, tokens: int = 1) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


_user_buckets = {}

def check_rate_limit(user_id: str, max_requests: int = 3, window: int = 10) -> bool:
    if user_id not in _user_buckets:
        _user_buckets[user_id] = TokenBucket(max_requests / window, max_requests)
    return _user_buckets[user_id].consume()
