from dotenv import load_dotenv
import os

load_dotenv()

LOCAL_API_KEY = os.getenv("LOCAL_API_KEY")
BASE_URL = os.getenv("BASE_URL")

LITELLM_TEXT_MODEL = os.getenv("LITELLM_TEXT_MODEL")
TEXT_MODEL = os.getenv("TEXT_MODEL")
IMAGE_MODEL = os.getenv("IMAGE_MODEL")
VIDEO_MODEL = os.getenv("VIDEO_MODEL")

# === PROVIDER SELECTION ===
TEXT_PROVIDER = os.getenv("TEXT_PROVIDER", "litellm")
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "litellm")
VIDEO_PROVIDER = os.getenv("VIDEO_PROVIDER", "litellm")

# === GROQ ===
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# === GEMINI ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# === CLOUDFLARE WORKERS AI ===
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CF_IMAGE_MODEL = os.getenv("CF_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell")

# === GOOGLE VERTEX AI ===
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
VERTEX_MODEL = os.getenv("VERTEX_MODEL", "veo-2.0-generate-001")
VERTEX_OUTPUT_GCS_URI = os.getenv("VERTEX_OUTPUT_GCS_URI")

WAHA_URL = os.getenv("WAHA_URL")
WAHA_API_KEY = os.getenv("WAHA_API_KEY")
WAHA_SESSION = os.getenv("WAHA_SESSION")
