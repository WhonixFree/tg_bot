# Implementation Plan — Telegram Subscription Bot MVP

This document is a practical execution plan for building the MVP described in:
- `mvp_scope.md`
- `system_design.md`

It is intended for Codex and developers as an implementation order, not as a product or architecture document.

---

## 1. How to Use This File

Before writing code:
1. Read `mvp_scope.md` to understand what is in MVP and what is explicitly out of scope.
2. Read `system_design.md` to understand the architecture and business rules.
3. Follow this file for implementation order.

Important rules:
- Do not implement post-MVP features.
- Do not implement any multi-plan or tier-selection logic.
- Do not implement duration variants, renewals, expiry reminders, or time-based channel removal in MVP.
- Do not implement payout API.
- Do not implement static wallets.
- Do not implement multi-admin roles.
- Prefer the smallest clean implementation that satisfies the scope.
- The current primary integration goal is **real 2328 payment flow**.
- BTC and ETH market-rate data may be fetched from free public market-data APIs as auxiliary metadata before invoice creation.

---

## 2. Suggested Tech Choices

Use the following stack unless explicitly overridden:
- Python 3.12+
- aiogram 3.x
- FastAPI
- SQLAlchemy 2.x
- Alembic for migrations
- SQLite
- APScheduler or equivalent async scheduler
- httpx for 2328 API and rate API calls
- pydantic-settings for config
- qrcode handling only if needed locally for mock mode; prefer provider QR data when live mode is enabled

---

## 3. Core Delivery Strategy

The correct strategy for the current project stage is:
1. keep the product model **single and fixed**;
2. implement the real 2328 integration cleanly;
3. add a dedicated rate service for BTC/ETH conversion;
4. keep mock mode only as a development convenience, not as the main product goal.

Architectural rules:
- do not build business logic around future tariff expansion;
- do not keep a `plans` subsystem unless it already exists and removing it would cost more than simplifying it;
- use one product constant like `GUIDE_ACCESS_LIFETIME`;
- if a legacy `plans` table is already part of the schema, keep only one seeded compatibility row and remove runtime plan branching;
- store USD as the canonical price;
- send the canonical USD amount to 2328 when creating the invoice;
- treat provider-returned `payer_amount` as the actual payable crypto amount for the created invoice;
- if BTC/ETH market data is fetched locally, use it only for preview/validation/audit unless the provider contract explicitly supports fixed crypto amount input and that behavior is confirmed as required.

---

## 4. Recommended Build Order

Build the MVP in the following order:

1. Project skeleton and config
2. Database schema and repositories
3. Telegram bot shell and screen framework
4. Fixed-product purchase flow
5. BTC/ETH rate service with fallback APIs
6. Real 2328 client: create invoice, check invoice, signing, schemas
7. Shared payment status processing
8. 2328 webhook route and verification
9. Lifetime access activation and invite link generation
10. Join request handling and channel access control
11. Minimal admin panel flows
12. Logging, validation, and edge cases
13. Dockerization and deployment polish
14. Mock mode support for local development if still useful
15. End-to-end testing and acceptance check

Do not spend time on tariff architecture.
The current implementation priority is 2328 + correct canonical USD invoice creation.

---

## 5. Phase-by-Phase Plan

## Phase 0 — Bootstrap

### Goal
Create a clean repository structure and basic app entrypoints.

### Deliverables
- project directory structure
- dependency file
- app bootstrap
- config loader
- `.env.example`
- logging setup

### Suggested structure
```text
app/
  bot/
    handlers/
    keyboards/
    screens/
    middlewares/
  api/
    routes/
  core/
    config.py
    logging.py
    enums.py
    constants.py
  db/
    base.py
    models/
    repositories/
    session.py
  services/
    payments/
    access/
    messaging/
    admin/
    rates/
  jobs/
  schemas/
  utils/
main.py
alembic/
Dockerfile
README.md
.env.example
```

### Done when
- app starts without crashing
- config values load from environment
- logger works
- empty bot polling loop and empty FastAPI app can run in same process

---

## Phase 1 — Configuration and Fixed Product Settings

### Goal
Centralize all environment and static business settings.

### Required config
- `BOT_TOKEN`
- `ADMIN_TG_ID`
- `PRIVATE_CHANNEL_ID`
- `DATABASE_URL` or SQLite file path
- `APP_BASE_URL` for public webhook routing
- `BOT_PUBLIC_NAME` or project label if desired
- `MAIN_MENU_IMAGE_PATH` or URL
- `FREE_CHANNEL_URL`
- `MANAGER_CONTACT_TEXT`
- `PROJECT_DESCRIPTION_TEXT`
- `PRODUCT_CODE` default `GUIDE_ACCESS_LIFETIME`
- `PRODUCT_NAME`
- `PRODUCT_PRICE_USD`
- `PAYMENT_PROVIDER_MODE` with allowed values `mock` or `live`, default `live` or explicit project choice
- `MERCHANT_PROJECT_UUID`
- `MERCHANT_API_KEY`
- `PAYMENT_WEBHOOK_PATH`
- `RATE_API_TIMEOUT_SECONDS`
- `RATE_CACHE_TTL_SECONDS`
- `COINGECKO_BASE_URL`
- `BINANCE_BASE_URL`

### Required static seeded data
- supported coins and networks
- display labels for networks:
  - `TRX-TRC20 -> TRC20`
  - `BSC-BEP20 -> BEP20`
  - `ETH-ERC20 -> ERC20`
  - `AVAX-C -> AVAX`
  - `POL-MATIC -> MATIC`
  - `TON -> TON`
  - `BTC -> BTC`

### Mandatory runtime rules
- the product must be represented as one fixed offer;
- app must fail fast if `live` mode is selected without 2328 credentials;
- BTC/ETH market-rate lookup, if used, must not override the provider invoice amount;
- mock mode, if kept, must not affect live-flow architecture.

### Done when
- config object is available everywhere through dependency injection or app context
- fixed product settings are defined clearly
- runtime mode switching is explicit and validated

---

## Phase 2 — Database Schema

### Goal
Create the minimum database schema needed for the full MVP.

### Tables to implement

#### `users`
Fields:
- `id`
- `telegram_user_id` unique
- `username` nullable
- `first_name` nullable
- `last_name` nullable
- `is_admin` bool
- `last_bot_message_id` nullable
- `created_at`
- `updated_at`

#### `access_grants`
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

#### `orders`
Fields:
- `id`
- `order_id` unique
- `user_id`
- `product_code`
- `amount_usd`
- `selected_currency`
- `selected_network`
- `payment_provider`
- `status`
- `created_at`
- `updated_at`

#### `payments`
Fields:
- `id`
- `order_id`
- `provider_payment_uuid` unique nullable
- `provider_status`
- `payer_currency`
- `payer_amount`
- `network`
- `address`
- `provider_url` nullable
- `qr_data_uri` nullable
- `txid` nullable
- `expires_at`
- `rate_source` nullable
- `rate_base_currency` nullable
- `rate_quote_currency` nullable
- `rate_value_usd` nullable
- `rate_fetched_at` nullable
- `amount_before_rounding` nullable
- `raw_payload_json`
- `paid_at` nullable
- `created_at`
- `updated_at`

#### `access_links`
Fields:
- `id`
- `user_id`
- `access_grant_id`
- `telegram_invite_link` unique
- `status`
- `created_at`
- `updated_at`
- `revoked_at` nullable

#### `join_requests_log`
Fields:
- `id`
- `access_grant_id` nullable
- `expected_telegram_user_id`
- `actual_telegram_user_id`
- `invite_link` nullable
- `decision` (`approved`, `declined`, `ignored`)
- `reason` nullable
- `created_at`

#### `admin_audit_log`
Fields:
- `id`
- `admin_telegram_user_id`
- `target_user_id` nullable
- `action`
- `details_json` nullable
- `created_at`

### Done when
- migrations run successfully
- DB can be created from scratch
- repository layer can read/write basic objects
- payment rows can persist locked BTC/ETH conversion data

---

## Phase 3 — Repository Layer

### Goal
Create thin repositories for persistence without business logic leakage.

### Repositories to implement
- `UserRepository`
- `OrderRepository`
- `PaymentRepository`
- `AccessGrantRepository`
- `AccessLinkRepository`
- `JoinRequestLogRepository`
- `AdminAuditRepository`

### Required behavior
- fetch or create user by Telegram profile
- get user active access
- get payment by provider uuid
- get payment by order id
- list recent users/payments for admin

### Done when
- repositories hide SQLAlchemy details from handlers/services
- repositories cover all read/write cases needed for MVP

---

## Phase 4 — Telegram Bot Shell and Screen Framework

### Goal
Bring up a minimal bot with routing and the single-message policy.

### Implement
- `/start`
- callback query router
- user bootstrap middleware or helper
- `MessageService` that:
  - stores `last_bot_message_id`
  - deletes previous message if present
  - sends a new message/photo with keyboard
  - stores new message id

### Initial screens to implement
- main menu
- offer confirmation
- coin select
- network select
- summary screen

### Important rule
Do not implement a tariff selection engine.
The product path is single and fixed.

### Done when
- user can navigate main menu to summary screen without errors
- chat stays clean with one current bot screen

---

## Phase 5 — Fixed Product Purchase Flow

### Goal
Implement the single purchase path end to end up to pre-invoice state.

### Implement
- one fixed lifetime product
- coin selection:
  - USDT
  - USDC
  - BTC
  - ETH
- conditional network screen:
  - show for USDT and USDC
  - skip for BTC and ETH with auto-assigned network
- summary DTO/state assembly

### Done when
- user can reliably select valid purchase parameters
- invalid currency/network combinations are impossible from UI
- there is no plan-selection state anywhere in the flow

---

## Phase 6 — BTC/ETH Market Rate Service

### Goal
Implement the service that converts USD price into BTC/ETH invoice amount.

### Implement
A dedicated service, for example `CryptoRateService`, with:
- primary source: CoinGecko simple price API
- fallback source: Binance public spot market data API
- methods:
  - `get_btc_usd_rate()`
  - `get_eth_usd_rate()`
  - `convert_usd_to_coin(amount_usd, coin)`
- short TTL cache
- timeout handling
- normalized DTO for rate result

### Rules
- USD remains canonical product price
- fetch rate only when selected coin is BTC or ETH
- lock fetched rate into the payment record at invoice creation
- never recalculate amount during status refresh
- round up deterministically to supported precision
- if no rate source succeeds, abort invoice creation cleanly

### Done when
- BTC and ETH summary screens can show converted amount
- rate source and timestamp are available for persistence
- failure path is user-safe

---

## Phase 7 — Real 2328 Client

### Goal
Implement the real 2328 integration cleanly.

### Implement
A live gateway/service with at minimum:
- `create_invoice(order, pricing_snapshot)`
- `get_payment_info(payment)`
- `verify_webhook(payload, sign_header)`
- `parse_webhook(payload)`
- signing helper based on Base64(JSON body) + HMAC-SHA256
- request/response schemas
- transport error handling and timeout handling

### Important rules
- do not hardcode invoice amounts for BTC/ETH;
- the amount passed to 2328 must come from the locked conversion result;
- one shared normalized payment DTO must be used by both manual checks and webhook flow.

### Done when
- live invoice creation works against 2328 contract
- live payment info checks work
- gateway code is isolated from handlers

---

## Phase 8 — Orders, Payments, and Active Invoice Flow

### Goal
Implement the app-level invoice lifecycle.

### Implement
- create order records
- enforce one active unpaid invoice per user
- create payment record through 2328 gateway
- render active invoice screen with QR/address/amount/expires_at
- `I've paid`
- `Refresh status`
- `Cancel invoice`
- invoice expiration handling
- return-to-main-menu behavior that keeps live invoice in DB

### Important behavior
If a still-valid unpaid invoice already exists:
- show existing invoice instead of creating a new one
- reuse the locked amount and, for BTC/ETH, the already stored exchange rate

### Done when
- the full invoice UI flow works end to end
- active invoice reuse works correctly
- expired invoice is never reused

---

## Phase 9 — Shared Payment Status Processing

### Goal
Centralize business logic for payment state transitions.

### Implement
A service like `PaymentStatusProcessor` that accepts normalized provider payment data and:
- updates payment row
- updates order status
- performs idempotency checks
- activates access on `paid` and `overpaid`
- handles `underpaid_check`, `underpaid`, `cancel`, `aml_lock`
- triggers success or failure user/admin notifications as needed

### Important rule
Both manual status checks and webhook callbacks must use this same processing path.

### Done when
- duplicate processing of the same successful payment does not duplicate access
- success/failure states are stable and repeat-safe

---

## Phase 10 — 2328 Webhook and FastAPI Routes

### Goal
Expose required HTTP routes and wire them to the shared payment processor.

### Routes to implement
- `GET /health`
- `POST /webhooks/2328`

### Webhook behavior
- verify signature through gateway/helper
- compute dedupe key
- reject invalid signatures
- return HTTP 200 quickly for valid payloads
- pass parsed payload to shared payment processing service

### Done when
- health route works
- webhook route works structurally and shares processing path with manual checks

---

## Phase 11 — Access Activation and Invite Links

### Goal
Grant lifetime access and generate Telegram access link.

### Implement
- lifetime access creation rules
- create invite link with join request enabled
- store invite link in DB
- send success/access message containing the link directly in message text

### Done when
- successful payment creates the lifetime access exactly once
- success screen shows valid access link

---

## Phase 12 — Join Request Handling and Channel Control

### Goal
Automate access control to the private channel.

### Implement
- handle join requests
- resolve invite link ownership
- approve only if:
  - link exists
  - link belongs to user
  - access is active
- decline otherwise
- log wrong-account attempts
- notify admin on wrong-account attempt

### Done when
- correct user gets approved
- wrong user gets declined and logged
- lifetime access approval works without rotating the link on wrong-account attempts

---

## Phase 13 — Background Jobs

### Goal
Add only the minimal automation needed for the MVP.

### Jobs to add
- unpaid invoice expiration checker
- optional stale rate-cache cleanup

### Important rule
Jobs must be safe to run repeatedly.
They should be idempotent at the application level.

### Done when
- expired invoice states are reflected correctly
- cached market-rate data does not interfere with locked invoice amounts

---

## Phase 14 — Admin Panel

### Goal
Implement the minimum admin tooling inside Telegram.

### Implement
- admin entry screen
- recent users
- search by telegram ID or username
- recent payments
- revoke access
- resend access link
- grant without payment
- admin audit logging

### Important rule
Do not build role hierarchy.
Single admin only.

### Done when
- admin can resolve common support cases without DB access

---

## Phase 15 — Edge Cases and Validation

### Goal
Stabilize the MVP.

### Must cover
- repeated button taps
- repeated successful payment processing
- expired invoice viewed again later
- user presses main menu from invoice screen
- wrong Telegram account join request
- admin actions on missing or revoked user state
- bot restart with existing active invoice/access state
- BTC/ETH rate provider timeout or malformed response
- fallback from primary rate source to secondary rate source

### Done when
- common race/duplicate scenarios are handled safely

---

## Phase 16 — Docker and Deployment

### Goal
Package the app for VPS deployment.

### Deliverables
- Dockerfile
- optional docker-compose example
- persistent volume for SQLite
- `.env.example`
- startup command that runs bot polling + FastAPI in same process or coordinated process model

### Important rule
The container must run correctly with the configured 2328 mode and rate API settings.

### Done when
- app can run on a clean VPS in Docker
- state persists across restarts

---

## Phase 17 — Testing and Acceptance

### Goal
Verify MVP behavior before release.

### Minimum test targets
- config validation
- single-product purchase flow
- one active unpaid invoice rule
- BTC/ETH conversion logic
- rate fallback logic
- payment status processor idempotency
- join request validation
- admin actions
- 2328 signing helper
- webhook signature verification helper

### Acceptance checklist
- full user purchase flow works
- BTC and ETH invoices use locked converted amounts
- access approval flow works in Telegram
- admin flow works
- no multi-plan logic remains in runtime flow

### Final release criterion
The MVP is shippable when:
- 2328 invoice creation and status checks work reliably
- BTC/ETH conversion is fetched from free public APIs with fallback
- payment processing is idempotent
- access delivery works end to end

---

## 6. Practical Notes for Codex

When in doubt, prefer these priorities:
1. `mvp_scope.md`
2. `system_design.md`
3. this file

If there is conflict:
- follow MVP scope first
- keep architecture clean but minimal
- avoid speculative features

Most important implementation constraints:
- do not spend time on future tariff architecture;
- implement 2328 cleanly now;
- for BTC/ETH, if live public market data is fetched, persist it only as auxiliary metadata and do not override the provider invoice amount.
