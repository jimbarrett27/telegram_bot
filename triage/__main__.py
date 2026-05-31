"""Run the triage backend locally:  uv run python -m triage

Must be launched from the repo root so the relative ``content_screening.db``
path resolves to the same database the Telegram bot uses.
"""

import uvicorn

from triage.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run("triage.app:app", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
