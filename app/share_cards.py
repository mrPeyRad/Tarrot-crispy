from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen

from app.biorhythm import BiorhythmSnapshot
from app.cosmic import CompatibilityInsight
from app.tarot import CardDraw, get_deck_info

try:
    from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps
except ImportError:  # pragma: no cover - depends on optional dependency
    Image = None  # type: ignore[assignment]
    ImageColor = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]
    ImageFont = None  # type: ignore[assignment]
    ImageOps = None  # type: ignore[assignment]


CANVAS_SIZE = (1080, 1350)


def render_tarot_share_card(
    draw_result: CardDraw,
    title: str,
    body_text: str,
    bot_username: str,
    question: str | None = None,
) -> bytes:
    _require_pillow()
    deck = get_deck_info(draw_result.deck_key)
    image = _create_canvas(
        primary=f"#{deck.background_hex}",
        secondary=f"#{deck.foreground_hex}",
    )
    draw = ImageDraw.Draw(image)
    title_font = _load_font(58, bold=True)
    subtitle_font = _load_font(34, bold=True)
    body_font = _load_font(28)
    small_font = _load_font(24)
    tiny_font = _load_font(24)

    _ = body_text
    _draw_header(draw, "Mystic Card", title, bot_username, title_font, small_font)
    _draw_glass_card(draw, (72, 220, 1008, 1240))

    art_bounds = (292, 278, 788, 946)
    _draw_tarot_art(image, draw_result, art_bounds)

    draw.text((108, 990), draw_result.card.name_ru, font=title_font, fill="#fff8ef")
    orientation_box = (108, 1068, 566, 1130)
    _draw_pill(draw, orientation_box, draw_result.orientation_label.title(), subtitle_font, "#fff8ef", "#00000055")

    info_text = f"Колода: {deck.name_ru}"
    draw.text((108, 1154), info_text, font=small_font, fill="#f7f0dd")

    if question:
        _draw_wrapped_text(draw, f"Вопрос: {question}", body_font, "#fff8ef", 108, 1184, 864, 1)

    watermark = f"репост из {bot_username}"
    draw.text((108, 1212), watermark, font=tiny_font, fill="#f8edd2cc")
    return _export_png(image)


def render_compatibility_share_card(
    insight: CompatibilityInsight,
    bot_username: str,
) -> bytes:
    _require_pillow()
    image = _create_canvas(primary="#18243d", secondary="#f48c6c")
    draw = ImageDraw.Draw(image)
    title_font = _load_font(72, bold=True)
    subtitle_font = _load_font(42, bold=True)
    body_font = _load_font(34)
    small_font = _load_font(26)
    tiny_font = _load_font(24)

    _draw_header(draw, "Cosmic Match", "Совместимость знаков", bot_username, title_font, small_font)
    _draw_glass_card(draw, (72, 220, 1008, 1240))

    pair_title = f"{insight.first.name} + {insight.second.name}"
    draw.text((108, 282), pair_title, font=title_font, fill="#fff8ef")

    score_bounds = (728, 260, 972, 504)
    draw.ellipse(score_bounds, fill="#f48c6c", outline="#fff4ea", width=6)
    score_text = f"{insight.score}%"
    _draw_centered_text(draw, score_text, _load_font(64, bold=True), "#18243d", score_bounds)
    _draw_centered_text(draw, "химия", small_font, "#18243d", (728, 408, 972, 460))

    _draw_section_label(draw, "Ключевая динамика", 108, 430, subtitle_font, small_font)
    next_y = _draw_wrapped_text(draw, insight.summary, body_font, "#fff8ef", 108, 492, 540, 4) + 28

    _draw_section_label(draw, "Сильная сторона", 108, next_y, subtitle_font, small_font)
    next_y = _draw_wrapped_text(draw, insight.strength, body_font, "#fff8ef", 108, next_y + 62, 864, 3) + 28

    _draw_section_label(draw, "Зона роста", 108, next_y, subtitle_font, small_font)
    next_y = _draw_wrapped_text(draw, insight.growth_zone, body_font, "#fff8ef", 108, next_y + 62, 864, 3) + 28

    _draw_section_label(draw, "Как любите", 108, next_y, subtitle_font, small_font)
    next_y = _draw_wrapped_text(
        draw,
        f"{insight.first.name}: {insight.first_love_style}",
        body_font,
        "#fff8ef",
        108,
        next_y + 62,
        864,
        3,
    ) + 18
    _draw_wrapped_text(
        draw,
        f"{insight.second.name}: {insight.second_love_style}",
        body_font,
        "#fff8ef",
        108,
        next_y,
        864,
        3,
    )

    draw.text((108, 1188), f"собрано для шаринга • {bot_username}", font=tiny_font, fill="#f7eee1cc")
    return _export_png(image)


def render_biorhythm_share_card(snapshot: BiorhythmSnapshot, bot_username: str) -> bytes:
    _require_pillow()
    image = _create_canvas(primary="#10253d", secondary="#1fa4a5")
    draw = ImageDraw.Draw(image)
    title_font = _load_font(68, bold=True)
    subtitle_font = _load_font(40, bold=True)
    body_font = _load_font(32)
    small_font = _load_font(26)
    tiny_font = _load_font(24)

    _draw_header(draw, "Body Cycles", "Биоритмы на сегодня", bot_username, title_font, small_font)
    _draw_glass_card(draw, (72, 220, 1008, 1240))

    draw.text((108, 274), snapshot.target_date.strftime("%d.%m.%Y"), font=title_font, fill="#eff8f7")
    draw.text(
        (108, 352),
        f"Дата рождения: {snapshot.birth_date.strftime('%d.%m.%Y')}",
        font=body_font,
        fill="#d7efed",
    )

    _draw_metric(draw, "Физический", snapshot.physical, (108, 430, 380, 542), "#ff8a65")
    _draw_metric(draw, "Эмоции", snapshot.emotional, (404, 430, 676, 542), "#ffd166")
    _draw_metric(draw, "Интеллект", snapshot.intellectual, (700, 430, 972, 542), "#1fa4a5")

    chart_bounds = (118, 620, 962, 1010)
    _draw_chart(draw, snapshot, chart_bounds, small_font)
    draw.text((108, 1188), f"цикл дня • {bot_username}", font=tiny_font, fill="#d7efedcc")
    return _export_png(image)


def _require_pillow() -> None:
    if Image is None or ImageColor is None or ImageDraw is None or ImageFont is None or ImageOps is None:
        raise RuntimeError("Для красивых карточек нужен Pillow.")


def _draw_tarot_art(image, draw_result: CardDraw, bounds: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = bounds
    width = right - left
    height = bottom - top
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        (left + 14, top + 18, right + 14, bottom + 18),
        radius=36,
        fill=(0, 0, 0, 72),
    )
    image.alpha_composite(shadow)

    art = _load_tarot_art(draw_result)
    if draw_result.is_reversed:
        art = art.rotate(180, expand=False)
    art = art.convert("RGBA")

    panel = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    panel_draw = ImageDraw.Draw(panel)
    frame_fill = (247, 239, 225, 245)
    frame_outline = (255, 243, 223, 255)
    inner_outline = (214, 191, 150, 235)
    panel_draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=36, fill=frame_fill, outline=frame_outline, width=5)
    panel_draw.rounded_rectangle((14, 14, width - 15, height - 15), radius=28, outline=inner_outline, width=2)

    padding = 26
    art = ImageOps.contain(
        art,
        (width - (padding * 2), height - (padding * 2)),
        method=_resampling_filter(),
    )
    art_left = (width - art.width) // 2
    art_top = (height - art.height) // 2

    art_shadow = Image.new("RGBA", panel.size, (0, 0, 0, 0))
    art_shadow_draw = ImageDraw.Draw(art_shadow)
    art_shadow_draw.rounded_rectangle(
        (art_left + 10, art_top + 14, art_left + art.width + 10, art_top + art.height + 14),
        radius=24,
        fill=(0, 0, 0, 38),
    )
    panel.alpha_composite(art_shadow)
    panel.alpha_composite(art, dest=(art_left, art_top))

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay.paste(panel, (left, top), panel)
    image.alpha_composite(overlay)

    border = ImageDraw.Draw(image)
    border.rounded_rectangle(bounds, radius=36, outline="#fff3df", width=5)


def _load_tarot_art(draw_result: CardDraw):
    candidates = [draw_result.image_url]
    if draw_result.card.image_url not in candidates:
        candidates.append(draw_result.card.image_url)

    for candidate in candidates:
        image = _download_remote_image(candidate)
        if image is not None:
            return image
    return _build_local_tarot_fallback(draw_result)


@lru_cache(maxsize=256)
def _download_remote_image(url: str):
    try:
        request = Request(url, headers={"User-Agent": "Tarrot-crispy/1.0"})
        with urlopen(request, timeout=3) as response:
            payload = response.read()
    except Exception:
        return None

    try:
        return Image.open(BytesIO(payload)).convert("RGB")
    except Exception:
        return None


def _build_local_tarot_fallback(draw_result: CardDraw):
    deck = get_deck_info(draw_result.deck_key)
    card = Image.new("RGB", (720, 1080), f"#{deck.background_hex}")
    draw = ImageDraw.Draw(card)
    border_color = f"#{deck.foreground_hex}"
    draw.rounded_rectangle((28, 28, 692, 1052), radius=36, fill="#fffaf2", outline=border_color, width=10)
    draw.rounded_rectangle((64, 76, 656, 1004), radius=26, outline=border_color, width=4)
    draw.text((96, 124), "TAROT", font=_load_font(40, bold=True), fill=border_color)
    _draw_wrapped_text(draw, draw_result.card.name_ru, _load_font(48, bold=True), border_color, 96, 220, 528, 4)
    _draw_wrapped_text(
        draw,
        ", ".join(draw_result.card.keywords),
        _load_font(30),
        border_color,
        96,
        500,
        528,
        5,
    )
    return card


def _create_canvas(primary: str, secondary: str):
    width, height = CANVAS_SIZE
    image = Image.new("RGBA", CANVAS_SIZE, primary)
    draw = ImageDraw.Draw(image)
    start = ImageColor.getrgb(primary)
    end = ImageColor.getrgb(secondary)
    for y in range(height):
        mix = y / max(1, height - 1)
        color = tuple(
            round(start[index] * (1 - mix) + end[index] * mix)
            for index in range(3)
        )
        draw.line((0, y, width, y), fill=color)

    overlay = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.ellipse((-120, -80, 520, 520), fill=(255, 255, 255, 24))
    overlay_draw.ellipse((620, 80, 1240, 760), fill=(255, 255, 255, 20))
    overlay_draw.ellipse((420, 960, 1120, 1600), fill=(255, 255, 255, 18))
    return Image.alpha_composite(image, overlay)


def _draw_header(draw, eyebrow: str, title: str, bot_username: str, title_font, small_font) -> None:
    draw.text((72, 52), eyebrow.upper(), font=small_font, fill="#f6ecd6cc")
    draw.text((72, 96), title, font=title_font, fill="#fff9ef")
    draw.text((842, 76), bot_username, font=small_font, fill="#fff9efcc")


def _draw_glass_card(draw, bounds: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(bounds, radius=42, fill="#00000055", outline="#ffffff30", width=2)


def _draw_pill(draw, bounds: tuple[int, int, int, int], text: str, font, text_fill: str, fill: str) -> None:
    draw.rounded_rectangle(bounds, radius=28, fill=fill)
    _draw_centered_text(draw, text, font, text_fill, bounds)


def _draw_centered_text(draw, text: str, font, fill: str, bounds: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = bounds
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    x = left + ((right - left) - text_width) / 2
    y = top + ((bottom - top) - text_height) / 2 - 4
    draw.text((x, y), text, font=font, fill=fill)


def _draw_section_label(draw, text: str, x: int, y: int, title_font, label_font) -> None:
    draw.text((x, y), text, font=title_font, fill="#fff9ef")
    draw.text((x, y - 26), "•", font=label_font, fill="#fff1d6")


def _draw_wrapped_text(
    draw,
    text: str,
    font,
    fill: str,
    x: int,
    y: int,
    max_width: int,
    max_lines: int,
) -> int:
    lines = _wrap_text(draw, text, font, max_width, max_lines)
    line_height = _line_height(font)
    for index, line in enumerate(lines):
        draw.text((x, y + (index * line_height)), line, font=font, fill=fill)
    return y + (len(lines) * line_height)


def _wrap_text(draw, text: str, font, max_width: int, max_lines: int) -> list[str]:
    words = text.replace("\n", " \n ").split()
    if not words:
        return [""]

    lines: list[str] = []
    current = ""
    for word in words:
        if word == "\n":
            if current:
                lines.append(current.rstrip())
                current = ""
            continue

        candidate = word if not current else f"{current} {word}"
        if _text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue

        if current:
            lines.append(current.rstrip())
            current = word
        else:
            lines.append(_truncate_to_width(draw, word, font, max_width))
            current = ""

        if len(lines) >= max_lines:
            break

    if current and len(lines) < max_lines:
        lines.append(current.rstrip())

    if len(lines) > max_lines:
        lines = lines[:max_lines]

    if len(lines) == max_lines and " ".join(lines) != " ".join(words).replace(" \n ", " ").strip():
        lines[-1] = _append_ellipsis(draw, lines[-1], font, max_width)
    return lines


def _truncate_to_width(draw, text: str, font, max_width: int) -> str:
    result = text
    while result and _text_width(draw, result, font) > max_width:
        result = result[:-1]
    return result.rstrip()


def _append_ellipsis(draw, text: str, font, max_width: int) -> str:
    candidate = text.rstrip(". ") + "…"
    while candidate and _text_width(draw, candidate, font) > max_width:
        candidate = candidate[:-2].rstrip() + "…"
    return candidate


def _text_width(draw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _line_height(font) -> int:
    bbox = font.getbbox("Ag")
    return (bbox[3] - bbox[1]) + 12


def _draw_metric(draw, label: str, value: float, bounds: tuple[int, int, int, int], accent: str) -> None:
    draw.rounded_rectangle(bounds, radius=30, fill="#ffffff12", outline="#ffffff22", width=2)
    left, top, _, _ = bounds
    draw.text((left + 24, top + 20), label, font=_load_font(26, bold=True), fill="#eff8f7")
    draw.text((left + 24, top + 62), f"{round(value * 100):+d}%", font=_load_font(42, bold=True), fill=accent)


def _draw_chart(draw, snapshot: BiorhythmSnapshot, bounds: tuple[int, int, int, int], label_font) -> None:
    left, top, right, bottom = bounds
    draw.rounded_rectangle(bounds, radius=32, fill="#0a162644", outline="#ffffff22", width=2)

    mid_y = top + ((bottom - top) / 2)
    draw.line((left + 28, mid_y, right - 28, mid_y), fill="#ffffff33", width=2)
    for fraction in (0.25, 0.75):
        y = top + ((bottom - top) * fraction)
        draw.line((left + 28, y, right - 28, y), fill="#ffffff18", width=1)

    points = snapshot.points
    step_x = (right - left - 80) / max(1, len(points) - 1)
    chart_height = bottom - top - 120

    def to_xy(index: int, value: float) -> tuple[float, float]:
        x = left + 40 + (index * step_x)
        y = top + 60 + ((1 - ((value + 1) / 2)) * chart_height)
        return x, y

    _draw_series(draw, [to_xy(index, point.physical) for index, point in enumerate(points)], "#ff8a65")
    _draw_series(draw, [to_xy(index, point.emotional) for index, point in enumerate(points)], "#ffd166")
    _draw_series(draw, [to_xy(index, point.intellectual) for index, point in enumerate(points)], "#1fa4a5")

    for index, point in enumerate(points):
        x = left + 40 + (index * step_x)
        label = point.day.strftime("%d.%m")
        bbox = draw.textbbox((0, 0), label, font=label_font)
        draw.text((x - ((bbox[2] - bbox[0]) / 2), bottom - 42), label, font=label_font, fill="#d7efed")


def _draw_series(draw, points: Iterable[tuple[float, float]], color: str) -> None:
    normalized_points = list(points)
    if len(normalized_points) >= 2:
        draw.line(normalized_points, fill=color, width=6)
    for x, y in normalized_points:
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=color)


def _load_font(size: int, bold: bool = False):
    candidates = _font_candidates(bold)
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            return ImageFont.truetype(str(candidate), size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _font_candidates(bold: bool) -> tuple[Path, ...]:
    if bold:
        names = (
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        )
    else:
        names = (
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        )
    return tuple(Path(name) for name in names)


def _resampling_filter():
    resampling = getattr(Image, "Resampling", None)
    if resampling is not None:
        return resampling.LANCZOS
    return Image.LANCZOS


def _export_png(image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
