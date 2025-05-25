"""Example demonstrating basic file upload and download with AWS S3.

This script shows how to use boto3 to upload a local file to an S3 bucket and
then download it back. Credentials are taken from the standard AWS credential
chain. Ensure `boto3` is installed and AWS credentials are configured before
running.

Usage:
    python examples/s3_upload_download_example.py --bucket my-bucket --upload local.txt --key uploads/myfile.txt
    python examples/s3_upload_download_example.py --bucket my-bucket --download downloaded.txt --key uploads/myfile.txt
"""
import argparse
import logging
import os
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
LOGGER = logging.getLogger("s3_example")


def upload_file(bucket: str, local_path: str, key: str) -> None:
    """Upload a file to an S3 bucket.

    Args:
        bucket: Target S3 bucket name.
        local_path: Path to the local file to upload.
        key: Destination object key within the bucket.
    """
    if not os.path.isfile(local_path):
        raise FileNotFoundError(f"Local file not found: {local_path}")

    client = boto3.client("s3")
    try:
        client.upload_file(local_path, bucket, key)
        LOGGER.info("Uploaded %s to s3://%s/%s", local_path, bucket, key)
    except (BotoCoreError, ClientError) as exc:
        LOGGER.error("Upload failed: %s", exc)
        raise


def download_file(bucket: str, key: str, dest_path: str) -> None:
    """Download a file from an S3 bucket.

    Args:
        bucket: Source S3 bucket name.
        key: Object key within the bucket.
        dest_path: Local path where the file will be saved.
    """
    dest_dir = Path(dest_path).resolve().parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    client = boto3.client("s3")
    try:
        client.download_file(bucket, key, dest_path)
        LOGGER.info("Downloaded s3://%s/%s to %s", bucket, key, dest_path)
    except (BotoCoreError, ClientError) as exc:
        LOGGER.error("Download failed: %s", exc)
        raise


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="S3 upload and download example")
    parser.add_argument("--bucket", required=True, help="Name of the S3 bucket")
    parser.add_argument("--key", required=True, help="S3 object key")
    parser.add_argument("--upload", help="Path of local file to upload")
    parser.add_argument("--download", help="Local path to save downloaded file")
    return parser.parse_args(args)


def main() -> None:
    """Execute the example based on CLI arguments."""
    options = parse_args()
    if options.upload:
        upload_file(options.bucket, options.upload, options.key)
    if options.download:
        download_file(options.bucket, options.key, options.download)
    if not options.upload and not options.download:
        LOGGER.warning("No action specified. Use --upload and/or --download.")


if __name__ == "__main__":
    main()
