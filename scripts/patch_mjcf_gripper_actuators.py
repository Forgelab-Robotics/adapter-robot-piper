#!/usr/bin/env python3
"""Apply the repository's total-opening gripper actuator semantics to Piper MJCF."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import quoteattr

_XML_TOKEN = re.compile(
    r"(?P<ignored><!--.*?-->|<!\[CDATA\[.*?\]\]>|<\?.*?\?>)"
    r"|(?P<position><position\b(?:[^>\"']|\"[^\"]*\"|'[^']*')*>)",
    re.DOTALL,
)
_JOINT_ATTRIBUTE = re.compile(
    r"\bjoint\s*=\s*(?P<quote>[\"'])(?P<value>.*?)(?P=quote)",
    re.DOTALL,
)
_SELF_CLOSING = re.compile(r"/\s*>$")
_ORDERED_ATTRIBUTES = (
    "name",
    "joint",
    "class",
    "inheritrange",
    "ctrlrange",
    "gear",
    "kp",
    "kv",
    "forcerange",
)
_GRIPPER_ATTRIBUTES = {
    "inheritrange": "0",
    "ctrlrange": "0 0.105",
    "gear": "2",
    "kp": "10",
    "kv": "1.25",
    "forcerange": "-5 5",
}


class PatchError(ValueError):
    """Raised when MJCF cannot be parsed or patched safely."""


def _raw_joint_name(tag: str) -> str:
    match = _JOINT_ATTRIBUTE.search(tag)
    return match.group("value") if match is not None else ""


def _parse_position_tag(tag: str, *, self_closing: bool) -> ElementTree.Element:
    parseable_tag = tag if self_closing else f"{tag[:-1]}/>"
    return ElementTree.fromstring(parseable_tag)


def _format_position_tag(element: ElementTree.Element, original: str) -> str:
    attribute_names = [
        attribute for attribute in _ORDERED_ATTRIBUTES if attribute in element.attrib
    ]
    attribute_names.extend(
        attribute
        for attribute in element.attrib
        if attribute not in _ORDERED_ATTRIBUTES
    )
    attributes = " ".join(
        f"{attribute}={quoteattr(element.attrib[attribute])}"
        for attribute in attribute_names
    )
    closing = " />" if re.search(r"\s/\s*>$", original) else "/>"
    return f"<position {attributes}{closing}"


def patch_mjcf_text(text: str) -> tuple[str, int]:
    """Patch canonical joint7 position actuators while preserving all other text."""
    try:
        ElementTree.fromstring(text)
    except ElementTree.ParseError as error:
        raise PatchError(f"cannot parse XML document: {error}") from error

    output: list[str] = []
    errors: list[str] = []
    cursor = 0
    matched_actuators = 0

    for match in _XML_TOKEN.finditer(text):
        tag = match.group("position")
        if tag is None:
            continue

        output.append(text[cursor : match.start()])
        replacement = tag
        self_closing = _SELF_CLOSING.search(tag) is not None
        try:
            element = _parse_position_tag(tag, self_closing=self_closing)
        except ElementTree.ParseError as error:
            joint = _raw_joint_name(tag)
            if joint.endswith("joint7"):
                line = text.count("\n", 0, match.start()) + 1
                errors.append(
                    f"line {line}: cannot parse joint7 position actuator: {error}"
                )
        else:
            joint = element.get("joint", "")
            if joint.endswith("joint7"):
                line = text.count("\n", 0, match.start()) + 1
                name = element.get("name", "")
                expected_name = f"{joint.removesuffix('joint7')}gripper"
                if not self_closing:
                    errors.append(
                        f"line {line}: joint7 position actuator {name or '<unnamed>'!r} "
                        "is not self-closing"
                    )
                elif not name:
                    errors.append(
                        f"line {line}: unnamed joint7 position actuator; "
                        f"expected name {expected_name!r}"
                    )
                elif name != expected_name:
                    errors.append(
                        f"line {line}: non-canonical joint7 actuator name {name!r}; "
                        f"expected {expected_name!r}"
                    )
                else:
                    matched_actuators += 1
                    if any(
                        element.get(attribute) != value
                        for attribute, value in _GRIPPER_ATTRIBUTES.items()
                    ):
                        element.attrib.update(_GRIPPER_ATTRIBUTES)
                        replacement = _format_position_tag(element, tag)

        output.append(replacement)
        cursor = match.end()

    output.append(text[cursor:])
    if errors:
        raise PatchError("\n".join(errors))
    return "".join(output), matched_actuators


def _xml_paths(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.rglob("*.xml"))
    raise FileNotFoundError(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="MJCF file or directory to patch")
    args = parser.parse_args(argv)

    try:
        paths = _xml_paths(args.path)
    except FileNotFoundError:
        print(f"Path not found: {args.path}", file=sys.stderr)
        return 2

    results: list[tuple[Path, str, str, int]] = []
    failures: list[tuple[Path, str]] = []
    for path in paths:
        original = path.read_text(encoding="utf-8")
        try:
            patched, matches = patch_mjcf_text(original)
        except PatchError as error:
            failures.append((path, str(error)))
        else:
            results.append((path, original, patched, matches))

    if failures:
        print("Refusing to patch invalid or unpatchable XML:", file=sys.stderr)
        for path, failure in failures:
            for detail in failure.splitlines():
                print(f"  {path}: {detail}", file=sys.stderr)
        return 1

    matched_actuators = sum(matches for _, _, _, matches in results)
    if matched_actuators == 0:
        print(f"No named gripper actuators found under: {args.path}", file=sys.stderr)
        return 1

    changed_files = 0
    for path, original, patched, _ in results:
        if patched != original:
            path.write_text(patched, encoding="utf-8")
            changed_files += 1

    print(
        f"Applied total-opening semantics to {matched_actuators} gripper actuator(s); "
        f"changed {changed_files} file(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
