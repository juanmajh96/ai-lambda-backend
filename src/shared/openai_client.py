"""
OpenAI client singleton — initialised once on cold start.

Reads OPENAI_API_KEY_SECRET_ARN from the environment, fetches the secret
from AWS Secrets Manager, and constructs an openai.OpenAI instance that is
reused across warm invocations.
"""

import json
import os

import boto3
from aws_lambda_powertools import Logger
from openai import OpenAI

logger = Logger(child=True)

_PLACEHOLDER = "PLACEHOLDER_REPLACE_AFTER_DEPLOY"


def _fetch_api_key() -> str:
    secret_arn = os.environ.get("OPENAI_API_KEY_SECRET_ARN", "")
    if not secret_arn:
        raise RuntimeError("OPENAI_API_KEY_SECRET_ARN environment variable is not set")

    sm = boto3.client("secretsmanager")
    response = sm.get_secret_value(SecretId=secret_arn)

    raw = response.get("SecretString", "")
    if not raw:
        raise RuntimeError("SecretsManager returned an empty secret")

    try:
        secret_dict = json.loads(raw)
        api_key = secret_dict["openai_api_key"]
    except (json.JSONDecodeError, KeyError) as exc:
        raise RuntimeError(f"Secret is not in expected format {{\"openai_api_key\": \"...\"}}: {exc}") from exc

    if not api_key or api_key == _PLACEHOLDER:
        raise RuntimeError(
            "OpenAI API key is still the deployment placeholder. "
            "Run `make update-secret` or update the secret manually."
        )

    return api_key


def _build_client() -> "OpenAI | None":
    """Return an OpenAI client, or None if the secret ARN is not configured."""
    arn = os.environ.get("OPENAI_API_KEY_SECRET_ARN", "")
    if not arn:
        return None
    try:
        api_key = _fetch_api_key()
        logger.info("OpenAI client initialised on cold start")
        return OpenAI(api_key=api_key)
    except Exception:
        logger.exception("Failed to initialise OpenAI client during cold start")
        raise


# Module-level singleton — evaluated once per container lifetime.
openai_client: "OpenAI | None" = _build_client()
