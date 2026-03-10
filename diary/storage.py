from datetime import date
from pathlib import Path

from util.logging_util import setup_logger

logger = setup_logger(__name__)

ENTRIES_DIR = Path(__file__).parent / "entries"
GCS_BUCKET = "jimmy-diary-eu"


def _month_file(d: date) -> Path:
    return ENTRIES_DIR / f"{d.strftime('%Y-%m')}.md"


def _date_heading(d: date) -> str:
    return d.strftime("%A %-d %B")


def entry_exists(d: date) -> bool:
    path = _month_file(d)
    if not path.exists():
        return False
    return _date_heading(d) in path.read_text()


def save_entry(d: date, text: str) -> None:
    ENTRIES_DIR.mkdir(exist_ok=True)
    path = _month_file(d)

    is_new_file = not path.exists()
    with path.open("a") as f:
        if is_new_file:
            f.write(f"# {d.strftime('%B %Y')}\n")
        f.write(f"\n## {_date_heading(d)}\n\n{text}\n")

    logger.info(f"Saved diary entry for {d} to {path.name}")
    _backup_to_gcs(path)


def _backup_to_gcs(path: Path) -> None:
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(path.name)
        blob.upload_from_filename(str(path))
        logger.info(f"Backed up {path.name} to GCS bucket {GCS_BUCKET}")
    except Exception as e:
        logger.error(f"GCS backup failed: {e}")
