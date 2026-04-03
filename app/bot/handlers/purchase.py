from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ChatJoinRequest, Message

from app.bot.keyboards.purchase import (
    build_coin_keyboard,
    build_expired_invoice_keyboard,
    build_invoice_keyboard,
    build_main_menu_keyboard,
    build_my_access_keyboard,
    build_network_keyboard,
    build_success_keyboard,
    build_summary_keyboard,
)
from app.bot.screens.purchase import (
    build_already_active_text,
    build_coin_selection_text,
    build_expired_invoice_text,
    build_invoice_text,
    build_main_menu_text,
    build_my_access_text,
    build_network_selection_text,
    build_no_access_text,
    build_payment_success_with_access_text,
    build_summary_text,
)
from app.bot.states import PurchaseStates
from app.core.enums import BotMessageType, PaymentStatus
from app.db.models import Plan, User
from app.db.session import session_manager
from app.services.payments.payment_service import PurchaseEntry
from app.services.payments.schemas import InvoiceView
from app.services.runtime import RuntimeServices, build_runtime_services

router = Router()


@router.message(F.text.startswith("/start"))
async def handle_start(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    async with session_manager.session() as session:
        services = build_runtime_services(session=session, bot=message.bot)
        user = await services.user_service.upsert_from_telegram(message.from_user)
        await _show_main_menu(
            services=services,
            state=state,
            user=user,
            chat_id=message.chat.id,
        )
        await session.commit()


@router.callback_query(F.data == "menu:home")
async def handle_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.message is None:
        return

    async with session_manager.session() as session:
        services = build_runtime_services(session=session, bot=callback.bot)
        user = await services.user_service.upsert_from_telegram(callback.from_user)
        await _show_main_menu(
            services=services,
            state=state,
            user=user,
            chat_id=callback.message.chat.id,
        )
        await session.commit()
    await callback.answer()


@router.callback_query(F.data == "menu:my_access")
async def handle_my_access(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.message is None:
        return

    async with session_manager.session() as session:
        services = build_runtime_services(session=session, bot=callback.bot)
        user = await services.user_service.upsert_from_telegram(callback.from_user)
        await _show_my_access(
            services=services,
            state=state,
            user=user,
            chat_id=callback.message.chat.id,
        )
        await session.commit()
    await callback.answer()


@router.callback_query(F.data == "menu:buy")
async def handle_buy_subscription(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.message is None:
        return

    async with session_manager.session() as session:
        services = build_runtime_services(session=session, bot=callback.bot)
        user = await services.user_service.upsert_from_telegram(callback.from_user)
        if await services.subscription_service.has_active_lifetime_access(user.id):
            await _show_my_access(
                services=services,
                state=state,
                user=user,
                chat_id=callback.message.chat.id,
                already_active=True,
            )
        else:
            plan = await services.catalog_service.get_mvp_plan()
            entry = await services.payment_service.get_purchase_entry(user_id=user.id, plan=plan)
            await _show_purchase_entry(
                services=services,
                state=state,
                user=user,
                chat_id=callback.message.chat.id,
                plan=plan,
                entry=entry,
            )
        await session.commit()
    await callback.answer()


@router.callback_query(F.data == "purchase:back_to_coin")
async def handle_back_to_coin_selection(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.message is None:
        return

    async with session_manager.session() as session:
        services = build_runtime_services(session=session, bot=callback.bot)
        user = await services.user_service.upsert_from_telegram(callback.from_user)

        if await services.subscription_service.has_active_lifetime_access(user.id):
            await _show_my_access(
                services=services,
                state=state,
                user=user,
                chat_id=callback.message.chat.id,
                already_active=True,
            )
        else:
            plan = await services.catalog_service.get_mvp_plan()
            await _show_coin_selection(
                services=services,
                state=state,
                user=user,
                chat_id=callback.message.chat.id,
                plan=plan,
            )
        await session.commit()
    await callback.answer()


@router.callback_query(F.data.startswith("coin:"))
async def handle_coin_selection(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.message is None:
        return

    coin_code = callback.data.split(":", maxsplit=1)[1]

    async with session_manager.session() as session:
        services = build_runtime_services(session=session, bot=callback.bot)
        user = await services.user_service.upsert_from_telegram(callback.from_user)

        if await services.subscription_service.has_active_lifetime_access(user.id):
            await _show_my_access(
                services=services,
                state=state,
                user=user,
                chat_id=callback.message.chat.id,
                already_active=True,
            )
        else:
            plan = await services.catalog_service.get_mvp_plan()
            if services.catalog_service.needs_network_selection(coin_code):
                await state.set_state(PurchaseStates.NETWORK_SELECTION)
                await state.update_data(coin_code=coin_code)
                await services.message_service.show_text(
                    user_id=user.id,
                    chat_id=callback.message.chat.id,
                    text=build_network_selection_text(plan, coin_code),
                    reply_markup=build_network_keyboard(
                        coin_code,
                        services.catalog_service.get_networks_for_coin(coin_code),
                    ),
                )
            else:
                network_code = services.catalog_service.get_default_network(coin_code)
                await _show_summary(
                    services=services,
                    state=state,
                    user=user,
                    chat_id=callback.message.chat.id,
                    plan=plan,
                    coin_code=coin_code,
                    network_code=network_code,
                )

        await session.commit()
    await callback.answer()


@router.callback_query(F.data.startswith("network:"))
async def handle_network_selection(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.message is None:
        return

    _, coin_code, network_code = callback.data.split(":", maxsplit=2)

    async with session_manager.session() as session:
        services = build_runtime_services(session=session, bot=callback.bot)
        user = await services.user_service.upsert_from_telegram(callback.from_user)

        if await services.subscription_service.has_active_lifetime_access(user.id):
            await _show_my_access(
                services=services,
                state=state,
                user=user,
                chat_id=callback.message.chat.id,
                already_active=True,
            )
        else:
            plan = await services.catalog_service.get_mvp_plan()
            await _show_summary(
                services=services,
                state=state,
                user=user,
                chat_id=callback.message.chat.id,
                plan=plan,
                coin_code=coin_code,
                network_code=network_code,
            )
        await session.commit()
    await callback.answer()


@router.callback_query(F.data == "summary:create_invoice")
async def handle_create_invoice(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.message is None:
        return

    data = await state.get_data()
    coin_code = data.get("coin_code")
    network_code = data.get("network_code")
    if not coin_code or not network_code:
        await callback.answer("Choose coin and network first.", show_alert=True)
        return

    async with session_manager.session() as session:
        services = build_runtime_services(session=session, bot=callback.bot)
        user = await services.user_service.upsert_from_telegram(callback.from_user)

        if await services.subscription_service.has_active_lifetime_access(user.id):
            await _show_my_access(
                services=services,
                state=state,
                user=user,
                chat_id=callback.message.chat.id,
                already_active=True,
            )
        else:
            plan = await services.catalog_service.get_mvp_plan()
            invoice = await services.payment_service.create_invoice(
                user_id=user.id,
                plan=plan,
                coin_code=coin_code,
                network_code=network_code,
            )
            await _show_invoice(
                services=services,
                state=state,
                user=user,
                chat_id=callback.message.chat.id,
                invoice=invoice,
            )
        await session.commit()
    await callback.answer()


@router.callback_query(F.data.startswith("invoice:paid:"))
async def handle_invoice_paid(callback: CallbackQuery, state: FSMContext) -> None:
    await _handle_invoice_status_action(
        callback=callback,
        state=state,
        user_confirmed_payment=True,
    )


@router.callback_query(F.data.startswith("invoice:refresh:"))
async def handle_invoice_refresh(callback: CallbackQuery, state: FSMContext) -> None:
    await _handle_invoice_status_action(
        callback=callback,
        state=state,
        user_confirmed_payment=False,
    )


@router.callback_query(F.data.startswith("invoice:cancel:"))
async def handle_invoice_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.message is None:
        return

    public_order_id = callback.data.split(":", maxsplit=2)[2]

    async with session_manager.session() as session:
        services = build_runtime_services(session=session, bot=callback.bot)
        user = await services.user_service.upsert_from_telegram(callback.from_user)
        invoice = await services.payment_service.cancel_invoice(public_order_id=public_order_id)
        await _show_expired_invoice(
            services=services,
            state=state,
            user=user,
            chat_id=callback.message.chat.id,
            invoice=invoice,
        )
        await session.commit()
    await callback.answer()


@router.callback_query(F.data == "invoice:new")
async def handle_create_new_invoice(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.message is None:
        return

    async with session_manager.session() as session:
        services = build_runtime_services(session=session, bot=callback.bot)
        user = await services.user_service.upsert_from_telegram(callback.from_user)

        if await services.subscription_service.has_active_lifetime_access(user.id):
            await _show_my_access(
                services=services,
                state=state,
                user=user,
                chat_id=callback.message.chat.id,
                already_active=True,
            )
        else:
            plan = await services.catalog_service.get_mvp_plan()
            await _show_coin_selection(
                services=services,
                state=state,
                user=user,
                chat_id=callback.message.chat.id,
                plan=plan,
            )
        await session.commit()
    await callback.answer()


@router.chat_join_request()
async def handle_chat_join_request(join_request: ChatJoinRequest) -> None:
    async with session_manager.session() as session:
        services = build_runtime_services(session=session, bot=join_request.bot)
        await services.access_service.handle_join_request(join_request)
        await session.commit()


async def _show_main_menu(
    *,
    services: RuntimeServices,
    state: FSMContext,
    user: User,
    chat_id: int,
) -> None:
    has_active_access = await services.subscription_service.has_active_lifetime_access(user.id)
    await state.set_state(PurchaseStates.MAIN_MENU)
    await state.set_data({})
    await services.message_service.show_main_menu(
        user_id=user.id,
        chat_id=chat_id,
        caption=build_main_menu_text(services.settings),
        reply_markup=build_main_menu_keyboard(has_active_access=has_active_access),
    )


async def _show_my_access(
    *,
    services: RuntimeServices,
    state: FSMContext,
    user: User,
    chat_id: int,
    already_active: bool = False,
) -> None:
    subscription = await services.subscription_service.get_active_lifetime_subscription(user.id)
    access_link = await services.access_service.get_active_access_link_for_user(user.id)
    if access_link is None and subscription is not None:
        access_link = await services.access_service.ensure_access_link(
            user_id=user.id,
            subscription=subscription,
        )
    await state.set_state(PurchaseStates.MAIN_MENU)
    await state.set_data({})

    if subscription is not None and access_link is not None:
        text = build_already_active_text(access_link) if already_active else build_my_access_text(access_link)
        await services.message_service.show_text(
            user_id=user.id,
            chat_id=chat_id,
            text=text,
            reply_markup=build_my_access_keyboard(has_active_access=True),
            message_type=BotMessageType.ACCESS,
        )
        return

    await services.message_service.show_text(
        user_id=user.id,
        chat_id=chat_id,
        text=build_no_access_text(),
        reply_markup=build_my_access_keyboard(has_active_access=False),
        message_type=BotMessageType.ACCESS,
    )


async def _show_purchase_entry(
    *,
    services: RuntimeServices,
    state: FSMContext,
    user: User,
    chat_id: int,
    plan: Plan,
    entry: PurchaseEntry,
) -> None:
    if entry.active_invoice is not None:
        await _show_invoice(
            services=services,
            state=state,
            user=user,
            chat_id=chat_id,
            invoice=entry.active_invoice,
        )
        return

    if entry.expired_invoice is not None:
        await _show_expired_invoice(
            services=services,
            state=state,
            user=user,
            chat_id=chat_id,
            invoice=entry.expired_invoice,
        )
        return

    await _show_coin_selection(
        services=services,
        state=state,
        user=user,
        chat_id=chat_id,
        plan=plan,
    )


async def _show_coin_selection(
    *,
    services: RuntimeServices,
    state: FSMContext,
    user: User,
    chat_id: int,
    plan: Plan,
) -> None:
    await state.set_state(PurchaseStates.COIN_SELECTION)
    await state.set_data({})
    await services.message_service.show_text(
        user_id=user.id,
        chat_id=chat_id,
        text=build_coin_selection_text(plan),
        reply_markup=build_coin_keyboard(),
    )


async def _show_summary(
    *,
    services: RuntimeServices,
    state: FSMContext,
    user: User,
    chat_id: int,
    plan: Plan,
    coin_code: str,
    network_code: str,
) -> None:
    await state.set_state(PurchaseStates.SUMMARY)
    await state.set_data({"coin_code": coin_code, "network_code": network_code})
    await services.message_service.show_text(
        user_id=user.id,
        chat_id=chat_id,
        text=build_summary_text(
            plan=plan,
            coin_code=coin_code,
            network_code=network_code,
            catalog_service=services.catalog_service,
        ),
        reply_markup=build_summary_keyboard(),
    )


async def _show_invoice(
    *,
    services: RuntimeServices,
    state: FSMContext,
    user: User,
    chat_id: int,
    invoice: InvoiceView,
    claimed_payment: bool = False,
    neutral_refresh: bool = False,
) -> None:
    await state.set_state(PurchaseStates.ACTIVE_INVOICE)
    await state.set_data(
        {
            "coin_code": invoice.payer_currency,
            "network_code": invoice.network,
            "public_order_id": invoice.public_order_id,
        }
    )
    await services.message_service.show_text(
        user_id=user.id,
        chat_id=chat_id,
        text=build_invoice_text(
            invoice,
            claimed_payment=claimed_payment,
            neutral_refresh=neutral_refresh,
        ),
        reply_markup=build_invoice_keyboard(invoice.public_order_id),
        message_type=BotMessageType.INVOICE,
    )


async def _show_expired_invoice(
    *,
    services: RuntimeServices,
    state: FSMContext,
    user: User,
    chat_id: int,
    invoice: InvoiceView,
) -> None:
    await state.set_state(PurchaseStates.ACTIVE_INVOICE)
    await state.set_data({})
    await services.message_service.show_text(
        user_id=user.id,
        chat_id=chat_id,
        text=build_expired_invoice_text(invoice),
        reply_markup=build_expired_invoice_keyboard(),
        message_type=BotMessageType.INVOICE,
    )


async def _show_payment_success(
    *,
    services: RuntimeServices,
    state: FSMContext,
    user: User,
    chat_id: int,
    invoice: InvoiceView,
    invite_link: str,
) -> None:
    await state.set_state(PurchaseStates.MAIN_MENU)
    await state.set_data({})
    await services.message_service.show_text(
        user_id=user.id,
        chat_id=chat_id,
        text=build_payment_success_with_access_text(invoice, invite_link),
        reply_markup=build_success_keyboard(),
        message_type=BotMessageType.ACCESS,
    )


async def _handle_invoice_status_action(
    *,
    callback: CallbackQuery,
    state: FSMContext,
    user_confirmed_payment: bool,
) -> None:
    if callback.from_user is None or callback.message is None:
        return

    public_order_id = callback.data.split(":", maxsplit=2)[2]

    async with session_manager.session() as session:
        services = build_runtime_services(session=session, bot=callback.bot)
        user = await services.user_service.upsert_from_telegram(callback.from_user)
        processing = await services.payment_service.refresh_invoice(
            public_order_id=public_order_id,
            user_confirmed_payment=user_confirmed_payment,
        )
        invoice = await services.payment_service.get_invoice(public_order_id=public_order_id)

        if processing.is_success and processing.access_link is not None:
            await _show_payment_success(
                services=services,
                state=state,
                user=user,
                chat_id=callback.message.chat.id,
                invoice=invoice,
                invite_link=processing.access_link.invite_link,
            )
        elif invoice.status == PaymentStatus.CANCEL:
            await _show_expired_invoice(
                services=services,
                state=state,
                user=user,
                chat_id=callback.message.chat.id,
                invoice=invoice,
            )
        else:
            await _show_invoice(
                services=services,
                state=state,
                user=user,
                chat_id=callback.message.chat.id,
                invoice=invoice,
                claimed_payment=user_confirmed_payment,
                neutral_refresh=not user_confirmed_payment,
            )

        await session.commit()
    await callback.answer()
