import os
import uuid
from httpx import AsyncClient

async def archive_upload(filename: str, contents: bytes) -> str | None:
    token = os.getenv("BLOB_READ_WRITE_TOKEN")
    if not token:
        print("BLOB_READ_WRITE_TOKEN missing - skipping archive")
        return None

    # Use UUID prefix to avoid collisions; Vercel Blob handles overwrites if same path
    pathname = f"uploads/{uuid.uuid4()}_{filename}"

    url = f"https://blob.vercel-storage.com/{pathname}"

    headers = {
        "Authorization": f"Bearer {token}",
        "x-vercel-blob-no-redirect": "1",  # Optional: get direct metadata vs redirect
    }

    try:
        async with AsyncClient() as client:
            response = await client.put(url, content=contents, headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            blob_url = data.get("url") or url  # Direct CDN URL
            print(f"Blob archived: {blob_url}")
            return blob_url
    except Exception as e:
        print(f"Blob upload failed: {str(e)} | Status: {getattr(e, 'response', None)}")
        return None