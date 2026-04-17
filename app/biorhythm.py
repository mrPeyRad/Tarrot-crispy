from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import math


@dataclass(frozen=True, slots=True)
class BiorhythmPoint:
    day: date
    physical: float
    emotional: float
    intellectual: float


@dataclass(frozen=True, slots=True)
class BiorhythmSnapshot:
    birth_date: date
    target_date: date
    days_lived: int
    physical: float
    emotional: float
    intellectual: float
    points: tuple[BiorhythmPoint, ...]


def parse_birth_date(text: str) -> date | None:
    normalized = text.strip()
    if not normalized:
        return None

    for separator in (".", "-", "/"):
        parts = normalized.split(separator)
        if len(parts) != 3:
            continue
        try:
            if len(parts[0]) == 4:
                year, month, day = (int(part) for part in parts)
            else:
                day, month, year = (int(part) for part in parts)
            parsed = date(year, month, day)
        except ValueError:
            continue
        if parsed > date.today():
            return None
        return parsed
    return None


def build_biorhythm_snapshot(
    birth_date: date,
    target_date: date | None = None,
    days_before: int = 3,
    days_after: int = 3,
) -> BiorhythmSnapshot:
    current_day = target_date or date.today()
    days_lived = (current_day - birth_date).days
    if days_lived < 0:
        raise ValueError("Дата рождения не может быть в будущем.")

    points = tuple(
        BiorhythmPoint(
            day=current_day + timedelta(days=offset),
            physical=_cycle_value(birth_date, current_day + timedelta(days=offset), 23),
            emotional=_cycle_value(birth_date, current_day + timedelta(days=offset), 28),
            intellectual=_cycle_value(birth_date, current_day + timedelta(days=offset), 33),
        )
        for offset in range(-days_before, days_after + 1)
    )

    return BiorhythmSnapshot(
        birth_date=birth_date,
        target_date=current_day,
        days_lived=days_lived,
        physical=_cycle_value(birth_date, current_day, 23),
        emotional=_cycle_value(birth_date, current_day, 28),
        intellectual=_cycle_value(birth_date, current_day, 33),
        points=points,
    )


def build_biorhythm_report(snapshot: BiorhythmSnapshot) -> str:
    return (
        f"Биоритмы на {snapshot.target_date.strftime('%d.%m.%Y')}\n\n"
        f"Дата рождения: {snapshot.birth_date.strftime('%d.%m.%Y')}\n"
        f"Прожито дней: {snapshot.days_lived}\n\n"
        f"Физический ритм: {_format_percent(snapshot.physical)} — {_describe_state(snapshot.physical, 'physical')}.\n"
        f"Эмоциональный ритм: {_format_percent(snapshot.emotional)} — {_describe_state(snapshot.emotional, 'emotional')}.\n"
        f"Интеллектуальный ритм: {_format_percent(snapshot.intellectual)} — {_describe_state(snapshot.intellectual, 'intellectual')}."
    )


def _cycle_value(birth_date: date, target_date: date, cycle_days: int) -> float:
    days_since_birth = (target_date - birth_date).days
    return math.sin((2 * math.pi * days_since_birth) / cycle_days)


def _format_percent(value: float) -> str:
    return f"{round(value * 100):+d}%"


def _describe_state(value: float, cycle_kind: str) -> str:
    if value >= 0.6:
        return {
            "physical": "телу проще держать темп и нагрузку",
            "emotional": "чувства устойчивее и теплее",
            "intellectual": "голова хорошо держит фокус и анализ",
        }[cycle_kind]
    if value >= 0.15:
        return {
            "physical": "ресурс ровный, можно двигаться без перегруза",
            "emotional": "фон мягкий, легче договариваться и проживать эмоции",
            "intellectual": "подходит для рабочих задач и обучения",
        }[cycle_kind]
    if value > -0.15:
        return {
            "physical": "ритм на переломе, лучше не рвать с места",
            "emotional": "настроение может быстро меняться",
            "intellectual": "полезно перепроверять решения и не спешить",
        }[cycle_kind]
    if value > -0.6:
        return {
            "physical": "энергию лучше распределять бережно",
            "emotional": "чувствительность выше обычного",
            "intellectual": "лучше дробить сложные задачи на этапы",
        }[cycle_kind]
    return {
        "physical": "организму полезен щадящий режим",
        "emotional": "фон более уязвимый, нужен мягкий темп",
        "intellectual": "лучше не перегружать себя дедлайнами и многозадачностью",
    }[cycle_kind]
