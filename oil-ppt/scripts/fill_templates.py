#!/usr/bin/env python3
"""Program-owned native markup for data-heavy component templates."""
from __future__ import annotations

import html
import math

from component_registry import DATA_STORY_QUESTIONS


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _precision(value: float, explicit: int | None) -> int:
    if explicit is not None:
        return explicit
    if math.isclose(value, round(value), rel_tol=0, abs_tol=1e-9):
        return 0
    magnitude = abs(value)
    if 0 < magnitude < 0.01:
        return min(6, max(3, -math.floor(math.log10(magnitude)) + 1))
    if math.isclose(value * 10, round(value * 10), rel_tol=0, abs_tol=1e-8):
        return 1
    return 2


def format_number(value: float, *, precision: int | None = None, compact: bool = False) -> str:
    """Format a validated finite number without delegating display choices to the model."""
    number = float(value)
    if number and abs(number) < 0.000001:
        digits = 2 if precision is None else max(0, min(precision, 6))
        return f"{number:.{digits}e}"
    suffix = ""
    scaled = number
    if compact:
        for threshold, token in (
            (1_000_000_000_000_000, "Q"), (1_000_000_000_000, "T"),
            (1_000_000_000, "B"), (1_000_000, "M"), (1_000, "k"),
        ):
            if abs(number) >= threshold:
                scaled = number / threshold
                suffix = token
                break
    digits = _precision(scaled, precision)
    rendered = f"{scaled:,.{digits}f}"
    if digits:
        rendered = rendered.rstrip("0").rstrip(".")
    if rendered == "-0":
        rendered = "0"
    return rendered + suffix


def _value(value: float, unit: str, precision: int | None, *, compact: bool = False) -> str:
    return f"{format_number(value, precision=precision, compact=compact)}{unit}"


def _nice_ticks(values: list[float], *, include_zero: bool, target: int = 5) -> list[float]:
    low = min(values)
    high = max(values)
    if include_zero:
        low = min(low, 0.0)
        high = max(high, 0.0)
    if math.isclose(low, high):
        pad = max(abs(low) * 0.2, 1.0)
        low -= pad
        high += pad
    else:
        pad = (high - low) * 0.06
        low -= pad
        high += pad
        if include_zero and min(values) >= 0:
            low = 0.0
        if include_zero and max(values) <= 0:
            high = 0.0
    raw = (high - low) / max(2, target - 1)
    power = 10 ** math.floor(math.log10(raw))
    scaled = raw / power
    step = (1 if scaled <= 1 else 2 if scaled <= 2 else 5 if scaled <= 5 else 10) * power
    start = math.floor(low / step) * step
    end = math.ceil(high / step) * step
    ticks: list[float] = []
    current = start
    while current <= end + step * 0.25 and len(ticks) < 8:
        ticks.append(0.0 if math.isclose(current, 0, abs_tol=step * 1e-9) else current)
        current += step
    return ticks


def _scale(value: float, domain: tuple[float, float], target: tuple[float, float]) -> float:
    start, end = domain
    if math.isclose(start, end):
        return sum(target) / 2
    return target[0] + (value - start) / (end - start) * (target[1] - target[0])


def _svg(body: str, label: str) -> str:
    return (
        f'<svg class="data-svg" viewBox="0 0 1000 580" role="img" '
        f'aria-label="{_esc(label)}" preserveAspectRatio="xMidYMid meet">{body}</svg>'
    )


def _category(data: dict) -> str:
    items = data["items"]
    values = [float(item["value"]) for item in items]
    unit = str(data.get("unit") or "")
    precision = data.get("precision")
    ticks = _nice_ticks(values, include_zero=True)
    domain = (ticks[0], ticks[-1])
    left, right, top, bottom = 210.0, 890.0, 42.0, 530.0
    zero_x = _scale(0, domain, (left, right))
    rows = []
    for tick in ticks:
        x = _scale(tick, domain, (left, right))
        rows.append(
            f'<line class="grid-line" x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}"/>'
            f'<text class="tick x-tick" x="{x:.1f}" y="560" text-anchor="middle">'
            f'{_esc(_value(tick, unit, precision, compact=True))}</text>'
        )
    row_height = (bottom - top) / len(items)
    peak = max(values)
    for index, item in enumerate(items):
        value = float(item["value"])
        value_x = _scale(value, domain, (left, right))
        x = min(zero_x, value_x)
        width = max(3.0, abs(value_x - zero_x))
        y = top + index * row_height + row_height * 0.5
        focus = " focus" if value == peak else ""
        anchor = "start" if value >= 0 else "end"
        value_label_x = value_x + (14 if value >= 0 else -14)
        rows.append(
            f'<text class="category-label" x="188" y="{y + 7:.1f}" text-anchor="end">{_esc(item["label"])}</text>'
            f'<rect class="category-bar{focus}" x="{x:.1f}" y="{y - 17:.1f}" width="{width:.1f}" height="34" rx="17"/>'
            f'<text class="value-label" x="{value_label_x:.1f}" y="{y + 7:.1f}" text-anchor="{anchor}">'
            f'{_esc(_value(value, unit, precision))}</text>'
        )
    rows.append(f'<line class="zero-line" x1="{zero_x:.1f}" y1="{top}" x2="{zero_x:.1f}" y2="{bottom}"/>')
    return _svg("".join(rows), DATA_STORY_QUESTIONS["category-comparison"])


def _trend(data: dict) -> str:
    items = data["items"]
    values = [float(item["value"]) for item in items]
    unit = str(data.get("unit") or "")
    precision = data.get("precision")
    ticks = _nice_ticks(values, include_zero=False)
    domain = (ticks[0], ticks[-1])
    left, right, top, bottom = 92.0, 952.0, 42.0, 470.0
    marks = []
    for tick in ticks:
        y = _scale(tick, domain, (bottom, top))
        marks.append(
            f'<line class="grid-line" x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}"/>'
            f'<text class="tick" x="72" y="{y + 6:.1f}" text-anchor="end">'
            f'{_esc(_value(tick, unit, precision, compact=True))}</text>'
        )
    x_step = (right - left) / max(1, len(items) - 1)
    points = [(left + index * x_step, _scale(value, domain, (bottom, top))) for index, value in enumerate(values)]
    path = " ".join(("M" if index == 0 else "L") + f"{x:.1f},{y:.1f}" for index, (x, y) in enumerate(points))
    area = path + f" L{right:.1f},{bottom:.1f} L{left:.1f},{bottom:.1f} Z"
    marks.append(f'<path class="trend-area" d="{area}"/><path class="trend-line" d="{path}"/>')
    for index, ((x, y), item, value) in enumerate(zip(points, items, values)):
        focus = " focus" if index == len(items) - 1 else ""
        marks.append(
            f'<circle class="trend-point{focus}" cx="{x:.1f}" cy="{y:.1f}" r="{10 if focus else 7}"/>'
            f'<text class="value-label" x="{x:.1f}" y="{max(25, y - 17):.1f}" text-anchor="middle">'
            f'{_esc(_value(value, unit, precision))}</text>'
            f'<text class="tick x-tick" x="{x:.1f}" y="520" text-anchor="middle">{_esc(item["label"])}</text>'
        )
    return _svg("".join(marks), DATA_STORY_QUESTIONS["trend"])


def _composition(data: dict) -> str:
    items = data["items"]
    values = [float(item["value"]) for item in items]
    total = sum(values)
    unit = str(data.get("unit") or "")
    precision = data.get("precision")
    left, width, y, height = 54.0, 892.0, 86.0, 94.0
    marks = [
        f'<text class="total-label" x="54" y="48">TOTAL</text>',
        f'<text class="total-value" x="946" y="50" text-anchor="end">{_esc(_value(total, unit, precision))}</text>',
    ]
    cursor = left
    for index, (item, value) in enumerate(zip(items, values), start=1):
        segment = width * value / total
        marks.append(
            f'<rect class="series-{index}" x="{cursor:.1f}" y="{y}" width="{max(0, segment):.1f}" height="{height}"/>'
        )
        if segment >= 88:
            marks.append(
                f'<text class="segment-label" x="{cursor + segment / 2:.1f}" y="{y + 57:.1f}" text-anchor="middle">'
                f'{_esc(format_number(value / total * 100, precision=1))}%</text>'
            )
        cursor += segment
    column_width = 445
    row_height = 102
    for index, (item, value) in enumerate(zip(items, values), start=1):
        column = (index - 1) % 2
        row = (index - 1) // 2
        x = 60 + column * column_width
        legend_y = 270 + row * row_height
        share = value / total * 100
        marks.append(
            f'<circle class="series-{index}" cx="{x + 12}" cy="{legend_y - 5}" r="12"/>'
            f'<text class="legend-label" x="{x + 38}" y="{legend_y + 2}">{_esc(item["label"])}</text>'
            f'<text class="legend-value" x="{x + 390}" y="{legend_y + 2}" text-anchor="end">'
            f'{_esc(_value(value, unit, precision))}</text>'
            f'<text class="legend-share" x="{x + 38}" y="{legend_y + 31}">'
            f'{_esc(format_number(share, precision=1))}%</text>'
        )
    return _svg("".join(marks), DATA_STORY_QUESTIONS["composition"])


def _relationship(data: dict) -> str:
    items = data["items"]
    x_values = [float(item["x"]) for item in items]
    y_values = [float(item["y"]) for item in items]
    x_ticks = _nice_ticks(x_values, include_zero=False)
    y_ticks = _nice_ticks(y_values, include_zero=False)
    x_domain = (x_ticks[0], x_ticks[-1])
    y_domain = (y_ticks[0], y_ticks[-1])
    x_unit = str(data.get("x_unit") or "")
    y_unit = str(data.get("y_unit") or "")
    precision = data.get("precision")
    left, right, top, bottom = 92.0, 952.0, 38.0, 402.0
    marks = []
    for tick in x_ticks:
        x = _scale(tick, x_domain, (left, right))
        marks.append(
            f'<line class="grid-line" x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}"/>'
            f'<text class="tick" x="{x:.1f}" y="434" text-anchor="middle">'
            f'{_esc(_value(tick, x_unit, precision, compact=True))}</text>'
        )
    for tick in y_ticks:
        y = _scale(tick, y_domain, (bottom, top))
        marks.append(
            f'<line class="grid-line" x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}"/>'
            f'<text class="tick" x="72" y="{y + 6:.1f}" text-anchor="end">'
            f'{_esc(_value(tick, y_unit, precision, compact=True))}</text>'
        )
    marks.extend([
        f'<text class="axis-label" x="{right}" y="466" text-anchor="end">{_esc(data["x_label"])}</text>',
        f'<text class="axis-label" x="22" y="{top}" transform="rotate(-90 22 {top})" text-anchor="end">{_esc(data["y_label"])}</text>',
    ])
    for index, item in enumerate(items, start=1):
        x = _scale(float(item["x"]), x_domain, (left, right))
        y = _scale(float(item["y"]), y_domain, (bottom, top))
        details = (
            f'{item["label"]}: {data["x_label"]} '
            f'{_value(float(item["x"]), x_unit, precision)}, {data["y_label"]} '
            f'{_value(float(item["y"]), y_unit, precision)}'
        )
        marks.append(
            f'<g class="relation-point"><title>{_esc(details)}</title>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="14"/>'
            f'<text x="{x:.1f}" y="{y + 5:.1f}" text-anchor="middle">{index:02d}</text></g>'
        )
    columns = 3
    for index, item in enumerate(items, start=1):
        column = (index - 1) % columns
        row = (index - 1) // columns
        x = 60 + column * 310
        y = 494 + row * 24
        marks.append(
            f'<text class="relation-legend" x="{x}" y="{y}">'
            f'<tspan class="relation-index">{index:02d}</tspan><tspan dx="10">{_esc(item["label"])}</tspan></text>'
        )
    return _svg("".join(marks), DATA_STORY_QUESTIONS["relationship"])


def render_data_story(slide: dict) -> str:
    data = slide["data"]
    variant = str(slide["variant"])
    renderers = {
        "category-comparison": _category,
        "trend": _trend,
        "composition": _composition,
        "relationship": _relationship,
    }
    return renderers[variant](data)
