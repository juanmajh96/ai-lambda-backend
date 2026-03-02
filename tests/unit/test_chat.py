"""Unit tests for POST /chat handler."""

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "ai-lambda-backend")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "AILambdaBackend")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("OPENAI_MODEL", "gpt-4o-mini")
os.environ.setdefault("OPENAI_MAX_TOKENS", "100")
os.environ.setdefault("OPENAI_TEMPERATURE", "0.7")


def _make_event(body: dict | None = None) -> dict:
    raw = json.dumps(body) if body is not None else None
    return {
        "version": "2.0",
        "routeKey": "POST /chat",
        "rawPath": "/chat",
        "rawQueryString": "",
        "headers": {"content-type": "application/json"},
        "requestContext": {
            "http": {"method": "POST", "path": "/chat"},
            "routeKey": "POST /chat",
        },
        "body": raw,
        "isBase64Encoded": False,
    }


def _make_context():
    class _Ctx:
        function_name = "ChatFunction"
        memory_limit_in_mb = 512
        invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:ChatFunction"
        aws_request_id = "test-request-id"

    return _Ctx()


def _mock_completion(content: str = "Hello!", total_tokens: int = 42):
    usage = SimpleNamespace(total_tokens=total_tokens, model_dump=lambda: {"total_tokens": total_tokens})
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=usage)


def _noop(self, fn=None, **kwargs):
    return fn if fn is not None else lambda f: f


def _noop_annotation(*a, **k):
    pass


_patches = [
    patch("aws_lambda_powertools.Tracer._patch_modules", lambda *a, **k: None),
    patch("aws_lambda_powertools.Tracer.capture_lambda_handler", _noop),
    patch("aws_lambda_powertools.Tracer.capture_method", _noop),
    patch("aws_lambda_powertools.Tracer.put_annotation", _noop_annotation),
    patch("aws_lambda_powertools.Metrics.log_metrics", lambda self, fn=None, **k: (fn if fn else lambda f: f)),
]


def _apply_patches(fn):
    for p in reversed(_patches):
        fn = p(fn)
    return fn


class TestChatSuccess:
    def setup_method(self):
        for mod in list(sys.modules):
            if mod.startswith("handlers.chat") or mod == "shared.openai_client":
                del sys.modules[mod]

    @_apply_patches
    def test_valid_messages_returns_200(self):
        import handlers.chat as chat_module
        chat_module.openai_client = MagicMock()
        chat_module.openai_client.chat.completions.create.return_value = _mock_completion("Hi!")

        response = chat_module.lambda_handler(
            _make_event({"messages": [{"role": "user", "content": "Hello"}]}),
            _make_context(),
        )
        assert response["statusCode"] == 200
        assert json.loads(response["body"])["message"] == "Hi!"

    @_apply_patches
    def test_response_includes_usage_and_model(self):
        import handlers.chat as chat_module
        chat_module.openai_client = MagicMock()
        chat_module.openai_client.chat.completions.create.return_value = _mock_completion(total_tokens=99)

        response = chat_module.lambda_handler(
            _make_event({"messages": [{"role": "user", "content": "Hi"}]}),
            _make_context(),
        )
        body = json.loads(response["body"])
        assert body["usage"]["total_tokens"] == 99
        assert "model" in body

    @_apply_patches
    def test_system_and_user_roles_accepted(self):
        import handlers.chat as chat_module
        chat_module.openai_client = MagicMock()
        chat_module.openai_client.chat.completions.create.return_value = _mock_completion()

        response = chat_module.lambda_handler(
            _make_event({
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Hello"},
                ]
            }),
            _make_context(),
        )
        assert response["statusCode"] == 200


class TestChatValidation:
    def setup_method(self):
        for mod in list(sys.modules):
            if mod.startswith("handlers.chat") or mod == "shared.openai_client":
                del sys.modules[mod]

    @_apply_patches
    def test_missing_messages_key_returns_400(self):
        import handlers.chat as chat_module
        chat_module.openai_client = MagicMock()
        assert chat_module.lambda_handler(_make_event({}), _make_context())["statusCode"] == 400

    @_apply_patches
    def test_empty_messages_list_returns_400(self):
        import handlers.chat as chat_module
        chat_module.openai_client = MagicMock()
        assert chat_module.lambda_handler(_make_event({"messages": []}), _make_context())["statusCode"] == 400

    @_apply_patches
    def test_invalid_role_returns_400(self):
        import handlers.chat as chat_module
        chat_module.openai_client = MagicMock()
        response = chat_module.lambda_handler(
            _make_event({"messages": [{"role": "hacker", "content": "pwn"}]}),
            _make_context(),
        )
        assert response["statusCode"] == 400

    @_apply_patches
    def test_whitespace_only_content_returns_400(self):
        import handlers.chat as chat_module
        chat_module.openai_client = MagicMock()
        response = chat_module.lambda_handler(
            _make_event({"messages": [{"role": "user", "content": "   "}]}),
            _make_context(),
        )
        assert response["statusCode"] == 400

    @_apply_patches
    def test_non_object_message_returns_400(self):
        import handlers.chat as chat_module
        chat_module.openai_client = MagicMock()
        response = chat_module.lambda_handler(
            _make_event({"messages": ["just a string"]}),
            _make_context(),
        )
        assert response["statusCode"] == 400


class TestChatOpenAIErrors:
    def setup_method(self):
        for mod in list(sys.modules):
            if mod.startswith("handlers.chat") or mod == "shared.openai_client":
                del sys.modules[mod]

    def _invoke(self, side_effect):
        import handlers.chat as chat_module
        chat_module.openai_client = MagicMock()
        chat_module.openai_client.chat.completions.create.side_effect = side_effect
        return chat_module.lambda_handler(
            _make_event({"messages": [{"role": "user", "content": "Hi"}]}),
            _make_context(),
        )

    @_apply_patches
    def test_rate_limit_returns_503(self):
        from openai import RateLimitError
        response = self._invoke(RateLimitError("rate limit", response=MagicMock(status_code=429), body={}))
        assert response["statusCode"] == 503

    @_apply_patches
    def test_connection_error_returns_503(self):
        from openai import APIConnectionError
        response = self._invoke(APIConnectionError(request=MagicMock()))
        assert response["statusCode"] == 503

    @_apply_patches
    def test_api_status_error_returns_503(self):
        from openai import APIStatusError
        response = self._invoke(
            APIStatusError("server error", response=MagicMock(status_code=500), body={})
        )
        assert response["statusCode"] == 503
