# database/models.py
# Pydantic models (data shapes) used across the API.

from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel


class ResearchRecord(BaseModel):
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    type: str  # product, niche, competitor, brand
    topic: str
    score: Optional[int] = None
    data: dict
    notes: Optional[str] = None


class AgentTask(BaseModel):
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    agent: str
    task: str
    status: str = "pending"  # pending, running, complete, failed
    input: Optional[dict] = None
    output: Optional[dict] = None
    error: Optional[str] = None
    duration_seconds: Optional[int] = None


class Product(BaseModel):
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    name: str
    niche: Optional[str] = None
    score: Optional[int] = None
    cost_estimate: Optional[float] = None
    sell_price_estimate: Optional[float] = None
    margin_estimate: Optional[float] = None
    status: str = "idea"  # idea, researching, testing, active, dropped
    notes: Optional[str] = None
    data: Optional[dict] = None


class Competitor(BaseModel):
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    name: str
    url: Optional[str] = None
    niche: Optional[str] = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    pricing: Optional[dict] = None
    data: Optional[dict] = None


class Decision(BaseModel):
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    category: Optional[str] = None
    decision: str
    reason: Optional[str] = None
    outcome: Optional[str] = None


class Memory(BaseModel):
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    agent: Optional[str] = None
    content: str
    metadata: Optional[dict] = None


class Action(BaseModel):
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    type: str  # create_shopify_product, update_shopify_product
    proposing_agent: str
    risk_level: str = "low"
    status: str = "proposed"  # proposed, approved, rejected, executed, failed
    idempotency_key: Optional[str] = None
    payload: dict
    before: Optional[dict] = None
    result: Optional[dict] = None
    error: Optional[str] = None


class Approval(BaseModel):
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    action_id: str
    decision: str  # approved, rejected
    reason: Optional[str] = None
    decided_by: Optional[str] = None


class AuditLogEntry(BaseModel):
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    action_id: str
    event: str  # proposed, approved, rejected, executed, failed
    detail: Optional[dict] = None


class Job(BaseModel):
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    type: str  # research_task
    payload: dict
    status: str = "pending"  # pending, running, complete, failed
    attempts: int = 0
    locked_at: Optional[datetime] = None
    error: Optional[str] = None
