"""
GET /health — liveness probe handler.
"""

import os
from typing import Any

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
tracer = Tracer()
metrics = Metrics()
app = APIGatewayHttpResolver()


@app.get("/health")
@tracer.capture_method
def health() -> dict[str, Any]:
    metrics.add_metric(name="HealthCheckInvocations", unit=MetricUnit.Count, value=1)
    return {
        "status": "healthy",
        "service": os.environ.get("POWERTOOLS_SERVICE_NAME", "ai-lambda-backend"),
        "version": "1.0.0",
    }


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
