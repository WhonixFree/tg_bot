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
- Do not implement Tier_2 in MVP.
- Do not implement duration variants, renewals, expiry reminders, or time-based channel removal in MVP.
- Do not implement payout API.
- Do not implement static wallets.
- Do not implement multi-admin roles.
- Prefer the smallest clean implementation that satisfies the scope.
- Real 2328 transport must be implemented, but default runtime must remain `mock` until the merchant project is approved.

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
- httpx for 2328 API
- pydantic-settings for config
- qrcode handling only if needed locally for mock mode; prefer provider QR data when live mode is enabled later

---

## 3. Core Delivery Strategy

The correct strategy is **provider abstraction first**.

Do not build business logic directly on top of raw 2328 HTTP calls.
Instead, define a payment gateway interface and implement two providers:
- `Mock2328Gateway` — default for MVP execution
- `Live2328Gateway` — coded now, but disabled by default until merchant approval

All handlers and services must depend on the gateway interface, not on httpx or raw 2328 request code.

This prevents rewrites later when the real project UUID/API key become usable.

---

## 4. Recommended Build Order

Build the MVP in the following order:

1. Project skeleton and config
2. Database schema and repositories
3. Telegram bot shell and basic routing
4. Screen rendering and single-message UI policy
5. Catalog/plan selection flow
6. Payment gateway abstractions and mock provider
7. Active invoice flow and local status checks
8. Subscription activation and access link generation
9. Join request handling and channel access control
10. Admin panel flows
11. Live 2328 client, signing, schemas, and webhook verification
12. FastAPI routes for webhook reception and health endpoints
13. Logging, validation, and edge cases
14. Dockerization and deployment polish
15. End-to-end testing and MVP acceptance check

Do not start with live 2328 HTTP integration.
Get the full app working end-to-end in mock mode first.

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
    subscriptions/
    access/
    messaging/
    admin/
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

## Phase 1 — Configuration and Runtime Modes

### Goal
Centralize all environment and static business settings.

### Required config
- `BOT_TOKEN`
- `ADMIN_TG_ID`
- `PRIVATE_CHANNEL_ID`
- `DATABASE_URL` or SQLite file path
- `APP_BASE_URL` for future public webhook routing
- `BOT_PUBLIC_NAME` or project label if desired
- `MAIN_MENU_IMAGE_PATH` or URL
- `FREE_CHANNEL_URL`
- `MANAGER_CONTACT_TEXT`
- `PROJECT_DESCRIPTION_TEXT`
- `PAYMENT_PROVIDER_MODE` with allowed values `mock` or `live`, default `mock`
- `MERCHANT_PROJECT_UUID` optional at MVP stage
- `MERCHANT_API_KEY` optional at MVP stage
- `PAYMENT_WEBHOOK_PATH`

### Required static seeded data
- supported coins and networks
- the single active MVP plan `TIER_1_LIFETIME` and its USD price
- display labels for networks:
  - `TRX-TRC20 -> TRC20`
  - `BSC-BEP20 -> BEP20`
  - `ETH-ERC20 -> ERC20`
  - `AVAX-C -> AVAX`
  - `POL-MATIC -> MATIC`
  - `TON -> TON`
  - `BTC -> BTC`

### Mandatory runtime mode rules
- default mode must be `mock`
- app must boot successfully without real 2328 credentials in `mock` mode
- app must fail fast if `live` mode is selected without required credentials

### Done when
- config object is available everywhere through dependency injection or app context
- seeded catalog structure is defined clearly
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

#### `plans`
Fields:
- `id`
- `code` unique
- `display_name`
- `description`
- `price_usd`
- `is_active`
- `access_type`
- `created_at`
- `updated_at`

#### `subscriptions`
Fields:
- `id`
- `user_id`
- `plan_id`
- `status` (`active`, `expired`, `revoked`)
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
- `plan_id`
- `amount_usd`
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
- `raw_payload_json`
- `paid_at` nullable
- `created_at`
- `updated_at`

#### `access_links`
Fields:
- `id`
- `user_id`
- `subscription_id`
- `telegram_invite_link` unique
- `status`
- `created_at`
- `updated_at`
- `revoked_at` nullable

#### `join_requests_log`
Fields:
- `id`
- `subscription_id` nullable
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

---

## Phase 3 — Repository Layer

### Goal
Create thin repositories for persistence without business logic leakage.

### Repositories to implement
- `UserRepository`
- `PlanRepository`
- `OrderRepository`
- `PaymentRepository`
- `SubscriptionRepository`
- `AccessLinkRepository`
- `JoinRequestLogRepository`
- `AdminAuditRepository`

### Required behavior
- fetch or create user by Telegram profile
- get user active subscription
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
- tier select
- coin select
- network select
- summary screen

### Important rule
Do not implement message editing engine.
Delete previous message and send a new one.

### Done when
- user can navigate main menu to summary screen without errors
- chat stays clean with one current bot screen

---

## Phase 5 — Catalog and Selection Flow

### Goal
Implement Tier_1 purchase path end to end up to pre-invoice state.

### Implement
- Tier_1 only
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

---

## Phase 6 — Payment Gateway Abstraction and Mock Provider

### Goal
Create the payment gateway interface and make the app fully usable in mock mode.

### Define gateway interface
Methods should include at minimum:
- `create_invoice(order)`
- `get_payment_info(payment)`
- `verify_webhook(payload)`
- `parse_webhook(payload)`

### Implement `Mock2328Gateway`
It must:
- generate local payment uuid
- generate mock address
- generate mock QR data URI or local placeholder QR
- compute deterministic fake `payer_amount`
- return realistic `expires_at`
- emulate 2328-like statuses
- support manual progression from waiting -> paid / expired / failed for development

### Important rule
Mock provider payload shape should resemble the real 2328 payload structure as closely as practical.
This reduces migration friction later.

### Done when
- invoice creation works fully without external API
- UI screens can be driven entirely by mock provider responses

---

## Phase 7 — Orders, Payments, and Active Invoice Flow

### Goal
Implement the app-level invoice lifecycle in mock mode.

### Implement
- create order records
- enforce one active unpaid invoice per user
- create payment record through gateway abstraction
- render active invoice screen with QR/address/amount/expires_at
- `I've paid`
- `Refresh status`
- `Cancel invoice`
- invoice expiration handling
- return-to-main-menu behavior that keeps live invoice in DB

### Important behavior
If a still-valid unpaid invoice already exists:
- show existing invoice instead of creating a new one

### Done when
- the full invoice UI flow works end to end in mock mode
- active invoice reuse works correctly
- expired invoice is never reused

---

## Phase 8 — Shared Payment Status Processing

### Goal
Centralize business logic for payment state transitions.

### Implement
A service like `PaymentStatusProcessor` that accepts normalized provider payment data and:
- updates payment row
- updates order status
- performs idempotency checks
- activates subscription on `paid` and `overpaid`
- handles `underpaid_check`, `underpaid`, `cancel`, `aml_lock`
- triggers success or failure user/admin notifications as needed

### Important rule
Both manual status checks and future webhook callbacks must use this same processing path.

### Done when
- duplicate processing of the same successful payment does not duplicate subscription access
- success/failure states are stable and repeat-safe

---

## Phase 9 — Subscription Activation and Access Links

### Goal
Grant subscription and generate Telegram access link.

### Implement
- lifetime subscription creation rules
- create invite link with join request enabled
- store invite link in DB
- send success/access message containing the link directly in message text

### Done when
- successful payment creates the lifetime subscription exactly once
- success screen shows valid access link

---

## Phase 10 — Join Request Handling and Channel Control

### Goal
Automate access control to the private channel.

### Implement
- handle join requests
- resolve invite link ownership
- approve only if:
  - link exists
  - link belongs to user
  - subscription is active
- decline otherwise
- log wrong-account attempts
- notify admin on wrong-account attempt

### Done when
- correct user gets approved
- wrong user gets declined and logged
- lifetime access approval works without rotating the link on wrong-account attempts

---

## Phase 11 — Background Jobs

### Goal
Add only the minimal invoice-related automation needed for the MVP.

### Jobs to add
- unpaid invoice expiration checker

### Important rule
Jobs must be safe to run repeatedly.
They should be idempotent at the application level.

### Done when
- expired invoice states are reflected correctly

---

## Phase 12 — Admin Panel

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

## Phase 13 — Live 2328 Client and Webhook Support

### Goal
Code the real 2328 integration fully, but keep it behind `PAYMENT_PROVIDER_MODE=live`.

### Implement `Live2328Gateway`
Must include:
- `POST /v1/payment` request builder
- `POST /v1/payment/info` request builder
- signing helper based on Base64(JSON body) + HMAC-SHA256
- webhook signature verification
- normalized response parsing
- transport error handling and timeout handling

### Important rules
- do not call live transport in `mock` mode
- live gateway must not be constructed if required credentials are missing
- webhook payload parsing should normalize into the same app-level payment model used by mock mode

### Done when
- code for live integration exists and is unit-testable
- switching to live mode later is config-only

---

## Phase 14 — FastAPI Routes

### Goal
Expose required HTTP routes.

### Routes to implement
- `GET /health`
- `POST /webhooks/2328`

### Webhook behavior
- verify signature through gateway/helper
- compute dedupe key
- reject invalid signatures
- return HTTP 200 quickly for valid payloads
- pass parsed payload to shared payment processing service

### Important note
In MVP execution, webhook route may be mostly used for internal/manual testing while app is still in mock mode.
That is acceptable.

### Done when
- health route works
- webhook route works structurally and shares processing path with manual checks

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
- bot restart with existing active invoice/subscription state
- switching from mock to live mode without code changes

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
The image must run correctly in `mock` mode without live provider credentials.

### Done when
- app can run on a clean VPS in Docker
- state persists across restarts

---

## Phase 17 — Testing and Acceptance

### Goal
Verify MVP behavior before enabling live provider mode later.

### Minimum test targets
- config validation
- plan selection logic
- one active unpaid invoice rule
- payment status processor idempotency
- join request validation
- admin actions
- mock gateway payload normalization
- live gateway signing helper
- webhook signature verification helper

### Acceptance checklist
- full user purchase flow works in mock mode
- access approval flow works in Telegram
- admin flow works
- live gateway code exists but remains disabled by default

### Final release criterion
The MVP is shippable before 2328 approval as long as:
- app works end to end in mock mode
- live gateway code is already present and isolated behind config
- enabling live mode later requires only approved project credentials and environment changes

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

Most important implementation constraint:
- code the real 2328 integration now, but design the app so that **no live outbound 2328 calls are required for MVP delivery**.
