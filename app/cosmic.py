from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import random
import re

from app.horoscope import ZodiacSign, format_date_ru, normalize_text, parse_sign


SYNODIC_MONTH = 29.53058867
KNOWN_NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)


@dataclass(frozen=True, slots=True)
class MoonPhase:
    name: str
    focus: str
    action_tip: str
    caution: str
    beauty_tip: str


@dataclass(frozen=True, slots=True)
class SignNature:
    element: str
    modality: str
    love_style: str
    support_style: str
    friction_style: str


@dataclass(frozen=True, slots=True)
class AstroAlert:
    title: str
    tone: str
    action_tip: str
    caution: str


@dataclass(frozen=True, slots=True)
class CompatibilityInsight:
    first: ZodiacSign
    second: ZodiacSign
    score: int
    summary: str
    score_comment: str
    first_love_style: str
    second_love_style: str
    strength: str
    growth_zone: str


MOON_PHASES: tuple[tuple[float, MoonPhase], ...] = (
    (
        1.5,
        MoonPhase(
            name="Новолуние",
            focus="намерения, перезапуск и мягкая настройка планов",
            action_tip="собирать идеи, выбирать один вектор и оставлять место для тишины",
            caution="не перегружать день обещаниями и не стартовать из паники",
            beauty_tip="бережный уход и обновление образа без резких экспериментов",
        ),
    ),
    (
        6.8,
        MoonPhase(
            name="Растущий серп",
            focus="первые шаги, обучение и набор импульса",
            action_tip="пробовать новое, отправлять заявки и раскручивать начатое",
            caution="не разбрасываться между десятью идеями сразу",
            beauty_tip="хорошее время для ухода, который хочется сделать привычкой",
        ),
    ),
    (
        8.8,
        MoonPhase(
            name="Первая четверть",
            focus="решительность, выбор и настройка курса",
            action_tip="резать лишнее, принимать решение и двигать проект через конкретное действие",
            caution="не спорить ради спора и не рубить с плеча в переписках",
            beauty_tip="можно освежить форму, если давно хотелось аккуратного обновления",
        ),
    ),
    (
        13.8,
        MoonPhase(
            name="Растущая луна",
            focus="расширение, рост и уверенное продвижение",
            action_tip="назначать встречи, презентовать идеи и показывать результат",
            caution="не брать на себя больше, чем реально удержать",
            beauty_tip="день поддерживает процедуры на укрепление и восстановление",
        ),
    ),
    (
        15.8,
        MoonPhase(
            name="Полнолуние",
            focus="кульминация, ясность и повышенная чувствительность",
            action_tip="завершать важное, замечать итоги и честно говорить о главном",
            caution="не раздувать эмоции и не реагировать на каждый импульс моментально",
            beauty_tip="лучше выбирать спокойный ритуал ухода, чем радикальную смену образа",
        ),
    ),
    (
        21.0,
        MoonPhase(
            name="Убывающая луна",
            focus="освобождение, чистка и снижение лишнего шума",
            action_tip="закрывать хвосты, упрощать процессы и разбирать накопившееся",
            caution="не тянуть в новый цикл то, что уже явно отжило",
            beauty_tip="подходит для очищающих и разгружающих процедур",
        ),
    ),
    (
        23.6,
        MoonPhase(
            name="Последняя четверть",
            focus="переоценка, корректировка и внутренний аудит",
            action_tip="смотреть, что сработало, а что пора пересобрать",
            caution="не цепляться за старую схему только потому, что она знакома",
            beauty_tip="хорошо идут аккуратные коррекции и поддерживающий уход",
        ),
    ),
    (
        SYNODIC_MONTH,
        MoonPhase(
            name="Убывающий серп",
            focus="замедление, отдых и подготовка к новому старту",
            action_tip="досыпать, доводить мелочи до конца и разгружать голову",
            caution="не форсировать большие начинания через усталость",
            beauty_tip="самое время для мягкого восстановления и режима по силам",
        ),
    ),
)


SIGN_NATURES: dict[str, SignNature] = {
    "Овен": SignNature(
        element="Огонь",
        modality="кардинальный",
        love_style="влюбляется через движение, азарт и ощущение живого пульса",
        support_style="зажигает и помогает не застрять на месте",
        friction_style="может торопить события и давить на скорость",
    ),
    "Телец": SignNature(
        element="Земля",
        modality="фиксированный",
        love_style="строит близость через надежность, телесность и постоянство",
        support_style="даёт опору, устойчивость и ощущение дома",
        friction_style="может упрямиться и долго не менять привычный сценарий",
    ),
    "Близнецы": SignNature(
        element="Воздух",
        modality="мутабельный",
        love_style="сближается через разговоры, юмор и живое любопытство",
        support_style="разряжает атмосферу и приносит новые идеи",
        friction_style="может распыляться и резко переключать внимание",
    ),
    "Рак": SignNature(
        element="Вода",
        modality="кардинальный",
        love_style="любит через заботу, память о мелочах и эмоциональную включенность",
        support_style="чутко ловит состояние другого и умеет беречь",
        friction_style="может закрываться и реагировать слишком лично",
    ),
    "Лев": SignNature(
        element="Огонь",
        modality="фиксированный",
        love_style="раскрывается через тепло, щедрость и гордость за союз",
        support_style="дает уверенность, яркость и ощущение праздника",
        friction_style="может болезненно реагировать на недостаток внимания",
    ),
    "Дева": SignNature(
        element="Земля",
        modality="мутабельный",
        love_style="проявляет любовь в деталях, заботе и реальной пользе",
        support_style="структурирует хаос и замечает, что можно улучшить",
        friction_style="может уйти в критику и избыточный контроль",
    ),
    "Весы": SignNature(
        element="Воздух",
        modality="кардинальный",
        love_style="ищет союз, где есть красота, уважение и живой обмен",
        support_style="сглаживает углы и помогает договариваться",
        friction_style="может затягивать решение ради внешней гармонии",
    ),
    "Скорпион": SignNature(
        element="Вода",
        modality="фиксированный",
        love_style="сближается глубоко, интенсивно и с высокой ставкой на доверие",
        support_style="дает мощную вовлеченность и верность",
        friction_style="может проверять чувства через напряжение и ревность",
    ),
    "Стрелец": SignNature(
        element="Огонь",
        modality="мутабельный",
        love_style="любит через вдохновение, свободу и общее приключение",
        support_style="расширяет горизонт и возвращает чувство смысла",
        friction_style="может избегать тяжёлых разговоров и рутины",
    ),
    "Козерог": SignNature(
        element="Земля",
        modality="кардинальный",
        love_style="проявляется через ответственность, поступки и долгую дистанцию",
        support_style="держит курс и помогает строить будущее",
        friction_style="может звучать слишком строго и требовательно",
    ),
    "Водолей": SignNature(
        element="Воздух",
        modality="фиксированный",
        love_style="ценит дружбу, свободу и нестандартный ритм близости",
        support_style="приносит свежий взгляд и ощущение пространства",
        friction_style="может неожиданно уходить в дистанцию",
    ),
    "Рыбы": SignNature(
        element="Вода",
        modality="мутабельный",
        love_style="любит интуитивно, мягко и через тонкую эмоциональную связь",
        support_style="умеет сочувствовать и смягчать сложные состояния",
        friction_style="может уходить в недосказанность и идеализацию",
    ),
}


ELEMENT_SCORES = {
    ("Огонь", "Огонь"): 14,
    ("Земля", "Земля"): 13,
    ("Воздух", "Воздух"): 12,
    ("Вода", "Вода"): 14,
    ("Огонь", "Воздух"): 18,
    ("Воздух", "Огонь"): 18,
    ("Земля", "Вода"): 18,
    ("Вода", "Земля"): 18,
    ("Огонь", "Земля"): -4,
    ("Земля", "Огонь"): -4,
    ("Огонь", "Вода"): -6,
    ("Вода", "Огонь"): -6,
    ("Воздух", "Земля"): -3,
    ("Земля", "Воздух"): -3,
    ("Воздух", "Вода"): -5,
    ("Вода", "Воздух"): -5,
}

MODALITY_SCORES = {
    ("кардинальный", "кардинальный"): -3,
    ("фиксированный", "фиксированный"): -5,
    ("мутабельный", "мутабельный"): -1,
    ("кардинальный", "фиксированный"): -1,
    ("фиксированный", "кардинальный"): -1,
    ("кардинальный", "мутабельный"): 4,
    ("мутабельный", "кардинальный"): 4,
    ("фиксированный", "мутабельный"): -2,
    ("мутабельный", "фиксированный"): -2,
}

ELEMENT_DYNAMICS = {
    ("Огонь", "Огонь"): "Оба заряжают союз энергией и любят чувствовать живой драйв.",
    ("Земля", "Земля"): "Вместе легко строить надежную опору и понятный быт.",
    ("Воздух", "Воздух"): "Сильная сторона пары — разговор, идеи и ощущение свободы.",
    ("Вода", "Вода"): "Между вами много тонкого понимания и эмоционального резонанса.",
    ("Огонь", "Воздух"): "Один зажигает импульс, второй раздувает его в идею и движение.",
    ("Воздух", "Огонь"): "Один приносит мысль, второй мгновенно превращает её в действие.",
    ("Земля", "Вода"): "Один создаёт форму и стабильность, второй — глубину и душевность.",
    ("Вода", "Земля"): "Один чувствует момент, второй помогает ему воплотиться в реальности.",
    ("Огонь", "Земля"): "Темп и осторожность могут спорить друг с другом почти каждый день.",
    ("Земля", "Огонь"): "Один хочет рисковать, другой — сначала всё проверить и укрепить.",
    ("Огонь", "Вода"): "Много страсти и чувства, но эмоции легко перегреваются.",
    ("Вода", "Огонь"): "Тепло и чувствительность сильные, но ритм реакции у вас разный.",
    ("Воздух", "Земля"): "Идеи и практичность могут давать классный союз, если слышать темп друг друга.",
    ("Земля", "Воздух"): "Один мыслит фактами, другой — возможностями, и это требует настройки.",
    ("Воздух", "Вода"): "Слова и чувства идут в разной скорости, поэтому важен переводчик между ними.",
    ("Вода", "Воздух"): "Когда один чувствует, а другой анализирует, легко промахнуться мимо сути.",
}

ASTRO_ALERTS: tuple[AstroAlert, ...] = (
    AstroAlert(
        title="Режим ретроградного Меркурия",
        tone="Сегодня особенно важно перечитывать сообщения, проверять адреса и не спорить на автопилоте.",
        action_tip="оставлять паузу перед отправкой важного текста и подтверждать договоренности коротко и ясно",
        caution="не опираться на первое впечатление от новости или переписки",
    ),
    AstroAlert(
        title="Энергия коридора затмений",
        tone="Фон дня будто подсвечивает всё, что давно просит честного решения и внутренней развязки.",
        action_tip="смотреть на повторяющийся сюжет, а не на случайную драму одного часа",
        caution="не принимать судьбоносное решение только на пике эмоции",
    ),
    AstroAlert(
        title="Венерианский день",
        tone="Хочется больше красоты, тепла, контакта и подтверждения, что всё не зря.",
        action_tip="делать ставку на приятный разговор, эстетичный жест и мягкую дипломатию",
        caution="не путать симпатию с отсутствием границ",
    ),
    AstroAlert(
        title="Марсианский импульс",
        tone="В воздухе больше скорости, азарта и желания продвинуться без лишних остановок.",
        action_tip="направить энергию в один конкретный шаг, а не в три одновременных рывка",
        caution="не отвечать резко там, где нужна не сила, а точность",
    ),
    AstroAlert(
        title="Сатурнианская проверка",
        tone="День просит дисциплины, взрослого тона и умения выдержать долгую дистанцию.",
        action_tip="доделывать, укреплять и спокойно брать ответственность за выбранный курс",
        caution="не превращать требовательность в внутренний кнут",
    ),
    AstroAlert(
        title="Нептунианский туман",
        tone="Интуиция сильная, но факты могут растворяться в красивых догадках и ожиданиях.",
        action_tip="держать рядом простую проверку реальности и не терять режим",
        caution="не обещать себе больше ясности, чем есть на самом деле",
    ),
)


def _moon_age(for_day: date) -> float:
    noon_utc = datetime(for_day.year, for_day.month, for_day.day, 12, tzinfo=timezone.utc)
    diff_days = (noon_utc - KNOWN_NEW_MOON).total_seconds() / 86400
    return diff_days % SYNODIC_MONTH


def _get_moon_phase(for_day: date) -> tuple[MoonPhase, float]:
    age = _moon_age(for_day)
    for upper_bound, phase in MOON_PHASES:
        if age < upper_bound:
            return phase, age
    return MOON_PHASES[-1][1], age


def build_lunar_calendar(for_day: date | None = None) -> str:
    current_day = for_day or date.today()
    phase, age = _get_moon_phase(current_day)
    return (
        f"Лунный календарь на {format_date_ru(current_day)}\n\n"
        f"Фаза: {phase.name}\n"
        f"Лунный возраст: примерно {age:.1f} суток\n"
        f"Фокус дня: {phase.focus}.\n\n"
        f"Хорошо для: {phase.action_tip}.\n"
        f"Лучше не делать: {phase.caution}.\n"
        f"Небольшой бьюти-совет: {phase.beauty_tip}."
    )


def extract_signs(text: str) -> tuple[ZodiacSign, ...]:
    seen: set[str] = set()
    result: list[ZodiacSign] = []
    tokens = re.findall(r"[^\W\d_]+", normalize_text(text), flags=re.UNICODE)
    for token in tokens:
        sign = parse_sign(token)
        if sign is None or sign.name in seen:
            continue
        seen.add(sign.name)
        result.append(sign)
    return tuple(result)


def _compatibility_score(first: ZodiacSign, second: ZodiacSign) -> int:
    if first.name == second.name:
        return 88

    first_nature = SIGN_NATURES[first.name]
    second_nature = SIGN_NATURES[second.name]
    pair_key = (first_nature.element, second_nature.element)
    mode_key = (first_nature.modality, second_nature.modality)
    score = 60
    score += ELEMENT_SCORES[pair_key]
    score += MODALITY_SCORES[mode_key]

    pair_fingerprint = "|".join(sorted((first.name, second.name)))
    seed = sha256(pair_fingerprint.encode("utf-8")).digest()
    score += (seed[0] % 5) - 2
    return max(35, min(96, score))


def _compatibility_summary(score: int) -> str:
    if score >= 85:
        return "Союз с очень сильной естественной химией."
    if score >= 74:
        return "Совместимость высокая: есть и притяжение, и хороший шанс на устойчивость."
    if score >= 62:
        return "Совместимость живая: многое держится на договоренности и уважении к темпу друг друга."
    if score >= 50:
        return "Совместимость средняя: союз рабочий, но без настройки легко теряются на нюансах."
    return "Совместимость непростая: притяжение возможно, но отношения потребуют зрелости и терпения."


def build_compatibility_report(first: ZodiacSign, second: ZodiacSign) -> str:
    insight = build_compatibility_insight(first, second)
    return (
        f"Совместимость: {insight.first.name} + {insight.second.name}\n\n"
        f"Процент совместимости: {insight.score}%\n"
        f"{insight.score_comment}\n\n"
        f"Динамика пары: {insight.summary}\n"
        f"{insight.first.name}: {insight.first_love_style}.\n"
        f"{insight.second.name}: {insight.second_love_style}.\n\n"
        f"Сильная сторона: {insight.strength}\n"
        f"Зона роста: {insight.growth_zone}"
    )


def build_compatibility_insight(first: ZodiacSign, second: ZodiacSign) -> CompatibilityInsight:
    if first.name == second.name:
        summary = "Пара одного знака часто понимает друг друга с полуслова, но и слабые места зеркалит без скидок."
        score = 88
    else:
        summary = ELEMENT_DYNAMICS[(SIGN_NATURES[first.name].element, SIGN_NATURES[second.name].element)]
        score = _compatibility_score(first, second)

    first_nature = SIGN_NATURES[first.name]
    second_nature = SIGN_NATURES[second.name]
    return CompatibilityInsight(
        first=first,
        second=second,
        score=score,
        summary=summary,
        score_comment=_compatibility_summary(score),
        first_love_style=first_nature.love_style,
        second_love_style=second_nature.love_style,
        strength=f"{first_nature.support_style}; {second_nature.support_style}.",
        growth_zone=f"{first_nature.friction_style}; {second_nature.friction_style}.",
    )


def build_daily_astro_alert(for_day: date | None = None) -> str:
    current_day = for_day or date.today()
    seed = sha256(current_day.isoformat().encode("utf-8")).digest()
    rng = random.Random(int.from_bytes(seed[:8], byteorder="big"))
    alert = rng.choice(ASTRO_ALERTS)
    return (
        f"Астро-алерт дня на {format_date_ru(current_day)}\n\n"
        f"Космический сюжет: {alert.title}\n"
        f"{alert.tone}\n\n"
        f"Что поможет: {alert.action_tip}.\n"
        f"Чего избегать: {alert.caution}."
    )
