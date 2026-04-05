from __future__ import annotations

from datetime import UTC
from decimal import Decimal

from app.core.config import Settings
from app.core.enums import PaymentStatus
from app.db.models import AccessLink
from app.services.payments.schemas import InvoiceView


def _status_label(status: PaymentStatus) -> str:
    value = str(status.value).lower()
    return {
        "new": "waiting for payment",
        "check": "checking payment",
        "paid": "paid",
        "confirmed": "paid",
        "expired": "expired",
        "failed": "failed",
    }.get(value, "processing")


def build_main_menu_text(settings: Settings) -> str:
    return (
        "Private channel with guides, workflows, and actual AI OFM setups.\n"
        "No fluff. Just useful stuff.\n\n"
        f"Free channel: {settings.free_channel_url}\n"
        f"Contact: {settings.manager_contact_text}"
    )


def build_already_active_text(access_link: AccessLink) -> str:
    return (
        "You already have lifetime access.\n\n"
        "Open the link from the same Telegram account used for the payment.\n\n"
        f"{access_link.invite_link}"
    )


def build_coin_selection_text(price_usd: Decimal) -> str:
    return (
        "Choose your payment coin.\n\n"
        f"Price: ${price_usd}\n\n"
        "Access unlocks right after payment."
    )


def build_network_selection_text(price_usd: Decimal, coin_code: str) -> str:
    return (
        "Now choose the network.\n\n"
        f"Price: ${price_usd}\n"
        f"Coin: {coin_code}\n\n"
        "Make sure the network matches."
    )


def build_summary_text(
    *,
    price_usd: Decimal,
    coin_code: str,
    network_label: str,
) -> str:
    return (
        "Check the details before paying.\n\n"
        f"Price: ${price_usd}\n"
        f"Coin: {coin_code}\n"
        f"Network: {network_label}\n\n"
        "If everything looks right, create the invoice."
    )


def build_invoice_text(
    invoice: InvoiceView,
    *,
    claimed_payment: bool = False,
    neutral_refresh: bool = False,
) -> str:
    lines = [
        "Invoice is ready.",
        "",
        f"Amount: {invoice.payer_amount} {invoice.payer_currency}",
        f"Network: {invoice.network_label}",
        f"Address: <code>{invoice.address}</code>",
        f"Valid until: {invoice.expires_at.astimezone(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Status: {_status_label(invoice.status)}",
        "",
        "Send the exact amount on the exact network.",
    ]

    if claimed_payment and invoice.status == PaymentStatus.CHECK:
        lines.extend([
            "",
            "Payment is not detected yet. The network may still be confirming it."
        ])
    elif neutral_refresh and invoice.status == PaymentStatus.CHECK:
        lines.extend([
            "",
            "Status refreshed. Payment is still being checked."
        ])

    return "\n".join(lines)


def build_expired_invoice_text(invoice: InvoiceView) -> str:
    return (
        "This invoice has expired.\n\n"
        f"Coin: {invoice.payer_currency}\n"
        f"Network: {invoice.network_label}\n\n"
        "Do not send funds to the old address.\n"
        "Create a new invoice to continue."
    )


def build_underpaid_invoice_text() -> str:
    return (
        "You have underpaid for this invoice.\n\n"
        "If you want to request a refund, please contact support."
    )


def build_payment_success_text(invoice: InvoiceView) -> str:
    return (
        "Payment confirmed.\n\n"
        f"Received: {invoice.payer_amount} {invoice.payer_currency}\n"
        f"Network: {invoice.network_label}\n"
        "Your lifetime access is now unlocked.\n\n"
        "Open the link from the same Telegram account used for the payment."
    )


def build_payment_success_with_access_text(invoice: InvoiceView, invite_link: str) -> str:
    return (
        f"{build_payment_success_text(invoice)}\n\n"
        f"{invite_link}"
    )


def build_my_access_text(access_link: AccessLink) -> str:
    return (
        "Your access is active.\n\n"
        "Here is your invite link:\n"
        f"{access_link.invite_link}\n\n"
        "Open it from the same Telegram account used for the payment."
    )


def build_no_access_text() -> str:
    return "You do not have active access yet."
