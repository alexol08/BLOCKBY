from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class Profile(BaseModel):
    id: str | None = None
    name: str = "Local hobbyist"
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    stock: list[str] = Field(default_factory=list)
    shippingAddress: str = ""
    notes: str = ""
    updatedAt: str | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: str = ""


class ProjectRefineRequest(BaseModel):
    profile: Profile | None = None
    idea: str = ""
    messages: list[ChatMessage | dict[str, Any]] = Field(default_factory=list)
    budgetQuality: int = 50
    ownedOptimisation: bool = True


class SourcingRequest(BaseModel):
    profile: dict[str, Any] = Field(default_factory=dict)
    brief: dict[str, Any] = Field(default_factory=dict)
    idea: str = ""
    budgetQuality: int = 50


class InstructionsRequest(BaseModel):
    profile: dict[str, Any] = Field(default_factory=dict)
    brief: dict[str, Any] = Field(default_factory=dict)
    sourcing: dict[str, Any] = Field(default_factory=dict)


class HelpRequest(BaseModel):
    question: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


class SourceCandidate(BaseModel):
    supplier: str
    productName: str
    manufacturer: str = ""
    manufacturerPartNumber: str = ""
    supplierPartNumber: str = ""
    description: str = ""
    productUrl: str = ""
    datasheetUrl: str = ""
    imageUrl: str = ""
    unitPrice: float = 0
    currency: str = "EUR"
    priceText: str = ""
    priceConfidence: Literal["exact", "unknown"] = "unknown"
    shippingEstimate: float = 0
    shippingText: str = ""
    shippingConfidence: Literal["exact", "estimated", "unknown"] = "unknown"
    totalPriceEstimate: float = 0
    stockAvailable: int | None = None
    minimumOrderQuantity: int = 1
    leadTime: str = "Unknown"
    lastChecked: str = Field(default_factory=now_iso)
    verificationStatus: Literal["verified", "unverified", "needs_review"] = "unverified"
    verificationMethod: str = ""
    verificationMessage: str = ""
    productUrlVerified: bool = False
    datasheetUrlVerified: bool = False
    linkVerification: dict[str, Any] = Field(default_factory=dict)
    sourceType: Literal["web_search", "supplier_search", "demo_catalogue", "supplier_api", "manual"] = "manual"
    evidenceNotes: str = ""


class BomItem(BaseModel):
    id: str | None = None
    name: str
    category: str = "general"
    required: bool = True
    quantity: float = 1
    unitPriceEstimate: float = 0
    vendorHint: str = ""
    ownedAlternative: str = ""
    compatibilityNotes: str = ""
    difficulty: Literal["easy", "medium", "hard"] = "easy"
    safetyNotes: str = ""
    sourceStatus: Literal["owned", "recommended", "optional", "blocked"] = "recommended"
    orderable: bool = True
    selected: bool = True
    sourceCandidates: list[SourceCandidate | dict[str, Any]] = Field(default_factory=list)
    selectedSourceIndex: int = -1
    verificationStatus: Literal["verified", "unverified", "needs_review"] = "unverified"


class OrderRequest(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    currency: str = "EUR"


class SaveProjectRequest(BaseModel):
    id: str | None = None
    title: str = "Untitled project"
    brief: dict[str, Any] = Field(default_factory=dict)
    sourcing: dict[str, Any] = Field(default_factory=dict)
    instructions: dict[str, Any] = Field(default_factory=dict)
    visibility: Literal["private", "public"] = "private"
    createdAt: str | None = None
