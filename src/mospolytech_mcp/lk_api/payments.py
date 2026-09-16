# Платежи и договоры личного кабинета (ФЛК-005).

from __future__ import annotations

from .models import Payments


class PaymentsMixin:
    async def get_payments(self) -> Payments:
        raw = await self.lk_get("getPayments")  # type: ignore[attr-defined]
        contracts = (raw or {}).get("contracts") or {}
        return Payments.from_dict(contracts)
