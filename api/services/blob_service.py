import os
from vercel_blob import put_blob
from typing import Optional

async def archive_upload(filename: str, contents: bytes) -> Optional[str]:
    token = os.getenv("BLOB_READ_WRITE_TOKEN")
    if not token:
        print("Blob token missing - skipping archive")
        return None
    
    try:
        blob = await put_blob(filename, contents, {"token": token})
        return blob.url
    except Exception as e:
        print(f"Blob archive failed: {str(e)}")
        return None