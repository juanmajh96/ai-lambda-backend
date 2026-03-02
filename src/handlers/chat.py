"""
POST /chat — OpenAI Chat Completions handler.

Validates the incoming message list, calls OpenAI, records Powertools
metrics + X-Ray annotations, and returns the assistant reply.
"""

import os
from typing import Any

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver
from aws_lambda_powertools.event_handler.exceptions import BadRequestError, ServiceUnavailableError
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from openai import APIConnectionError, APIStatusError, RateLimitError

from shared.openai_client import openai_client

logger = Logger()
tracer = Tracer()
metrics = Metrics()
app = APIGatewayHttpResolver()

ALLOWED_ROLES = {"system", "user", "assistant"}


# ── Route ──────────────────────────────────────────────────────────────────────

@app.post("/chat")
@tracer.capture_method
def chat() -> dict[str, Any]:
    body: dict = app.current_event.json_body or {}

    messages = body.get("messages")
    if not messages or not isinstance(messages, list):
        raise BadRequestError("'messages' must be a non-empty list")

    _validate_messages(messages)

    model = body.get("model") or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    max_tokens = int(body.get("max_tokens") or os.environ.get("OPENAI_MAX_TOKENS", "2048"))
    temperature = float(body.get("temperature") or os.environ.get("OPENAI_TEMPERATURE", "0.7"))

    tracer.put_annotation(key="model", value=model)
    tracer.put_annotation(key="message_count", value=len(messages))

    response_content, usage = _call_openai(messages, model, max_tokens, temperature)

    metrics.add_metric(name="SuccessfulChatCompletions", unit=MetricUnit.Count, value=1)
    if usage:
        metrics.add_metric(name="TokensUsed", unit=MetricUnit.Count, value=usage.get("total_tokens", 0))

    return {
        "message": response_content,
        "usage": usage,
        "model": model,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _validate_messages(messages: list) -> None:
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            raise BadRequestError(f"messages[{i}] must be an object")
        role = msg.get("role")
        content = msg.get("content")
        if role not in ALLOWED_ROLES:
            raise BadRequestError(
                f"messages[{i}].role must be one of {sorted(ALLOWED_ROLES)}, got '{role}'"
            )
        if not isinstance(content, str) or not content.strip():
            raise BadRequestError(f"messages[{i}].content must be a non-empty string")


@tracer.capture_method
def _call_openai(
    messages: list,
    model: str,
    max_tokens: int,
    temperature: float,
) -> tuple[str, dict | None]:
    if openai_client is None:
        raise ServiceUnavailableError("OpenAI client is not available — check secret configuration")

    try:
        completion = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = completion.choices[0].message.content or ""
        usage = completion.usage.model_dump() if completion.usage else None
        return content, usage

    except RateLimitError as exc:
        logger.warning("OpenAI rate limit exceeded", extra={"error": str(exc)})
        metrics.add_metric(name="RateLimitErrors", unit=MetricUnit.Count, value=1)
        raise ServiceUnavailableError("OpenAI rate limit exceeded — please retry") from exc

    except APIConnectionError as exc:
        logger.error("OpenAI connection error", extra={"error": str(exc)})
        metrics.add_metric(name="ConnectionErrors", unit=MetricUnit.Count, value=1)
        raise ServiceUnavailableError("Could not reach OpenAI API") from exc

    except APIStatusError as exc:
        logger.error(
            "OpenAI API status error",
            extra={"status_code": exc.status_code, "error": str(exc)},
        )
        metrics.add_metric(name="APIStatusErrors", unit=MetricUnit.Count, value=1)
        raise ServiceUnavailableError(f"OpenAI API error: {exc.status_code}") from exc


# ── Lambda handler ─────────────────────────────────────────────────────────────

@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
