from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import random

from app.horoscope import format_date_ru


@dataclass(frozen=True, slots=True)
class Rune:
    name: str
    transliteration: str
    theme: str
    advice: str


@dataclass(frozen=True, slots=True)
class RuneDraw:
    rune: Rune
    for_day: date


@dataclass(frozen=True, slots=True)
class MagicBallReply:
    answer: str
    mood: str


RUNE_SYMBOLS: dict[str, str] = {
    "F": "ᚠ",
    "U": "ᚢ",
    "Th": "ᚦ",
    "A": "ᚨ",
    "R": "ᚱ",
    "K": "ᚲ",
    "G": "ᚷ",
    "W": "ᚹ",
    "H": "ᚺ",
    "N": "ᚾ",
    "I": "ᛁ",
    "J": "ᛃ",
    "Ei": "ᛇ",
    "P": "ᛈ",
    "Z": "ᛉ",
    "S": "ᛋ",
    "T": "ᛏ",
    "B": "ᛒ",
    "E": "ᛖ",
    "M": "ᛗ",
    "L": "ᛚ",
    "Ng": "ᛜ",
    "D": "ᛞ",
    "O": "ᛟ",
}


RUNES: tuple[Rune, ...] = (
    Rune("Феху", "F", "ресурсы и приток энергии", "смотри, куда реально уходит твоя сила, время и внимание"),
    Rune("Уруз", "U", "сила, выносливость и телесный импульс", "делай ставку на действие, а не на долгое раскачивание"),
    Rune("Турисаз", "Th", "порог, защита и пауза перед рывком", "не спеши входить туда, где ещё не проверены границы"),
    Rune("Ансуз", "A", "слово, послание и важный разговор", "обрати внимание на формулировки и смысл между строк"),
    Rune("Райдо", "R", "путь, движение и верный ритм", "проверь, туда ли ведет привычный маршрут"),
    Rune("Кеназ", "K", "ясность, ремесло и внутренний огонь", "покажи навык, который нельзя держать в тени"),
    Rune("Гебо", "G", "обмен, союз и встречное движение", "смотри, где важно не только брать, но и отвечать взаимностью"),
    Rune("Вуньо", "W", "радость, облегчение и светлый результат", "не обесценивай маленький повод порадоваться сегодня"),
    Rune("Хагалаз", "H", "встряска, резкая перемена и освобождение", "если что-то ломается, смотри, что именно это освобождает"),
    Rune("Наутиз", "N", "необходимость, дисциплина и зрелый минимум", "выбирай не идеал, а то, что действительно нужно"),
    Rune("Иса", "I", "стоп, кристаллизация и сохранение ресурса", "не путай паузу с проигрышем, иногда это умная остановка"),
    Rune("Йера", "J", "урожай, цикл и отдача за пройденный путь", "оцени, что уже созрело и готово к сбору"),
    Rune("Эйваз", "Ei", "опора, внутренняя ось и выдержка", "стой ровно в том, что действительно для тебя важно"),
    Rune("Перт", "P", "тайна, шанс и скрытый поворот", "оставь место для варианта, который пока не виден полностью"),
    Rune("Альгиз", "Z", "защита, интуиция и безопасная дистанция", "лучше лишний раз проверить границы, чем потом их собирать"),
    Rune("Соулу", "S", "успех, витальность и ясное направление", "день любит уверенный шаг и прямую позицию"),
    Rune("Тейваз", "T", "воля, честь и точное усилие", "направь силу туда, где нужен поступок, а не шум"),
    Rune("Беркана", "B", "рост, забота и мягкое раскрытие", "поддержи то, что ещё растет, а не требуй от него зрелости"),
    Rune("Эваз", "E", "партнёрство, синхрон и движение в паре", "проверь, совпадает ли ваш темп с теми, кто рядом"),
    Rune("Манназ", "M", "человек, отражение и социальная роль", "заметь, что сегодня помогает именно контакт с людьми"),
    Rune("Лагуз", "L", "интуиция, поток и чувствование момента", "не дави на решение, если его ещё нужно дослушать внутри"),
    Rune("Ингуз", "Ng", "созревание, внутренний заряд и готовность", "то, что копилось внутри, может попроситься в форму"),
    Rune("Дагаз", "D", "прорыв, рассвет и смена перспективы", "день хорошо подходит для новой оптики на старую задачу"),
    Rune("Одал", "O", "корни, дом и личная территория", "береги то, что создаёт ощущение своей опоры"),
)

MAGIC_BALL_REPLIES: tuple[MagicBallReply, ...] = (
    MagicBallReply("Бесспорно", "энергия ответа прямая и уверенная"),
    MagicBallReply("Скорее да", "сценарий складывается в твою пользу, если не тянуть"),
    MagicBallReply("Да, но с оговорками", "результат возможен, если учесть тонкий момент"),
    MagicBallReply("Пока неясно", "сейчас картинка ещё недосказана"),
    MagicBallReply("Спроси позже", "вопросу нужно немного времени и новых данных"),
    MagicBallReply("Лучше не торопиться", "сначала проверь основание решения"),
    MagicBallReply("Скорее нет", "энергия ответа больше про паузу и пересмотр"),
    MagicBallReply("Нет", "сейчас это направление не выглядит удачным"),
)


def draw_rune_of_day(user_id: int, for_day: date | None = None) -> RuneDraw:
    current_day = for_day or date.today()
    seed = sha256(f"{current_day.isoformat()}:{user_id}".encode("utf-8")).digest()
    rng = random.Random(int.from_bytes(seed[:8], byteorder="big"))
    return RuneDraw(rune=rng.choice(RUNES), for_day=current_day)


def get_rune_symbol(rune: Rune) -> str:
    return RUNE_SYMBOLS.get(rune.transliteration, rune.transliteration)


def format_rune_draw(draw: RuneDraw) -> str:
    symbol = get_rune_symbol(draw.rune)
    return (
        f"Руна дня на {format_date_ru(draw.for_day)}\n\n"
        f"{draw.rune.name} {symbol} ({draw.rune.transliteration})\n"
        f"Тема: {draw.rune.theme}.\n"
        f"Совет: {draw.rune.advice}."
    )


def ask_magic_ball(question: str, rng: random.Random | None = None) -> MagicBallReply:
    generator = rng or random.SystemRandom()
    return generator.choice(MAGIC_BALL_REPLIES)


def format_magic_ball_reply(question: str, reply: MagicBallReply) -> str:
    return (
        "Шар предсказаний отвечает\n\n"
        f"Вопрос: {question}\n"
        f"Ответ: {reply.answer}\n"
        f"Оттенок: {reply.mood}."
    )
