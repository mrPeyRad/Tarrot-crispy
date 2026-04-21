from __future__ import annotations

from dataclasses import dataclass
import random
from urllib.parse import quote


_WIKIMEDIA_REDIRECT_URL = "https://commons.wikimedia.org/wiki/Special:Redirect/file/{filename}"


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().replace("ё", "е").split())


@dataclass(frozen=True, slots=True)
class TarotDeckInfo:
    key: str
    name_ru: str
    name_en: str
    description: str
    aliases: tuple[str, ...]
    background_hex: str
    foreground_hex: str


@dataclass(frozen=True, slots=True)
class TarotCard:
    card_id: str
    deck_key: str
    name_ru: str
    name_en: str
    suit: str
    arcana: str
    image_filename: str
    keywords: tuple[str, ...]
    upright_meaning: str
    reversed_meaning: str
    yes_weight: int
    aliases: tuple[str, ...]

    @property
    def image_url(self) -> str:
        return _WIKIMEDIA_REDIRECT_URL.format(filename=quote(self.image_filename))


@dataclass(frozen=True, slots=True)
class CardDraw:
    position: str
    card: TarotCard
    is_reversed: bool
    deck_key: str = "rider-waite"

    @property
    def orientation_label(self) -> str:
        return "перевёрнутое положение" if self.is_reversed else "прямое положение"

    @property
    def meaning(self) -> str:
        return self.card.reversed_meaning if self.is_reversed else self.card.upright_meaning

    @property
    def image_url(self) -> str:
        return build_card_image_url(self.card, self.deck_key)

    def to_history_payload(self) -> dict[str, object]:
        return {
            "position": self.position,
            "card_id": self.card.card_id,
            "name_ru": self.card.name_ru,
            "is_reversed": self.is_reversed,
            "deck_key": self.deck_key,
        }


DEFAULT_DECK_KEY = "rider-waite"
DECKS: dict[str, TarotDeckInfo] = {
    DEFAULT_DECK_KEY: TarotDeckInfo(
        key=DEFAULT_DECK_KEY,
        name_en="Rider-Waite",
        name_ru="Классическая колода Райдера-Уэйта",
        description="Базовая колода с классическими образами и открытыми иллюстрациями.",
        aliases=("райдер", "райдера уэйта", "уэйт", "rider", "waite", "классика", "classic"),
        background_hex="e9d6b0",
        foreground_hex="513729",
    ),
    "marseille": TarotDeckInfo(
        key="marseille",
        name_en="Marseille Classic",
        name_ru="Марсельская классика",
        description="Исторический марсельский визуал на открытых изображениях из семейства Tarot de Marseille.",
        aliases=("марсель", "марсельская", "marseille", "marseilles", "classic marseille"),
        background_hex="d7c3a5",
        foreground_hex="7a2e1f",
    ),
    "sola-busca": TarotDeckInfo(
        key="sola-busca",
        name_en="Sola-Busca",
        name_ru="Sola-Busca",
        description="Ренессансный исторический арт-режим с детализированными гравюрами.",
        aliases=("sola", "busca", "sola busca", "сола", "сола-буска", "буска"),
        background_hex="4e3a32",
        foreground_hex="d8ba85",
    ),
    "minimal": TarotDeckInfo(
        key="minimal",
        name_en="Minimal",
        name_ru="Минималистичный визуал",
        description="Светлая лаконичная тема с чистым фоном. Пока использует классические изображения карт.",
        aliases=("минимал", "минималистичная", "minimal", "simple", "чистая"),
        background_hex="f8f5ef",
        foreground_hex="364152",
    ),
}


_MAJOR_ARCANA: tuple[dict[str, object], ...] = (
    {"card_id": "major-00", "name_ru": "Шут", "name_en": "The Fool", "image_filename": "RWS_Tarot_00_Fool.jpg", "keywords": ("начало", "свобода", "спонтанность"), "upright": "Карта дня про новый маршрут, смелость попробовать и живой интерес к миру.", "shadow": "неосмотрительность и прыжок в неизвестность без опоры", "yes_weight": 1, "aliases": ("дурак",)},
    {"card_id": "major-01", "name_ru": "Маг", "name_en": "The Magician", "image_filename": "RWS_Tarot_01_Magician.jpg", "keywords": ("воля", "инициатива", "мастерство"), "upright": "Сегодня многое решается через твою инициативу, слово и точное намерение.", "shadow": "манипуляцию, переоценку контроля и игру в силу", "yes_weight": 2, "aliases": ()},
    {"card_id": "major-02", "name_ru": "Верховная Жрица", "name_en": "High Priestess", "image_filename": "RWS_Tarot_02_High_Priestess.jpg", "keywords": ("интуиция", "тайна", "наблюдение"), "upright": "Ответ рождается не из суеты, а из тишины, наблюдения и доверия себе.", "shadow": "закрытость, путаницу в догадках и пассивное ожидание", "yes_weight": 0, "aliases": ("жрица",)},
    {"card_id": "major-03", "name_ru": "Императрица", "name_en": "Empress", "image_filename": "RWS_Tarot_03_Empress.jpg", "keywords": ("рост", "забота", "изобилие"), "upright": "День поддерживает рост, заботу о себе и то, что нужно бережно развивать.", "shadow": "избыточность, лень и растворение в комфорте", "yes_weight": 2, "aliases": ()},
    {"card_id": "major-04", "name_ru": "Император", "name_en": "Emperor", "image_filename": "RWS_Tarot_04_Emperor.jpg", "keywords": ("структура", "рамка", "ответственность"), "upright": "Сегодня выигрывают ясные правила, порядок и взрослое управление ситуацией.", "shadow": "жесткость, упрямый контроль и давление сверху", "yes_weight": 1, "aliases": ()},
    {"card_id": "major-05", "name_ru": "Иерофант", "name_en": "Hierophant", "image_filename": "RWS_Tarot_05_Hierophant.jpg", "keywords": ("традиция", "учитель", "смысл"), "upright": "Полезно опереться на проверенный опыт, традиции или хороший совет.", "shadow": "догматизм, чужие правила без понимания и пустую мораль", "yes_weight": 1, "aliases": ("жрец", "первосвященник")},
    {"card_id": "major-06", "name_ru": "Влюблённые", "name_en": "The Lovers", "image_filename": "RWS_Tarot_06_Lovers.jpg", "keywords": ("выбор", "близость", "согласие"), "upright": "Карта про честный выбор сердцем и гармонию там, где есть взаимность.", "shadow": "разлад, внутренний раскол и уход от важного выбора", "yes_weight": 2, "aliases": ("влюбленные",)},
    {"card_id": "major-07", "name_ru": "Колесница", "name_en": "Chariot", "image_filename": "RWS_Tarot_07_Chariot.jpg", "keywords": ("движение", "прорыв", "цель"), "upright": "Можно смело брать курс и двигаться вперёд, если ты держишь направление.", "shadow": "рывок без управления, конфликт целей и перегрузку", "yes_weight": 2, "aliases": ()},
    {"card_id": "major-08", "name_ru": "Сила", "name_en": "Strength", "image_filename": "RWS_Tarot_08_Strength.jpg", "keywords": ("смелость", "самообладание", "мягкая сила"), "upright": "Настоящая сила сегодня в спокойствии, выдержке и доверии собственной устойчивости.", "shadow": "внутренний срыв, подавленную злость и потерю контакта с собой", "yes_weight": 1, "aliases": ()},
    {"card_id": "major-09", "name_ru": "Отшельник", "name_en": "Hermit", "image_filename": "RWS_Tarot_09_Hermit.jpg", "keywords": ("пауза", "поиск", "мудрость"), "upright": "Лучше замедлиться, подумать и выбрать путь после честного внутреннего разговора.", "shadow": "изоляцию, затянувшуюся паузу и уход от реальности", "yes_weight": 0, "aliases": ()},
    {"card_id": "major-10", "name_ru": "Колесо Фортуны", "name_en": "Wheel of Fortune", "image_filename": "RWS_Tarot_10_Wheel_of_Fortune.jpg", "keywords": ("цикл", "шанс", "перемены"), "upright": "Ситуация может быстро развернуться, так что важно поймать момент и быть гибким.", "shadow": "чувство бессилия перед качелями судьбы и хаотичную смену курса", "yes_weight": 1, "aliases": ("фортуна",)},
    {"card_id": "major-11", "name_ru": "Справедливость", "name_en": "Justice", "image_filename": "RWS_Tarot_11_Justice.jpg", "keywords": ("баланс", "честность", "решение"), "upright": "День просит честности, ясных договорённостей и умения видеть последствия.", "shadow": "предвзятость, перекос и отказ смотреть на факты", "yes_weight": 1, "aliases": ("правосудие",)},
    {"card_id": "major-12", "name_ru": "Повешенный", "name_en": "Hanged Man", "image_filename": "RWS_Tarot_12_Hanged_Man.jpg", "keywords": ("переосмысление", "пауза", "новый угол"), "upright": "Сейчас важнее сменить взгляд, чем ломать ситуацию через силу.", "shadow": "застревание, ощущение жертвы и пустое ожидание", "yes_weight": 0, "aliases": ()},
    {"card_id": "major-13", "name_ru": "Смерть", "name_en": "Death", "image_filename": "RWS_Tarot_13_Death.jpg", "keywords": ("завершение", "трансформация", "обновление"), "upright": "Карта не про буквальный финал, а про глубокое обновление и честное завершение старого.", "shadow": "страх перемен, зацепленность за отжившее и сопротивление трансформации", "yes_weight": 0, "aliases": ()},
    {"card_id": "major-14", "name_ru": "Умеренность", "name_en": "Temperance", "image_filename": "RWS_Tarot_14_Temperance.jpg", "keywords": ("гармония", "мера", "исцеление"), "upright": "Лучший ритм дня ровный: спокойные шаги и умение смешать несовместимое в баланс.", "shadow": "крайности, внутреннюю разбалансировку и спешку", "yes_weight": 1, "aliases": ()},
    {"card_id": "major-15", "name_ru": "Дьявол", "name_en": "Devil", "image_filename": "RWS_Tarot_15_Devil.jpg", "keywords": ("искушение", "привязка", "тень"), "upright": "Карта показывает, где желание, страх или зависимость забирают свободу выбора.", "shadow": "глубокое запутывание, самообман и добровольные цепи", "yes_weight": -2, "aliases": ()},
    {"card_id": "major-16", "name_ru": "Башня", "name_en": "Tower", "image_filename": "RWS_Tarot_16_Tower.jpg", "keywords": ("встряска", "правда", "слом шаблона"), "upright": "Что-то лишнее может рухнуть, чтобы открыть место для более честной конструкции.", "shadow": "паническую реакцию, разрушение без вывода и страх перемен", "yes_weight": -2, "aliases": ()},
    {"card_id": "major-17", "name_ru": "Звезда", "name_en": "Star", "image_filename": "RWS_Tarot_17_Star.jpg", "keywords": ("надежда", "вдохновение", "свет"), "upright": "День поддерживает веру в путь, исцеление и тихое вдохновение.", "shadow": "потерю ориентира, цинизм и выгоревшую надежду", "yes_weight": 2, "aliases": ()},
    {"card_id": "major-18", "name_ru": "Луна", "name_en": "Moon", "image_filename": "RWS_Tarot_18_Moon.jpg", "keywords": ("неясность", "интуиция", "подсознание"), "upright": "Карта советует осторожнее обращаться с догадками и слушать интуицию без драматизации.", "shadow": "страхи, самообман и блуждание в тумане", "yes_weight": -1, "aliases": ()},
    {"card_id": "major-19", "name_ru": "Солнце", "name_en": "Sun", "image_filename": "RWS_Tarot_19_Sun.jpg", "keywords": ("радость", "ясность", "успех"), "upright": "Очень светлая карта: она про ясность, успех и живую энергию проявиться.", "shadow": "перегрев эго, детскую беспечность и шум вместо сути", "yes_weight": 2, "aliases": ()},
    {"card_id": "major-20", "name_ru": "Суд", "name_en": "Judgement", "image_filename": "RWS_Tarot_20_Judgement.jpg", "keywords": ("зов", "пробуждение", "итог"), "upright": "Сегодня важно услышать внутренний зов и трезво посмотреть, к чему ты уже созрел.", "shadow": "самоосуждение, страх ответа и нежелание услышать правду", "yes_weight": 1, "aliases": ()},
    {"card_id": "major-21", "name_ru": "Мир", "name_en": "World", "image_filename": "RWS_Tarot_21_World.jpg", "keywords": ("целостность", "результат", "завершение"), "upright": "Карта говорит о собранности, зрелом результате и успешном завершении цикла.", "shadow": "ощущение незавершённости и ход по кругу вместо точки", "yes_weight": 2, "aliases": ()},
)

_MINOR_SUIT_SPECS: tuple[dict[str, object], ...] = (
    {"key": "wands", "name_ru": "Жезлов", "name_en": "Wands", "theme": "энергии, инициативы и действия", "gift": "двигаться смело и не терять темп", "shadow": "спешка и выгорание", "yes_modifier": 0, "keywords": ("энергия", "воля")},
    {"key": "cups", "name_ru": "Кубков", "name_en": "Cups", "theme": "чувств, близости и внутреннего отклика", "gift": "слышать себя и не закрываться от тепла", "shadow": "эмоциональный перегиб и обидчивость", "yes_modifier": 1, "keywords": ("чувства", "связь")},
    {"key": "swords", "name_ru": "Мечей", "name_en": "Swords", "theme": "мыслей, решений и границ", "gift": "называть вещи своими именами", "shadow": "перегруз мыслями и конфликтность", "yes_modifier": -1, "keywords": ("ясность", "решение")},
    {"key": "pentacles", "name_ru": "Пентаклей", "name_en": "Pentacles", "theme": "ресурсов, работы и опоры", "gift": "делать ставку на практику и устойчивость", "shadow": "застой в материальном и страх потери опоры", "yes_modifier": 1, "keywords": ("ресурсы", "стабильность")},
)

_MINOR_RANK_SPECS: tuple[dict[str, object], ...] = (
    {"number": 1, "ru": "Туз", "en": "Ace", "focus": "Карта открывает новое окно возможностей и первый сильный импульс.", "reversed": "задержка старта и сомнение в собственном импульсе", "yes_weight": 2, "keywords": ("старт", "импульс")},
    {"number": 2, "ru": "Двойка", "en": "Two", "focus": "Сегодня многое крутится вокруг выбора, баланса и точки развилки.", "reversed": "застревание между вариантами и шаткое равновесие", "yes_weight": 1, "keywords": ("выбор", "баланс")},
    {"number": 3, "ru": "Тройка", "en": "Three", "focus": "Карта показывает рост, поддержку развития и появление перспективы.", "reversed": "слабую координацию, задержку роста и недособранность", "yes_weight": 1, "keywords": ("рост", "перспектива")},
    {"number": 4, "ru": "Четвёрка", "en": "Four", "focus": "День просит укрепить фундамент и почувствовать, что уже создаёт опору.", "reversed": "застой, слишком жёсткую фиксацию или шаткую основу", "yes_weight": 1, "keywords": ("основа", "покой")},
    {"number": 5, "ru": "Пятёрка", "en": "Five", "focus": "Карта приносит трение, проверку на устойчивость и урок через напряжение.", "reversed": "затяжной конфликт и упрямое удержание дискомфорта", "yes_weight": -1, "keywords": ("напряжение", "урок")},
    {"number": 6, "ru": "Шестёрка", "en": "Six", "focus": "Сегодня становится заметнее поддержка, движение вперёд или честный обмен.", "reversed": "несбалансированность обмена и трудность принять помощь", "yes_weight": 1, "keywords": ("поддержка", "движение")},
    {"number": 7, "ru": "Семёрка", "en": "Seven", "focus": "День требует стратегии, точности и умения не идти напролом.", "reversed": "хаотичную тактику, распыление сил и неуверенную оборону", "yes_weight": 0, "keywords": ("стратегия", "проверка")},
    {"number": 8, "ru": "Восьмёрка", "en": "Eight", "focus": "События могут ускоряться, если ты держишь фокус и рабочий ритм.", "reversed": "суету, перегрузку и ощущение, что темп вышел из-под контроля", "yes_weight": 1, "keywords": ("ускорение", "фокус")},
    {"number": 9, "ru": "Девятка", "en": "Nine", "focus": "Карта про зрелость, выносливость и умение не сдавать позиции раньше времени.", "reversed": "усталость, тревожную оборону и пробои в ресурсе", "yes_weight": 0, "keywords": ("зрелость", "границы")},
    {"number": 10, "ru": "Десятка", "en": "Ten", "focus": "Перед тобой кульминация: что-то уже дозрело до итога и просит грамотного завершения.", "reversed": "перегрузку, затянутый финал и лишний груз", "yes_weight": 0, "keywords": ("итог", "нагрузка")},
    {"number": 11, "ru": "Паж", "en": "Page", "focus": "День приносит новость, идею или шанс посмотреть на тему свежим взглядом.", "reversed": "наивность, хаотичное любопытство и пропуск важной детали", "yes_weight": 1, "keywords": ("новость", "интерес")},
    {"number": 12, "ru": "Рыцарь", "en": "Knight", "focus": "Карта усиливает движение и просит направить импульс в конкретную цель.", "reversed": "рывок без маршрута и резкость без результата", "yes_weight": 0, "keywords": ("движение", "напор")},
    {"number": 13, "ru": "Королева", "en": "Queen", "focus": "Сегодня особенно сильны зрелость, тонкость и влияние без лишнего давления.", "reversed": "внутренний перекос, капризность или скрытое напряжение", "yes_weight": 1, "keywords": ("зрелость", "мягкая власть")},
    {"number": 14, "ru": "Король", "en": "King", "focus": "Карта подчёркивает лидерство, ответственность и умение держать рамку.", "reversed": "жёсткий контроль, перегиб власти и упрямую позицию", "yes_weight": 1, "keywords": ("авторитет", "управление")},
)


def _reversed_major_text(shadow: str) -> str:
    return (
        f"В перевёрнутом положении карта говорит про {shadow}. "
        "Сегодня полезно замедлиться и проверить, что именно управляет твоим выбором."
    )


def _clamp_yes_weight(value: int) -> int:
    return max(-2, min(2, value))


def _minor_aliases(rank_name: str, number: int, suit_name: str) -> tuple[str, ...]:
    aliases = [f"{rank_name} {suit_name}"]
    if number <= 10:
        aliases.append(f"{number} {suit_name}")
    return tuple(aliases)


def _build_major_arcana() -> tuple[TarotCard, ...]:
    cards: list[TarotCard] = []
    for item in _MAJOR_ARCANA:
        aliases = tuple(item["aliases"]) + (str(item["name_ru"]), str(item["name_en"]))
        cards.append(
            TarotCard(
                card_id=str(item["card_id"]),
                deck_key=DEFAULT_DECK_KEY,
                name_ru=str(item["name_ru"]),
                name_en=str(item["name_en"]),
                suit="major",
                arcana="major",
                image_filename=str(item["image_filename"]),
                keywords=tuple(item["keywords"]),
                upright_meaning=str(item["upright"]),
                reversed_meaning=_reversed_major_text(str(item["shadow"])),
                yes_weight=int(item["yes_weight"]),
                aliases=aliases,
            )
        )
    return tuple(cards)


def _build_minor_arcana() -> tuple[TarotCard, ...]:
    cards: list[TarotCard] = []
    for suit in _MINOR_SUIT_SPECS:
        suit_key = str(suit["key"])
        suit_ru = str(suit["name_ru"])
        suit_en = str(suit["name_en"])
        suit_theme = str(suit["theme"])
        suit_gift = str(suit["gift"])
        suit_shadow = str(suit["shadow"])
        suit_keywords = tuple(suit["keywords"])
        yes_modifier = int(suit["yes_modifier"])

        for rank in _MINOR_RANK_SPECS:
            number = int(rank["number"])
            rank_ru = str(rank["ru"])
            rank_en = str(rank["en"])
            aliases = _minor_aliases(rank_ru, number, suit_ru)
            cards.append(
                TarotCard(
                    card_id=f"{suit_key}-{number:02d}",
                    deck_key=DEFAULT_DECK_KEY,
                    name_ru=f"{rank_ru} {suit_ru}",
                    name_en=f"{rank_en} of {suit_en}",
                    suit=suit_key,
                    arcana="minor",
                    image_filename=f"{suit_en}{number:02d}.jpg",
                    keywords=tuple(rank["keywords"]) + suit_keywords,
                    upright_meaning=(
                        f"{rank['focus']} В центре внимания темы {suit_theme}. "
                        f"Сегодня помогает {suit_gift}."
                    ),
                    reversed_meaning=(
                        f"В перевёрнутом положении карта показывает {rank['reversed']} "
                        f"в зоне {suit_theme}. Важно вовремя заметить {suit_shadow}."
                    ),
                    yes_weight=_clamp_yes_weight(int(rank["yes_weight"]) + yes_modifier),
                    aliases=aliases + (f"{rank_en} of {suit_en}",),
                )
            )
    return tuple(cards)


def build_tarot_deck() -> tuple[TarotCard, ...]:
    return _build_major_arcana() + _build_minor_arcana()


TAROT_DECK = build_tarot_deck()
_CARD_ID_INDEX = {card.card_id: card for card in TAROT_DECK}

_SEARCH_INDEX: dict[str, TarotCard] = {}
for _card in TAROT_DECK:
    for _alias in (_card.name_ru, _card.name_en, *_card.aliases):
        _SEARCH_INDEX.setdefault(normalize_text(_alias), _card)

_DECK_SEARCH_INDEX: dict[str, TarotDeckInfo] = {}
for _deck in DECKS.values():
    for _alias in (_deck.key, _deck.name_ru, _deck.name_en, *_deck.aliases):
        _DECK_SEARCH_INDEX.setdefault(normalize_text(_alias), _deck)


def get_deck_info(deck_key: str = DEFAULT_DECK_KEY) -> TarotDeckInfo:
    return DECKS.get(deck_key, DECKS[DEFAULT_DECK_KEY])


def get_available_decks() -> tuple[TarotDeckInfo, ...]:
    return tuple(DECKS.values())


def parse_deck(query: str) -> TarotDeckInfo | None:
    normalized = normalize_text(query)
    if not normalized:
        return None
    return _DECK_SEARCH_INDEX.get(normalized)


def build_card_image_url(card: TarotCard, deck_key: str = DEFAULT_DECK_KEY) -> str:
    if deck_key == "marseille":
        return _build_redirect_url(_build_marseille_filename(card))
    if deck_key == "sola-busca":
        return _build_redirect_url(_build_sola_busca_filename(card))
    return card.image_url


def _build_redirect_url(filename: str) -> str:
    return _WIKIMEDIA_REDIRECT_URL.format(filename=quote(filename))


def _build_marseille_filename(card: TarotCard) -> str:
    if card.arcana == "major":
        if card.card_id == "major-00":
            return "TT Tarot.png"
        major_number = int(card.card_id.split("-")[1])
        return f"T{major_number} Tarot.png"

    suit_codes = {
        "wands": "B",
        "cups": "C",
        "pentacles": "P",
        "swords": "S",
    }
    rank_codes = {
        11: "J",
        12: "H",
        13: "Q",
        14: "K",
    }
    rank_number = _minor_rank_number(card)
    rank_code = rank_codes.get(rank_number, str(rank_number))
    return f"{rank_code}{suit_codes[card.suit]} Tarot.png"


def _build_sola_busca_filename(card: TarotCard) -> str:
    if card.arcana == "major":
        major_number = int(card.card_id.split("-")[1])
        return f"Sola Busca tarot card {major_number:02d}.jpg"

    suit_bases = {
        "cups": 22,
        "pentacles": 36,
        "wands": 50,
        "swords": 64,
    }
    card_number = suit_bases[card.suit] + _minor_rank_number(card) - 1
    return f"Sola Busca tarot card {card_number:02d}.jpg"


def _minor_rank_number(card: TarotCard) -> int:
    if card.arcana != "minor":
        raise ValueError("Rank number is only available for minor arcana cards.")
    return int(card.card_id.split("-")[1])


def get_card_by_id(card_id: str) -> TarotCard | None:
    return _CARD_ID_INDEX.get(card_id)


def get_card_by_query(query: str) -> TarotCard | None:
    return _SEARCH_INDEX.get(normalize_text(query))


def search_cards(query: str, limit: int = 5) -> tuple[TarotCard, ...]:
    normalized_query = normalize_text(query)
    if not normalized_query:
        return ()

    exact = _SEARCH_INDEX.get(normalized_query)
    if exact is not None:
        return (exact,)

    matches: list[TarotCard] = []
    seen: set[str] = set()
    for card in TAROT_DECK:
        haystacks = (card.name_ru, card.name_en, *card.aliases)
        if any(normalized_query in normalize_text(value) for value in haystacks):
            if card.card_id not in seen:
                seen.add(card.card_id)
                matches.append(card)
            if len(matches) >= limit:
                break
    return tuple(matches)


def _choose_cards(count: int) -> tuple[TarotCard, ...]:
    return tuple(random.sample(TAROT_DECK, count))


def _random_orientation() -> bool:
    return random.random() < 0.35


def draw_daily_card(deck_key: str = DEFAULT_DECK_KEY) -> CardDraw:
    return CardDraw(
        position="Карта дня",
        card=_choose_cards(1)[0],
        is_reversed=_random_orientation(),
        deck_key=deck_key,
    )


def draw_weekly_card(deck_key: str = DEFAULT_DECK_KEY) -> CardDraw:
    return CardDraw(
        position="Карта недели",
        card=_choose_cards(1)[0],
        is_reversed=_random_orientation(),
        deck_key=deck_key,
    )


def draw_three_card_spread(deck_key: str = DEFAULT_DECK_KEY) -> tuple[CardDraw, ...]:
    positions = ("Прошлое", "Настоящее", "Будущее")
    cards = _choose_cards(3)
    return tuple(
        CardDraw(position=position, card=card, is_reversed=_random_orientation(), deck_key=deck_key)
        for position, card in zip(positions, cards)
    )


def draw_yes_no_card(deck_key: str = DEFAULT_DECK_KEY) -> CardDraw:
    return CardDraw(
        position="Ответ",
        card=_choose_cards(1)[0],
        is_reversed=_random_orientation(),
        deck_key=deck_key,
    )


def draw_relationship_card(deck_key: str = DEFAULT_DECK_KEY) -> CardDraw:
    return CardDraw(
        position="Динамика отношений",
        card=_choose_cards(1)[0],
        is_reversed=_random_orientation(),
        deck_key=deck_key,
    )


def draw_question_card(deck_key: str = DEFAULT_DECK_KEY) -> CardDraw:
    return CardDraw(
        position="Вопрос к таро",
        card=_choose_cards(1)[0],
        is_reversed=_random_orientation(),
        deck_key=deck_key,
    )


def evaluate_yes_no(draw: CardDraw) -> tuple[str, str]:
    score = draw.card.yes_weight if not draw.is_reversed else -draw.card.yes_weight
    if score >= 2:
        return ("Да", "Карта поддерживает действие и прямой ход событий.")
    if score == 1:
        return ("Скорее да", "Есть зелёный свет, но важно не торопить ситуацию.")
    if score == 0:
        return ("Пока неясно", "Ответ зависит от деталей и твоего следующего шага.")
    if score == -1:
        return ("Скорее нет", "Лучше перепроверить мотивацию и не давить на результат.")
    return ("Нет", "Энергия карты скорее закрывает запрос, чем открывает его.")


def format_daily_caption(draw: CardDraw) -> str:
    return (
        f"Карта дня: {draw.card.name_ru}\n"
        f"Колода: {get_deck_info(draw.deck_key).name_ru}\n"
        f"Положение: {draw.orientation_label}\n"
        f"Ключевые слова: {', '.join(draw.card.keywords)}\n\n"
        f"{draw.meaning}"
    )


def format_weekly_caption(draw: CardDraw) -> str:
    return (
        f"Карта недели: {draw.card.name_ru}\n"
        f"Колода: {get_deck_info(draw.deck_key).name_ru}\n"
        f"Положение: {draw.orientation_label}\n"
        f"Ключевые слова: {', '.join(draw.card.keywords)}\n\n"
        f"{draw.meaning}"
    )


def format_three_card_caption(draw: CardDraw) -> str:
    return (
        f"{draw.position}: {draw.card.name_ru}\n"
        f"Колода: {get_deck_info(draw.deck_key).name_ru}\n"
        f"{draw.orientation_label}\n"
        f"{draw.meaning}"
    )


def format_yes_no_caption(draw: CardDraw, question: str | None = None) -> str:
    answer, nuance = evaluate_yes_no(draw)
    question_block = f"Вопрос: {question}\n" if question else ""
    return (
        f"{question_block}Ответ: {answer}\n"
        f"Карта: {draw.card.name_ru}\n"
        f"Колода: {get_deck_info(draw.deck_key).name_ru}\n"
        f"Положение: {draw.orientation_label}\n\n"
        f"{nuance}\n"
        f"Подсказка карты: {draw.meaning}"
    )


def format_relationship_caption(draw: CardDraw) -> str:
    return (
        f"Карта отношений: {draw.card.name_ru}\n"
        f"Колода: {get_deck_info(draw.deck_key).name_ru}\n"
        f"Положение: {draw.orientation_label}\n"
        f"Ключевые слова: {', '.join(draw.card.keywords)}\n\n"
        f"Динамика между вами сейчас читается так: {draw.meaning}"
    )


def format_question_caption(draw: CardDraw, question: str, interpretation: str) -> str:
    return (
        f"Вопрос: {question}\n"
        f"Карта: {draw.card.name_ru}\n"
        f"Колода: {get_deck_info(draw.deck_key).name_ru}\n"
        f"Положение: {draw.orientation_label}\n"
        f"Ключевые слова: {', '.join(draw.card.keywords)}\n\n"
        f"{interpretation}"
    )


def format_card_guide(card: TarotCard, deck_key: str = DEFAULT_DECK_KEY) -> str:
    return (
        f"{card.name_ru}\n"
        f"Колода: {get_deck_info(deck_key).name_ru}\n"
        f"Ключевые слова: {', '.join(card.keywords)}\n\n"
        f"Прямое положение: {card.upright_meaning}\n\n"
        f"Перевёрнутое положение: {card.reversed_meaning}"
    )
