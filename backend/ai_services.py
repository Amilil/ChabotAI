import asyncio
import httpx
import uuid
import os
import base64
import random
import time

import backend.config as config

from openai import AsyncOpenAI, APIConnectionError, APITimeoutError, APIStatusError, AuthenticationError, RateLimitError


TIMEOUT = httpx.Timeout(
    timeout=120.0,
    connect=20.0
)


_base = config.BASE_URL.rstrip("/")

# URL untuk OpenAI SDK (text)
if not _base.endswith("/v1"):
    OPENAI_BASE_URL = f"{_base}/v1"
else:
    OPENAI_BASE_URL = _base

RAW_BASE_URL = _base[:-3] if _base.endswith("/v1") else _base

print(f"[CONFIG] BASE_URL      : {config.BASE_URL}")
print(f"[CONFIG] OPENAI_BASE   : {OPENAI_BASE_URL}")
print(f"[CONFIG] RAW_BASE      : {RAW_BASE_URL}")


# ==========================================
# RATE LIMITER (in-memory token bucket)
# ==========================================

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


# ==========================================
# RETRY WITH EXPONENTIAL BACKOFF
# ==========================================

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


# ==========================================
# BUDGET GUARD
# ==========================================

class BudgetExceededError(Exception):
    """Raised saat API key melebihi budget harian — hentikan semua retry."""
    pass


def _raise_if_budget_exceeded(response: httpx.Response):
    """Cek apakah 429 disebabkan budget habis. Kalau iya, raise BudgetExceededError."""
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

# Client untuk text (OpenAI SDK) — LiteLLM
client_text = AsyncOpenAI(
    api_key=config.LOCAL_API_KEY,
    base_url=OPENAI_BASE_URL,
    timeout=TIMEOUT
)

# Client untuk Groq (OpenAI-compatible)
client_groq = AsyncOpenAI(
    api_key=config.GROQ_API_KEY or "",
    base_url="https://api.groq.com/openai/v1",
    timeout=TIMEOUT
)

# ==========================================
# MAPPING RASIO + RESOLUSI → SIZE
# ==========================================

RESOLUSI_BASE = {
    "480p": 480,
    "720p": 720,
}

# Resolusi maksimal yang diizinkan
RESOLUSI_MAX = "720p"
RESOLUSI_ALLOWED = {"480p", "720p"}

RASIO_MAP = {
    "1:1":  (1, 1),
    "9:16": (9, 16),
    "16:9": (16, 9),
    "3:4":  (3, 4),
    "4:3":  (4, 3),
    "4:5":  (4, 5),
    "5:4":  (5, 4),
    "3:2":  (3, 2),
    "2:3":  (2, 3),
    "21:9": (21, 9),
}

def get_size(rasio: str = "1:1", resolusi: str = "720p") -> str:
    # Clamp resolusi ke maksimal 720p
    if resolusi not in RESOLUSI_ALLOWED:
        resolusi = RESOLUSI_MAX
    base = RESOLUSI_BASE.get(resolusi, 720)
    w_ratio, h_ratio = RASIO_MAP.get(rasio, (1, 1))

    if w_ratio >= h_ratio:
        width  = base
        height = round(base * h_ratio / w_ratio)
    else:
        height = base
        width  = round(base * w_ratio / h_ratio)

    width  = (width  // 8) * 8
    height = (height // 8) * 8

    return f"{width}x{height}"


# ==========================================
# IMAGE SIZE — ukuran standar yang didukung model
# ==========================================

IMAGE_SIZE_MAP = {
    "1:1":  "1024x1024",
    "9:16": "768x1344",
    "16:9": "1344x768",
    "3:4":  "768x1024",
    "4:3":  "1024x768",
    "4:5":  "768x960",
    "5:4":  "960x768",
    "3:2":  "1152x768",
    "2:3":  "768x1152",
    "21:9": "1536x640",
}

def get_image_size(rasio: str) -> str:
    return IMAGE_SIZE_MAP.get(rasio, "1024x1024")


# ==========================================
# DOWNLOAD FILE
# ==========================================

def _write_file_sync(path: str, content: bytes):
    with open(path, "wb") as f:
        f.write(content)


async def download_file(url: str, extension: str):
    try:
        os.makedirs("generated", exist_ok=True)
    except OSError as e:
        print(f"[DOWNLOAD] Gagal buat folder 'generated': {e}")
        raise Exception(f"Gagal buat folder penyimpanan: {e}")

    filename = f"generated/{uuid.uuid4()}.{extension}"

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.get(url)
            response.raise_for_status()
            await asyncio.to_thread(_write_file_sync, filename, response.content)
        print(f"[DOWNLOAD] Berhasil simpan ke: {filename}")
        return filename

    except httpx.TimeoutException as e:
        print(f"[DOWNLOAD] Timeout: {e}")
        raise Exception("Download file timeout — server terlalu lambat merespons")

    except httpx.ConnectError as e:
        print(f"[DOWNLOAD] Tidak bisa koneksi ke {url}: {e}")
        raise Exception("Tidak bisa koneksi ke server untuk download file")

    except httpx.HTTPStatusError as e:
        print(f"[DOWNLOAD] HTTP error {e.response.status_code}: {e}")
        raise Exception(f"Download file gagal — server return HTTP {e.response.status_code}")

    except OSError as e:
        print(f"[DOWNLOAD] Gagal tulis file ke disk: {e}")
        raise Exception(f"Gagal simpan file ke disk: {e}")


# ==========================================
# TEXT
# ==========================================

async def generate_text(prompt: str) -> str:
    primary = (config.TEXT_PROVIDER or "litellm").lower()

    # Provider chain: primary → fallback
    providers = []
    if primary == "groq":
        if not config.GROQ_API_KEY:
            print("[TEXT] GROQ_API_KEY tidak dikonfigurasi, fallback ke LiteLLM")
        else:
            providers.append(("groq", client_groq, config.TEXT_MODEL))
        providers.append(("litellm", client_text, config.LITELLM_TEXT_MODEL))
    else:
        providers.append(("litellm", client_text, config.LITELLM_TEXT_MODEL))
        if config.GROQ_API_KEY:
            providers.append(("groq", client_groq, config.TEXT_MODEL))

    print("\n========== TEXT ==========")
    print("PRIMARY PROVIDER:", primary)
    print("PROMPT          :", prompt[:100], "..." if len(prompt) > 100 else "")

    last_error = None
    for pname, _client, _model in providers:
        print(f"[TEXT/{pname}] Mencoba provider (model: {_model})...")

        try:
            response = await _retry_with_backoff(
                lambda: asyncio.wait_for(
                    _client.chat.completions.create(
                        model=_model,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=1000,
                        temperature=0.7
                    ),
                    timeout=120
                ),
                max_retries=2,
                base_delay=2,
                label=f"TEXT/{pname}"
            )

        except asyncio.TimeoutError as e:
            print(f"[TEXT/{pname}] Timeout: {e}")
            last_error = Exception("AI text timeout — tidak ada respons dalam 120 detik")
            continue

        except AuthenticationError as e:
            print(f"[TEXT/{pname}] Authentication error: {e}")
            if pname == providers[-1][0]:
                raise Exception("API key tidak valid atau tidak punya akses ke model text")
            last_error = Exception(f"API key {pname} tidak valid")
            continue

        except RateLimitError as e:
            print(f"[TEXT/{pname}] Rate limit: {e}")
            last_error = Exception("Terlalu banyak request ke AI, coba lagi beberapa saat")
            continue

        except APITimeoutError as e:
            print(f"[TEXT/{pname}] API timeout: {e}")
            last_error = Exception("AI text timeout — server tidak merespons")
            continue

        except APIConnectionError as e:
            print(f"[TEXT/{pname}] Tidak bisa koneksi: {e}")
            last_error = Exception("Tidak bisa koneksi ke server AI — cek koneksi internet")
            continue

        except APIStatusError as e:
            status = e.status_code
            body = e.response.text[:300] if hasattr(e, 'response') else str(e)
            print(f"[TEXT/{pname}] API status error {status}: {body}")

            if status == 400:
                raise Exception("Request text tidak valid — coba prompt yang berbeda")
            elif status == 403:
                raise Exception("Request text di-block oleh content filter server")
            elif status == 404:
                raise Exception(f"Model text '{_model}' tidak ditemukan di server")
            elif status == 429:
                last_error = Exception("Rate limit server AI — coba lagi beberapa saat")
                continue
            elif status >= 500:
                last_error = Exception(f"Server AI sedang bermasalah (HTTP {status}) — coba lagi")
                continue
            else:
                raise Exception(f"AI text error HTTP {status}: {body}")

        except Exception as e:
            if "API key" in str(e):
                raise
            print(f"[TEXT/{pname}] Error tidak terduga: {type(e).__name__}: {e}")
            last_error = Exception(f"Error tidak terduga saat generate text: {type(e).__name__}: {e}")
            continue

        if not response.choices or not response.choices[0].message.content:
            print(f"[TEXT/{pname}] Respons kosong dari AI")
            last_error = Exception("AI mengembalikan respons kosong")
            continue

        result = response.choices[0].message.content.strip()
        if not result:
            print(f"[TEXT/{pname}] Teks kosong")
            last_error = Exception("AI mengembalikan teks kosong")
            continue

        print(f"\n========== SUCCESS ({pname}) ==========")
        print(result[:200])
        print("=============================")

        return result

    raise last_error or Exception("Semua provider text gagal")


# ==========================================
# IMAGE — Gemini (primary) + LiteLLM (fallback)
# ==========================================

async def _generate_image_gemini(prompt: str, rasio: str = "1:1") -> str:
    from google import genai
    from google.genai import types
    from google.genai.errors import ClientError, APIError
    import time

    if not config.GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY belum dikonfigurasi")

    size = get_image_size(rasio)

    print("\n========== IMAGE (Gemini) ==========")
    print("PROVIDER  : Gemini")
    print("MODEL     :", config.IMAGE_MODEL)
    print("PROMPT    :", prompt[:100])
    print("RASIO     :", rasio)

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    start_time = time.time()
    try:
        response = await _retry_with_backoff(
            lambda: client.aio.models.generate_content(
                model=config.IMAGE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["Image", "Text"],
                    image_config=types.ImageConfig(
                        aspect_ratio=rasio,
                    ),
                ),
            ),
            max_retries=3,
            base_delay=2,
            label="IMAGE/GEMINI"
        )
        elapsed = time.time() - start_time
        print(f"[IMAGE/GEMINI] Response Time: {elapsed:.2f}s")
        print(f"[IMAGE/GEMINI] HTTP Status: 200")

    except ClientError as e:
        elapsed = time.time() - start_time
        print(f"[IMAGE/GEMINI] Response Time: {elapsed:.2f}s")
        print(f"[IMAGE/GEMINI] HTTP Status: {e.code}")
        print(f"[IMAGE/GEMINI] Exception Type: ClientError")
        print(f"[IMAGE/GEMINI] Status: {e.status}")
        print(f"[IMAGE/GEMINI] Message: {e.message}")

        if e.code == 429:
            raise Exception("Kuota Gemini API hari ini sudah habis. Silakan coba lagi besok atau gunakan API key lain.")
        elif e.code == 401 or (e.status and "PERMISSION_DENIED" in str(e.status)):
            raise Exception("API key Gemini tidak valid atau belum memiliki akses.")
        elif e.code == 404:
            raise Exception("Model Gemini tidak ditemukan.")
        else:
            raise Exception(f"Gemini API error (HTTP {e.code}): {e.message or 'Unknown error'}")

    except APIError as e:
        elapsed = time.time() - start_time
        print(f"[IMAGE/GEMINI] Response Time: {elapsed:.2f}s")
        print(f"[IMAGE/GEMINI] HTTP Status: {e.code}")
        print(f"[IMAGE/GEMINI] Exception Type: APIError")
        print(f"[IMAGE/GEMINI] Message: {e.message}")
        raise Exception(f"Gemini API error: {e.message or 'Unknown error'}")

    except httpx.ConnectError as e:
        elapsed = time.time() - start_time
        print(f"[IMAGE/GEMINI] Response Time: {elapsed:.2f}s")
        print(f"[IMAGE/GEMINI] Exception Type: httpx.ConnectError")
        print(f"[IMAGE/GEMINI] Detail: {e}")
        raise Exception("Tidak dapat terhubung ke server Gemini. Periksa koneksi internet, firewall, VPN, atau proxy.")

    except (httpx.TimeoutException, asyncio.TimeoutError) as e:
        elapsed = time.time() - start_time
        print(f"[IMAGE/GEMINI] Response Time: {elapsed:.2f}s")
        print(f"[IMAGE/GEMINI] Exception Type: {type(e).__name__}")
        raise Exception("Request ke Gemini timeout.")

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[IMAGE/GEMINI] Response Time: {elapsed:.2f}s")
        print(f"[IMAGE/GEMINI] Exception Type: {type(e).__name__}")
        print(f"[IMAGE/GEMINI] Error: {e}")
        raise Exception(f"Gagal generate gambar lewat Gemini: {e}")

    if not response.candidates:
        print("[IMAGE/GEMINI] Tidak ada kandidat dalam respons")
        raise Exception("Gemini tidak mengembalikan kandidat gambar")

    image_bytes = None
    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type and part.inline_data.mime_type.startswith("image/"):
            image_bytes = part.inline_data.data
            break

    if not image_bytes:
        print("[IMAGE/GEMINI] Tidak ada inline_data gambar dalam respons")
        raise Exception("Gemini tidak mengembalikan data gambar")

    try:
        os.makedirs("generated", exist_ok=True)
    except OSError as e:
        print(f"[IMAGE/GEMINI] Gagal buat folder: {e}")
        raise Exception(f"Gagal buat folder penyimpanan: {e}")

    filename = f"generated/{uuid.uuid4()}.png"
    try:
        with open(filename, "wb") as f:
            f.write(image_bytes)
        print(f"[IMAGE/GEMINI] Berhasil simpan ke: {filename}")
        print("\n========== SUCCESS ==========")
        print(filename)
        print("=============================")
        return filename
    except OSError as e:
        print(f"[IMAGE/GEMINI] Gagal simpan file: {e}")
        raise Exception(f"Gagal simpan gambar ke disk: {e}")


# ==========================================
# IMAGE — Cloudflare Workers AI
# ==========================================

async def _generate_image_cloudflare(prompt: str, rasio: str = "1:1") -> str:
    import time

    if not config.CLOUDFLARE_API_TOKEN:
        raise Exception("CLOUDFLARE_API_TOKEN belum dikonfigurasi di .env")

    if not config.CLOUDFLARE_ACCOUNT_ID:
        raise Exception("CLOUDFLARE_ACCOUNT_ID belum dikonfigurasi di .env")

    model = config.CF_IMAGE_MODEL or "@cf/black-forest-labs/flux-1-schnell"
    account_id = config.CLOUDFLARE_ACCOUNT_ID
    endpoint = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"

    size_str = get_image_size(rasio)
    parts = size_str.split("x")
    width = int(parts[0]) if len(parts) == 2 else 1024
    height = int(parts[1]) if len(parts) == 2 else 1024

    print("\n========== IMAGE (Cloudflare) ==========")
    print("PROVIDER  : Cloudflare")
    print("MODEL     :", model)
    print("PROMPT    :", prompt[:100])
    print("RASIO     :", rasio)
    print("SIZE      :", size_str)

    start_time = time.time()

    async def _post():
        async with httpx.AsyncClient(timeout=120) as client:
            return await client.post(
                endpoint,   
                headers={
                    "Authorization": f"Bearer {config.CLOUDFLARE_API_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                }
            )

    try:
        response = await _retry_with_backoff(
            _post,
            max_retries=3,
            base_delay=2,
            label="IMAGE/CLOUDFLARE"
        )
        elapsed = time.time() - start_time
        print(f"[IMAGE/CLOUDFLARE] Response Time: {elapsed:.2f}s")
        print(f"[IMAGE/CLOUDFLARE] HTTP Status: {response.status_code}")

    except httpx.TimeoutException as e:
        elapsed = time.time() - start_time
        print(f"[IMAGE/CLOUDFLARE] Response Time: {elapsed:.2f}s")
        print(f"[IMAGE/CLOUDFLARE] Exception Type: httpx.TimeoutException")
        raise Exception("Request ke Cloudflare AI timeout — server terlalu lambat merespons")

    except httpx.ConnectError as e:
        elapsed = time.time() - start_time
        print(f"[IMAGE/CLOUDFLARE] Response Time: {elapsed:.2f}s")
        print(f"[IMAGE/CLOUDFLARE] Exception Type: httpx.ConnectError")
        raise Exception("Tidak dapat terhubung ke Cloudflare AI. Periksa koneksi internet, firewall, atau VPN.")

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[IMAGE/CLOUDFLARE] Response Time: {elapsed:.2f}s")
        print(f"[IMAGE/CLOUDFLARE] Exception Type: {type(e).__name__}")
        print(f"[IMAGE/CLOUDFLARE] Error: {e}")
        raise

    status = response.status_code

    content_type = response.headers.get("content-type", "")
    error_detail = ""
    if "json" in content_type:
        try:
            err_json = response.json()
            if err_json.get("errors"):
                error_detail = str(err_json["errors"])
            elif not err_json.get("success"):
                error_detail = str(err_json.get("errors", err_json))
        except Exception:
            pass
    if not error_detail:
        error_detail = response.text[:300]

    if status == 401:
        print(f"[IMAGE/CLOUDFLARE] HTTP Status: 401")
        print(f"[IMAGE/CLOUDFLARE] Response Body: {error_detail}")
        raise Exception("API token Cloudflare tidak valid — periksa CLOUDFLARE_API_TOKEN di .env")
    elif status == 403:
        print(f"[IMAGE/CLOUDFLARE] HTTP Status: 403")
        print(f"[IMAGE/CLOUDFLARE] Response Body: {error_detail}")
        raise Exception("API token Cloudflare tidak memiliki izin akses Workers AI")
    elif status == 404:
        print(f"[IMAGE/CLOUDFLARE] HTTP Status: 404")
        print(f"[IMAGE/CLOUDFLARE] Response Body: {error_detail}")
        raise Exception(f"Model '{model}' tidak ditemukan — atau Account ID salah")
    elif status == 408:
        print(f"[IMAGE/CLOUDFLARE] HTTP Status: 408")
        print(f"[IMAGE/CLOUDFLARE] Response Body: {error_detail}")
        raise Exception("Request timeout — Cloudflare AI tidak merespons tepat waktu")
    elif status == 429:
        print(f"[IMAGE/CLOUDFLARE] HTTP Status: 429")
        print(f"[IMAGE/CLOUDFLARE] Response Body: {error_detail}")
        raise Exception("Rate limit Cloudflare AI tercapai — coba lagi beberapa saat")
    elif status >= 500:
        print(f"[IMAGE/CLOUDFLARE] HTTP Status: {status}")
        print(f"[IMAGE/CLOUDFLARE] Response Body: {error_detail}")
        raise Exception(f"Server Cloudflare AI bermasalah (HTTP {status}) — coba lagi nanti")
    elif status != 200:
        print(f"[IMAGE/CLOUDFLARE] HTTP Status: {status}")
        print(f"[IMAGE/CLOUDFLARE] Response Body: {error_detail}")
        raise Exception(f"Cloudflare AI mengembalikan HTTP {status}")

    # Cloudflare Workers AI returns Base64 in JSON, not raw binary
    try:
        body = response.json()
    except Exception as e:
        print(f"[IMAGE/CLOUDFLARE] Response is not valid JSON: {e}")
        print(f"[IMAGE/CLOUDFLARE] Body: {response.text[:400]}")
        raise Exception("Cloudflare AI mengembalikan data yang tidak valid")

    if "result" not in body:
        print(f"[IMAGE/CLOUDFLARE] Missing 'result' in response")
        print(f"[IMAGE/CLOUDFLARE] Body: {str(body)[:200]}")
        raise Exception("Format respons Cloudflare AI tidak valid")

    result = body["result"]

    if "image" not in result:
        print(f"[IMAGE/CLOUDFLARE] Missing 'image' in result")
        if error_detail:
            print(f"[IMAGE/CLOUDFLARE] error_detail: {error_detail}")
        raise Exception("Cloudflare AI tidak mengembalikan data gambar")

    image_b64 = result["image"]

    if not image_b64 or len(image_b64) < 100:
        print(f"[IMAGE/CLOUDFLARE] Base64 content too small or empty ({len(image_b64) if image_b64 else 0} chars)")
        raise Exception("Cloudflare AI mengembalikan Base64 yang tidak valid")

    try:
        image_bytes = base64.b64decode(image_b64)
    except Exception as e:
        print(f"[IMAGE/CLOUDFLARE] Base64 decode failed: {e}")
        raise Exception("Gagal mendekode data Base64 dari Cloudflare AI")

    if len(image_bytes) < 100:
        print(f"[IMAGE/CLOUDFLARE] Decoded image size too small ({len(image_bytes)} bytes)")
        raise Exception("Cloudflare AI tidak mengembalikan data gambar yang valid")

    try:
        os.makedirs("generated", exist_ok=True)
    except OSError as e:
        print(f"[IMAGE/CLOUDFLARE] Gagal buat folder: {e}")
        raise Exception(f"Gagal buat folder penyimpanan: {e}")

    filename = f"generated/{uuid.uuid4()}.png"
    try:
        with open(filename, "wb") as f:
            f.write(image_bytes)
        print(f"[IMAGE/CLOUDFLARE] Berhasil simpan ke: {filename}")
        print("\n========== SUCCESS ==========")
        print(filename)
        print("=============================")
        return filename
    except OSError as e:
        print(f"[IMAGE/CLOUDFLARE] Gagal simpan file: {e}")
        raise Exception(f"Gagal simpan gambar ke disk: {e}")


async def generate_image(prompt: str, rasio: str = "1:1", resolusi: str = "720p"):
    provider = (config.IMAGE_PROVIDER or "litellm").lower()

    if provider == "cloudflare":
        return await _generate_image_cloudflare(prompt, rasio=rasio)

    if provider == "gemini":
        return await _generate_image_gemini(prompt, rasio=rasio)

    # LiteLLM fallback — unchanged
    size = get_image_size(rasio)

    print("\n========== IMAGE ==========")
    print("MODEL    :", config.IMAGE_MODEL)
    print("PROMPT   :", prompt[:100])
    print("SIZE     :", size)

    endpoint = f"{RAW_BASE_URL}/v1/images/generations"
    print("ENDPOINT :", endpoint)

    async def _post_image():
        async with httpx.AsyncClient(timeout=120) as c:
            return await c.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {config.LOCAL_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": config.IMAGE_MODEL,
                    "prompt": prompt,
                    "size": size
                }
            )

    try:
        response = await _retry_with_backoff(
            _post_image,
            max_retries=3,
            base_delay=2,
            label="IMAGE/LITELLM"
        )

    except httpx.TimeoutException as e:
        print(f"[IMAGE] Timeout: {e}")
        raise Exception("Generate gambar timeout — server tidak merespons dalam 120 detik")

    except httpx.ConnectError as e:
        print(f"[IMAGE] Tidak bisa koneksi: {e}")
        raise Exception("Tidak bisa koneksi ke server AI untuk generate gambar")

    except Exception as e:
        print(f"[IMAGE] Error tidak terduga saat request: {type(e).__name__}: {e}")
        raise Exception(f"Error tidak terduga saat generate gambar: {type(e).__name__}")

    print(f"[IMAGE] Status: {response.status_code}")
    print(f"[IMAGE] Body: {response.text[:300]}")

    status = response.status_code
    if status == 400:
        raise Exception(f"Ukuran gambar '{size}' tidak didukung model ini, atau prompt tidak valid")
    elif status == 401:
        raise Exception("API key tidak valid untuk generate gambar")
    elif status == 403:
        raise Exception("Request gambar di-block oleh content filter server")
    elif status == 404:
        raise Exception(f"Model image '{config.IMAGE_MODEL}' tidak ditemukan di server")
    elif status == 429:
        _raise_if_budget_exceeded(response)
        raise Exception("Rate limit server AI — coba lagi beberapa saat")
    elif status >= 500:
        raise Exception(f"Server AI bermasalah (HTTP {status}) saat generate gambar")
    elif status not in (200, 201):
        raise Exception(f"Server image return HTTP {status}")

    try:
        data = response.json()
    except Exception as e:
        print(f"[IMAGE] Respons bukan JSON valid: {e}")
        raise Exception("Respons server image tidak bisa dibaca — format tidak valid")

    if not data.get("data"):
        print("[IMAGE] data['data'] kosong")
        raise Exception("AI tidak menghasilkan gambar — respons kosong")

    image = data["data"][0]

    # Coba ambil dari URL
    image_url = image.get("url")
    if image_url:
        try:
            return await download_file(image_url, "png")
        except Exception as e:
            print(f"[IMAGE] Gagal download dari URL: {e}")
            raise Exception(f"Gambar dibuat tapi gagal didownload: {e}")

    # Coba ambil dari base64
    b64 = image.get("b64_json")
    if b64:
        try:
            os.makedirs("generated", exist_ok=True)
            filename = f"generated/{uuid.uuid4()}.png"
            with open(filename, "wb") as f:
                f.write(base64.b64decode(b64))
            print(f"[IMAGE] Berhasil decode b64 ke: {filename}")
            return filename
        except base64.binascii.Error as e:
            print(f"[IMAGE] Data base64 corrupt: {e}")
            raise Exception("Data gambar dari AI corrupt — coba generate ulang")
        except OSError as e:
            print(f"[IMAGE] Gagal simpan gambar: {e}")
            raise Exception(f"Gagal simpan gambar ke disk: {e}")

    print("[IMAGE] Tidak ada url maupun b64_json dalam respons")
    raise Exception("Format respons gambar dari AI tidak dikenal")


# ==========================================
# VIDEO
# ==========================================

async def _generate_video_vertex(prompt: str, rasio: str = "1:1", resolusi: str = "720p") -> str:
    from backend.video.vertex_provider import generate_video_vertex as _vertex_gen
    return await _vertex_gen(prompt, rasio=rasio, resolusi=resolusi)


async def _post_video(client: httpx.AsyncClient, prompt: str, size: str) -> httpx.Response:
    """Helper: kirim satu request POST video ke LiteLLM."""
    return await client.post(
        f"{RAW_BASE_URL}/v1/videos",
        headers={
            "Authorization": f"Bearer {config.LOCAL_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": config.VIDEO_MODEL,
            "prompt": prompt,
            "size": size
        }
    )


def _extract_video_url(data: dict) -> str | None:
    """Coba ambil URL video dari berbagai format respons."""
    # Format standar: {"data": [{"url": "..."}]}
    items = data.get("data") or []
    if items:
        return items[0].get("url") or items[0].get("video_url")

    # Format alternatif langsung di root
    return data.get("url") or data.get("video_url")


async def generate_video(prompt: str, rasio: str = "1:1", resolusi: str = "720p"):
    provider = (config.VIDEO_PROVIDER or "litellm").lower()

    if provider == "vertex":
        return await _generate_video_vertex(prompt, rasio=rasio, resolusi=resolusi)

    size = get_size(rasio, resolusi)

    print("\n========== VIDEO ==========")
    print("MODEL    :", config.VIDEO_MODEL)
    print("PROMPT   :", prompt[:100])
    print("SIZE     :", size)
    print("ENDPOINT :", f"{RAW_BASE_URL}/v1/videos")

    # ── TAHAP 1: Request awal dengan timeout panjang ──
    # LiteLLM kadang blocking sampai video selesai (bisa 3-8 menit)
    # Timeout 720 detik = 12 menit
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(720.0, connect=20.0)) as client:
            print("[VIDEO] Mengirim request... (bisa memakan waktu beberapa menit)")
            response = await _post_video(client, prompt, size)

    except httpx.TimeoutException:
        print("[VIDEO] Request pertama timeout 720 detik")
        raise Exception("Generate video timeout — proses terlalu lama (>12 menit)")

    except httpx.ConnectError as e:
        print(f"[VIDEO] Tidak bisa koneksi: {e}")
        raise Exception("Tidak bisa koneksi ke server AI untuk generate video")

    except Exception as e:
        print(f"[VIDEO] Error tidak terduga: {type(e).__name__}: {e}")
        raise Exception(f"Error tidak terduga saat generate video: {type(e).__name__}")

    print(f"[VIDEO] Status: {response.status_code}")
    print(f"[VIDEO] Body: {response.text[:600]}")

    # ── Validasi status HTTP ──
    status = response.status_code
    if status == 400:
        raise Exception(f"Parameter video tidak valid — ukuran '{size}' mungkin tidak didukung")
    elif status in (401, 403):
        raise Exception("API key tidak valid atau request video di-block oleh server")
    elif status == 404:
        raise Exception(f"Endpoint video atau model '{config.VIDEO_MODEL}' tidak ditemukan")
    elif status == 429:
        _raise_if_budget_exceeded(response)
        raise Exception("Rate limit server AI — coba generate video lagi nanti")
    elif status >= 500:
        raise Exception(f"Server AI bermasalah (HTTP {status}) saat generate video")
    elif status not in (200, 201):
        raise Exception(f"Server video return HTTP {status}")

    try:
        data = response.json()
    except Exception:
        raise Exception("Respons server video tidak bisa dibaca — format tidak valid")

    # ── TAHAP 2: Cek URL langsung di respons pertama ──
    video_url = _extract_video_url(data)
    if video_url:
        print(f"[VIDEO] URL langsung ditemukan: {video_url[:80]}")
        try:
            return await download_file(video_url, "mp4")
        except Exception as e:
            raise Exception(f"Video dibuat tapi gagal didownload: {e}")

    # ── TAHAP 3: Respons async job — LiteLLM return {id, status} tanpa URL ──
    # Karena polling via GET /v1/videos/{id} tidak bisa (key restriction),
    # strategi: kirim ulang request POST yang sama, LiteLLM akan
    # deduplicate / queue dan akhirnya return URL saat video selesai.
    job_id  = data.get("id", "")
    job_status = (data.get("status") or "").lower()

    print(f"[VIDEO] Async job detected — id: {job_id[:40]}... status: '{job_status}'")
    print("[VIDEO] Mulai retry loop (kirim ulang POST tiap 30 detik)...")

    max_retries   = 5     # Maksimal 5x retry (hemat biaya)
    retry_interval = 60   # Jeda 60 detik per retry (total max ~5 menit)

    for attempt in range(1, max_retries + 1):
        print(f"[VIDEO] Retry {attempt}/{max_retries} — tunggu {retry_interval} detik...")
        await asyncio.sleep(retry_interval)

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=20.0)) as rc:
                retry_resp = await _post_video(rc, prompt, size)
        except httpx.TimeoutException:
            print(f"[VIDEO] Retry {attempt} timeout, lanjut...")
            continue
        except Exception as e:
            print(f"[VIDEO] Retry {attempt} error: {e}")
            continue

        print(f"[VIDEO] Retry {attempt} status: {retry_resp.status_code}")
        print(f"[VIDEO] Retry {attempt} body: {retry_resp.text[:400]}")

        if retry_resp.status_code not in (200, 201):
            # Cek budget dulu — kalau budget habis, stop total, jangan retry lagi
            if retry_resp.status_code == 429:
                _raise_if_budget_exceeded(retry_resp)
            print(f"[VIDEO] Retry {attempt} HTTP {retry_resp.status_code}, skip")
            continue

        try:
            retry_data = retry_resp.json()
        except Exception:
            print(f"[VIDEO] Retry {attempt} respons bukan JSON, skip")
            continue

        video_url = _extract_video_url(retry_data)
        if video_url:
            print(f"[VIDEO] URL ditemukan di retry {attempt}: {video_url[:80]}")
            try:
                return await download_file(video_url, "mp4")
            except Exception as e:
                raise Exception(f"Video dibuat tapi gagal didownload: {e}")

        # Cek apakah ada error eksplisit
        retry_status = (retry_data.get("status") or "").lower()
        if retry_status in ("failed", "error", "cancelled"):
            err_msg = retry_data.get("error") or retry_data.get("message") or "tidak diketahui"
            raise Exception(f"Server AI gagal generate video: {err_msg}")

        print(f"[VIDEO] Retry {attempt} — video belum selesai (status: '{retry_status}'), lanjut polling...")

    raise Exception(f"Video timeout setelah {max_retries} retry — server tidak kunjung selesai")


# ==========================================
# IMAGE + CAPTION
# ==========================================

async def generate_image_with_caption(prompt: str, rasio: str = "1:1", resolusi: str = "720p"):
    image = await generate_image(prompt, rasio=rasio, resolusi=resolusi)

    if not image:
        return None

    caption = await generate_text(
        f"Create a professional, engaging social media caption (max 3 sentences) in Indonesian language for: {prompt}"
    )

    return {
        "image": image,
        "caption": caption
    }


# ==========================================
# VIDEO + CAPTION
# ==========================================

async def generate_video_with_caption(prompt: str, rasio: str = "1:1", resolusi: str = "720p"):
    video = await generate_video(prompt, rasio=rasio, resolusi=resolusi)

    if not video:
        return None

    print("[CAPTION] Start")
    try:
        caption = await generate_text(
            f"Create a professional, engaging social media caption (max 3 sentences) in Indonesian language for: {prompt}"
        )
        print("[CAPTION] Success")
    except Exception as e:
        print(f"[CAPTION] Failed: {e}")
        caption = None

    return {
        "video": video,
        "caption": caption
    }
