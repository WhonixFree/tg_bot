from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.catalog import NetworkOption


def build_main_menu_keyboard(*, has_active_access: bool) -> InlineKeyboardMarkup:
    button = (
        InlineKeyboardButton(text="My access", callback_data="menu:my_access")
        if has_active_access
        else InlineKeyboardButton(text="Buy subscription", callback_data="menu:buy")
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [button],
        ]
    )


def build_coin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="USDT", callback_data="coin:USDT"),
                InlineKeyboardButton(text="USDC", callback_data="coin:USDC"),
            ],
            [
                InlineKeyboardButton(text="BTC", callback_data="coin:BTC"),
                InlineKeyboardButton(text="ETH", callback_data="coin:ETH"),
            ],
            [InlineKeyboardButton(text="Main Menu", callback_data="menu:home")],
        ]
    )


def build_network_keyboard(coin_code: str, options: list[NetworkOption]) -> InlineKeyboardMarkup:
    row_sizes = [3, 3] if coin_code == "USDT" else [2, 2]
    buttons = [
        InlineKeyboardButton(
            text=option.label,
            callback_data=f"network:{coin_code}:{option.code}",
        )
        for option in options
    ]

    rows: list[list[InlineKeyboardButton]] = []
    offset = 0
    for row_size in row_sizes:
        row = buttons[offset : offset + row_size]
        if row:
            rows.append(row)
        offset += row_size

    rows.append([InlineKeyboardButton(text="Back to coin selection", callback_data="purchase:back_to_coin")])
    rows.append([InlineKeyboardButton(text="Main Menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_summary_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Create invoice", callback_data="summary:create_invoice")],
            [InlineKeyboardButton(text="Back to coin selection", callback_data="purchase:back_to_coin")],
            [InlineKeyboardButton(text="Main Menu", callback_data="menu:home")],
        ]
    )


def build_invoice_keyboard(public_order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="I've paid", callback_data=f"invoice:paid:{public_order_id}")],
            [
                InlineKeyboardButton(text="Refresh status", callback_data=f"invoice:refresh:{public_order_id}"),
                InlineKeyboardButton(text="Cancel invoice", callback_data=f"invoice:cancel:{public_order_id}"),
            ],
            [InlineKeyboardButton(text="Main Menu", callback_data="menu:home")],
        ]
    )


def build_expired_invoice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Create new invoice",
                    callback_data="invoice:new",
                )
            ],
            [InlineKeyboardButton(text="Main Menu", callback_data="menu:home")],
        ]
    )


def build_success_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Main Menu", callback_data="menu:home"),
                InlineKeyboardButton(text="My access", callback_data="menu:my_access"),
            ],
        ]
    )


def build_my_access_keyboard(*, has_active_access: bool) -> InlineKeyboardMarkup:
    if has_active_access:
        rows = [[InlineKeyboardButton(text="Main Menu", callback_data="menu:home")]]
    else:
        rows = [
            [InlineKeyboardButton(text="Buy subscription", callback_data="menu:buy")],
            [InlineKeyboardButton(text="Main Menu", callback_data="menu:home")],
        ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
