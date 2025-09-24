from minio import Minio
from ..core.config import settings

minio_client = Minio(
    endpoint=settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ROOT_USER,
    secret_key=settings.MINIO_ROOT_PASSWORD,
    secure=False  # Set to True if using HTTPS
)

def get_minio_client() -> Minio:
    """FastAPI dependency to get the Minio client."""
    return minio_client

def ensure_buckets_exist():
    """
    Checks if the required buckets exist in Minio and creates them if they don't.
    This function is intended to be called on application startup.
    """
    buckets_to_create = [
        settings.MINIO_BUCKET_ORIGINALS,
        settings.MINIO_BUCKET_ASSETS,
        settings.MINIO_BUCKET_CANONICAL_CONTENTS,
        settings.MINIO_BUCKET_PDFS
    ]
    for bucket_name in buckets_to_create:
        try:
            found = minio_client.bucket_exists(bucket_name)
            if not found:
                minio_client.make_bucket(bucket_name)
                print(f"Successfully created Minio bucket: {bucket_name}")
            else:
                print(f"Minio bucket '{bucket_name}' already exists.")
        except Exception as e:
            print(f"Error checking or creating Minio bucket '{bucket_name}': {e}")
            # Depending on the desired behavior, you might want to raise the exception
            # to prevent the application from starting if Minio is not available.
            raise e
