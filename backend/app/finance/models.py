from datetime import date
from pydantic import BaseModel, Field, ConfigDict


class Transaction(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    txn_date: date
    merchant: str
    amount: float
    currency: str
    txn_type: str
    category: str
    category_confidence: float | None = None
    category_source: str | None = None
    account_last4: str | None = None
    description: str | None = None
    source: str
    created_at: str


class BudgetProposal(BaseModel):
    category: str = Field(min_length=1)
    new_amount: float = Field(ge=0)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    model: str | None = None


class ChatResponse(BaseModel):
    answer: str
    tool_trace: list[dict]
    requires_confirmation: bool
