"""Rewrite real HTML/CSS URL syntax without touching visible code examples."""
from __future__ import annotations

from collections.abc import Callable, Iterator


URLTransform = Callable[[str], str]


def _tag_spans(source: str) -> Iterator[tuple[int, int]]:
    position = 0
    while True:
        start = source.find("<", position)
        if start < 0:
            return
        if source.startswith("<!--", start):
            end = source.find("-->", start + 4)
            if end < 0:
                return
            position = end + 3
            continue
        quote = ""
        escaped = False
        end = start + 1
        while end < len(source):
            character = source[end]
            if quote:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == quote:
                    quote = ""
            elif character in {'"', "'"}:
                quote = character
            elif character == ">":
                yield start, end + 1
                position = end + 1
                break
            end += 1
        else:
            return


def _srcset(value: str, transform: URLTransform) -> str:
    candidates: list[str] = []
    for candidate in value.split(","):
        parts = candidate.strip().split()
        if parts:
            candidates.append(" ".join([transform(parts[0]), *parts[1:]]))
    return ", ".join(candidates)


def _rewrite_tag(tag: str, transform: URLTransform) -> str:
    if tag.startswith(("</", "<!", "<?")):
        return tag
    replacements: list[tuple[int, int, str]] = []
    index = 1
    while index < len(tag) and not tag[index].isspace() and tag[index] not in "/>":
        index += 1
    while index < len(tag):
        while index < len(tag) and tag[index].isspace():
            index += 1
        if index >= len(tag) or tag[index] in "/>":
            break
        name_start = index
        while index < len(tag) and not tag[index].isspace() and tag[index] not in "=/>":
            index += 1
        name = tag[name_start:index].lower()
        while index < len(tag) and tag[index].isspace():
            index += 1
        if index >= len(tag) or tag[index] != "=":
            continue
        index += 1
        while index < len(tag) and tag[index].isspace():
            index += 1
        if index >= len(tag):
            break
        if tag[index] in {'"', "'"}:
            quote = tag[index]
            value_start = index + 1
            index = value_start
            while index < len(tag) and tag[index] != quote:
                index += 1
            value_end = index
            index = min(len(tag), index + 1)
        else:
            value_start = index
            while index < len(tag) and not tag[index].isspace() and tag[index] not in "/>":
                index += 1
            value_end = index
        value = tag[value_start:value_end]
        if name in {"src", "href", "poster", "xlink:href"}:
            replacements.append((value_start, value_end, transform(value)))
        elif name == "srcset":
            replacements.append((value_start, value_end, _srcset(value, transform)))
        elif name == "style":
            replacements.append((value_start, value_end, rewrite_css_urls(value, transform)))
    for start, end, value in reversed(replacements):
        tag = tag[:start] + value + tag[end:]
    return tag


def rewrite_html_urls(fragment: str, transform: URLTransform) -> str:
    """Rewrite URL attributes on actual tags while preserving all other bytes."""
    pieces: list[str] = []
    position = 0
    for start, end in _tag_spans(fragment):
        pieces.append(fragment[position:start])
        pieces.append(_rewrite_tag(fragment[start:end], transform))
        position = end
    pieces.append(fragment[position:])
    return "".join(pieces)


def rewrite_css_urls(css: str, transform: URLTransform) -> str:
    """Rewrite CSS url() functions, ignoring comments and quoted strings."""
    pieces: list[str] = []
    position = 0
    index = 0
    while index < len(css):
        if css.startswith("/*", index):
            end = css.find("*/", index + 2)
            index = len(css) if end < 0 else end + 2
            continue
        if css[index] in {'"', "'"}:
            quote = css[index]
            index += 1
            while index < len(css):
                if css[index] == "\\":
                    index += 2
                    continue
                if css[index] == quote:
                    index += 1
                    break
                index += 1
            continue
        if css[index:index + 3].lower() != "url":
            index += 1
            continue
        cursor = index + 3
        while cursor < len(css) and css[cursor].isspace():
            cursor += 1
        if cursor >= len(css) or css[cursor] != "(":
            index += 1
            continue
        cursor += 1
        while cursor < len(css) and css[cursor].isspace():
            cursor += 1
        quote = css[cursor] if cursor < len(css) and css[cursor] in {'"', "'"} else ""
        if quote:
            cursor += 1
        value_start = cursor
        while cursor < len(css):
            if quote and css[cursor] == "\\":
                cursor += 2
                continue
            if quote and css[cursor] == quote:
                value_end = cursor
                cursor += 1
                while cursor < len(css) and css[cursor].isspace():
                    cursor += 1
                if cursor < len(css) and css[cursor] == ")":
                    break
                index += 1
                break
            if not quote and css[cursor] == ")":
                value_end = cursor
                break
            cursor += 1
        else:
            index += 1
            continue
        if cursor >= len(css) or css[cursor] != ")":
            continue
        value = css[value_start:value_end].strip()
        pieces.append(css[position:index])
        pieces.append(f'url("{transform(value)}")')
        position = cursor + 1
        index = cursor + 1
    pieces.append(css[position:])
    return "".join(pieces)


def css_urls(css: str) -> list[str]:
    """Return actual CSS url() values, excluding comments and strings."""
    values: list[str] = []

    def collect(value: str) -> str:
        values.append(value)
        return value

    rewrite_css_urls(css, collect)
    return values
