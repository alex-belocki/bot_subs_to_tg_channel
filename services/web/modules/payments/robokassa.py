import hashlib
import hmac
import os
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote_plus, urlencode


def _algo_name() -> str:
    return (os.getenv("ROBO_SIGNATURE_ALGO") or "md5").strip().lower()


def _hash_hexdigest(payload: str) -> str:
    algo = _algo_name()
    data = payload.encode("utf-8")
    if algo == "md5":
        return hashlib.md5(data).hexdigest()  # noqa: S324
    if algo in {"sha256", "sha-256"}:
        return hashlib.sha256(data).hexdigest()
    raise ValueError(f"unsupported_signature_algo:{algo}")


def constant_time_equal_hex(a: str, b: str) -> bool:
    return hmac.compare_digest(a.strip().lower(), b.strip().lower())


def parse_decimal(value: str) -> Decimal:
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("invalid_decimal") from exc


def normalize_amount_2dp(value: Decimal) -> Decimal:
    # Robokassa в тестовом режиме может присылать сумму с 2 знаками после запятой,
    # а в боевом с 6 — сравниваем на уровне 2 знаков.
    return value.quantize(Decimal("0.01"))


def build_signature_base_with_shp(*parts: str, shp: dict[str, Any]) -> str:
    # По докам Robokassa Shp_* добавляются в базу подписи как:
    # ...:Shp_key=value:Shp_other=value (в алфавитном порядке по имени параметра)
    tail = []
    for k in sorted(shp.keys(), key=lambda s: s.lower()):
        tail.append(f"{k}={shp[k]}")
    all_parts = list(parts) + tail
    return ":".join(all_parts)


def build_payment_link(
    *,
    merchant_login: str,
    password1: str,
    out_sum: Decimal,
    inv_id: int,
    description: str,
    shp: dict[str, Any],
) -> str:
    out_sum_str = str(normalize_amount_2dp(out_sum))

    base = build_signature_base_with_shp(
        merchant_login,
        out_sum_str,
        str(inv_id),
        password1,
        shp=shp,
    )
    signature = _hash_hexdigest(base)

    params: dict[str, Any] = {
        "MerchantLogin": merchant_login,
        "OutSum": out_sum_str,
        "InvId": str(inv_id),
        "Description": description,
        "SignatureValue": signature,
    }
    params.update(shp)

    # Robokassa ожидает form-style query параметры.
    query = urlencode(params, quote_via=quote_plus)
    return f"https://auth.robokassa.ru/Merchant/Index.aspx?{query}"


def is_result_signature_valid(
    *,
    out_sum: Decimal,
    inv_id: int,
    password2: str,
    signature_value: str,
    shp: dict[str, Any],
) -> bool:
    out_sum_str = str(normalize_amount_2dp(out_sum))
    base = build_signature_base_with_shp(
        out_sum_str,
        str(inv_id),
        password2,
        shp=shp,
    )
    expected = _hash_hexdigest(base)
    return constant_time_equal_hex(expected, signature_value)

