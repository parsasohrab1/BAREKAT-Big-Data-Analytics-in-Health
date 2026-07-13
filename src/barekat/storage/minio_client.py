"""MinIO object storage client for raw health data files (DICOM, HL7, CSV)."""

import io
from pathlib import Path
from typing import BinaryIO

from minio import Minio
from minio.error import S3Error

from barekat.config.settings import get_settings


class ObjectStorage:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket_raw = settings.minio_bucket_raw
        self.bucket_processed = settings.minio_bucket_processed
        self.bucket_lake = settings.minio_bucket_lake
        self._ensure_buckets()

    def _ensure_buckets(self) -> None:
        for bucket in (self.bucket_raw, self.bucket_processed, self.bucket_lake):
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)

    def upload_file(self, bucket: str, object_name: str, file_path: Path) -> str:
        self.client.fput_object(bucket, object_name, str(file_path))
        return object_name

    def upload_bytes(self, bucket: str, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self.client.put_object(bucket, object_name, io.BytesIO(data), len(data), content_type=content_type)
        return object_name

    def download_file(self, bucket: str, object_name: str, dest_path: Path) -> Path:
        self.client.fget_object(bucket, object_name, str(dest_path))
        return dest_path

    def get_object_stream(self, bucket: str, object_name: str) -> BinaryIO:
        response = self.client.get_object(bucket, object_name)
        return response

    def list_objects(self, bucket: str, prefix: str = "") -> list[str]:
        try:
            return [obj.object_name for obj in self.client.list_objects(bucket, prefix=prefix, recursive=True)]
        except S3Error:
            return []
