from datetime import date

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.agent.ollama import AgentError, OllamaAgent
from app.agent.watcher import run_watcher
from app.core.config import get_settings
from app.finance.models import BudgetProposal, ChatRequest, ChatResponse
from app.finance.service import FinanceService
from app.sources.email.gmail_client import GmailAuthError, GmailClient
from app.sources.email.gmail_source import GmailTransactionSource
from app.storage.repository import TransactionRepository
from app.importer import parse_csv

router = APIRouter(prefix="/api")
finance = FinanceService(TransactionRepository())
agent = OllamaAgent()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/import/csv")
async def import_csv(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="A .csv file is required.")

    try:
        data = await file.read()
        transactions = parse_csv(data)
        return TransactionRepository().insert_many(transactions)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/import/gmail")
def import_gmail():
    settings = get_settings()

    try:
        client = GmailClient(settings.gmail_token_file)
    except GmailAuthError as exc:
        raise HTTPException(status_code=428, detail=str(exc)) from exc

    source = GmailTransactionSource(client, settings.gmail_query, settings.gmail_max_results)
    try:
        result = source.fetch()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Gmail API error: {exc}") from exc

    insert_result = TransactionRepository().insert_many(result["transactions"])
    return {
        **insert_result,
        "scanned_emails": result["scanned"],
        "unparsed_emails": result["unparsed"],
    }


@router.get("/transactions")
def transactions(
    category: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 100,
):
    return finance.list_transactions(
        category=category,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )


@router.get("/summary/{year}/{month}")
def summary(year: int, month: int):
    try:
        return finance.monthly_summary(year, month)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/budgets")
def list_budgets():
    return finance.list_budgets()


@router.post("/budgets")
def set_budget(body: BudgetProposal):
    return finance.set_budget(body.category, body.new_amount)


@router.get("/budgets/status/{year}/{month}")
def budgets_status(year: int, month: int):
    return finance.all_budget_status(year, month)


@router.get("/insights")
def list_insights(unresolved_only: bool = False, year: int | None = None, month: int | None = None):
    return finance.insights(unresolved_only, year, month)


@router.post("/insights/run")
def trigger_watcher():
    return run_watcher()


@router.post("/insights/{insight_id}/resolve")
def resolve_insight(insight_id: int):
    if not finance.resolve_insight(insight_id):
        raise HTTPException(status_code=404, detail="Insight not found.")
    return {"resolved": insight_id}


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        return agent.run(request.message, request.model)
    except AgentError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
