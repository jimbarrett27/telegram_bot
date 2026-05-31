"""FastAPI application for the triage backend.

Identity is enforced at the edge by Cloudflare Access. As defence in depth, the
backend also verifies the ``Cf-Access-Authenticated-User-Email`` header on every
``/api/triage`` request when ``TRIAGE_REQUIRE_CF_ACCESS`` is enabled (the backend
is only reachable through the Cloudflare Tunnel, so the header can be trusted).
``/healthz`` is intentionally left open for container/tunnel health probes.
"""

from typing import Iterator, Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from content_screening.db_engine import get_session
from triage import repository, routing
from triage.config import Settings, get_settings
from triage.schemas import DecideRequest, PaperOut
from util.logging_util import setup_logger

logger = setup_logger(__name__)

API_PREFIX = "/api/triage"
CF_ACCESS_EMAIL_HEADER = "Cf-Access-Authenticated-User-Email"


def db_session() -> Iterator[Session]:
    """FastAPI dependency yielding a screening-DB session."""
    with get_session() as session:
        yield session


def make_access_guard(settings: Settings):
    """Build the Cloudflare Access verification dependency for this app."""

    def verify_cf_access(
        cf_email: Optional[str] = Header(default=None, alias=CF_ACCESS_EMAIL_HEADER),
    ) -> None:
        if not settings.require_cf_access:
            return
        if not cf_email:
            raise HTTPException(
                status_code=403, detail="Missing Cloudflare Access identity"
            )
        if settings.allowed_email and cf_email.lower() != settings.allowed_email.lower():
            logger.warning("rejected Access identity: %s", cf_email)
            raise HTTPException(status_code=403, detail="Identity not permitted")

    return verify_cf_access


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Paper Triage",
        # Namespaced so everything lives under the proxied /api/triage/* path.
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )

    # The SPA is served from the main domain and calls the API on a separate
    # `triage-api.<domain>` host, so cross-origin requests need CORS. Credentials
    # are allowed so the Cloudflare Access cookie is sent.
    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.allowed_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    # Every triage route is gated by the Access guard.
    router = APIRouter(
        prefix=API_PREFIX,
        dependencies=[Depends(make_access_guard(settings))],
    )

    @router.get("/queue", response_model=list[PaperOut])
    def queue(session: Session = Depends(db_session)) -> list[PaperOut]:
        papers = repository.get_pending_papers(session, settings.min_relevance_score)
        logger.info("queue requested: %d pending papers", len(papers))
        return [PaperOut.from_orm_article(p) for p in papers]

    @router.get("/papers/{paper_id}", response_model=PaperOut)
    def get_paper(paper_id: int, session: Session = Depends(db_session)) -> PaperOut:
        paper = repository.get_paper(session, paper_id)
        if paper is None:
            raise HTTPException(status_code=404, detail="Paper not found")
        return PaperOut.from_orm_article(paper)

    @router.post("/papers/{paper_id}/decide", response_model=PaperOut)
    def decide(
        paper_id: int,
        body: DecideRequest,
        session: Session = Depends(db_session),
    ) -> PaperOut:
        paper = repository.get_paper(session, paper_id)
        if paper is None:
            raise HTTPException(status_code=404, detail="Paper not found")
        repository.apply_decision(paper, body.decision)
        # Initial routing attempt runs inline; the retry loop (step 8) will pick
        # up anything that failed. Failures are recorded on the row, not raised.
        routing.route_decision(paper, settings)
        logger.info("decision: paper=%d -> %s", paper_id, body.decision)
        return PaperOut.from_orm_article(paper)

    @router.post("/papers/{paper_id}/undo", response_model=PaperOut)
    def undo(paper_id: int, session: Session = Depends(db_session)) -> PaperOut:
        paper = repository.get_paper(session, paper_id)
        if paper is None:
            raise HTTPException(status_code=404, detail="Paper not found")
        if paper.status == "pending":
            raise HTTPException(status_code=409, detail="Nothing to undo")
        if not repository.within_undo_window(paper, settings.undo_window_seconds):
            raise HTTPException(status_code=409, detail="Undo window has expired")
        repository.clear_decision(paper)
        logger.info("undo: paper=%d -> pending", paper_id)
        return PaperOut.from_orm_article(paper)

    app.include_router(router)
    return app


app = create_app()
