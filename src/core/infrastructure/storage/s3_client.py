import os
from typing import Dict, Any

import boto3
from botocore.client import Config as BotoConfig


def _bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).lower() in {"1", "true", "yes", "y"}


def create_s3_client():
    endpoint = os.getenv("S3_ENDPOINT")
    region = os.getenv("S3_REGION", "auto")
    access_key = os.getenv("S3_ACCESS_KEY")
    secret_key = os.getenv("S3_SECRET_KEY")
    force_path = _bool_env("S3_FORCE_PATH_STYLE", False)

    session = boto3.session.Session()
    cfg = BotoConfig(
        region_name=region if region and region != "auto" else None,
        s3={"addressing_style": "path" if force_path else "auto"},
        signature_version="s3v4",
    )
    client = session.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=cfg,
    )
    return client


def presign_post(filename: str, content_type: str, size: int, expires_in: int = 600) -> Dict[str, Any]:
    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        raise RuntimeError("S3_BUCKET is not set")
    client = create_s3_client()
    key = filename
    conditions = [["content-length-range", 1, size or 1024 * 1024 * 1024]]
    fields = {"Content-Type": content_type}
    resp = client.generate_presigned_post(
        Bucket=bucket,
        Key=key,
        Fields=fields,
        Conditions=conditions,
        ExpiresIn=expires_in,
    )
    return resp
