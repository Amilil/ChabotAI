# google_drive_service.py

import os
import pickle

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
import threading
from backend.utils.file_naming import get_today_folder
import backend.config as config


SCOPES = [
    "https://www.googleapis.com/auth/drive"
]

FOLDER_ID = config.DRIVE_ROOT_FOLDER_ID

_cache = {}
_lock = threading.RLock()


def normalize_user_id(sender: str) -> str:
    if not sender:
        return "unknown"
    return sender.split("@")[0]


def get_drive_service():
    """Authenticate and return a Google Drive API service instance."""

    creds = None

    # LOAD TOKEN
    if os.path.exists("token.pickle"):

        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

    # LOGIN
    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                print("[Google Drive] Refresh token invalid. Starting OAuth login again...")
                if os.path.exists("token.pickle"):
                    os.remove("token.pickle")
                creds = None

        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json",
                SCOPES
            )

            creds = flow.run_local_server(port=0, prompt="consent")

        # SAVE TOKEN
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    service = build(
        "drive",
        "v3",
        credentials=creds
    )

    return service


drive_service = get_drive_service()



def _ensure_folder(logical_path: str) -> str:
    parts = logical_path.split("/")
    folder_name = parts[-1]

    with _lock:
        cached = _cache.get(logical_path)
        if cached:
            return cached

        if len(parts) == 1:
            parent_id = FOLDER_ID
        else:
            parent_id = _ensure_folder("/".join(parts[:-1]))

        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false and '{parent_id}' in parents"
        print(f"[GDRIVE-DEBUG] LIST {logical_path}")
        result = drive_service.files().list(q=query, spaces="drive", fields="files(id)").execute()
        files = result.get("files", [])

        if files:
            folder_id = files[0]["id"]
            print(f"[GDRIVE-DEBUG] FOUND {logical_path} → {folder_id}")
        else:
            print(f"[GDRIVE-DEBUG] CREATE {logical_path}")
            folder_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id]
            }
            created = drive_service.files().create(body=folder_metadata, fields="id").execute()
            folder_id = created.get("id")
            print(f"[GDRIVE-DEBUG] CREATED {logical_path} → {folder_id}")

        _cache[logical_path] = folder_id
        return folder_id


def upload_file_to_drive(file_path, mime_type, sender_number: str = "unknown") -> str:
    """Upload a file to Google Drive and return a publicly shareable link."""

    import traceback

    print("[DRIVE] Upload started")
    print(f"[DRIVE] File path: {file_path}")
    print(f"[DRIVE] File exists: {os.path.exists(file_path)}")
    print(f"[DRIVE] File size: {os.path.getsize(file_path)} bytes")
    print(f"[DRIVE] MIME: {mime_type}")

    file_name = os.path.basename(file_path)

    root_type = "Photo" if mime_type.startswith("image/") else "Video"
    date_str = get_today_folder()
    user_id = normalize_user_id(sender_number)
    logical_path = f"{user_id}/{date_str}/{root_type}"

    print(f"[GDRIVE] Folder   : {logical_path}")
    print(f"[GDRIVE] Filename : {file_name}")

    print(f"[GDRIVE-DEBUG] ENSURE {logical_path}")
    folder_id = _ensure_folder(logical_path)
    print(f"[GDRIVE-DEBUG] ENSURE_DONE {logical_path} → {folder_id}")

    file_metadata = {
        "name": file_name,
        "parents": [folder_id]
    }

    print("[DRIVE] Creating MediaFileUpload...")
    media = MediaFileUpload(
        file_path,
        mimetype=mime_type
    )

    print("[DRIVE] Calling files.create()...")
    try:
        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id"
        ).execute(num_retries=3)
    except Exception as e:
        status_code = None
        if hasattr(e, 'resp') and hasattr(e.resp, 'status'):
            status_code = e.resp.status

        if status_code == 404 or "not found" in str(e).lower():
            print("[GDRIVE][RECOVERY] Folder tidak ditemukan, recovery...")
            with _lock:
                _cache.pop(logical_path, None)
                _cache.pop(root_type, None)
            folder_id = _ensure_folder(logical_path)
            file_metadata["parents"] = [folder_id]
            media = MediaFileUpload(file_path, mimetype=mime_type)
            uploaded_file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id"
            ).execute(num_retries=3)
        else:
            print("[DRIVE][ERROR]")
            print(f"STEP: files.create()")
            print(f"TYPE: {type(e).__name__}")
            print(f"MESSAGE: {e}")
            print(f"REPR: {repr(e)}")
            print(f"TRACEBACK:")
            traceback.print_exc()
            raise

    file_id = uploaded_file.get("id")
    print(f"[DRIVE] files.create() success")
    print(f"[DRIVE] File ID: {file_id}")

    print("[DRIVE] Setting public permission...")
    try:
        drive_service.permissions().create(
            fileId=file_id,
            body={
                "role": "reader",
                "type": "anyone"
            }
        ).execute()
    except Exception as e:
        print("[DRIVE][ERROR]")
        print(f"STEP: permissions.create()")
        print(f"TYPE: {type(e).__name__}")
        print(f"MESSAGE: {e}")
        print(f"REPR: {repr(e)}")
        print(f"TRACEBACK:")
        traceback.print_exc()
        raise

    print("[DRIVE] Permission success")

    print("[DRIVE] Building share link...")
    public_url = f"https://drive.google.com/file/d/{file_id}/view"

    print("[DRIVE] Upload finished")
    print(f"[GDRIVE] Upload   : Success")
    return public_url