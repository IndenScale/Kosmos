
import os
from backend.app.tasks.service_factory import get_services_scope
from backend.app.utils.storage_utils import parse_storage_path

# This script is designed to be run from the project root directory.
# It downloads a specific file from MinIO and prints its content.

MINIO_STORAGE_PATH = "/kosmos-canonical-contents/3b98645097ba1c556ca269ba7ae0efa390c653bbe14b4241f25fe6caef20cf79.md"

def download_and_print():
    """
    Uses the application's MinIO client to download and print a file.
    """
    print(f"--- Attempting to download from MinIO path: {MINIO_STORAGE_PATH} ---")
    try:
        with get_services_scope() as services:
            minio_client = services["minio_client"]
            bucket, object_name = parse_storage_path(MINIO_STORAGE_PATH)
            
            print(f"--- Bucket: {bucket}, Object: {object_name} ---")
            
            response = minio_client.get_object(bucket, object_name)
            content = response.read().decode('utf-8')
            
            print("\n--- [FILE CONTENT START] ---")
            print(content)
            print("--- [FILE CONTENT END] ---\n")
            
    except Exception as e:
        print(f"\n--- [ERROR] ---")
        print(f"An error occurred: {e}")
    finally:
        # Clean up the response object
        if 'response' in locals() and hasattr(response, 'close'):
            response.close()
            response.release_conn()

if __name__ == "__main__":
    download_and_print()
