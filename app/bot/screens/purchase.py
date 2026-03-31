from __future__ import annotations

from datetime import UTC

from app.core.config import Settings
from app.core.enums import PaymentStatus
from app.db.models import AccessLink
from app.db.models import Plan
from app.services.catalog import CatalogService
from app.services.payments.schemas import InvoiceView


def build_main_menu_text(settings: Settings) -> str:
    return (
        f"{settings.project_description_text}\n\n"
        f"Free channel: {settings.free_channel_url}\n"
        f"Manager: {settings.manager_contact_text}"
    )


def build_already_active_text(access_link: AccessLink) -> str:
    return (
        "Lifetime access is already active.\n\n"
        "Use the access link from the same Telegram account that completed the purchase.\n"
        f"{access_link.invite_link}"
    )


def build_coin_selection_text(plan: Plan) -> str:
    return (
        "Choose the coin for your payment.\n\n"
        f"Plan: {plan.display_name}\n"
        f"Price: ${plan.price_usd}"
    )


def build_network_selection_text(plan: Plan, coin_code: str) -> str:
    return (
        "Choose the network.\n\n"
        f"Plan: {plan.display_name}\n"
        f"Price: ${plan.price_usd}\n"
        f"Coin: {coin_code}"
    )


def build_summary_text(
    *,
    plan: Plan,
    coin_code: str,
    network_code: str,
    catalog_service: CatalogService,
) -> str:
    return (
        "Order summary\n\n"
        f"Plan: {plan.display_name}\n"
        f"Price: ${plan.price_usd}\n"
        f"Coin: {coin_code}\n"
        f"Network: {catalog_service.get_network_label(network_code)}"
    )


def build_invoice_text(
    invoice: InvoiceView,
    *,
    claimed_payment: bool = False,
    neutral_refresh: bool = False,
) -> str:
    lines = [
        "Active invoice",
        "",
        f"Plan: {invoice.plan_name}",
        f"Amount to send: {invoice.payer_amount} {invoice.payer_currency}",
        f"Network: {invoice.network_label}",
        f"Address: <code>{invoice.address}</code>",
        f"Valid until: {invoice.expires_at.astimezone(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Status: {invoice.status.value}",
        "",
        "Send the exact amount to the exact network shown above.",
    ]
    if claimed_payment and invoice.status == PaymentStatus.CHECK:
        lines.extend(["", "Payment not detected yet."])
    elif neutral_refresh and invoice.status == PaymentStatus.CHECK:
        lines.extend(["", "Status refreshed. Payment is still pending."])
    return "\n".join(lines)


def build_expired_invoice_text(invoice: InvoiceView) -> str:
    return (
        "Invoice is no longer active.\n\n"
        f"Coin: {invoice.payer_currency}\n"
        f"Network: {invoice.network_label}\n"
        "Do not send funds to the old address.\n"
        "Create a new invoice to continue."
    )


def build_payment_success_text(invoice: InvoiceView) -> str:
    return (
        "Payment confirmed.\n\n"
        f"Amount received: {invoice.payer_amount} {invoice.payer_currency}\n"
        f"Network: {invoice.network_label}\n"
        "Lifetime access activated.\n\n"
        "Use the link from the same Telegram account that completed the purchase."
    )


def build_payment_success_with_access_text(invoice: InvoiceView, invite_link: str) -> str:
    return (
        f"{build_payment_success_text(invoice)}\n\n"
        f"{invite_link}"
    )


def build_my_access_text(access_link: AccessLink) -> str:
    return (
        "Lifetime access is active.\n\n"
        "Use this link from the same Telegram account used for the purchase.\n\n"
        f"{access_link.invite_link}"
    )


def build_no_access_text() -> str:
    return "No active access."
