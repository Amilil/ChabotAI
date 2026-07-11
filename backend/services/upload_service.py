import os
import uuid
import httpx
import asyncio

from backend.google_drive_service import upload_file_to_drive


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


async def upload_to_drive(file_path: str, mime_type: str) -> str:
    return await asyncio.to_thread(upload_file_to_drive, file_path, mime_type)
