import asyncio
import datetime as dt
import hashlib
import hmac
import json
import os
from decimal import Decimal
from typing import Any

from flask import Blueprint, Response, jsonify, request

from common.models.payments_models import Payment
from core.database.database import db

from .nats_publish import publish_payment_succeeded_event
from .robokassa import (
    is_result_signature_valid,
    normalize_amount_2dp,
    parse_decimal,
    build_payment_link,
)
from common.events import PaymentSucceededEvent


payments_bp = Blueprint("payments", __name__)


def _require_internal_token() -> None:
    expected = os.getenv("INTERNAL_API_TOKEN") or ""
    if not expected:
        # Если токен не задан — не разрешаем вызов, чтобы случайно не открыть эндпойнт наружу.
        raise PermissionError("internal_api_token_not_set")
    provided = request.headers.get("X-Internal-Token") or ""
    if provided != expected:
        raise PermissionError("invalid_internal_token")


def _get_client_ip() -> str:
    # В prod будет nginx — поэтому учитываем X-Forwarded-For.
    xff = (request.headers.get("X-Forwarded-For") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return (request.remote_addr or "").strip()


def _enforce_robokassa_ip_allowlist() -> None:
    raw = (os.getenv("ROBO_ALLOWED_IPS") or "").strip()
    if not raw:
        return
    allowed = {ip.strip() for ip in raw.split(",") if ip.strip()}
    if not allowed:
        return
    ip = _get_client_ip()
    if ip not in allowed:
        raise PermissionError("robokassa_ip_not_allowed")


def _tariff_amount_kzt() -> Any:
    """Получает стоимость тарифа в KZT из переменных окружения."""
    value = (os.getenv("TARIFF_AMOUNT_KZT") or "").strip()
    if not value:
        raise RuntimeError("TARIFF_AMOUNT_KZT is not set")
    return parse_decimal(value)

def _verify_cryptobot_signature(raw_body: bytes, signature_hex: str, token: str) -> bool:
    """
    Верификация webhook Crypto Pay API:
    сравниваем заголовок `crypto-pay-api-signature` с HMAC-SHA256(request_body),
    где ключ = SHA256(app_token).

    Док: https://help.crypt.bot/crypto-pay-api#verifying-webhook-updates
    """
    if not signature_hex:
        return False
    secret = hashlib.sha256(token.encode("utf-8")).digest()
    digest = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature_hex.strip().lower())


@payments_bp.post("/payments/robokassa/create")
def robokassa_create():
    """
    Внутренний эндпойнт. Бот вызывает его, чтобы получить ссылку оплаты.
    """
    _require_internal_token()

    data = request.get_json(silent=True) or {}
    user_id_raw = data.get("user_id")
    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_user_id"}), 400

    merchant_login = (os.getenv("ROBO_MERCHANT_LOGIN") or "").strip()
    password1 = (os.getenv("ROBO_PASSWORD_1") or "").strip()
    if not merchant_login or not password1:
        return jsonify({"error": "robokassa_not_configured"}), 500

    amount = _tariff_amount_kzt()

    payment = Payment(
        user_id=user_id,
        provider="robokassa",
        amount=amount,
        currency="KZT",
        status="pending",
    )
    db.session.add(payment)
    db.session.commit()

    inv_id = payment.id
    description = "Подписка на 90 дней"
    shp = {"Shp_user_id": str(user_id)}
    payment_url = build_payment_link(
        merchant_login=merchant_login,
        password1=password1,
        out_sum=amount,
        inv_id=inv_id,
        description=description,
        shp=shp,
    )

    return jsonify({"inv_id": inv_id, "payment_url": payment_url})


@payments_bp.post("/payments/robokassa/result")
def robokassa_result():
    """
    ResultURL callback. Подтверждение оплаты делаем только по нему.
    Должны ответить Robokassa текстом: OK{InvId}.
    """
    _enforce_robokassa_ip_allowlist()

    # Robokassa шлёт параметры как form (обычно POST).
    form = request.form or {}

    out_sum_raw = form.get("OutSum") or form.get("out_sum") or form.get("OUTSUM")
    inv_id_raw = form.get("InvId") or form.get("InvID") or form.get("inv_id")
    signature = (
        form.get("SignatureValue")
        or form.get("Signature")
        or form.get("signature_value")
        or ""
    )

    if not out_sum_raw or not inv_id_raw or not signature:
        return jsonify({"error": "missing_params"}), 400

    try:
        out_sum = parse_decimal(out_sum_raw)
        inv_id = int(inv_id_raw)
    except ValueError:
        return jsonify({"error": "invalid_params"}), 400

    password2 = (os.getenv("ROBO_PASSWORD_2") or "").strip()
    if not password2:
        return jsonify({"error": "robokassa_not_configured"}), 500

    # Собираем Shp_* параметры (в Robokassa они возвращаются как есть).
    shp: dict[str, Any] = {}
    for k, v in form.items():
        if k.lower().startswith("shp_"):
            shp[k] = v

    # Проверка суммы (фиксированный тариф в KZT).
    expected_amount = normalize_amount_2dp(_tariff_amount_kzt())
    incoming_amount = normalize_amount_2dp(out_sum)
    if incoming_amount != expected_amount:
        return jsonify({"error": "amount_mismatch"}), 400

    if not is_result_signature_valid(
        out_sum=out_sum,
        inv_id=inv_id,
        password2=password2,
        signature_value=signature,
        shp=shp,
    ):
        return jsonify({"error": "invalid_signature"}), 400

    payment: Payment | None = db.session.get(Payment, inv_id)
    if not payment:
        return jsonify({"error": "payment_not_found"}), 404

    # Идемпотентность: если уже success — просто OK{InvId}.
    if payment.status == "success":
        return Response(f"OK{inv_id}", mimetype="text/plain")

    # Доп. защита: сверяем user_id из Shp_user_id (если есть).
    shp_user_id = shp.get("Shp_user_id") or shp.get("shp_user_id")
    if shp_user_id is not None and str(payment.user_id) != str(shp_user_id):
        return jsonify({"error": "user_mismatch"}), 400

    now = dt.datetime.now(dt.timezone.utc)
    payment.status = "success"
    payment.signature_verified = True
    payment.paid_at = now
    payment.raw_callback = {k: v for k, v in form.items()}
    db.session.commit()

    event = PaymentSucceededEvent(
        payment_id=payment.id,
        user_id=int(payment.user_id),
        provider=payment.provider,
        amount=str(payment.amount),
        currency=payment.currency,
        paid_at=now,
    )
    asyncio.run(publish_payment_succeeded_event(event))

    return Response(f"OK{inv_id}", mimetype="text/plain")


@payments_bp.post("/payments/cryptobot/create")
def cryptobot_create():
    """
    Внутренний эндпойнт. Бот вызывает его, чтобы получить ссылку оплаты в TON через CryptoBot.
    """
    _require_internal_token()

    data = request.get_json(silent=True) or {}
    user_id_raw = data.get("user_id")
    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_user_id"}), 400

    token = (os.getenv("CRYPTOBOT_TOKEN") or "").strip()
    if not token:
        return jsonify({"error": "cryptobot_not_configured"}), 500

    amount = _tariff_amount_kzt()
    description = (os.getenv("CRYPTOBOT_DESCRIPTION") or "Подписка на 90 дней").strip()

    # 1) Создаём запись Payment в KZT.
    payment = Payment(
        user_id=user_id,
        provider="cryptobot",
        amount=amount,
        currency="KZT",
        status="pending",
    )
    db.session.add(payment)
    db.session.commit()

    payload = f"pay:{payment.id}"

    # 2) Создаём invoice в CryptoBot в фиате (KZT), оплата в TON по курсу.
    try:
        from aiosend import CryptoPay
    except Exception as exc:
        return jsonify({"error": f"aiosend_not_available:{exc}"}), 500

    try:
        cp = CryptoPay(token=token)
        invoice = asyncio.run(
            cp.create_invoice(
                amount=float(amount),
                currency_type="fiat",
                fiat="KZT",
                accepted_assets=["TON"],
                description=description,
                payload=payload,
            )
        )
    except Exception as exc:
        # Если invoice не создался — помечаем payment как failed (чтобы не оставлять вечные pending).
        payment.status = "failed"
        payment.raw_callback = {"error": str(exc)}
        db.session.commit()
        return jsonify({"error": f"cryptobot_create_invoice_failed:{exc}"}), 502

    payment.provider_invoice_id = str(invoice.invoice_id)
    payment.provider_payload = payload
    db.session.commit()

    return jsonify(
        {
            "payment_id": payment.id,
            "invoice_id": invoice.invoice_id,
            "pay_url": invoice.mini_app_invoice_url,
            "bot_invoice_url": invoice.bot_invoice_url,
            "web_app_invoice_url": invoice.web_app_invoice_url,
        }
    )


@payments_bp.post("/payments/cryptobot/webhook")
def cryptobot_webhook():
    """
    Public endpoint для webhook CryptoBot (Crypto Pay API).

    Ожидаем JSON-объект Update:
    - update_type == invoice_paid
    - payload содержит Invoice
    """
    token = (os.getenv("CRYPTOBOT_TOKEN") or "").strip()
    if not token:
        return jsonify({"error": "cryptobot_not_configured"}), 500

    raw_body = request.get_data(cache=True)  # bytes
    signature = (request.headers.get("crypto-pay-api-signature") or "").strip()
    if not _verify_cryptobot_signature(raw_body, signature, token):
        return jsonify({"error": "invalid_signature"}), 401

    try:
        data = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return jsonify({"error": "invalid_json"}), 400

    # Извлекаем поля без зависимости от aiosend, чтобы не требовать extras для webhook.
    update_type = (data.get("update_type") or "").strip()
    payload = data.get("payload") or {}
    if update_type != "invoice_paid":
        # неизвестные update_type просто игнорируем (не ошибка для провайдера)
        return jsonify({"ok": True}), 200
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_payload"}), 400

    invoice_id = payload.get("invoice_id")
    invoice_status = (payload.get("status") or "").strip()
    invoice_asset = (payload.get("asset") or "").strip()
    invoice_fiat = (payload.get("fiat") or "").strip()
    invoice_amount = payload.get("amount")
    invoice_payload = payload.get("payload")

    try:
        invoice_id_int = int(invoice_id)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_invoice_id"}), 400

    # В webhook update может прилетать статус paid; проверяем его.
    if invoice_status and invoice_status != "paid":
        return jsonify({"ok": True}), 200
    # Фиатный инвойс (KZT): asset может отсутствовать или быть у paid_asset.
    if invoice_fiat and invoice_fiat != "KZT":
        return jsonify({"error": "currency_not_supported"}), 400
    if not invoice_fiat and invoice_asset and invoice_asset != "TON":
        return jsonify({"error": "asset_not_supported"}), 400

    # Ищем Payment по invoice_id, либо по payload.
    payment: Payment | None = (
        db.session.query(Payment)
        .filter(Payment.provider == "cryptobot")
        .filter(Payment.provider_invoice_id == str(invoice_id_int))
        .one_or_none()
    )
    if not payment and isinstance(invoice_payload, str) and invoice_payload:
        payment = (
            db.session.query(Payment)
            .filter(Payment.provider == "cryptobot")
            .filter(Payment.provider_payload == invoice_payload)
            .one_or_none()
        )

    if not payment and isinstance(invoice_payload, str) and invoice_payload.startswith("pay:"):
        # Доп. фолбэк: payload вида pay:<payment_id>
        try:
            payment_id = int(invoice_payload.split(":", 1)[1])
        except (IndexError, ValueError):
            payment_id = 0
        if payment_id:
            payment = db.session.get(Payment, payment_id)
            if payment and payment.provider != "cryptobot":
                payment = None

    if not payment:
        return jsonify({"error": "payment_not_found"}), 404

    # Идемпотентность: если уже success — просто OK.
    if payment.status == "success":
        return jsonify({"ok": True}), 200

    # Сверяем сумму: для KZT — фиатная сумма (2 знака), для TON — крипто (9 знаков).
    if payment.currency == "KZT":
        if invoice_fiat != "KZT":
            return jsonify({"error": "currency_mismatch"}), 400
        try:
            incoming_val = Decimal(str(invoice_amount)).quantize(Decimal("0.01"))
            expected_val = Decimal(str(payment.amount)).quantize(Decimal("0.01"))
        except Exception:
            return jsonify({"error": "invalid_amount"}), 400
        if incoming_val != expected_val:
            return jsonify({"error": "amount_mismatch"}), 400
    else:
        # Старые инвойсы в TON.
        try:
            incoming_amount = Decimal(str(invoice_amount)).quantize(Decimal("0.000000001"))
            expected_amount = Decimal(str(payment.amount)).quantize(Decimal("0.000000001"))
        except Exception:
            return jsonify({"error": "invalid_amount"}), 400
        if incoming_amount != expected_amount:
            return jsonify({"error": "amount_mismatch"}), 400

    # Доп. верификация через API: подтягиваем invoice и убеждаемся, что он реально PAID.
    try:
        from aiosend import CryptoPay

        cp = CryptoPay(token=token)
        invoices = asyncio.run(cp.get_invoices(invoice_ids=[invoice_id_int]))
        inv = invoices[0] if invoices else None
        if not inv or str(inv.status) != "paid":
            return jsonify({"error": "invoice_not_paid"}), 409
    except Exception as exc:
        # Не блокируем оплату из-за временного сбоя в API, т.к. подпись уже проверили.
        # Это fallback: reconcile в Taskiq всё равно сможет перепроверить позже.
        _ = exc

    now = dt.datetime.now(dt.timezone.utc)
    payment.status = "success"
    payment.signature_verified = True
    payment.paid_at = now
    payment.provider_invoice_id = payment.provider_invoice_id or str(invoice_id_int)
    payment.provider_payload = payment.provider_payload or (
        invoice_payload if isinstance(invoice_payload, str) else None
    )
    payment.raw_callback = {"update": data, "signature": signature}
    db.session.commit()

    event = PaymentSucceededEvent(
        payment_id=payment.id,
        user_id=int(payment.user_id),
        provider=payment.provider,
        amount=str(payment.amount),
        currency=payment.currency,
        paid_at=now,
    )
    asyncio.run(publish_payment_succeeded_event(event))

    return jsonify({"ok": True}), 200
