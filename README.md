# Telegram Subscription Bot

Minimal MVP Telegram bot that sells one fixed lifetime access product to a private Telegram guide channel.

The source of truth is:
- `mvp_scope.md`
- `system_design.md`
- `implementation_plan.md`

## Current MVP Focus

The current implementation focus is:
- real 2328 invoice flow;
- correct payment status processing;
- optional BTC/ETH auxiliary market-rate metadata from free public APIs;
- lifetime access delivery to one private channel.

The project does **not** target multi-plan logic, post-MVP tariff selection, renewals, or upgrade flows.
The runtime purchase flow is single-product only.
The legacy `plans` table is retained only as a one-row DB compatibility layer for existing foreign keys.

## Requirements

- Python 3.12+ for local runs
- Docker Engine with Docker Compose plugin for the default deployment flow

## Environment

Copy the example file first:

```bash
cp .env.example .env
```

Minimum required values:
- `BOT_TOKEN`
- `ADMIN_TG_ID`
- `PRIVATE_CHANNEL_ID`
- `APP_BASE_URL`
- `DATABASE_URL` or `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- the existing business/UI variables from `.env.example`

Additional required values for live 2328 flow:
- `MERCHANT_PROJECT_UUID`
- `MERCHANT_API_KEY`
- `PAYMENT_WEBHOOK_PATH`
- `PAYMENT_WEBHOOK_REGISTER_URL`

Recommended auxiliary rate configuration:
- primary source: CoinGecko
- fallback source: Binance public market data
- short timeout and short TTL cache

For the end-to-end MVP flow, the bot must be an admin in the private guide channel and have permission to:
- create invite links
- approve join requests
- decline join requests

## Run With Docker Compose

```bash
docker compose up --build
```

This starts:
- `db`: PostgreSQL 16 in a dedicated container with a named persistent volume
- `bot`: FastAPI + aiogram in one container
- Alembic migrations during bot startup

Health endpoint:

```text
GET /health
```

Webhook endpoint:

```text
POST {PAYMENT_WEBHOOK_PATH}
```

For live 2328 invoices, the webhook callback is passed per invoice in the create payment request as `url_callback`.
The app builds it from `APP_BASE_URL + PAYMENT_WEBHOOK_PATH`.

## Database Configuration

Preferred configuration:

```text
DATABASE_URL=postgresql+psycopg://bot:<password>@db:5432/ai_tg_bot
```

Equivalent decomposed variables:
- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`

Inside Docker Compose, the bot connects to PostgreSQL through the Docker network hostname `db`.

## Migrations

The bot container runs `alembic upgrade head` on startup and fails if migrations cannot be applied.

Run migrations manually:

```bash
docker compose run --rm bot alembic upgrade head
```

Open a `psql` shell in the database container:

```bash
docker compose exec db psql -U "$DB_USER" -d "$DB_NAME"
```

## Local Python Run

If you want to run the app directly on the host, point `DATABASE_URL` at a reachable PostgreSQL instance first.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python main.py
```

## Pricing Rules

The canonical product price is stored in USD.

Invoice amount rules:
- the canonical product price is stored in USD and that USD amount is sent to 2328 at invoice creation;
- `payer_amount` is the provider-returned payable crypto amount for the created invoice;
- for `BTC` and `ETH`, external market-rate fetching is auxiliary audit/preview data and must not override the actual provider invoice amount.

The canonical default webhook path is:

```text
/webhooks/2328
```

## Local Webhook

Expose the local API port with one of these commands:

```bash
ngrok http 8000
```

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

Final 2328 callback URL format:

```text
https://<public-host>/webhooks/2328
```

The checked-in 2328 reference documents `url_callback` for invoice creation, but does not document a merchant-level webhook registration endpoint. For that reason, `PAYMENT_WEBHOOK_REGISTER_URL` remains explicit and must point to the correct 2328 endpoint for your account/integration when `PAYMENT_PROVIDER_MODE=live`.

## Local Testing Guidance

Suggested test sequence:
1. Start the app.
2. Open the bot and use `/start`.
3. Go through the fixed product purchase flow.
4. Create an invoice in each supported currency.
5. Verify that the USD order amount is the canonical invoice input and `payer_amount` is the provider-returned payable amount.
6. Verify that auxiliary BTC/ETH rate metadata, if available, does not override provider invoice creation.
7. Verify payment success processing.
8. Use the delivered invite link from the same Telegram account to submit a join request to the private channel.

## MVP Result

The MVP is considered correct when:
- the bot sells exactly one fixed lifetime access product;
- 2328 invoice creation and status checks work;
- BTC/ETH market-rate metadata is auxiliary only and does not override the provider invoice amount;
- access is granted exactly once after successful payment.
