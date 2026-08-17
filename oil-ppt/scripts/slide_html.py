"""Exact standalone slide document parsing and static safety validation."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from html_urls import css_urls

CSS_START = "/* OIL-SLIDE-CSS:START */"
CSS_END = "/* OIL-SLIDE-CSS:END */"
HTML_START = "<!-- OIL-SLIDE:START -->"
HTML_END = "<!-- OIL-SLIDE:END -->"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SECTION_RE = re.compile(r"<section\b(?P<attrs>[^>]*)>(?P<body>.*?)</section\s*>", re.I | re.S)
ATTR_RE = re.compile(r"(?P<name>[a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(?P<q>['\"])(?P<value>.*?)(?P=q)", re.S)


@dataclass(frozen=True)
class Slide:
    path: Path
    slide_id: str
    title: str
    css: str
    section: str


class _HandlerDetector(HTMLParser):
    has_handler = False
    urls: list[str]
    inline_styles: list[str]

    def __init__(self) -> None:
        super().__init__()
        self.urls = []
        self.inline_styles = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.has_handler = self.has_handler or any(name.lower().startswith("on") for name, _ in attrs)
        for name, value in attrs:
            lowered = name.lower()
            if value is None:
                continue
            if lowered in {"src", "href", "poster", "xlink:href"}:
                self.urls.append(value)
            elif lowered == "srcset":
                self.urls.extend(candidate.strip().split()[0] for candidate in value.split(",") if candidate.strip())
            elif lowered == "style":
                self.inline_styles.append(value)


class _LiteralEscapeDetector(HTMLParser):
    """Find repeated visible escape sequences while preserving intentional code."""

    def __init__(self) -> None:
        super().__init__()
        self.ignored: list[bool] = []
        self.matches: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            return
        values = {name.lower(): value for name, value in attrs}
        parent_ignored = self.ignored[-1] if self.ignored else False
        explicit = str(values.get("data-literal-escape") or "").lower() == "true"
        self.ignored.append(parent_ignored or tag.lower() in {"script", "style"} or explicit)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        return

    def handle_endtag(self, tag: str) -> None:
        if self.ignored:
            self.ignored.pop()

    def handle_data(self, data: str) -> None:
        if not (self.ignored[-1] if self.ignored else False):
            self.matches.extend(re.findall(r"\\[nrt]", data))


@dataclass
class _CompositionNode:
    """Small semantic tree used only for conservative composition advice."""

    tag: str
    attrs: dict[str, str]
    children: list[_CompositionNode]
    own_text: list[str]

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def descendants(self) -> list[_CompositionNode]:
        result: list[_CompositionNode] = []
        for child in self.children:
            result.append(child)
            result.extend(child.descendants())
        return result


class _CompositionParser(HTMLParser):
    """Build enough DOM shape to notice overloaded repeated lanes."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__()
        self.roots: list[_CompositionNode] = []
        self.stack: list[_CompositionNode] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _CompositionNode(tag.lower(), {name.lower(): value or "" for name, value in attrs}, [], [])
        (self.stack[-1].children if self.stack else self.roots).append(node)
        if node.tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _CompositionNode(tag.lower(), {name.lower(): value or "" for name, value in attrs}, [], [])
        (self.stack[-1].children if self.stack else self.roots).append(node)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        while self.stack:
            node = self.stack.pop()
            if node.tag == lowered:
                break

    def handle_data(self, data: str) -> None:
        if self.stack and data.strip():
            self.stack[-1].own_text.append(data.strip())


def _equal_column_count(css: str) -> int:
    """Return the largest explicit equal-column grid; unknown grids stay zero."""
    maximum = 0
    for value in re.findall(r"grid-template-columns\s*:\s*([^;{}]+)", css, re.I):
        for count in re.findall(r"repeat\s*\(\s*(\d+)\s*,", value, re.I):
            maximum = max(maximum, int(count))
        maximum = max(maximum, len(re.findall(r"\b1fr\b", value, re.I)))
    return maximum


def _has_overloaded_repeated_lanes(slide: Slide) -> bool:
    """Four-up overview lanes should not each become a miniature document."""
    columns = _equal_column_count(slide.css)
    if columns < 4:
        return False
    parser = _CompositionParser()
    parser.feed(slide.section)
    nodes = [node for root in parser.roots for node in [root, *root.descendants()]]
    repeatable = [node for node in nodes if node.tag in {"article", "li"}]
    groups: dict[str, list[_CompositionNode]] = {}
    for node in repeatable:
        for token in node.classes - {"oil-panel", "oil-surface"}:
            groups.setdefault(token, []).append(node)
    for group in groups.values():
        if len(group) < 4:
            continue
        overloaded = 0
        for node in group:
            layers = 0
            for descendant in node.descendants():
                direct_text = "".join(descendant.own_text).strip()
                if descendant.tag in {"p", "ul", "ol", "blockquote", "pre"} and len(direct_text) >= 6:
                    layers += 1
                elif descendant.tag == "div" and len(direct_text) >= 6:
                    layers += 1
            overloaded += layers >= 2
        if overloaded >= 4:
            return True
    return False


def _repeated_semantic_classes(section: str, minimum: int = 3) -> set[str]:
    """Classes repeated on content units, excluding decorative repeated marks."""
    parser = _CompositionParser()
    parser.feed(section)
    nodes = [node for root in parser.roots for node in [root, *root.descendants()]]
    counts = Counter(
        token
        for node in nodes
        if node.tag in {"article", "li"}
        for token in node.classes - {"oil-panel", "oil-surface"}
    )
    return {token for token, count in counts.items() if count >= minimum}


def _composition_nodes(section: str) -> list[_CompositionNode]:
    parser = _CompositionParser()
    parser.feed(section)
    return [node for root in parser.roots for node in [root, *root.descendants()]]


def _node_text(node: _CompositionNode) -> str:
    parts = [*node.own_text]
    for child in node.children:
        parts.append(_node_text(child))
    return " ".join(part for part in parts if part).strip()


def _display_units(value: str) -> int:
    return sum(
        2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1
        for character in value
        if not character.isspace()
    )


def _implementation_identifiers(nodes: list[_CompositionNode]) -> set[str]:
    """Find implementation-facing dotted identifiers in ordinary audience copy."""
    identifiers: set[str] = set()
    for node in nodes:
        if node.tag in {"code", "pre", "script", "style"} or node.classes & {"oil-code"}:
            continue
        for value in node.own_text:
            identifiers.update(re.findall(
                r"(?<![a-z0-9_-])[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+(?![a-z0-9_-])",
                value,
                re.I,
            ))
    return identifiers


def _fail(path: Path, message: str) -> None:
    raise SystemExit(f"{path}: {message}")


def _single(text: str, start: str, end: str, path: Path, label: str) -> str:
    if text.count(start) != 1 or text.count(end) != 1:
        _fail(path, f"requires exactly one {label} marker pair")
    left, right = text.index(start) + len(start), text.index(end)
    if right < left:
        _fail(path, f"invalid {label} marker order")
    return text[left:right]


def _attrs(source: str) -> dict[str, str]:
    return {match.group("name").lower(): match.group("value") for match in ATTR_RE.finditer(source)}


def _validate_css(css: str, slide_id: str, path: Path) -> None:
    scrubbed = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    _validate_css_blocks(scrubbed, slide_id, path)
    for value in css_urls(css):
        _validate_url(value.strip(), path)


def _matching_brace(text: str, start: int, path: Path) -> int:
    depth = 0
    quote = ""
    escaped = False
    for index in range(start, len(text)):
        character = text[index]
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = ""
            continue
        if character in {'"', "'"}:
            quote = character
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return index
    _fail(path, "local CSS has an unmatched brace")
    raise AssertionError("unreachable")


def _selector_list(value: str) -> list[str]:
    selectors: list[str] = []
    start = 0
    depth = 0
    quote = ""
    escaped = False
    for index, character in enumerate(value):
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = ""
            continue
        if character in {'"', "'"}:
            quote = character
        elif character in "([":
            depth += 1
        elif character in ")]":
            depth = max(0, depth - 1)
        elif character == "," and depth == 0:
            selectors.append(value[start:index].strip())
            start = index + 1
    selectors.append(value[start:].strip())
    return [selector for selector in selectors if selector]


def _validate_css_blocks(text: str, slide_id: str, path: Path) -> None:
    position = 0
    scope = f".s-{slide_id}"
    while position < len(text):
        while position < len(text) and text[position].isspace():
            position += 1
        if position == len(text):
            return
        opening = text.find("{", position)
        if opening < 0:
            _fail(path, "local CSS contains text outside a rule")
        preamble = text[position:opening].strip()
        closing = _matching_brace(text, opening, path)
        body = text[opening + 1:closing]
        if preamble.startswith("@"):
            match = re.match(r"@([a-z-]+)\b\s*(.*)", preamble, re.I | re.S)
            name = match.group(1).lower() if match else ""
            tail = match.group(2).strip() if match else ""
            if name in {"media", "supports", "container", "layer"}:
                _validate_css_blocks(body, slide_id, path)
            elif name in {"keyframes", "-webkit-keyframes"}:
                animation_name = tail.split()[0] if tail else ""
                if not animation_name.startswith(f"s-{slide_id}-"):
                    _fail(path, f"animation names must begin with s-{slide_id}-")
            else:
                _fail(path, f"local CSS at-rule is not allowed: @{name or '?'}")
        else:
            for selector in _selector_list(preamble):
                if not re.match(rf"^{re.escape(scope)}(?:$|(?=[^a-z0-9-]))", selector):
                    _fail(path, f"local CSS leaks outside {scope}: {selector}")
        position = closing + 1


def _validate_url(url: str, path: Path) -> None:
    if url in {"../runtime/deck.css", "../runtime/theme.css", "../runtime/deck.js"}:
        return
    if url.startswith(("data:", "#")):
        return
    lowered = url.lower()
    if lowered.startswith(("http:", "https:", "//", "file:")):
        _fail(path, f"remote or file URL is not allowed: {url}")
    if url.startswith(("/", "\\")) or re.match(r"^[a-zA-Z]:[\\/]", url):
        _fail(path, f"absolute path is not allowed: {url}")
    if not url.startswith("../assets/") or ".." in Path(url).parts[1:]:
        _fail(path, f"path escapes slide assets: {url}")
    asset = (path.parent / url).resolve()
    if not asset.is_file():
        _fail(path, f"missing local asset: {url}")


def _validate_document(text: str, path: Path) -> None:
    if not re.search(r"<!doctype\s+html", text, re.I) or not re.search(r"<html\b", text, re.I):
        _fail(path, "must be a standalone HTML document")
    if not re.search(r"<meta\s+charset=['\"]?utf-8", text, re.I):
        _fail(path, "must declare UTF-8")
    links = re.findall(r"<link\b([^>]*)>", text, re.I | re.S)
    link_targets = [_attrs(link).get("href", "") for link in links]
    if sorted(link_targets) != ["../runtime/deck.css", "../runtime/theme.css"]:
        _fail(path, "must link only ../runtime/deck.css and ../runtime/theme.css")
    styles = re.findall(r"<style\b[^>]*>(.*?)</style\s*>", text, re.I | re.S)
    if (
        len(styles) != 1
        or not styles[0].strip().startswith(CSS_START)
        or not styles[0].strip().endswith(CSS_END)
    ):
        _fail(path, "requires one style block containing only the marked page CSS")
    scripts = re.findall(r"<script\b([^>]*)>(.*?)</script\s*>", text, re.I | re.S)
    if len(scripts) != 1 or not re.fullmatch(r"\s*src\s*=\s*(['\"])\.\./runtime/deck\.js\1\s*", scripts[0][0], re.I) or scripts[0][1].strip():
        _fail(path, "only the ../runtime/deck.js script is allowed")
    detector = _HandlerDetector()
    detector.feed(text)
    if detector.has_handler:
        _fail(path, "inline event handlers are not allowed")
    if len(re.findall(r"<section\b", text, re.I)) != 1:
        _fail(path, "document must contain exactly one section")
    for url in detector.urls:
        _validate_url(url.strip(), path)
    for inline_style in detector.inline_styles:
        for value in css_urls(inline_style):
            _validate_url(value.strip(), path)
    escapes = _LiteralEscapeDetector()
    escapes.feed(text)
    if len(escapes.matches) >= 2:
        _fail(path, "visible text contains repeated literal escape sequences; use real line breaks or data-literal-escape=true")
    if re.search(r"(?:__[^_]+__|{{|}}|\[TODO\]|\bTBD\b)", text, re.I):
        _fail(path, "contains an unresolved placeholder")


def parse_slide(path: Path, expected_id: str | None = None) -> Slide:
    if not path.is_file():
        _fail(path, "slide file is missing")
    text = path.read_text(encoding="utf-8")
    _validate_document(text, path)
    css = _single(text, CSS_START, CSS_END, path, "OIL-SLIDE-CSS")
    fragment = _single(text, HTML_START, HTML_END, path, "OIL-SLIDE")
    matches = list(SECTION_RE.finditer(fragment))
    if len(matches) != 1 or matches[0].group(0).strip() != fragment.strip():
        _fail(path, "OIL-SLIDE markers must contain exactly one section")
    attrs = _attrs(matches[0].group("attrs"))
    classes = set(attrs.get("class", "").split())
    slide_id = attrs.get("data-slide-id", "")
    if not ID_RE.fullmatch(slide_id) or "oil-slide" not in classes or f"s-{slide_id}" not in classes:
        _fail(path, "section requires oil-slide, matching s-<id>, and a stable data-slide-id")
    if expected_id and slide_id != expected_id:
        _fail(path, f"data-slide-id {slide_id!r} does not match deck path id {expected_id!r}")
    if "data-title" not in attrs or not attrs["data-title"].strip():
        _fail(path, "section requires a non-empty data-title")
    if len(re.findall(r"<section\b", fragment, re.I)) != 1 or len(re.findall(r"class=['\"][^'\"]*\bslide-safe\b", matches[0].group("body"), re.I)) != 1:
        _fail(path, "section requires one .slide-safe")
    _validate_css(css, slide_id, path)
    return Slide(path, slide_id, attrs["data-title"], css, matches[0].group(0))


def _style_advice_for_slide(slide: Slide) -> list[dict[str, str]]:
    """Return deliberately conservative, non-blocking composition suggestions."""
    source = slide.css + "\n" + slide.section
    advice: list[dict[str, str]] = []
    nodes = _composition_nodes(slide.section)
    display_title = next((_node_text(node) for node in nodes if node.tag == "h1"), "")
    if _display_units(display_title) > 34:
        advice.append({
            "slide": slide.slide_id,
            "rule": "long-display-title",
            "message": "标题的投影阅读宽度偏长。先把完整判断留给讲述或主视觉，标题改成简短、平铺直叙的内容标签；界面和证据页优先控制在一行。",
        })
    has_browser_showcase = any("oil-browser" in node.classes for node in nodes)
    has_external_summary = any(node.classes & {"summary", "oil-lede"} for node in nodes)
    if has_browser_showcase and has_external_summary:
        advice.append({
            "slide": slide.slide_id,
            "rule": "redundant-showcase-summary",
            "message": "浏览器展示页同时出现了标题外说明段。主界面已经能承担解释时直接删除；只有来源、限制或阅读方法确实必要时才保留一行。",
        })
    implementation_identifiers = _implementation_identifiers(nodes)
    if len(implementation_identifiers) >= 2 or any(value.count(".") >= 2 for value in implementation_identifiers):
        advice.append({
            "slide": slide.slide_id,
            "rule": "implementation-identifiers-in-audience-copy",
            "message": "页面正文出现多个带点号的内部名称。如果本页不是专门讲实现，请改成观众能识别的位置、动作、用途或产物；原始名称放到附录或讲者备注。",
        })
    ink_strokes = re.findall(
        r"border(?:-(?:top|right|bottom|left))?\s*:\s*(?:[2-9]\d*|1\d+)px\b[^;{}]*(?:var\(--ink\)|#(?:292929|353633))",
        source,
        re.I,
    )
    if len(ink_strokes) >= 2:
        advice.append({
            "slide": slide.slide_id,
            "rule": "repeated-ink-strokes",
            "message": "检测到多处 2px 以上深色描边；可考虑打开流程轨道、关系图或特征主次，用位置和留白替代重复框线。",
        })
    dark_surfaces = len(re.findall(r"data-tone\s*=\s*['\"]ink['\"]", source, re.I))
    dark_surfaces += len(re.findall(r"background(?:-color)?\s*:\s*var\(--ink\)", slide.css, re.I))
    if dark_surfaces >= 2:
        advice.append({
            "slide": slide.slide_id,
            "rule": "repeated-dark-surfaces",
            "message": "检测到多个深色面；默认保留一个主深色面，把其余关系改为浅色层级、开放轨道、关系图或 feature hierarchy 会更轻。",
        })
    dark_hexes = re.findall(r"background(?:-color)?\s*:\s*(#[0-9a-f]{6})\b", slide.css, re.I)

    def is_dark(value: str) -> bool:
        red, green, blue = (int(value[index:index + 2], 16) / 255 for index in (1, 3, 5))
        linear = [channel / 12.92 if channel <= .04045 else ((channel + .055) / 1.055) ** 2.4 for channel in (red, green, blue)]
        return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2] < .08

    frame_blocks = re.findall(rf"\.s-{re.escape(slide.slide_id)}\s+\.frame\s*\{{([^{{}}]*)\}}", slide.css, re.I | re.S)
    frame_is_dark = any(any(is_dark(value) for value in re.findall(r"background(?:-color)?\s*:\s*(#[0-9a-f]{6})\b", block, re.I)) for block in frame_blocks)
    if frame_is_dark and sum(is_dark(value) for value in dark_hexes) >= 3:
        advice.append({
            "slide": slide.slide_id,
            "rule": "nested-dark-surfaces",
            "message": "检测到深色整页内继续嵌套多层深色容器；可压平为一个主深色画布，用列、留白和一处强调块建立层级。",
        })
    panel_count = len(re.findall(r"\bclass\s*=\s*['\"][^'\"]*\boil-panel\b", slide.section, re.I))
    dark_summary = bool(re.search(
        r"<(?:aside|div|section|article)\b(?=[^>]*\bclass\s*=\s*['\"][^'\"]*(?:summary|outcome|result|takeaway|conclusion|rail-note)[^'\"]*['\"])(?=[^>]*\bdata-tone\s*=\s*['\"]ink['\"])[^>]*>",
        slide.section,
        re.I | re.S,
    ))
    if panel_count >= 2 and dark_summary:
        advice.append({
            "slide": slide.slide_id,
            "rule": "dark-summary-after-light-panels",
            "message": "检测到多张面板后又追加通栏深色结论。优先把结论写进标题、重点单元，或改成细分隔线后的共享说明；不要让深色页脚截断轻盈层级。",
        })
    grid_columns = re.findall(r"grid-template-columns\s*:\s*([^;{}]+)", slide.css, re.I)
    equal_grid = any(
        re.search(r"repeat\s*\(\s*[3-9]\s*,\s*(?:minmax\([^)]*\)|1fr)", value, re.I)
        or len(re.findall(r"\b1fr\b", value, re.I)) >= 3
        for value in grid_columns
    )
    repeated_items = _repeated_semantic_classes(slide.section)

    def repeated_class_is_card(token: str) -> bool:
        blocks = re.findall(rf"[^{{}}]*\.{re.escape(token)}(?:\b|[^a-z0-9_-])[^{{}}]*\{{([^{{}}]*)\}}", slide.css, re.I | re.S)
        return any(
            "border-radius" in block
            and re.search(r"(?:^|;)\s*(?:background(?:-color)?|border(?!-radius)|box-shadow)\s*:", block, re.I)
            for block in blocks
        )

    card_treatment = panel_count >= 3 or any(repeated_class_is_card(token) for token in repeated_items)
    if equal_grid and card_treatment:
        advice.append({
            "slide": slide.slide_id,
            "rule": "equal-card-wall",
            "message": "检测到等权面板墙；可尝试用开放轨道、关系图或一主多辅的 feature hierarchy，让判断先于容器出现。",
        })
    if _has_overloaded_repeated_lanes(slide):
        advice.append({
            "slide": slide.slide_id,
            "rule": "overloaded-repeated-lanes",
            "message": "检测到四个以上等宽步骤都承载了两层以上解释。总览轨道每个节点只保留编号或时间、标题和一句短说明；把重复护栏、指标或补充说明改成一个共享区、只展开一个重点，或拆到下一页。",
        })
    decorated_surfaces = 0
    mixed_decorations = 0
    for match in re.finditer(r"<(?:div|article|section)\b([^>]*)>", slide.section, re.I | re.S):
        attrs = match.group(1)
        classes = re.search(r"\bclass\s*=\s*(['\"])(.*?)\1", attrs, re.I | re.S)
        is_surface = classes and ("oil-surface" in classes.group(2).split() or "oil-panel" in classes.group(2).split())
        if is_surface and re.search(r"\bdata-(?:decor|motif)\s*=", attrs, re.I):
            decorated_surfaces += 1
            mixed_decorations += bool(re.search(r"\bdata-decor\s*=", attrs, re.I) and re.search(r"\bdata-motif\s*=", attrs, re.I))
    if mixed_decorations:
        advice.append({
            "slide": slide.slide_id,
            "rule": "mixed-surface-decoration",
            "message": "检测到同一表面同时声明 dots 和 motif；请只保留一种局部 craft，避免装饰互相竞争。",
        })
    if decorated_surfaces >= 3:
        advice.append({
            "slide": slide.slide_id,
            "rule": "overdecorated-surfaces",
            "message": "检测到三个以上带 dots 或 motif 的表面；默认只给一个主表面添加局部装饰，其余用留白、面积和色调建立层级。",
        })
    return advice


def style_advice(
    project: Path,
    deck: dict,
    *,
    slides: list[Slide] | None = None,
) -> list[dict[str, str]]:
    """Read real standalone HTML only; advice never participates in validation."""
    result: list[dict[str, str]] = []
    if slides is None:
        slides = []
        for relative in deck.get("slides", []):
            path = project / str(relative)
            try:
                slides.append(parse_slide(path, Path(relative).stem))
            except SystemExit:
                # Structural problems are handled by the normal blocking workflow.
                continue
    for slide in slides:
        result.extend(_style_advice_for_slide(slide))
    card_wall_slides = [item["slide"] for item in result if item.get("rule") == "equal-card-wall"]
    if len(card_wall_slides) >= 2:
        result.append({
            "slide": ",".join(card_wall_slides),
            "rule": "repeated-card-silhouette",
            "message": "多页重复使用同一种等权卡片墙轮廓；交付前至少把其中一页改成开放轨道、关系图、主次特征或单一证据画布。",
        })
    return result


def new_slide_document(slide_id: str, title: str) -> str:
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{safe_title}</title>
<link rel="stylesheet" href="../runtime/deck.css"><link rel="stylesheet" href="../runtime/theme.css"><style>
{CSS_START}
.s-{slide_id} .slide-title {{ margin: 0; font-size: 88px; line-height: var(--oil-leading-display); letter-spacing: var(--oil-tracking-display); }}
.s-{slide_id} .slide-subtitle {{ margin: 28px 0 0; font-size: 30px; line-height: var(--oil-leading-body); color: var(--ink-2); }}
{CSS_END}
</style></head><body data-oil-mode="preview"><div class="slide-preview-viewport"><div class="slide-preview-shell"><div class="slide-preview-stage">
{HTML_START}
<section class="oil-slide s-{slide_id}" data-slide-id="{slide_id}" data-title="{safe_title}"><div class="slide-safe"><h1 class="slide-title">{safe_title}</h1><p class="slide-subtitle">Edit this slide directly in HTML.</p></div></section>
{HTML_END}
</div></div></div><script src="../runtime/deck.js"></script></body></html>
'''
