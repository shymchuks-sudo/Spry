import base64
import json
import logging
import os
import time
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import jwt
from anthropic import APIError, RateLimitError
from jwt import PyJWKClient

from app.ai.agenda import PARSER_MODEL, PROMPT_VERSION, AgendaParseError, parse_agenda

log = logging.getLogger()
log.setLevel(logging.INFO)

REGION = os.environ.get("COGNITO_REGION", "us-east-1")
USER_POOL_ID = os.environ["USER_POOL_ID"]
APP_CLIENT_ID = os.environ["APP_CLIENT_ID"]
ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"
_jwks = PyJWKClient(f"{ISSUER}/.well-known/jwks.json", cache_keys=True)  # keys are cached

MAX_TEXT = 10_000

# USD per million tokens (input, output). Check against the prices in Part 1 of the lab:
# 1.00 / 5.00 is my assumption for Haiku 4.5.
PRICES = {"us.anthropic.claude-haiku-4-5-20251001-v1:0": (1.00, 5.00)}


class Unauthorized(Exception):
    pass


def verify_cognito_token(auth_header: str) -> dict:
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise Unauthorized("missing bearer token")
    try:
        key = _jwks.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=ISSUER,
            options={"require": ["exp", "iss", "sub"], "verify_aud": False},
        )
    except jwt.PyJWTError as e:
        raise Unauthorized(str(e)) from e
    # access tokens carry client_id, not aud
    if claims.get("token_use") != "access" or claims.get("client_id") != APP_CLIENT_ID:
        raise Unauthorized("wrong token")
    return claims


def cost_usd(model: str, usage: dict) -> float | None:
    price = PRICES.get(model)
    if price is None:
        return None
    total = usage["input_tokens"] * price[0] + usage["output_tokens"] * price[1]
    return round(total / 1_000_000, 6)


def _response(status: int, payload: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload, ensure_ascii=False),
    }


def handler(event, context):
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    try:
        user = verify_cognito_token(headers.get("authorization", ""))
    except Unauthorized:
        return _response(401, {"error": "unauthorized"})

    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    try:
        body = json.loads(raw)
        text = body["text"]
        today = date.fromisoformat(body["today"])
        tz = body["tz"]
        ZoneInfo(tz)
    except (ValueError, KeyError, TypeError, ZoneInfoNotFoundError):
        return _response(400, {"error": "expected JSON with text, today (YYYY-MM-DD) and tz"})
    if not isinstance(text, str) or not text.strip():
        return _response(400, {"error": "text is empty"})
    if len(text) > MAX_TEXT:
        return _response(413, {"error": f"text is longer than {MAX_TEXT} characters"})

    started = time.monotonic()
    try:
        agenda, usage = parse_agenda(text, today, tz)
    except AgendaParseError as e:
        return _response(422, {"error": str(e)})
    except RateLimitError:
        return _response(429, {"error": "the service is busy, try again in a minute"})
    except APIError:
        log.exception("model call failed")
        return _response(502, {"error": "the model is not available"})

    log.info(
        json.dumps(
            {
                "event": "agenda_parsed",
                "user": user["sub"],
                "model": PARSER_MODEL,
                "prompt_version": PROMPT_VERSION,
                **usage,
                "latency_ms": int((time.monotonic() - started) * 1000),
                "cost_usd": cost_usd(PARSER_MODEL, usage),
            }
        )
    )
    return _response(
        200,
        {
            "agenda": agenda.model_dump(mode="json"),
            "model": PARSER_MODEL,
            "prompt_version": PROMPT_VERSION,
        },
    )
