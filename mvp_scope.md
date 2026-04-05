# MVP Scope — Telegram Channel Access Bot

## 1. Goal of MVP

Build the smallest production-usable version of the Telegram bot that:
- sells access to one private Telegram channel;
- accepts crypto payments via 2328.io;
- optionally stores auxiliary BTC/ETH market-rate metadata from external free market price APIs;
- activates access automatically after successful payment;
- keeps user chat clean with one current bot screen;
- provides a simple admin panel inside the bot.

## 2. What MUST be in MVP

### 2.1 Product scope
MVP must implement only one product:
- **GUIDE_ACCESS_LIFETIME**

This means:
- user gets lifetime access to one private guide channel;
- payment is a one-time purchase;
- there is no recurring billing;
- there are no duration variants;
- there are no multiple tariff plans;
- there is no post-payment extension logic.

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

### 2.3 Invoice amount calculation rules
The product price is stored in **USD** as the canonical price.

Invoice creation rules:
- the canonical product price is stored in USD and that USD amount is sent to 2328 for invoice creation;
- `payer_amount` is the provider-returned crypto amount payable for the created invoice;
- for BTC and ETH, external market-rate fetching is auxiliary preview/validation/audit logic only unless the provider contract explicitly requires fixed crypto amount input;
- once the invoice is created, the provider-returned payable amount must be treated as locked and must not be recalculated on refresh or payment recheck.

Rate-source rules:
- use a free public market-data API as the primary source;
- use a second free public market-data API as fallback;
- if both sources fail, local preview/audit rate data may be absent, but invoice creation from the canonical USD amount may still proceed.

Suggested sources for implementation:
- CoinGecko Simple Price API as primary source, which documents price lookup by coin id and vs currency; citeturn308066search0turn308066search4
- Binance Spot Market Data endpoint `GET /api/v3/ticker/price` as fallback, which is documented as public market data with no authentication required. citeturn308066search1turn308066search3

### 2.4 User screens
MVP must include these screens:
- Main Menu
- Offer / Product Confirmation
- Choose Coin
- Choose Network (only where needed)
- Order Summary
- Active Invoice
- Payment Pending / Not detected yet
- Invoice Expired
- Payment Success / Access message
- My Access

MVP must not include:
- Choose Tier
- Choose Duration
- Expiring Soon
- Subscription Expired

### 2.5 Admin scope
MVP admin panel must include:
- open admin panel
- list recent users
- search user by telegram ID or username
- list recent payments
- revoke access
- resend access link
- grant access without payment
- view payment and access state

MVP admin panel must not include:
- manual extension by 1 / 3 / 6 / 12 months
- duration management
- plan management

### 2.6 Payment integration
MVP must implement:
- create invoice via `POST /v1/payment`
- status check via `POST /v1/payment/info`
- webhook processing from `url_callback`
- 2328 signature verification
- idempotent processing
- optional pre-invoice BTC/ETH rate fetch for preview/validation/audit metadata
- rate-source fallback logic
- storing rate metadata together with the invoice/payment record

### 2.7 Access automation
MVP must implement:
- create join-request invite links
- approve join requests only for the correct Telegram account
- decline join requests from another account
- send admin notification on wrong-account access attempt
- keep access active after successful payment unless manually revoked by admin

MVP must not implement:
- automatic expiration-based channel removal
- renewal-based access extension rules
- timed access periods

### 2.8 Jobs/automation
MVP must implement background processing for:
- invoice expiration detection

MVP must not implement background processing for:
- 1-day subscription reminder
- subscription expiration
- channel removal on expiration

### 2.9 Infrastructure
MVP must run as one Dockerized app container with:
- Telegram long polling
- FastAPI webhook endpoint for 2328
- SQLite as persistent DB
- environment variable configuration

## 3. UX Rules That MUST Be Followed

### 3.1 Single current message
The bot should not spam the chat.
Each new screen should delete the previous bot message and send a new one.

### 3.2 Main Menu rules
- main menu must include an image
- free channel link is shown in message text, not as button
- manager contact is shown in message text, not as button
- regular user sees only `Buy access` or `My access`
- admin sees only `Admin panel`

### 3.3 Product selection rules
The user flow must not expose multiple plans or durations.
The product is fixed.
The user only confirms purchase, then selects payment asset and network.

### 3.4 Invoice message rules
Invoice screen must show:
- QR
- exact amount
- coin
- network
- address
- validity time
- warning that the address is valid only until expiration
- warning to send the exact amount on the correct network
- for BTC and ETH, optional informational note that auxiliary market-rate metadata may be shown without overriding the provider invoice amount

Buttons:
- row 1: `I've paid`
- row 2: `Refresh status`, `Cancel invoice`
- row 3: `Main Menu`

### 3.5 Returning to main menu from invoice
If user presses `Main Menu` from invoice screen:
- delete invoice message from chat
- keep invoice in DB if still active
- if user starts buying again and invoice is still valid, show the same active invoice
- if invoice expired, show expired screen instead

### 3.6 Access link rule
Payment success screen must include the access invite link directly in the message text.
Buttons:
- `Main Menu`
- `My access`

## 4. Business Rules That MUST Be Followed

### 4.1 One active unpaid invoice per user
Do not create multiple active unpaid invoices for the same user.

### 4.2 Lifetime-only access model
After successful payment:
- create one lifetime access record;
- do not calculate expiration date for the paid access;
- do not implement renewal or extension behavior.

### 4.3 Wrong Telegram account
If another Telegram account uses the access link:
- decline join request
- log it
- notify admin
- do not approve access

### 4.4 Admin model
There is only one admin role for MVP.
No multi-role permission system.

### 4.5 Exchange-rate integrity
For BTC and ETH invoices:
- store the fetched market rate used for calculation;
- store which source produced the rate;
- store when the rate was fetched;
- do not silently recalculate an already created invoice;
- if auxiliary rate fetch fails before invoice creation, the provider invoice may still be created from the canonical USD amount.

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
- multiple tariff plans
- duration variants
- renewal logic
- subscription expiry reminders
- automatic channel removal by expiry schedule
- analytics dashboard
- microservice split
- Postgres migration
- message editing engine

## 6. Acceptable MVP Simplifications

The following simplifications are intentional and acceptable:
- supported currencies and networks are seeded locally
- only one admin account
- only one channel is managed
- one SQLite database file
- long polling instead of Telegram webhook
- delete-and-send UI instead of complex message edit flow
- no dynamic provider metadata sync
- rate lookup may use simple public market endpoints without websocket streaming
- no advanced retry orchestration beyond idempotent processing and scheduled checks

## 7. Definition of Done for MVP

MVP is considered complete when all of the following are true:

1. A new user can open the bot and see the main menu.
2. The user can confirm the single product, then select coin and network.
3. The bot can fetch BTC and ETH rates before invoice creation when those assets are selected.
4. The bot can create a valid 2328 invoice with the correct locked amount.
5. The bot shows QR/address/amount/expiration correctly.
6. The bot can confirm payment via webhook or manual status check.
7. The bot activates access exactly once.
8. The bot sends an access link for the private channel.
9. The bot approves the correct Telegram account and declines other accounts.
10. Admin can manually find user, revoke access, resend link, and grant without payment.
11. The app runs in Docker with persistent SQLite storage and working 2328 webhook endpoint.

## 8. Post-MVP Roadmap Items

These items are explicitly deferred:
- additional paid products or plan variants
- multiple channels/community access bundle
- richer admin workflows
- product/catalog management UI
- provider metadata sync if 2328 later exposes such endpoint
- higher-scale database migration
- separate RU and EN deployments from the same repo template
