"""Storage system: S3-backed for prod, or local files in ./data for testing.

Storage layout:
  - songs.json
  - changes.jsonl
  - write.lock (prod only)
"""

import contextlib
import json
import logging
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import ClientError

from . import config

if TYPE_CHECKING:
    # boto3-stubs is dev-only; this import would fail in production.
    from mypy_boto3_s3.client import S3Client

logger = logging.getLogger(__name__)

SONGS_KEY = "songs.json"
CHANGES_KEY = "changes.jsonl"
LOCK_KEY = "write.lock"

LOCK_STALE_AFTER_SECONDS = 30 * 60  # 30 minutes.


class LockHeldError(RuntimeError):
    """Raised when write.lock is held by another, non-stale run."""


_s3_client: "S3Client" = boto3.client(
    "s3",
    region_name=config.KANADE_S3_REGION,
    aws_access_key_id=config.KANADE_S3_ACCESS_KEY_ID,
    aws_secret_access_key=config.KANADE_S3_SECRET_ACCESS_KEY,
)


class _LocalMode:
    """Tracks whether storage operations are redirected to a local directory."""

    dir: Path | None = None


_local = _LocalMode()


def use_local_storage() -> None:
    """Store data under ./data instead of S3."""
    local_dir = Path.cwd() / "data"
    local_dir.mkdir(exist_ok=True)
    _local.dir = local_dir


def _get(key: str) -> bytes | None:
    """Fetch an object's body, or None if it doesn't exist yet."""
    if _local.dir is not None:
        path = _local.dir / key
        return path.read_bytes() if path.exists() else None

    try:
        return _s3_client.get_object(Bucket=config.KANADE_S3_BUCKET, Key=key)[
            "Body"
        ].read()
    except ClientError as err:
        if err.response["Error"]["Code"] == "NoSuchKey":
            return None
        raise


def _put(key: str, body: bytes, content_type: str) -> None:
    """Write an object's body, either locally or to S3."""
    if _local.dir is not None:
        (_local.dir / key).write_bytes(body)
        return

    _s3_client.put_object(
        Bucket=config.KANADE_S3_BUCKET, Key=key, Body=body, ContentType=content_type
    )


def load_songs() -> list[dict[str, Any]]:
    """Read and parse the current snapshot.

    Returns [] if it doesn't exist yet.
    """
    body = _get(SONGS_KEY)
    return json.loads(body) if body else []


def save_songs(songs: list[dict[str, Any]]) -> None:
    """Overwrite the songs snapshot. Assumes caller has the write lock."""
    _put(
        SONGS_KEY,
        json.dumps(songs, indent=2, ensure_ascii=False).encode(),
        "application/json",
    )


def append_changes(events: list[dict[str, Any]]) -> None:
    """Append change events to the log. Assumes caller has the write lock."""
    if not events:
        return

    ts = time.time()
    body = _get(CHANGES_KEY)
    lines = body.decode().splitlines() if body else []
    lines.extend(
        json.dumps({"ts": ts, **event}, ensure_ascii=False) for event in events
    )
    _put(CHANGES_KEY, ("\n".join(lines) + "\n").encode(), "application/x-ndjson")


@contextlib.contextmanager
def lock() -> Iterator[None]:
    """Hold the write lock for the duration of the block.

    Only used for prod. Uses S3's conditional-write support.

    Raises LockHeldError if another run holds a lock that isn't stale yet.
    """
    if _local.dir is not None:
        yield
        return

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
