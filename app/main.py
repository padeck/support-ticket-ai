import json
import logging
import threading
import time
import uuid

from fastapi import FastAPI, HTTPException, Query, Depends, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from . import models, schemas
from .config import settings
from .database import Base, engine, get_db, ensure_schema
from .ai_service import analyze_request

Base.metadata.create_all(bind=engine)
ensure_schema()

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": %(message)s}',
)
logger = logging.getLogger("support-tickets")

app = FastAPI(
    title="Support Ticket AI Processor",
    description="Analyzes incoming support requests with an LLM or a simulated AI component.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _log_json(level: str, message: str, **extra):
    record_extra = {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in extra.items()}
    getattr(logger, level)(f"{json.dumps(message, ensure_ascii=False)} {json.dumps(record_extra, ensure_ascii=False)}")


# ---------- Rate limiting (in-memory) ----------
_rate_limit = {}
_rate_limit_lock = threading.Lock()


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = 60
    with _rate_limit_lock:
        record = _rate_limit.get(client_ip)
        if record is None or now - record[1] >= window:
            _rate_limit[client_ip] = [1, now]
        else:
            record[0] += 1
            if record[0] > settings.rate_limit_per_minute:
                return JSONResponse(
                    status_code=429,
                    content={"error": "rate_limited", "message": "Too many requests. Try again later."},
                )
    response = await call_next(request)
    return response


# ---------- Optional auth ----------
def require_api_key(x_api_key: str | None = Header(default=None)):
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


# ---------- Request ID ----------
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    _log_json("info", "request processed", request_id=request_id, path=request.url.path, method=request.method, status=response.status_code)
    return response


# ---------- Helpers ----------
def _generate_ticket_id() -> str:
    return f"T-{uuid.uuid4().hex[:6]}"


def _to_response(ticket: models.Ticket) -> schemas.TicketResponse:
    return schemas.TicketResponse(
        ticketId=ticket.ticket_id,
        category=ticket.category,
        priority=ticket.priority,
        assignedTeam=ticket.assigned_team,
        summary=ticket.summary,
        status=ticket.status,
        aiProvider=ticket.ai_provider,
        createdAt=ticket.created_at.isoformat() if ticket.created_at else None,
    )


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(select(1))
        return {"status": "healthy", "database": "connected"}
    except Exception as exc:
        logger.error(f"health check failed: {exc}")
        return JSONResponse(status_code=503, content={"status": "unhealthy", "database": "disconnected"})


@app.post("/api/tickets", response_model=schemas.TicketResponse, dependencies=[Depends(require_api_key)])
def create_ticket(payload: schemas.TicketCreate, db: Session = Depends(get_db)):
    _log_json("info", "ticket received", request_text=payload.request)
    result = analyze_request(payload.request)
    _log_json("info", "ticket analyzed", category=result.category, priority=result.priority, assigned_team=result.assigned_team, status=result.status, ai_provider=result.provider)

    ticket_id = _generate_ticket_id()
    ticket = models.Ticket(
        ticket_id=ticket_id,
        request_text=payload.request,
        category=result.category,
        priority=result.priority,
        assigned_team=result.assigned_team,
        summary=result.summary,
        status=result.status,
        ai_provider=result.provider,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    _log_json("info", "ticket stored", ticket_id=ticket.ticket_id)
    return _to_response(ticket)


@app.get("/api/tickets", response_model=schemas.TicketListResponse, dependencies=[Depends(require_api_key)])
def list_tickets(
    request: Request,
    status: str | None = None,
    category: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(models.Ticket)
    if status:
        query = query.filter(models.Ticket.status == status)
    if category:
        query = query.filter(models.Ticket.category == category)
    total = query.count()
    tickets = query.order_by(models.Ticket.created_at.desc()).offset(offset).limit(limit).all()
    return schemas.TicketListResponse(tickets=[_to_response(t) for t in tickets], total=total)


@app.get("/api/tickets/{ticket_id}", response_model=schemas.TicketResponse, dependencies=[Depends(require_api_key)])
def get_ticket(ticket_id: str, db: Session = Depends(get_db)):
    ticket = db.query(models.Ticket).filter(models.Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return _to_response(ticket)


@app.patch("/api/tickets/{ticket_id}", response_model=schemas.TicketResponse, dependencies=[Depends(require_api_key)])
def update_ticket_status(ticket_id: str, payload: schemas.StatusUpdate, db: Session = Depends(get_db)):
    ticket = db.query(models.Ticket).filter(models.Ticket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    ticket.status = payload.status
    db.commit()
    db.refresh(ticket)
    _log_json("info", "ticket status updated", ticket_id=ticket.ticket_id, status=payload.status)
    return _to_response(ticket)
