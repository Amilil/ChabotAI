RASIO_OPTIONS = {
    "1":  {"label": "1:1",  "desc": "Square — Feed"},
    "2":  {"label": "9:16", "desc": "Portrait — Story/Reels"},
    "3":  {"label": "16:9", "desc": "Landscape — YouTube/Banner"},
    "4":  {"label": "3:4",  "desc": "Portrait — Feed"},
    "5":  {"label": "4:3",  "desc": "Landscape — Presentasi"},
    "6":  {"label": "4:5",  "desc": "Portrait — Feed Instagram"},
    "7":  {"label": "5:4",  "desc": "Landscape — Feed"},
    "8":  {"label": "3:2",  "desc": "Landscape — Foto"},
    "9":  {"label": "2:3",  "desc": "Portrait — Foto"},
    "10": {"label": "21:9", "desc": "Ultrawide — Cinematic"},
}

RESOLUSI_OPTIONS = {
    "1": {"label": "480p", "desc": "Cepat, ukuran kecil"},
    "2": {"label": "720p", "desc": "Standar, kualitas baik"},
}

SESSION_TIMEOUT = 120


# ==========================================
# SIZE MAPPING
# ==========================================

RESOLUSI_BASE = {
    "480p": 480,
    "720p": 720,
}

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


def get_size(rasio: str = "1:1", resolusi: str = "720p") -> str:
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


def get_image_size(rasio: str) -> str:
    return IMAGE_SIZE_MAP.get(rasio, "1024x1024")
