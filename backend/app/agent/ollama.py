import datetime
import json
import httpx

from app.agent.definitions import TOOLS
from app.agent.tools import FUNCTIONS
from app.core.config import get_settings
from app.core.security import redact_for_model


SYSTEM_PROMPT_TEMPLATE = '''
You are a private, local-first finance coach.

Today's date is {today} (year={year}, month={month}). "This month" means
year={year}, month={month}. "Last month" means the calendar month before that.
Never guess or default to a different year.

Rules:
1. Never invent financial facts.
2. Use tools for transaction data, totals, comparisons, anomalies, budgets and forecasts.
3. You may call multiple tools when a question requires investigation.
4. Treat tool output as the source of truth for calculations.
5. Account identifiers and source identifiers are redacted and must never be reconstructed.
6. A proposal is not an executed financial change.
7. Explain conclusions using the evidence returned by tools.
8. Do not provide investment, tax, lending or other regulated financial advice.
9. Keep answers concise and actionable.
10. For broad review questions ("how am I doing", "anything to worry about"), check get_recent_insights for prior Watcher findings before answering.
'''.strip()


def _system_prompt() -> str:
    today = datetime.date.today()
    return SYSTEM_PROMPT_TEMPLATE.format(today=today.isoformat(), year=today.year, month=today.month)


class AgentError(RuntimeError):
    pass


class OllamaAgent:
    def __init__(self):
        self.settings = get_settings()

    def run(self, user_message: str, model: str | None = None) -> dict:
        model_name = model or self.settings.ollama_model
        messages = [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": user_message},
        ]
        trace = []

        for step in range(1, 7):
            response = self._chat(model_name, messages)
            assistant = response.get("message", {})
            calls = assistant.get("tool_calls") or []

            if not calls:
                return {
                    "answer": assistant.get("content", "").strip(),
                    "tool_trace": trace,
                    "requires_confirmation": any(x["requires_confirmation"] for x in trace),
                }

            messages.append(assistant)

            for call in calls:
                function = call.get("function", {})
                name = function.get("name")
                args = function.get("arguments") or {}

                if name not in FUNCTIONS:
                    raise AgentError(f"Model requested unknown tool: {name}")

                result = FUNCTIONS[name](**args)
                safe_result = redact_for_model(result)
                requires_confirmation = name == "propose_budget_change"

                trace.append({
                    "step": step,
                    "tool": name,
                    "arguments": args,
                    "result": safe_result,
                    "requires_confirmation": requires_confirmation,
                })

                messages.append({
                    "role": "tool",
                    "tool_name": name,
                    "content": json.dumps(safe_result),
                })

        return {
            "answer": "I could not complete the analysis within the agent step limit.",
            "tool_trace": trace,
            "requires_confirmation": any(x["requires_confirmation"] for x in trace),
        }

    def _chat(self, model: str, messages: list[dict]) -> dict:
        url = f"{self.settings.ollama_base_url.rstrip('/')}/api/chat"
        try:
            response = httpx.post(
                url,
                json={
                    "model": model,
                    "messages": messages,
                    "tools": TOOLS,
                    "stream": False,
                    "think": False,
                },
                timeout=self.settings.ollama_timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise AgentError(
                f"Could not reach local Ollama at {self.settings.ollama_base_url}. "
                f"Start Ollama and make sure model '{model}' is available."
            ) from exc
