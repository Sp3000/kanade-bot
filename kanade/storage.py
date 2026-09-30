"""S3-backed storage system.

Bucket layout:
  - songs.json
  - changes.jsonl
  - write.lock
"""

import contextlib
import json
import logging
import time
import uuid
from collections.abc import Iterator
from typing import Any

import boto3
from botocore.exceptions import ClientError
from mypy_boto3_s3.client import S3Client

from . import config

logger = logging.getLogger(__name__)

SONGS_KEY = "songs.json"
CHANGES_KEY = "changes.jsonl"
LOCK_KEY = "write.lock"

LOCK_STALE_AFTER_SECONDS = 30 * 60  # 30 minutes.


class LockHeldError(RuntimeError):
    """Raised when write.lock is held by another, non-stale run."""


_s3_client: S3Client = boto3.client(
    "s3",
    aws_access_key_id=config.KANADE_S3_ACCESS_KEY_ID,
    aws_secret_access_key=config.KANADE_S3_SECRET_ACCESS_KEY,
)


def _get(key: str) -> bytes | None:
    """Fetch an object's body, or None if it doesn't exist yet."""
    try:
        return _s3_client.get_object(Bucket=config.KANADE_S3_BUCKET, Key=key)[
            "Body"
        ].read()
    except ClientError as err:
        if err.response["Error"]["Code"] == "NoSuchKey":
            return None
        raise


def load_songs() -> list[dict[str, Any]]:
    """Read and parse the current snapshot.

    Returns [] if it doesn't exist yet.
    """
    body = _get(SONGS_KEY)
    return json.loads(body) if body else []


def save_songs(songs: list[dict[str, Any]]) -> None:
    """Overwrite the songs snapshot. Assumes caller has the write lock."""
    _s3_client.put_object(
        Bucket=config.KANADE_S3_BUCKET,
        Key=SONGS_KEY,
        Body=json.dumps(songs, indent=2).encode(),
        ContentType="application/json",
    )


def append_changes(events: list[dict[str, Any]]) -> None:
    """Append change events to the log. Assumes caller has the write lock."""
    if not events:
        return
    body = _get(CHANGES_KEY)
    lines = body.decode().splitlines() if body else []
    lines.extend(json.dumps(event) for event in events)
    _s3_client.put_object(
        Bucket=config.KANADE_S3_BUCKET,
        Key=CHANGES_KEY,
        Body=("\n".join(lines) + "\n").encode(),
        ContentType="application/x-ndjson",
    )


@contextlib.contextmanager
def lock() -> Iterator[None]:
    """Hold the write lock for the duration of the block.

    Uses S3's conditional-write support.

    Raises LockHeldError if another run holds a lock that isn't stale yet.
    """
    payload = json.dumps(
        {"acquired_at": time.time(), "run_id": str(uuid.uuid4())}
    ).encode()

    def try_acquire() -> bool:
        try:
            _s3_client.put_object(
                Bucket=config.KANADE_S3_BUCKET,
                Key=LOCK_KEY,
                Body=payload,
                ContentType="application/json",
                IfNoneMatch="*",
            )
            return True
        except ClientError as err:
            if err.response["Error"]["Code"] == "PreconditionFailed":
                return False
            raise

    if not try_acquire():
        try:
            existing = _s3_client.get_object(
                Bucket=config.KANADE_S3_BUCKET, Key=LOCK_KEY
            )
        except ClientError as err:
            if err.response["Error"]["Code"] != "NoSuchKey":
                raise
        else:
            acquired_at = json.loads(existing["Body"].read())["acquired_at"]
            if time.time() - acquired_at < LOCK_STALE_AFTER_SECONDS:
                raise LockHeldError("write.lock is held by another run")
            logger.warning(
                "write.lock is stale (acquired_at=%s), taking over", acquired_at
            )
            try:
                # IfMatch to only delete the exact lock object just read as stale, not
                # a different new lock object from a separate run.
                _s3_client.delete_object(
                    Bucket=config.KANADE_S3_BUCKET,
                    Key=LOCK_KEY,
                    IfMatch=existing["ETag"],
                )
            except ClientError as err:
                if err.response["Error"]["Code"] != "PreconditionFailed":
                    raise
                raise LockHeldError("write.lock changed during stale takeover") from err

        if not try_acquire():
            raise LockHeldError(
                "write.lock was re-acquired by another run during takeover"
            )

    try:
        yield
    finally:
        _s3_client.delete_object(Bucket=config.KANADE_S3_BUCKET, Key=LOCK_KEY)
