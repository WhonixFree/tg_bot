from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class PurchaseStates(StatesGroup):
    MAIN_MENU = State()
    COIN_SELECTION = State()
    NETWORK_SELECTION = State()
    SUMMARY = State()
    ACTIVE_INVOICE = State()
