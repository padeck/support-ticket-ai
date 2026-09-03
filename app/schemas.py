from pydantic import BaseModel, Field
from typing import Optional


class TicketCreate(BaseModel):
    request: str = Field(..., min_length=1, max_length=5000)


class TicketResponse(BaseModel):
    ticketId: str
    category: str
    priority: str
    assignedTeam: str
    summary: str
    status: str
    createdAt: Optional[str] = None


class TicketListResponse(BaseModel):
    tickets: list[TicketResponse]
    total: int


class StatusUpdate(BaseModel):
    status: str = Field(
        ...,
        pattern="^(open|in_progress|resolved|manual_review_required)$",
    )
