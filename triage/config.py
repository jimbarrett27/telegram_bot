"""Runtime configuration for the triage backend, sourced from the environment.

Kept deliberately small. Zotero/Obsidian settings are added here as those
integrations land (build steps 6 and 7).
"""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    # Only papers the screener scored strictly above this make it into the
    # triage queue. The screener sets non-relevant papers to 0.0, so the
    # default of 0.0 selects exactly the "surfaced" papers.
    min_relevance_score: float = 0.0

    # Bind address for local/dev runs. In production the service sits behind a
    # Cloudflare Tunnel, so binding to localhost is fine.
    host: str = "127.0.0.1"
    port: int = 8077

    # How long after a decision the user may still undo it.
    undo_window_seconds: int = 30

    # --- Cloudflare Access (defence in depth) ---
    # When enabled, every /api/triage request must carry a
    # Cf-Access-Authenticated-User-Email header matching `allowed_email`.
    # Off by default so local/dev runs need no auth; enabled in production.
    require_cf_access: bool = False
    allowed_email: str = ""

    # Origins permitted by CORS. Needed because the SPA (main domain) calls the
    # API on a separate `triage-api.<domain>` host. Empty disables CORS.
    allowed_origins: tuple[str, ...] = field(default_factory=tuple)

    # --- Obsidian ---
    # Filesystem path to the Obsidian vault root on jim-server (or a folder that
    # syncs into it). Empty disables stub writing.
    obsidian_vault: str = ""
    # Vault-relative folder stubs are written into.
    obsidian_inbox_subdir: str = "literature/inbox"


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def get_settings() -> Settings:
    """Build settings from environment variables (with sensible defaults)."""
    return Settings(
        min_relevance_score=float(
            os.environ.get("TRIAGE_MIN_RELEVANCE_SCORE", "0.0")
        ),
        host=os.environ.get("TRIAGE_HOST", "127.0.0.1"),
        port=int(os.environ.get("TRIAGE_PORT", "8077")),
        undo_window_seconds=int(os.environ.get("TRIAGE_UNDO_WINDOW_SECONDS", "30")),
        require_cf_access=os.environ.get("TRIAGE_REQUIRE_CF_ACCESS", "false").lower()
        in ("1", "true", "yes"),
        allowed_email=os.environ.get("TRIAGE_ALLOWED_EMAIL", ""),
        allowed_origins=_csv(os.environ.get("TRIAGE_ALLOWED_ORIGINS", "")),
        obsidian_vault=os.environ.get("TRIAGE_OBSIDIAN_VAULT", ""),
        obsidian_inbox_subdir=os.environ.get(
            "TRIAGE_OBSIDIAN_INBOX_SUBDIR", "literature/inbox"
        ),
    )
