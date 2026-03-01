import os
import boto3
import base64
import uuid
from botocore.exceptions import ClientError
from urllib.parse import urlparse
from datetime import datetime

class MinioClient:
    def __init__(self):
        self.endpoint = os.getenv("MINIO_ENDPOINT")
        self.access_key = os.getenv("MINIO_ACCESS_KEY")
        self.secret_key = os.getenv("MINIO_SECRET_KEY")
        self.bucket_name = os.getenv("MINIO_BUCKET_NAME", "ai-media")
        self.secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        
        self.s3_client = boto3.client(
            's3',
            endpoint_url=f"http{'s' if self.secure else ''}://{self.endpoint}",
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=boto3.session.Config(signature_version='s3v4'),
            verify=False 
        )
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
        except ClientError:
            try:
                self.s3_client.create_bucket(Bucket=self.bucket_name)
            except ClientError as e:
                print(f"Error creating bucket {self.bucket_name}: {e}")

    def upload_file(self, file_path: str, object_name: str) -> str:
        """Uploads a file to MinIO and returns a presigned URL."""
        try:
            self.s3_client.upload_file(file_path, self.bucket_name, object_name)
            return self.generate_presigned_url(object_name)
        except ClientError as e:
            print(f"MinIO Upload Error: {e}")
            raise

    def upload_bytes(self, data: bytes, object_name: str, content_type: str = "application/octet-stream") -> str:
        """Uploads bytes to MinIO and returns a presigned URL."""
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=object_name,
                Body=data,
                ContentType=content_type
            )
            return self.generate_presigned_url(object_name)
        except ClientError as e:
            print(f"MinIO Bytes Upload Error: {e}")
            raise

    def generate_presigned_url(self, object_name: str, expiration: int = 3600) -> str:
        try:
            return self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_name},
                ExpiresIn=expiration
            )
        except ClientError as e:
            print(f"MinIO Presigned URL Error: {e}")
            raise

    def delete_object(self, object_name: str):
        """Deletes an object from MinIO."""
        if not object_name:
            return
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_name)
            print(f"Deleted object {object_name} from MinIO")
        except ClientError as e:
            print(f"MinIO Delete Error: {e}")

    def extract_object_name(self, presigned_url: str) -> str:
        """Extracts the object name from a presigned URL."""
        if not presigned_url:
            return ""
        try:
            parsed = urlparse(presigned_url)
            path = parsed.path
            # path is usually /bucket_name/object_name
            # remove leading slash
            if path.startswith("/"):
                path = path[1:]
            
            parts = path.split("/", 1)
            if len(parts) == 2 and parts[0] == self.bucket_name:
                return parts[1]
            return path # Fallback if structure is different (e.g. host-style)
        except Exception as e:
            print(f"Error extracting object name from URL {presigned_url}: {e}")
            return ""

# Initialize a global instance or allow instantiation
minio_client = MinioClient()
