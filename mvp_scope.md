# MVP Scope — Telegram Subscription Bot

## 1. Goal of MVP

Build the smallest production-usable version of the Telegram bot that:
- sells access to one private Telegram channel;
- prepares full 2328.io payment integration for later activation;
- can already run end-to-end in **mock payment mode** before the 2328 project is approved;
- activates access automatically after payment;
- keeps user chat clean with one current bot screen;
- provides a simple admin panel inside the bot.

## 2. What MUST be in MVP

### 2.1 Product scope
MVP must implement only **Tier_1**.

Tier_1 means:
- user gets access to one private guide channel;
- Tier_1 is a one-time lifetime purchase;
- after payment, user gets lifetime access to the guide channel;
- no recurring billing.

### 2.2 Supported payment assets
MVP must support:
- USDT
- USDC
- BTC
- ETH

Supported networks:
- USDT: TRC20, BEP20, ERC20, AVAX, MATIC, TON
- USDC: BEP20, ERC20, AVAX, MATIC
- BTC: BTC
- ETH: ERC20

### 2.3 User screens
MVP must include these screens:
- Main Menu
- Choose Tier
- Choose Coin
- Choose Network (only where needed)
- Order Summary
- Active Invoice
- Payment Pending / Not detected yet
- Invoice Expired
- Payment Success / Access message
- My Access

### 2.4 Admin scope
MVP admin panel must include:
- open admin panel
- list recent users
- search user by telegram ID or username
- list recent payments
- revoke access
- resend access link
- grant access without payment

### 2.5 Payment integration
MVP must implement the **full 2328 integration surface in code**, but real outbound API calls must stay disabled by default until the merchant project is approved on the 2328 side.

MVP must implement:
- request/response schemas for `POST /v1/payment`
- request/response schemas for `POST /v1/payment/info`
- signature generation for authenticated requests
- webhook payload schema and signature verification
- idempotent processing logic
- provider abstraction that supports both `mock` and `live` modes
- mock payment provider flow that mimics 2328 invoice creation and status progression

Important rule:
- **all 2328 API calls must be coded, but not executed in MVP by default**
- default runtime mode must be `mock`
- switching to real 2328 calls later must require only config changes and real credentials/project approval, not architecture changes

### 2.6 Access automation
MVP must implement:
- create join-request invite links
- approve join requests only for the correct Telegram account
- decline join requests from another account
- send admin notification on wrong-account access attempt
- keep the access link attached to the user/subscription
- allow admin-driven access revocation later

### 2.7 Jobs/automation
MVP must implement background processing only where needed for invoice/payment flow.
Do not implement subscription expiry reminders or time-based channel removal in the lifetime-only MVP.

### 2.8 Infrastructure
MVP must run as one Dockerized app container with:
- Telegram long polling
- FastAPI webhook endpoint for 2328
- SQLite as persistent DB
- environment variable configuration

The project must remain deployable as a single independent bot instance.

## 3. UX Rules That MUST Be Followed

### 3.1 Single current message
The bot should not spam the chat.
Each new screen should delete the previous bot message and send a new one.

### 3.2 Main Menu rules
- main menu must include an image
- free channel link is shown in message text, not as button
- manager contact is shown in message text, not as button
- regular user sees only `Buy subscription` or `My access`
- admin sees only `Admin panel`

### 3.3 Invoice message rules
Invoice screen must show:
- QR
- exact amount
- coin
- network
- address
- validity time
- warning that the address is valid only until expiration

Buttons:
- row 1: `I've paid`
- row 2: `Refresh status`, `Cancel invoice`
- row 3: `Main Menu`

### 3.4 Returning to main menu from invoice
If user presses `Main Menu` from invoice screen:
- delete invoice message from chat
- keep invoice in DB if still active
- if user starts buying again and invoice is still valid, show the same active invoice
- if invoice expired, show expired screen instead

### 3.5 Access link rule
Payment success screen must include the access invite link directly in the message text.
Buttons:
- `Main Menu`
- `My access`

## 4. Business Rules That MUST Be Followed

### 4.1 One active unpaid invoice per user
Do not create multiple active unpaid invoices for the same user.

### 4.2 Lifetime access logic
For the current MVP, Tier_1 grants lifetime access.
Do not implement duration-based renewal logic yet.

### 4.3 Wrong Telegram account
If another Telegram account uses the access link:
- decline join request
- log it
- notify admin
- do not approve access

### 4.4 Admin model
There is only one admin role for MVP.
No multi-role permission system.

### 4.5 Payment provider runtime modes
The application must support two runtime modes:
- `mock` — used before the 2328 merchant project is approved
- `live` — used only after approval and credential activation

In `mock` mode:
- do not make outbound 2328 API calls
- still create local invoice/payment records
- still render invoice screens exactly like live flow
- still support manual status progression for development/testing
- still process webhook-shaped payloads through the same business logic where possible

In `live` mode:
- use real 2328 credentials
- send signed requests
- consume real webhook callbacks

## 5. What MUST NOT Be in MVP

Do not implement:
- Tier_2 user flow
- second paid channel/community channel
- payout API
- static wallets
- dynamic sync of available currencies/networks from 2328
- Telegram Stars
- Telegram native paid subscriptions
- multi-admin role system
- tariff editing through admin panel
- analytics dashboard
- microservice split
- Postgres migration
- message editing engine

Also do not:
- hardwire payment logic directly to live 2328 transport
- require real 2328 approval to run the app end-to-end locally or on VPS
- silently call live 2328 API in default configuration

## 6. Acceptable MVP Simplifications

The following simplifications are intentional and acceptable:
- supported currencies and networks are seeded locally
- only one admin account
- only one channel is managed
- one SQLite database file
- long polling instead of Telegram webhook
- delete-and-send UI instead of complex message edit flow
- no dynamic provider metadata sync
- no advanced retry orchestration beyond idempotent processing and scheduled checks
- mock payment provider is the default execution mode until 2328 approval is completed

## 7. Definition of Done for MVP

MVP is considered complete when all of the following are true:

1. A new user can open the bot and see the main menu.
2. The user can select Tier_1, coin, and network.
3. The bot can create a local invoice in `mock` mode with the same app-level flow expected from 2328.
4. The bot shows QR/address/amount/expiration correctly.
5. The bot can confirm payment via mock provider flow and via the shared status-processing path.
6. The bot activates a lifetime subscription exactly once.
7. The bot sends an access link for the private channel.
8. The bot approves the correct Telegram account and declines other accounts.
9. Admin can manually find user, revoke access, resend link, and grant without payment.
10. The app runs in Docker with persistent SQLite storage and a working FastAPI server.
11. The codebase already contains the live 2328 client, signing logic, request/response models, and webhook verification, but live API execution remains disabled by default.
12. Enabling `live` mode later should require configuration and approved project credentials, not a redesign.

## 8. Post-MVP / Activation Roadmap Items

These items are explicitly deferred:
- Tier_2 implementation
- multiple channels/community access bundle
- richer admin workflows
- tariff management UI
- provider metadata sync if 2328 later exposes such endpoint
- higher-scale database migration
- separate RU and EN deployments from the same repo template
- switching default payment mode from `mock` to `live` before the 2328 project is approved
