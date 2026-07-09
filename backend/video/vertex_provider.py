import os
import time
import uuid
import asyncio

import backend.config as config


POLL_INTERVAL = 20
POLL_TIMEOUT = 600


def _parse_gcs_uri(uri: str):
    """Parse gs://bucket-name/object/path into (bucket_name, object_path)."""
    if not uri or not uri.startswith("gs://"):
        raise ValueError(f"URI bukan GCS path yang valid: {uri}")
    parts = uri[5:].split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"URI GCS tidak memiliki object path: {uri}")
    return parts[0], parts[1]


async def _download_video(video_obj, local_path):
    """Download video dari GCS URI menggunakan google-cloud-storage."""
    from google.cloud import storage

    uri = getattr(video_obj, 'uri', None)
    if not uri:
        raise Exception("Objek video tidak memiliki field 'uri' — tidak bisa download dari GCS")

    bucket_name, object_path = _parse_gcs_uri(uri)

    print(f"[VERTEX/GCS] Bucket : {bucket_name}")
    print(f"[VERTEX/GCS] Object : {object_path}")

    try:
        gcs_client = await asyncio.to_thread(storage.Client)
        bucket = await asyncio.to_thread(gcs_client.bucket, bucket_name)
        blob = bucket.blob(object_path)
        await asyncio.to_thread(blob.download_to_filename, local_path)
    except Exception as e:
        err_str = str(e).lower()
        if "not found" in err_str or "nosuchkey" in err_str:
            raise Exception(
                f"File tidak ditemukan di GCS.\n"
                f"Bucket: {bucket_name}\n"
                f"Object: {object_path}\n\n"
                f"Kemungkinan objek sudah expired atau path salah.\n"
                f"Detail teknis: {e}"
            )
        elif "permission" in err_str or "denied" in err_str or "forbidden" in err_str or "403" in err_str:
            raise Exception(
                f"Tidak memiliki izin untuk membaca object dari GCS.\n"
                f"Bucket: {bucket_name}\n\n"
                "Pastikan service account memiliki role:\n"
                "• Storage Object Admin\n"
                "• Storage Legacy Object Reader\n\n"
                f"Detail teknis: {e}"
            )
        elif "bucket" in err_str and ("not found" in err_str or "does not exist" in err_str):
            raise Exception(
                f"Bucket GCS '{bucket_name}' tidak ditemukan.\n\n"
                "Pastikan:\n"
                "• Nama bucket benar\n"
                "• Bucket sudah dibuat di Google Cloud Storage\n"
                "• Service account memiliki akses ke bucket\n\n"
                f"Detail teknis: {e}"
            )
        elif "timeout" in err_str or "deadline" in err_str:
            raise Exception(
                f"Download dari GCS timeout.\n"
                f"Bucket: {bucket_name}\n"
                f"Object: {object_path}\n\n"
                f"Coba lagi — jaringan mungkin lambat.\n"
                f"Detail teknis: {e}"
            )
        else:
            raise Exception(
                f"Gagal download video dari GCS.\n"
                f"Bucket: {bucket_name}\n"
                f"Object: {object_path}\n"
                f"Local: {local_path}\n\n"
                f"Detail teknis: {type(e).__name__}: {e}"
            )

    if not os.path.isfile(local_path) or os.path.getsize(local_path) == 0:
        raise Exception(
            f"Download dari GCS selesai tapi file kosong atau tidak ditemukan.\n"
            f"Local: {local_path}"
        )

    print(f"[VERTEX/GCS] Download success — {os.path.getsize(local_path)} bytes")
    print(f"[VERTEX/GCS] Local path: {os.path.abspath(local_path)}")


async def generate_video_vertex(prompt: str, rasio: str = "1:1", resolusi: str = "720p") -> str:
    from google import genai
    from google.genai import types

    # ── validasi konfigurasi ──
    if not config.GOOGLE_CLOUD_PROJECT:
        raise Exception(
            "GOOGLE_CLOUD_PROJECT belum dikonfigurasi di .env. "
            "Isi dengan project ID Google Cloud Anda."
        )

    if not config.VERTEX_LOCATION:
        raise Exception(
            "VERTEX_LOCATION belum dikonfigurasi di .env. "
            "Contoh: us-central1"
        )

    if config.GOOGLE_APPLICATION_CREDENTIALS:
        cred_path = os.path.abspath(config.GOOGLE_APPLICATION_CREDENTIALS)
        if not os.path.isfile(cred_path):
            raise Exception(
                f"File credential tidak ditemukan di:\n{cred_path}\n\n"
                "Pastikan:\n"
                "• GOOGLE_APPLICATION_CREDENTIALS di .env mengarah ke file JSON yang valid\n"
                "• File service account JSON tersedia di path tersebut\n"
                "• Path menggunakan format yang benar (contoh: ./credentials/vertex.json)"
            )
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path

    # ── mapping aspek rasio ──
    valid_ratios = {"1:1", "9:16", "16:9", "3:4", "4:3", "4:5", "5:4", "3:2", "2:3", "21:9"}
    aspect_ratio = rasio if rasio in {"16:9", "9:16"} else "16:9"

    # ── logging header ──
    print("\n========== VIDEO (Vertex) ==========")
    print("PROVIDER  : Vertex AI")
    print("MODEL     :", config.VERTEX_MODEL)
    print("PROMPT    :", prompt[:100], "..." if len(prompt) > 100 else "")
    print("RASIO     :", rasio, f"(dipetakan ke {aspect_ratio})" if rasio != aspect_ratio else "")
    print("RESOLUSI  :", resolusi)
    print("PROJECT   :", config.GOOGLE_CLOUD_PROJECT)
    print("LOCATION  :", config.VERTEX_LOCATION)
    print("GCS URI   :", config.VERTEX_OUTPUT_GCS_URI or "(tidak diset — default SDK)")
    print("===================================")

    start_time = time.time()

    # ── init client ──
    try:
        client = await asyncio.to_thread(
            lambda: genai.Client(
                vertexai=True,
                project=config.GOOGLE_CLOUD_PROJECT,
                location=config.VERTEX_LOCATION,
            )
        )
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[VERTEX] Response Time: {elapsed:.2f}s")
        err_str = str(e).lower()

        if "credential" in err_str or "auth" in err_str or "not found" in err_str:
            raise Exception(
                "Gagal autentikasi ke Vertex AI.\n\n"
                "Kemungkinan penyebab:\n"
                "• File credential tidak valid atau tidak memiliki izin\n"
                "• Service account tidak memiliki akses ke Vertex AI\n"
                "• GOOGLE_CLOUD_PROJECT salah atau tidak memiliki Vertex AI API aktif\n\n"
                f"Detail teknis: {e}"
            )
        elif "project" in err_str and ("not found" in err_str or "invalid" in err_str):
            raise Exception(
                f"Google Cloud Project '{config.GOOGLE_CLOUD_PROJECT}' tidak ditemukan "
                f"atau tidak valid.\n\n"
                "Pastikan:\n"
                "• Project ID benar di GOOGLE_CLOUD_PROJECT\n"
                "• Project sudah memiliki API Vertex AI diaktifkan\n"
                "• Service account memiliki izin di project tersebut"
            )
        elif "permission" in err_str or "denied" in err_str or "forbidden" in err_str:
            raise Exception(
                "Service account tidak memiliki izin yang cukup.\n\n"
                "Pastikan service account memiliki role:\n"
                "• Vertex AI User\n"
                "• Storage Object Admin (untuk akses GCS bucket)"
            )
        else:
            raise Exception(
                f"Gagal inisialisasi Vertex AI client.\n\n"
                f"Detail teknis: {e}"
            )

    # ── kirim request generate video ──
    gen_config = types.GenerateVideosConfig(
        aspect_ratio=aspect_ratio,
        number_of_videos=1,
    )
    if config.VERTEX_OUTPUT_GCS_URI:
        gen_config.output_gcs_uri = config.VERTEX_OUTPUT_GCS_URI

    try:
        operation = await asyncio.to_thread(
            client.models.generate_videos,
            model=config.VERTEX_MODEL,
            source=types.GenerateVideosSource(prompt=prompt),
            config=gen_config,
        )
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[VERTEX] Response Time: {elapsed:.2f}s")
        err_str = str(e).lower()

        if "not found" in err_str or "404" in err_str:
            suspect = "project"
            if "location" in err_str or "region" in err_str:
                suspect = "location"
            elif "model" in err_str:
                suspect = "model"
            raise Exception(
                f"Resource {suspect} tidak ditemukan.\n\n"
                f"Periksa konfigurasi {suspect.upper()} di .env.\n"
                f"Detail teknis: {e}"
            )
        elif "permission" in err_str or "denied" in err_str or "forbidden" in err_str:
            raise Exception(
                "Service account tidak memiliki izin untuk generate video.\n\n"
                "Pastikan service account memiliki role:\n"
                "• Vertex AI User\n"
                "• Izin untuk menggunakan model Veo 2.0"
            )
        elif "exhausted" in err_str or "quota" in err_str or "429" in err_str or "rate" in err_str:
            raise Exception(
                "Kuota Vertex AI telah habis atau rate limit tercapai.\n\n"
                "Coba lagi nanti atau tingkatkan kuota di:\n"
                "https://console.cloud.google.com/vertex-ai/quotas"
            )
        elif "timeout" in err_str or "deadline" in err_str:
            raise Exception(
                "Request ke Vertex AI timeout — server terlalu sibuk.\n"
                "Coba lagi beberapa saat."
            )
        elif "bucket" in err_str or "storage" in err_str:
            raise Exception(
                f"Bucket GCS tidak valid atau tidak dapat diakses.\n\n"
                f"Periksa VERTEX_OUTPUT_GCS_URI di .env:\n"
                f"  {config.VERTEX_OUTPUT_GCS_URI}\n\n"
                "Pastikan:\n"
                "• Bucket sudah dibuat\n"
                "• Service account memiliki izin Storage Object Admin\n"
                "• Nama bucket benar (gs://nama-bucket/prefix)"
            )
        else:
            raise Exception(
                f"Gagal memulai generate video di Vertex AI.\n\n"
                f"Detail teknis: {e}"
            )

    print("[VERTEX] Generate request sent (once)")

    # ── polling ──
    print("[VERTEX] Polling operation status...")
    deadline = time.time() + POLL_TIMEOUT
    while not operation.done:
        remaining = deadline - time.time()
        if remaining <= 0:
            elapsed = time.time() - start_time
            print(f"[VERTEX] Response Time: {elapsed:.2f}s")
            raise Exception(
                f"Generate video timeout setelah {POLL_TIMEOUT // 60} menit.\n\n"
                "Vertex AI membutuhkan waktu lebih lama dari biasanya.\n"
                "Coba lagi nanti atau cek status job di Google Cloud Console."
            )
        print(f"[VERTEX] Menunggu video selesai... (timeout {int(remaining)}s remaining)")
        await asyncio.sleep(POLL_INTERVAL)

        # ── Retry loop khusus client.operations.get ──
        # Tidak memanggil generate_videos() — hanya polling status
        _poll_err = None
        for poll_attempt in range(1, 4):
            try:
                operation = await asyncio.to_thread(client.operations.get, operation)
                _poll_err = None
                break
            except (TimeoutError, asyncio.TimeoutError, OSError, ConnectionError) as e:
                _poll_err = e
                err_str = str(e).lower()
                if "not found" in err_str:
                    raise Exception(
                        "Operation ID tidak ditemukan — kemungkinan sudah expired.\n"
                        "Coba generate ulang."
                    )
                if poll_attempt < 3:
                    backoff = {1: 2, 2: 5}[poll_attempt]
                    print(f"[VERTEX] Polling retry {poll_attempt}/3 "
                          f"({type(e).__name__}) — tunggu {backoff}s...")
                    await asyncio.sleep(backoff)
                    continue
            except Exception as e:
                err_str = str(e).lower()
                if "not found" in err_str:
                    raise Exception(
                        "Operation ID tidak ditemukan — kemungkinan sudah expired.\n"
                        "Coba generate ulang."
                    )
                _poll_err = e
                if poll_attempt < 3:
                    backoff = {1: 2, 2: 5}[poll_attempt]
                    print(f"[VERTEX] Polling retry {poll_attempt}/3 "
                          f"({type(e).__name__}) — tunggu {backoff}s...")
                    await asyncio.sleep(backoff)
                    continue
                break

        if _poll_err is not None:
            elapsed = time.time() - start_time
            print(f"[VERTEX] Response Time: {elapsed:.2f}s")
            print(f"[VERTEX] Polling gagal setelah 3 retry: {type(_poll_err).__name__}: {_poll_err}")
            raise Exception(
                f"Gagal mengecek status generasi video setelah 3 kali percobaan.\n\n"
                f"Detail: {type(_poll_err).__name__}: {_poll_err}"
            )
    elapsed_generate = time.time() - start_time
    print(f"[VERTEX] Response Time: {elapsed_generate:.2f}s")

    # ── ambil hasil ──
    try:
        response = operation.response
    except Exception as e:
        raise Exception(
            f"Gagal membaca response dari Vertex AI.\n\n"
            f"Detail teknis: {e}"
        )

    if not response:
        raise Exception(
            "Vertex AI mengembalikan response kosong.\n"
            "Coba generate ulang atau periksa log di Google Cloud Console."
        )

    generated_videos = getattr(response, 'generated_videos', None)
    if not generated_videos or len(generated_videos) == 0:
        raise Exception(
            "Vertex AI tidak mengembalikan video apapun dalam response.\n"
            "Coba prompt yang berbeda atau periksa log di Google Cloud Console."
        )

    video_obj = generated_videos[0].video if hasattr(generated_videos[0], 'video') else generated_videos[0]

    if not video_obj:
        raise Exception(
            "Struktur response Vertex AI tidak mengandung objek video.\n"
            f"Response keys: {dir(response) if hasattr(response, '__dir__') else 'N/A'}"
        )

    # ── DEBUG: struktu objek response ──

    # ── download ──
    try:
        os.makedirs("generated", exist_ok=True)
    except OSError as e:
        raise Exception(f"Gagal buat folder penyimpanan 'generated': {e}")

    local_filename = f"generated/{uuid.uuid4()}.mp4"

    download_start = time.time()
    try:
        await _download_video(video_obj, local_filename)
    except Exception as e:
        download_elapsed = time.time() - download_start
        print(f"[VERTEX] Download Time: {download_elapsed:.2f}s")
        print(f"[VERTEX] Download Error: {e}")
        raise Exception(
            f"Video berhasil dibuat di Vertex AI, tapi gagal di-download.\n\n"
            f"Detail: {e}\n\n"
            f"Video mungkin masih tersedia di GCS bucket: {config.VERTEX_OUTPUT_GCS_URI or '(default)'}"
        )

    download_elapsed = time.time() - download_start
    total_elapsed = time.time() - start_time

    # ── logging footer ──
    print(f"[VERTEX] Download Time: {download_elapsed:.2f}s")
    print(f"[VERTEX] Saved: {os.path.abspath(local_filename)}")
    print(f"[VERTEX] Total Time: {total_elapsed:.2f}s")
    print("=============================\n")

    return local_filename
