#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from urllib.parse import urlparse


DOC_PREFIXES = (
    "/apps/",
    "/clients/",
    "/deployment/",
    "/development/",
    "/getting-started/",
    "/integrations/",
    "/patterns/",
    "/python-sdk/",
    "/servers/",
    "/v2/",
)

TOP_LEVEL_DOCS = {
    "/",
    "/changelog",
    "/updates",
    "/sitemap.xml",
    "/llms.txt",
    "/llms-full.txt",
}

ASSET_PREFIXES = (
    "/assets/",
    "/mintlify-assets/",
)

ASSET_EXTENSIONS = (
    ".css",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".mp4",
    ".png",
    ".svg",
    ".woff",
    ".woff2",
    ".xml",
    ".yaml",
    ".yml",
)

RSC_PARAM_RE = re.compile(r"[?&]_rsc=")


@dataclass(frozen=True)
class RouteRow:
    route: str
    tree: str
    section: str
    has_v2_counterpart: str
    notes: str


def iter_lines(path: str | None) -> list[str]:
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().splitlines()
    return sys.stdin.read().splitlines()


def strip_trailing_backslashes(value: str) -> str:
    while value.endswith("\\"):
        value = value[:-1]
    return value


def normalize_candidate(raw: str) -> tuple[str, str] | None:
    s = strip_trailing_backslashes(raw.strip())
    if not s:
        return None

    if s.startswith("#"):
        return None
    if s.startswith("window."):
        return None

    if s.startswith("http://") or s.startswith("https://"):
        parsed = urlparse(s)
        if parsed.netloc and parsed.netloc != "gofastmcp.com":
            return None
        s = parsed.path or "/"
        if parsed.query and RSC_PARAM_RE.search(f"?{parsed.query}"):
            pass

    if not s.startswith("/"):
        return None

    if "#" in s:
        s = s.split("#", 1)[0]
    if "?" in s:
        s = s.split("?", 1)[0]

    if not s:
        return None

    if s != "/" and s.endswith("/"):
        s = s[:-1]

    if s.startswith(ASSET_PREFIXES) or s.endswith(ASSET_EXTENSIONS):
        return None

    if s in TOP_LEVEL_DOCS or s.startswith(DOC_PREFIXES):
        return s, classify_tree(s)

    return None


def classify_tree(route: str) -> str:
    if route.startswith("/v2/"):
        return "v2"
    if route.startswith("/python-sdk/"):
        return "python-sdk"
    return "default"


def classify_section(route: str, tree: str) -> str:
    normalized = route
    if tree == "v2":
        normalized = route[3:]

    if normalized == "/":
        return "root"
    if normalized in {"/changelog", "/updates", "/sitemap.xml", "/llms.txt", "/llms-full.txt"}:
        return "meta"

    parts = [part for part in normalized.split("/") if part]
    if not parts:
        return "root"
    return parts[0]


def note_for_route(route: str, tree: str, has_v2_counterpart: str) -> str:
    if route == "/":
        return "site root"
    if route in {"/changelog", "/updates"}:
        return "top-level docs page"
    if route in {"/sitemap.xml", "/llms.txt", "/llms-full.txt"}:
        return "metadata file"
    if tree == "v2":
        return "v2 docs"
    if tree == "python-sdk":
        return "API reference page"
    if has_v2_counterpart == "no":
        return "default-only docs"
    return "docs"


def build_rows(lines: list[str]) -> list[RouteRow]:
    routes: dict[str, str] = {}
    for line in lines:
        normalized = normalize_candidate(line)
        if normalized is None:
            continue
        route, tree = normalized
        routes[route] = tree

    default_routes = {route for route, tree in routes.items() if tree == "default"}
    rows: list[RouteRow] = []

    for route in sorted(routes):
        tree = routes[route]
        if tree == "default":
            has_v2_counterpart = "yes" if f"/v2{route}" in routes else "no"
        else:
            has_v2_counterpart = "n/a"
        rows.append(
            RouteRow(
                route=route,
                tree=tree,
                section=classify_section(route, tree),
                has_v2_counterpart=has_v2_counterpart,
                notes=note_for_route(route, tree, has_v2_counterpart),
            )
        )

    return rows


def write_csv(
    rows: list[RouteRow],
    output_path: str | None,
    tree_filter: str | None,
    section_filter: str | None,
) -> None:
    filtered_rows = rows
    if tree_filter:
        filtered_rows = [row for row in rows if row.tree == tree_filter]
    if section_filter:
        filtered_rows = [row for row in filtered_rows if row.section == section_filter]

    output = sys.stdout
    should_close = False
    if output_path:
        output = open(output_path, "w", encoding="utf-8", newline="")
        should_close = True

    try:
        writer = csv.writer(output)
        writer.writerow(["route", "tree", "section", "has_v2_counterpart", "notes"])
        for row in filtered_rows:
            writer.writerow(
                [row.route, row.tree, row.section, row.has_v2_counterpart, row.notes]
            )
    finally:
        if should_close:
            output.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize a raw FastMCP site scrape into canonical CSV routes."
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Path to a raw scrape text file. If omitted, reads from stdin.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write CSV output to this file instead of stdout.",
    )
    parser.add_argument(
        "--tree",
        choices=("default", "v2", "python-sdk"),
        help="Only emit rows for one tree.",
    )
    parser.add_argument(
        "--section",
        help="Only emit rows for one top-level section, like clients or servers.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    lines = iter_lines(args.input)
    rows = build_rows(lines)
    write_csv(rows, args.output, args.tree, args.section)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
