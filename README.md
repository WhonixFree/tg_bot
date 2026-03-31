# Telegram Subscription Bot

Minimal bootstrap for the MVP Telegram subscription bot described in `mvp_scope.md`, `system_design.md`, and `implementation_plan.md`.

## Requirements

- Python 3.12+

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Update `.env` with a real Telegram bot token and your project values. `PAYMENT_PROVIDER_MODE=mock` is the default and does not require 2328 merchant credentials. `PAYMENT_PROVIDER_MODE=live` requires both `MERCHANT_PROJECT_UUID` and `MERCHANT_API_KEY`.

For the end-to-end MVP flow, the bot must be an admin in the private guide channel and have permission to:
- create invite links
- approve join requests
- decline join requests

## Run

```bash
alembic upgrade head
python main.py
```

This starts:

- FastAPI on `API_HOST:API_PORT`
- Telegram long polling in the same process
- Mock payment flow by default

Health endpoint:

```text
GET /health
```

Webhook endpoint:

```text
POST {PAYMENT_WEBHOOK_PATH}
```

## Alembic

Apply the existing schema before using the bot flow:

```bash
alembic upgrade head
```

## Testing In Mock Mode

1. Set `PAYMENT_PROVIDER_MODE=mock` in `.env`.
2. Run `alembic upgrade head`.
3. Start the app with `python main.py`.
4. Open the bot and use `/start`.
5. Complete the buy flow and create an invoice.
6. Press `I've paid` twice to move the mock payment from `check` to `paid`.
7. Use the delivered invite link from the same Telegram account to submit a join request to the private channel.

Live 2328 gateway code and webhook verification are present in the codebase, but live mode is not intended for use until the merchant project is approved and credentials are ready.
