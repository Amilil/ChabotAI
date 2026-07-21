import asyncio
import random
import httpx

from openai import AuthenticationError


class BudgetExceededError(Exception):
    pass


async def _retry_with_backoff(coro_factory, max_retries=3, base_delay=2, label="AI"):
    for attempt in range(1, max_retries + 1):
        try:
            return await coro_factory()
        except (AuthenticationError, BudgetExceededError) as e:
            raise
        except Exception as e:
            code = None
            if hasattr(e, 'status_code'):
                code = e.status_code
            elif hasattr(e, 'code'):
                code = e.code

            if code in (400, 401, 403, 404):
                raise

            if attempt == max_retries:
                raise

            delay = base_delay * (2 ** (attempt - 1)) * random.uniform(0.75, 1.25)
            print(f"[RETRY/{label}] Attempt {attempt}/{max_retries}" +
                  (f" HTTP {code}" if code else "") +
                  f": {type(e).__name__}. Retry in {delay:.1f}s...")
            await asyncio.sleep(delay)


def _raise_if_budget_exceeded(response: httpx.Response):
    if response.status_code != 429:
        return
    try:
        body = response.json()
        msg = body.get("error", {}).get("message", "")
    except Exception:
        msg = response.text

    if "budget" in msg.lower() or "exceededbudget" in msg.lower():
        print(f"[BUDGET] Budget harian habis: {msg}")
        raise BudgetExceededError(
            "⚠️ Budget API harian telah habis. Silakan hubungi admin untuk menaikkan limit."
        )
