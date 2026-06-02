"""FastAPI application for the triage backend.

Identity is enforced at the edge by Cloudflare Access. As defence in depth, the
backend also verifies the ``Cf-Access-Authenticated-User-Email`` header on every
``/api/triage`` request when ``TRIAGE_REQUIRE_CF_ACCESS`` is enabled (the backend
is only reachable through the Cloudflare Tunnel, so the header can be trusted).
``/healthz`` is intentionally left open for container/tunnel health probes.
"""

import asyncio
import contextlib
from typing import AsyncIterator, Iterator, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from content_screening.db_engine import get_session
from triage import repository, retry, routing
from triage.config import Settings, get_settings
from triage.schemas import Decision, PaperOut
from util.logging_util import setup_logger

logger = setup_logger(__name__)

API_PREFIX = "/api/triage"
CF_ACCESS_EMAIL_HEADER = "Cf-Access-Authenticated-User-Email"


def db_session() -> Iterator[Session]:
    """FastAPI dependency yielding a screening-DB session."""
    with get_session() as session:
        yield session


def route_paper_in_background(paper_id: int, settings: Settings) -> None:
    """Route a freshly-decided paper off the request path.

    Opens its own session (the request's is already closed) and re-loads the
    paper so a quick undo between the response and this task is respected:
    ``route_and_schedule`` is a no-op for a paper reverted to ``pending``.
    """
    with get_session() as session:
        paper = repository.get_paper(session, paper_id)
        if paper is None:
            return
        routing.route_and_schedule(paper, settings)


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

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # Start the background routing retry loop, cancelling it on shutdown.
        task = (
            asyncio.create_task(retry.retry_loop(settings))
            if settings.routing_retry_enabled
            else None
        )
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(
        title="Paper Triage",
        # Namespaced so everything lives under the proxied /api/triage/* path.
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
        lifespan=lifespan,
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

    @router.get("/history", response_model=list[PaperOut])
    def history(session: Session = Depends(db_session)) -> list[PaperOut]:
        papers = repository.get_decided_papers(session)
        logger.info("history requested: %d decided papers", len(papers))
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
        decision: Decision,
        background_tasks: BackgroundTasks,
        session: Session = Depends(db_session),
    ) -> PaperOut:
        # `decision` is a query parameter (not a JSON body) deliberately: with an
        # empty body and no Content-Type the browser treats the cross-origin POST
        # as a "simple" request and skips the CORS preflight, which Cloudflare's
        # edge rejects for OPTIONS. The Access cookie still rides along.
        paper = repository.get_paper(session, paper_id)
        if paper is None:
            raise HTTPException(status_code=404, detail="Paper not found")
        repository.apply_decision(paper, decision)
        # Persist the decision now so the background task (its own session) sees
        # it, then route off the request path. The response returns immediately
        # with routing pending; the retry loop covers any failure.
        session.commit()
        background_tasks.add_task(route_paper_in_background, paper_id, settings)
        logger.info("decision: paper=%d -> %s", paper_id, decision)
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
