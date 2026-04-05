# System Design — Telegram Bot for Selling Channel Access

## 1. Purpose

This document defines the target architecture for an MVP Telegram bot that sells paid lifetime access to one private Telegram channel using crypto payments via 2328.io.

The document is written to be used by code generation tools and developers as the source of truth for implementation decisions.

## 2. Product Context

### 2.1 Business goal
The bot sells access to a private Telegram channel with guide content.

### 2.2 Scope for MVP
The product has exactly **one fixed offer**:
- one-time payment;
- lifetime access;
- access to one private Telegram channel with the guide.

There is no tariff matrix, no multi-plan catalog, and no post-MVP plan-selection logic in this scope.

### 2.3 Fixed commercial model
For the current project stage, Codex must treat the product as a single immutable commercial offer.

Implementation rules:
- do not design multiple subscription plans;
- do not add Tier_1 / Tier_2 switching;
- do not add hidden abstractions for future tariff selection unless they are strictly required by existing code;
- do not add renewal periods, monthly billing, upgrade flows, downgrade flows, or plan comparison UI.

Use one product constant such as:
- `PRODUCT_CODE = GUIDE_ACCESS_LIFETIME`
- `PRODUCT_PRICE_USD = <configured_value>`

Current implementation note:
- runtime purchase/payment flow must use one fixed product service;
- if a legacy `plans` table still exists, keep only one seeded compatibility row instead of a runtime plan catalog.

## 3. High-Level Decisions

### 3.1 Tech stack
Recommended stack:
- Python 3.12+
- aiogram 3.x for Telegram bot
- FastAPI for webhook HTTP server and internal admin endpoints if needed
- SQLAlchemy 2.x ORM
- SQLite for MVP persistence
- APScheduler or simple async background jobs only where needed for invoice/payment flow
- Docker for deployment
- httpx for external HTTP calls to 2328 and public rate APIs

### 3.2 Runtime model
A single project instance runs as **one container named `bot`** containing:
- Telegram bot handlers
- FastAPI app for 2328 webhook endpoint
- background jobs
- business logic/services
- SQLite database file mounted as Docker volume

This design must keep each bot instance self-contained.
If later there are RU and EN bots, they should run as separate copies of the same project with:
- separate `.env`
- separate SQLite file
- separate Telegram bot token
- separate 2328 project credentials

No runtime coupling between bot instances should be required.

### 3.3 Telegram updates mode
Use **long polling** for Telegram updates.
Do not require Telegram webhook.

### 3.4 Payments model
Use only **2328 Payment API**:
- create invoice with `POST /v1/payment`
- check status with `POST /v1/payment/info`
- receive async updates through `url_callback`

Do **not** implement:
- payout API
- static wallets
- Telegram Stars / Telegram-native subscription billing

### 3.5 Market rate model for BTC and ETH
USD remains the canonical product price.

Invoice amount rules:
- the canonical product price is stored in USD and that USD amount is the invoice input sent to 2328;
- the provider response defines the payable crypto amount as `payer_amount`;
- for `BTC` and `ETH`, public market-rate fetching is auxiliary preview/validation/audit data only;
- local BTC/ETH rate data must not override the actual provider-created invoice amount unless the provider contract explicitly supports a fixed crypto amount field and that behavior is confirmed as required.

The project must include a dedicated rate service with fallback sources.

## 4. External Integrations

### 4.1 Telegram Bot API
The bot interacts with:
- private chat with the user
- private Telegram channel
- join requests for access approval

Bot requirements in the private channel:
- bot must be admin
- bot must be able to create invite links
- bot must be able to approve/decline join requests

### 4.2 2328.io
Use 2328 hosted invoice flow, but present payment details inside Telegram.

Required request headers for API calls:
- `Content-Type: application/json`
- `project: <MERCHANT_PROJECT_UUID>`
- `sign: <HMAC_SHA256_BASE64_JSON_SIGNATURE>`

Webhook security requirements:
- verify `sign`
- process idempotently
- return HTTP 200 quickly

### 4.3 Public crypto rate APIs
The bot may use free public market-data APIs for BTC and ETH preview/validation/audit metadata.

Recommended source policy:
- primary source: CoinGecko simple price API;
- fallback source: Binance public spot market data API;
- optional extra fallback may be added later if needed.

Supported rate lookups:
- BTC/USD
- ETH/USD

Operational rules:
- fetch a fresh rate only if auxiliary preview/validation/audit data is needed for `BTC` or `ETH`;
- cache rates only for a short TTL (for example 30–60 seconds) to reduce external calls;
- if all rate sources fail, the provider invoice may still be created from the canonical USD amount;
- store the rate source, raw response, fetched timestamp, and any locally derived audit conversion data in DB without replacing the provider invoice amount.

## 5. Payment Model

### 5.1 Supported currencies for MVP
Supported coins:
- USDT
- USDC
- BTC
- ETH

### 5.2 Supported networks for MVP
Currency/network mapping is static in the project config or database seed data.
Do not fetch it dynamically from 2328.

Mapping:
- USDT:
  - TRX-TRC20
  - BSC-BEP20
  - ETH-ERC20
  - AVAX-C
  - POL-MATIC
  - TON
- USDC:
  - BSC-BEP20
  - ETH-ERC20
  - AVAX-C
  - POL-MATIC
- BTC:
  - BTC
- ETH:
  - ETH-ERC20

### 5.3 Canonical pricing currency
The product price is stored in **USD**.
USD is the only authoritative business price.

### 5.4 Conversion rules
Conversion rules by selected coin:
- `USDT` -> `amount_coin = amount_usd`
- `USDC` -> `amount_coin = amount_usd`
- `BTC` -> `amount_coin = amount_usd / btc_usd_rate`
- `ETH` -> `amount_coin = amount_usd / eth_usd_rate`

These formulas are for auxiliary local preview/audit only unless 2328 explicitly supports fixed coin-amount invoice creation and that mode is intentionally enabled.

Rounding rules:
- for `BTC` and `ETH`, round **up** to the supported invoice precision so the user is never asked to send less than required;
- keep the rounding rule stable and deterministic;
- store both pre-rounded and final rounded values in the payment record.

### 5.5 Active invoice policy
At most **one active unpaid invoice per user** is allowed.

If the user tries to buy again and there is an active unpaid invoice that is not expired:
- do not create a new invoice;
- show the existing invoice instead.

If the existing invoice was created in `BTC` or `ETH`, reuse the already locked amount and locked exchange rate.

### 5.6 Invoice expiration behavior
When invoice expires:
- remove the invoice message from chat if still present;
- show a new screen stating the invoice expired;
- warn the user not to send funds to the old address;
- allow creating a new invoice.

A new invoice created after expiration must fetch a new BTC/ETH rate if the user selects BTC or ETH again.

## 6. Access Model

### 6.1 MVP access shape
The product is a lifetime purchase in MVP.
Access records should therefore support `expires_at = NULL` for lifetime access.

### 6.2 Access scope for MVP
MVP grants access only to one private guide channel.

### 6.3 Explicit simplification
Do not build generalized plan management for the current project stage.
The access model exists only to represent the purchased lifetime access state.

## 7. User Experience and Screen Contracts

The bot should keep the chat clean.

### 7.1 Single-message policy
For normal user flow, the bot should aim to keep only the latest bot message visible.

Mechanism:
- store `last_bot_message_id` for each user
- before sending a new UI screen, try to delete the previous bot message
- then send the new message
- store the new message id

Do not build a complex message-editing architecture for MVP.
Prefer delete-and-send.

### 7.2 Content format rules
- Main Menu: `photo + caption + inline keyboard`
- Invoice screen: `photo + caption + inline keyboard`
- Other screens: regular text message or photo if needed

## 8. User Flow

### 8.1 Main Menu
Content:
- project description
- free channel link in caption text
- manager contact in caption text
- access status if any

Buttons for regular user:
- row 1: `[Buy access]` or `[My access]`

Buttons for admin:
- row 1: `[Admin panel]`

### 8.2 Offer Confirmation
The project has one fixed product path.
No tariff selection screen is needed.

Show:
- product name
- lifetime access note
- price in USD

Buttons:
- row 1: `[Continue to payment]`
- row 2: `[Main Menu]`

### 8.3 Choose Coin
Buttons:
- row 1: `[USDT] [USDC]`
- row 2: `[BTC] [ETH]`
- row 3: `[Main Menu]`

### 8.4 Choose Network
If selected coin has multiple supported networks, show a network selection screen.
If selected coin has only one supported network, assign it automatically and skip this screen.

For USDT:
- row 1: `[TRC20] [BEP20] [ERC20]`
- row 2: `[AVAX] [MATIC] [TON]`

For USDC:
- row 1: `[BEP20] [ERC20]`
- row 2: `[AVAX] [MATIC]`

BTC and ETH skip this screen.

Internal mapping from button labels to API values:
- TRC20 -> TRX-TRC20
- BEP20 -> BSC-BEP20
- ERC20 -> ETH-ERC20
- AVAX -> AVAX-C
- MATIC -> POL-MATIC
- TON -> TON
- BTC -> BTC

### 8.5 Order Summary
Show:
- product name
- price in USD
- selected coin
- selected network
- for BTC/ETH: locked market rate source and converted amount

Buttons:
- row 1: `[Create invoice]`
- row 2: `[Main Menu]`

### 8.6 Active Invoice Screen
After invoice creation, show:
- QR image
- exact amount to send
- coin
- network
- address
- valid until timestamp
- note that address is valid only until expiration
- note to send exact amount on correct network
- for BTC/ETH: short line like `Rate locked at invoice creation`

Buttons:
- row 1: `[I've paid]`
- row 2: `[Refresh status] [Cancel invoice]`
- row 3: `[Main Menu]`

Behavior:
- `I've paid` -> calls payment status check immediately
- `Refresh status` -> checks status without claiming payment was made
- `Cancel invoice` -> marks invoice locally as abandoned and returns to a non-invoice screen
- `Main Menu` -> delete invoice message from chat, keep invoice in DB if still active

### 8.7 Pending Payment Result Screen
If payment is still not detected, send a new message like:
- payment not detected yet
- invoice still valid until X
- blockchain confirmations may take time

Buttons:
- row 1: `[Refresh status]`
- row 2: `[Main Menu]`

### 8.8 Expired Invoice Screen
Show:
- invoice expired
- do not send funds to the old address
- create new invoice to continue

Buttons:
- row 1: `[Create new invoice]`
- row 2: `[Main Menu]`

### 8.9 Payment Success / Access Screen
After successful payment, show one combined message:
- payment confirmed
- lifetime access activated
- use the access link from the same Telegram account that completed the purchase
- include the invite link directly in the message text

Buttons:
- row 1: `[Main Menu] [My access]`

## 9. Access Control Design

### 9.1 Channel access strategy
Use a private channel with join requests.

Create invite links with:
- `creates_join_request = true`

The invite link is bound logically to one user access record.

### 9.2 Access approval rule
When a join request is received:
- if requester Telegram ID equals the owner of the active paid access -> approve
- otherwise -> decline and log the event for admin review

### 9.3 Wrong account behavior
If another Telegram account uses the link:
- decline join request
- keep the same invite link logic for MVP
- notify admin about attempted access from another ID

### 9.4 MVP access behavior
The purchase grants lifetime access.
Do not implement time-based access expiration or automatic channel removal.

## 10. Payment State Machine

### 10.1 Local invoice states
Suggested local states:
- `created`
- `waiting_payment`
- `paid`
- `overpaid`
- `underpaid_check`
- `underpaid`
- `cancelled`
- `aml_locked`
- `expired`
- `abandoned`

### 10.2 Mapping from 2328 statuses
Map 2328 statuses to local behavior:
- `pending` -> waiting_payment
- `check` -> waiting_payment
- `paid` -> paid and activate access
- `overpaid` -> overpaid and activate access
- `underpaid_check` -> underpaid_check, no activation
- `underpaid` -> underpaid, no activation
- `cancel` -> cancelled/expired, no activation
- `aml_lock` -> aml_locked, no activation

### 10.3 Source of truth
Payment status may be updated by:
- webhook from 2328
- manual status check via `/v1/payment/info`

Both must call the same idempotent application service.

## 11. Background Jobs

### 11.1 Invoice watcher / cleanup
Responsibilities:
- mark expired invoices locally when `expires_at < now`
- optionally delete stale invoice messages if needed

### 11.2 Rate cache cleanup
If a local short-term cache is used for BTC/ETH rates:
- clean stale cache entries safely;
- do not let cache state become the source of truth for existing invoices.

## 12. Admin Panel in Bot

Admin is a single configured Telegram ID.
No multi-admin role system.

### 12.1 Admin main menu
Buttons may include:
- users
- payments
- search user
- grant access
- revoke access
- resend access link
- grant without payment

### 12.2 Minimal admin actions
Required admin capabilities:
- list recent users
- search by telegram ID or username
- list recent payments
- revoke access
- resend access link
- grant access without payment
- view user status and audit trail

### 12.3 Admin notifications
Send admin notifications for:
- successful payment
- underpaid / aml locked payment
- wrong-account join request attempt
- market-rate lookup failure for BTC/ETH invoice creation if repeated or critical
- manual admin action completion

## 13. Data Model

Suggested tables:

### 13.1 `users`
Fields:
- `id`
- `telegram_user_id` (unique)
- `username`
- `first_name`
- `last_name`
- `is_admin`
- `created_at`
- `updated_at`

### 13.2 `product_config`
Use either one DB row or static config for the current commercial offer.

Required fields if stored in DB:
- `id`
- `product_code` (`GUIDE_ACCESS_LIFETIME`)
- `display_name`
- `description`
- `price_usd`
- `is_active`
- `created_at`
- `updated_at`

If static config is simpler, Codex may skip this table and keep the product in config.

Current compatibility rule:
- if existing migrations already use `plans`, `orders.plan_id`, and `subscriptions.plan_id`, keep them temporarily;
- seed exactly one row for `GUIDE_ACCESS_LIFETIME`;
- do not expose plan selection or multi-plan runtime logic.

### 13.3 `supported_currencies`
Fields:
- `id`
- `code` (USDT, USDC, BTC, ETH)
- `is_active`

### 13.4 `supported_networks`
Fields:
- `id`
- `currency_code`
- `network_code`
- `display_name`
- `sort_order`
- `is_active`

### 13.5 `access_grants`
Fields:
- `id`
- `user_id`
- `status` (`active`, `revoked`)
- `is_lifetime`
- `starts_at`
- `expires_at` nullable
- `granted_by_admin`
- `created_at`
- `updated_at`

### 13.6 `orders`
Fields:
- `id`
- `user_id`
- `order_id` (internal unique order id)
- `product_code`
- `amount_usd`
- `selected_currency`
- `selected_network`
- `payment_provider`
- `status`
- `created_at`
- `updated_at`

### 13.7 `payments`
Fields:
- `id`
- `order_id`
- `provider_payment_uuid`
- `provider_status`
- `payer_currency`
- `payer_amount`
- `network`
- `address`
- `provider_url`
- `qr_data_uri`
- `expires_at`
- `txid`
- `rate_source` nullable
- `rate_base_currency` nullable (`USD`)
- `rate_quote_currency` nullable (`BTC` or `ETH`)
- `rate_value_usd` nullable
- `rate_fetched_at` nullable
- `amount_before_rounding` nullable
- `raw_payload_json`
- `paid_at`
- `created_at`
- `updated_at`

Constraints:
- unique on `provider_payment_uuid`
- unique on internal `order_id`

### 13.8 `access_links`
Fields:
- `id`
- `user_id`
- `access_grant_id`
- `telegram_invite_link`
- `telegram_invite_link_name`
- `is_active`
- `created_at`
- `revoked_at`

### 13.9 `join_request_logs`
Fields:
- `id`
- `access_grant_id`
- `invite_link`
- `requested_by_telegram_user_id`
- `owner_telegram_user_id`
- `decision` (`approved`, `declined`)
- `reason`
- `created_at`

### 13.10 `bot_messages`
Fields:
- `id`
- `user_id`
- `chat_id`
- `last_bot_message_id`
- `last_screen`
- `updated_at`

### 13.11 `admin_audit_logs`
Fields:
- `id`
- `admin_telegram_user_id`
- `target_user_id`
- `action`
- `details_json`
- `created_at`

## 14. Internal Services

Suggested service layer:

### 14.1 `MessageService`
Responsibilities:
- send screen to user
- delete previous bot message if exists
- store latest message id

### 14.2 `PaymentProvider2328Service`
Responsibilities:
- sign requests
- create invoice
- check payment status
- verify webhook signature
- normalize 2328 payloads to internal DTOs

### 14.3 `CryptoRateService`
Responsibilities:
- fetch BTC/USD and ETH/USD rates from configured public APIs
- apply fallback policy
- validate freshness
- cache short-lived results
- normalize external payloads to internal DTOs
- return deterministic converted invoice amount

### 14.4 `OrderService`
Responsibilities:
- create internal order
- enforce one active unpaid invoice per user
- mark invoice abandoned/expired
- lock conversion data to the order/payment at invoice creation time

### 14.5 `AccessService`
Responsibilities:
- activate lifetime access
- create Telegram invite link
- process join requests
- approve/decline based on Telegram ID
- resend access link

### 14.6 `AdminService`
Responsibilities:
- admin searches
- grants without payment
- revoke access
- audit logging

## 15. API Endpoints (Internal HTTP)

FastAPI should expose at least:
- `POST /webhooks/2328` — 2328 payment webhook
- `GET /health` — health endpoint for container/liveness

Optional internal endpoints may be added later, but not required for MVP.

## 16. Security Requirements

### 16.1 Secrets
Use environment variables for:
- `BOT_TOKEN`
- `ADMIN_TG_ID`
- `CHANNEL_ID`
- `BOT_USERNAME`
- `APP_BASE_URL`
- `PAY2328_PROJECT_UUID`
- `PAY2328_API_KEY`
- `DB_PATH`
- `TZ`

Optional environment variables for rate integration:
- `RATE_API_TIMEOUT_SECONDS`
- `RATE_CACHE_TTL_SECONDS`
- `COINGECKO_BASE_URL`
- `BINANCE_BASE_URL`

### 16.2 Payment webhook verification
Always verify webhook signature before any processing.
Reject invalid signature with 401.

### 16.3 Idempotency
Webhook and manual status checks must be idempotent.
A payment/order must not activate access more than once.

### 16.4 Input validation
Validate:
- supported currency
- supported network for selected currency
- active access before access actions
- admin permissions before admin actions

### 16.5 Market-rate safety
Validate:
- rate timestamp freshness before invoice creation
- source response contains expected symbol/currency
- converted amount is positive
- fallback source usage is logged

## 17. Deployment Design

### 17.1 Container
One Docker image / one bot container.

### 17.2 Persistent data
Mount a Docker volume for SQLite database and local app data if needed.

### 17.3 Public access
The container must be reachable through HTTPS for 2328 webhook callback.
Typical production setup:
- VPS
- Docker container running the bot app
- reverse proxy such as Nginx or Caddy
- HTTPS certificate

### 17.4 Multi-project deployment
If later deploying RU and EN versions on one VPS:
- run two independent bot containers
- expose different webhook paths or hostnames
- keep separate `.env` and database file per container

## 18. Error Handling Rules

### 18.1 Payment creation failure
If 2328 invoice creation fails:
- show generic payment creation error
- allow returning to main menu
- do not leave partial order in inconsistent state

### 18.2 Rate fetch failure for BTC/ETH
If the bot cannot fetch a valid BTC/ETH market rate from any configured source:
- do not create the invoice;
- show a temporary error;
- allow retry;
- allow the user to choose another coin.

### 18.3 Wrong-account access attempt
If join request comes from a different Telegram ID:
- decline request
- log the attempt
- notify admin

### 18.4 User sends payment after expiration
Bot cannot prevent blockchain transfer after expiration.
Therefore invoice screen must clearly show expiration time.
If payment arrives after expiration but provider still reports success, processing must follow provider status and internal business rule defined in code.
For MVP, rely on provider final status and idempotent order processing.

### 18.5 Duplicate webhooks
Must be harmless.
Do not grant access twice.

## 19. Folder Structure Suggestion

```text
project/
  app/
    api/
      routes/
        webhook_2328.py
        health.py
    bot/
      handlers/
      keyboards/
      screens/
      middlewares/
    core/
      config.py
      logging.py
      enums.py
    db/
      models/
      repositories/
      session.py
      migrations/
      seed.py
    services/
      message_service.py
      payment_2328_service.py
      crypto_rate_service.py
      order_service.py
      access_service.py
      admin_service.py
    jobs/
      invoice_jobs.py
    main.py
  docker/
  Dockerfile
  docker-compose.yml
  .env.example
  README.md
```

## 20. Non-Goals

The following are intentionally excluded from MVP and this implementation phase:
- any multi-plan runtime implementation
- any post-MVP tariff architecture work beyond what is strictly necessary for clean current code
- payout API
- static wallets
- monthly subscriptions and renewals
- dynamic sync of supported currencies/networks from provider
- multi-admin roles and permissions
- tariff editing from admin panel
- advanced analytics/dashboard
- separate microservices

## 21. Implementation Priority

Recommended build order:
1. project skeleton, config, DB
2. user screens and message lifecycle
3. fixed-product purchase flow
4. BTC/ETH rate service and conversion locking
5. 2328 invoice creation and status checks
6. webhook endpoint and idempotent payment processing
7. lifetime access activation logic
8. Telegram access link generation and join-request approval
9. admin panel features
10. hardening, validation, logging, Docker deployment
