# Успеваемость (ФЛК-003).

from __future__ import annotations

from .models import PerformanceRecord


class PerformanceMixin:
    async def get_academic_performance(self, semester: int) -> list[PerformanceRecord]:
        raw = await self.lk_get(  # type: ignore[attr-defined]
            f"getAcademicPerformance&semestr={semester}"
        )
        records = (raw or {}).get("academicPerformance") or []
        return [PerformanceRecord.from_dict(r) for r in records]
