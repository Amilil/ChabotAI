from zoneinfo import ZoneInfo
from datetime import datetime


def now_wib():
    return datetime.now(ZoneInfo("Asia/Jakarta"))


def generate_timestamp():
    now = now_wib()
    return now.strftime("%Y%m%d_%H%M%S_") + f"{now.microsecond // 1000:03d}"


def generate_local_filename(extension: str) -> str:
    return f"generated/{generate_timestamp()}.{extension}"


def get_today_folder() -> str:
    return now_wib().strftime("%Y-%m-%d")
