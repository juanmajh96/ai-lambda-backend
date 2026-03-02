"""Unit tests for GET /health handler."""

import json
import os
import sys
from unittest.mock import patch

# Ensure src/ is on sys.path so handlers can be imported without the Lambda layer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "ai-lambda-backend")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "AILambdaBackend")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


def _make_event(method: str = "GET", path: str = "/health") -> dict:
    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"content-type": "application/json"},
        "requestContext": {
            "http": {"method": method, "path": path},
            "routeKey": f"{method} {path}",
        },
        "isBase64Encoded": False,
    }


def _make_context():
    class _Ctx:
        function_name = "HealthFunction"
        memory_limit_in_mb = 256
        invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:HealthFunction"
        aws_request_id = "test-request-id"

    return _Ctx()


def _noop_decorator(self, fn=None, **kwargs):
    return fn if fn is not None else lambda f: f


class TestHealthHandler:
    def setup_method(self):
        for mod in list(sys.modules):
            if "handlers.health" in mod:
                del sys.modules[mod]

    @patch("aws_lambda_powertools.Tracer._patch_modules", lambda *a, **k: None)
    @patch("aws_lambda_powertools.Tracer.capture_lambda_handler", _noop_decorator)
    @patch("aws_lambda_powertools.Tracer.capture_method", _noop_decorator)
    @patch("aws_lambda_powertools.Metrics.log_metrics", lambda self, fn=None, **k: (fn if fn else lambda f: f))
    def test_health_returns_200(self):
        import handlers.health as health_module
        response = health_module.lambda_handler(_make_event(), _make_context())
        assert response["statusCode"] == 200

    @patch("aws_lambda_powertools.Tracer._patch_modules", lambda *a, **k: None)
    @patch("aws_lambda_powertools.Tracer.capture_lambda_handler", _noop_decorator)
    @patch("aws_lambda_powertools.Tracer.capture_method", _noop_decorator)
    @patch("aws_lambda_powertools.Metrics.log_metrics", lambda self, fn=None, **k: (fn if fn else lambda f: f))
    def test_health_body_structure(self):
        import handlers.health as health_module
        response = health_module.lambda_handler(_make_event(), _make_context())
        body = json.loads(response["body"])
        assert body["status"] == "healthy"
        assert "service" in body
        assert body["version"] == "1.0.0"
