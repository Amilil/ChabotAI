# google_drive_service.py

import os
import pickle

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError


SCOPES = [
    "https://www.googleapis.com/auth/drive"
]

#route folder id
FOLDER_ID = "1SQD0yp8TNTePRNaEYSiDhFPUeP2w3T26"


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


def upload_file_to_drive(file_path, mime_type) -> str:
    """Upload a file to Google Drive and return a publicly shareable link."""

    import traceback

    print("[DRIVE] Upload started")
    print(f"[DRIVE] File path: {file_path}")
    print(f"[DRIVE] File exists: {os.path.exists(file_path)}")
    print(f"[DRIVE] File size: {os.path.getsize(file_path)} bytes")
    print(f"[DRIVE] MIME: {mime_type}")

    file_name = os.path.basename(file_path)

    file_metadata = {
        "name": file_name,
        "parents": [FOLDER_ID]
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
        ).execute()
    except Exception as e:
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
    return public_url