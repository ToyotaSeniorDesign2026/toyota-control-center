from __future__ import annotations

import csv
import json
import logging
import os
import re
import threading
import time
import httpx
from dataclasses import asdict, dataclass, field
import asyncio
from pathlib import Path
from typing import Generic, Iterable, TypeVar
from urllib.parse import urlparse
from fastmcp import Client


logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://gofastmcp.com"
DEFAULT_UPSTREAM_MCP_URL = f"{DEFAULT_BASE_URL}/mcp"
DEFAULT_UPSTREAM_TOOL_CALL = "search_fast_mcp"  # Recently changed from "SearchFastMcp"
DEFAULT_USER_AGENT = "fastmcp-docs-agent/1.0"
DEFAULT_METADATA_SUFFIXES = (".txt", ".xml", ".json", ".yaml", ".yml")
DEFAULT_VALID_CORPORA = {"default", "v2", "python-sdk"}
DEFAULT_ROUTES_CSV = Path(__file__).with_name("routes.csv")
DEFAULT_LLMS_CACHE_TTL_SECONDS = 20 * 60

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
LINK_BULLET_RE = re.compile(r"^\s*-\s+\[(?P<title>[^]]+)]\((?P<url>[^)]+)\)(?::\s*(?P<description>.*))?\s*$")

T = TypeVar("T")


@dataclass(frozen=True)
class BackendSettings:
    base_url: str = DEFAULT_BASE_URL
    upstream_mcp_url: str = DEFAULT_UPSTREAM_MCP_URL
    user_agent: str = DEFAULT_USER_AGENT
    routes_csv_path: Path = DEFAULT_ROUTES_CSV
    llms_cache_ttl_seconds: int = DEFAULT_LLMS_CACHE_TTL_SECONDS
    metadata_suffixes: tuple[str, ...] = DEFAULT_METADATA_SUFFIXES
    valid_corpora: frozenset[str] = field(
        default_factory=lambda: frozenset(DEFAULT_VALID_CORPORA)
    )

    def __post_init__(self) -> None:
        base_url = self.base_url.rstrip("/")
        object.__setattr__(self, "base_url", base_url)
        if self.upstream_mcp_url == DEFAULT_UPSTREAM_MCP_URL:
            object.__setattr__(self, "upstream_mcp_url", f"{base_url}/mcp")

    @property
    def llms_txt_url(self) -> str:
        return f"{self.base_url}/llms.txt"

    @classmethod
    def from_env(cls) -> BackendSettings:
        routes_csv = os.environ.get("FASTMCP_ROUTES_CSV")

        raw_suffixes = os.environ.get("FASTMCP_DOCS_METADATA_SUFFIXES", "")
        metadata_suffixes: tuple[str, ...] = (
            tuple(s.strip() for s in raw_suffixes.split(",") if s.strip())
            if raw_suffixes
            else DEFAULT_METADATA_SUFFIXES
        )

        raw_corpora = os.environ.get("FASTMCP_DOCS_VALID_CORPORA", "")
        valid_corpora: frozenset[str] = (
            frozenset(s.strip() for s in raw_corpora.split(",") if s.strip())
            if raw_corpora
            else frozenset(DEFAULT_VALID_CORPORA)
        )

        return cls(
            base_url=os.environ.get("FASTMCP_DOCS_BASE_URL", DEFAULT_BASE_URL),
            upstream_mcp_url=os.environ.get(
                "FASTMCP_DOCS_UPSTREAM_MCP_URL", DEFAULT_UPSTREAM_MCP_URL
            ),
            user_agent=os.environ.get("FASTMCP_DOCS_USER_AGENT", DEFAULT_USER_AGENT),
            routes_csv_path=(
                Path(routes_csv).expanduser() if routes_csv else DEFAULT_ROUTES_CSV
            ),
            llms_cache_ttl_seconds=int(
                os.environ.get(
                    "FASTMCP_DOCS_LLMS_CACHE_TTL_SECONDS",
                    str(DEFAULT_LLMS_CACHE_TTL_SECONDS),
                )
            ),
            metadata_suffixes=metadata_suffixes,
            valid_corpora=valid_corpora,
        )


@dataclass(frozen=True)
class RouteEntry:
    route: str
    tree: str
    section: str
    has_v2_counterpart: str
    notes: str
    base_url: str
    metadata_suffixes: tuple[str, ...]

    @property
    def url(self) -> str:
        return f"{self.base_url}{self.route}"

    @property
    def md_url(self) -> str:
        if self.route == "/" or self.route.endswith(self.metadata_suffixes):
            return self.url
        return f"{self.url}.md"

    def to_dict(self) -> dict[str, str]:
        return {
            "route": self.route,
            "tree": self.tree,
            "section": self.section,
            "has_v2_counterpart": self.has_v2_counterpart,
            "notes": self.notes,
            "url": self.url,
            "md_url": self.md_url,
        }


@dataclass(frozen=True)
class SearchMatch:
    title: str
    route: str
    url: str
    md_url: str
    section: str
    tree: str
    notes: str
    snippet: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class LlmsTxtEntry:
    title: str
    url: str
    route: str
    md_url: str
    tree: str
    section: str
    section_path: str
    description: str
    has_v2_counterpart: str
    notes: str
    is_artifact: bool
    artifact_type: str

    def to_dict(self) -> dict[str, str | bool]:
        return asdict(self)


@dataclass(frozen=True)
class FetchFailure:
    target: str
    error_type: str
    error_message: str

    def to_payload(self) -> dict[str, object]:
        return {
            "found": False,
            "error_type": self.error_type,
            "error": self.error_message,
        }


@dataclass
class _CacheEntry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int):
        self._ttl_seconds = ttl_seconds
        self._entry: _CacheEntry[T] | None = None
        self._lock = threading.Lock()

    def get(self) -> T | None:
        with self._lock:
            if self._entry is None:
                return None
            if self._entry.expires_at <= time.monotonic():
                self._entry = None
                return None
            return self._entry.value

    def set(self, value: T) -> None:
        with self._lock:
            self._entry = _CacheEntry(
                value=value,
                expires_at=time.monotonic() + self._ttl_seconds,
            )

    def clear(self) -> None:
        with self._lock:
            self._entry = None


def clean_text(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        return cleaned[1:-1].strip()
    return cleaned


def normalize_source_name(value: str | None) -> str:
    if value is None:
        return ""
    return clean_text(value).strip().lower()


def normalize_tree_name(value: str) -> str:
    return clean_text(value).lower()


def normalize_tree_list(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    for value in values:
        tree = normalize_tree_name(value)
        if tree and tree not in normalized:
            normalized.append(tree)
    return normalized


def parse_search_result_text(text: str) -> tuple[str, str, str]:
    title = ""
    link = ""
    snippet = ""
    for line in text.splitlines():
        if line.startswith("Title: "):
            title = line.removeprefix("Title: ").strip()
        elif line.startswith("Link: "):
            link = line.removeprefix("Link: ").strip()
        elif line.startswith("Content: "):
            snippet = line.removeprefix("Content: ").strip()
            break
    return title, link, snippet


def split_markdown_sections(markdown: str) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    current_heading = "Introduction"
    current_lines: list[str] = []

    for line in markdown.splitlines():
        if line.startswith("#"):
            # Always flush the current section, even if it has no content,
            # so that consecutive headings don't cause the first to be silently dropped.
            sections.append(
                {
                    "heading": current_heading,
                    "content": "\n".join(current_lines).strip(),
                }
            )
            current_lines = []
            current_heading = line.lstrip("#").strip() or "Untitled"
        else:
            current_lines.append(line)

    # Flush the final section.
    sections.append(
        {
            "heading": current_heading,
            "content": "\n".join(current_lines).strip(),
        }
    )

    # Drop the synthetic leading "Introduction" section if it has no content
    # (i.e. the document opened directly with a heading).
    if sections and sections[0]["heading"] == "Introduction" and not sections[0]["content"]:
        sections = sections[1:]

    return sections


def looks_like_api_query(query: str) -> bool:
    cleaned = clean_text(query)
    # Check for explicit API-style markers (excluding bare underscore).
    markers = ("::", "()", "fastmcp.", "client(", "server(")
    if any(marker in cleaned for marker in markers):
        return True
    # Match snake_case identifiers (word_word) rather than any lone underscore.
    if re.search(r'\b\w+_\w+\b', cleaned):
        return True
    if cleaned.startswith("/") and "/python-sdk/" in cleaned:
        return True
    tokens = cleaned.split()
    return any(
        token and token[0].isupper() and any(char.islower() for char in token[1:])
        for token in tokens
    )


def semantic_match_sort_key(match: SearchMatch, query: str) -> tuple[int, int, int, str]:
    if looks_like_api_query(query):
        tree_rank = {"python-sdk": 0, "default": 1, "v2": 2, "unknown": 3}.get(
            match.tree, 4
        )
    else:
        tree_rank = {"default": 0, "python-sdk": 1, "v2": 2, "unknown": 3}.get(
            match.tree, 4
        )
    section_penalty = 1 if match.section == "meta" else 0
    phrase_penalty = (
        0 if clean_text(query).lower() in f"{match.title} {match.route}".lower() else 1
    )
    return tree_rank, section_penalty, phrase_penalty, match.route


def clamp_limit(limit: int | None, total: int, *, minimum: int = 1, maximum: int = 10_000) -> int:
    if limit is None:
        return total
    return max(minimum, min(limit, maximum))


class HttpFetcher:
    def __init__(self, settings: BackendSettings):
        self._settings = settings
        self._client: httpx.AsyncClient | None = None
        self._client_lock: asyncio.Lock | None = None

    def _get_lock(self) -> asyncio.Lock:
        # Lazily create the lock inside the running event loop.
        if self._client_lock is None:
            self._client_lock = asyncio.Lock()
        return self._client_lock

    async def _get_client(self) -> httpx.AsyncClient:
        async with self._get_lock():
            if self._client is None:
                self._client = httpx.AsyncClient(
                    headers={"User-Agent": self._settings.user_agent},
                    timeout=20.0,
                    follow_redirects=True,
                )
        return self._client

    async def fetch_text_async(self, url: str, timeout_seconds: float = 20.0) -> str:
        client = await self._get_client()
        # per-request timeout override
        resp = await client.get(url, timeout=timeout_seconds)
        resp.raise_for_status()
        return resp.text

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


class RouteNormalizer:
    def __init__(self, settings: BackendSettings):
        self._settings = settings

    def normalize_route(self, value: str) -> str:
        route = clean_text(value)
        parsed = urlparse(route)
        if parsed.scheme and parsed.netloc:
            candidate = parsed.path or "/"
        else:
            candidate = route.split("?", 1)[0].split("#", 1)[0]
        if candidate.startswith(self._settings.base_url):
            candidate = candidate[len(self._settings.base_url):] or "/"
        route = candidate or "/"
        if not route.startswith("/"):
            route = f"/{route}"
        if route != "/" and route.endswith("/"):
            route = route[:-1]
        return route

    def canonicalize_route(self, value: str) -> str:
        route = self.normalize_route(value)
        if route.endswith(".md"):
            route = route[:-3]  # Enforce invariant: no .md internally
        return route

    def build_urls(self, route: str) -> tuple[str, str]:
        canonical_url = f"{self._settings.base_url}{route}"
        if route == "/" or route.endswith(self._settings.metadata_suffixes) or route.endswith(".md"):
            return canonical_url, canonical_url
        return canonical_url, f"{canonical_url}.md"

    def normalize_route_or_url(self, value: str) -> tuple[str, str, str]:
        route = self.canonicalize_route(value)
        url, md_url = self.build_urls(route)
        return route, url, md_url

    def normalize_docs_route(self, value: str) -> tuple[str, str, str]:
        route = self.canonicalize_route(value)
        url, md_url = self.build_urls(route)
        return route, url, md_url

    @staticmethod
    def classify_corpus(route: str) -> str:
        if route.startswith("/v2/"):
            return "v2"
        if route.startswith("/python-sdk/"):
            return "python-sdk"
        return "default"

    @staticmethod
    def infer_section(route: str, tree: str) -> str:
        normalized = route[3:] or "/" if tree == "v2" else route
        if normalized == "/":
            return "root"
        if normalized in {"/changelog", "/updates", "/llms.txt", "/llms-full.txt", "/sitemap.xml"}:
            return "meta"
        parts = [part for part in normalized.split("/") if part]
        return parts[0] if parts else "root"

    @staticmethod
    def classify_artifact(route: str) -> tuple[bool, str]:
        if route == "/package-lock.json":
            return True, "lockfile"
        if route.startswith("/v3/api-ref/") and route.endswith(".json"):
            return True, "api_spec"
        if route.startswith("/styles/Google/") or route.startswith("/styles/CustomStyles/"):
            return True, "style_rule"
        if route.startswith("/integrations/catalog/") and (
            route.endswith(".yaml") or route.endswith(".yml")
        ):
            return True, "catalog_yaml"
        if route.endswith(".json") or route.endswith(".yaml") or route.endswith(".yml"):
            return True, "artifact"
        return False, ""


class DocsIndex:
    def __init__(self, csv_path: Path, normalizer: RouteNormalizer):
        self.csv_path = csv_path
        self._normalizer = normalizer
        self._lock = threading.Lock()
        self._cached_routes: list[RouteEntry] | None = None

    @classmethod
    def from_settings(cls, settings: BackendSettings) -> DocsIndex:
        return cls(csv_path=settings.routes_csv_path, normalizer=RouteNormalizer(settings))

    def load(self) -> list[RouteEntry]:
        with self._lock:
            if self._cached_routes is not None:
                return self._cached_routes

            if not self.csv_path.exists():
                self._cached_routes = []
                return self._cached_routes

            required = {"route", "tree", "section", "has_v2_counterpart", "notes"}

            with self.csv_path.open("r", encoding="utf-8", newline="") as handle:
                reader: csv.DictReader[str] = csv.DictReader(handle)

                if not reader.fieldnames or not required.issubset(reader.fieldnames):
                    missing = required - set(reader.fieldnames or [])
                    raise ValueError(f"CSV missing columns: {sorted(missing)}")

                routes: list[RouteEntry] = []
                settings = self._normalizer._settings
                for raw_row in reader:

                    row: dict[str, str] = {k: (v or "") for k, v in raw_row.items() if k is not None}

                    routes.append(
                        RouteEntry(
                            route=row["route"],
                            tree=row["tree"],
                            section=row["section"],
                            has_v2_counterpart=row["has_v2_counterpart"],
                            notes=row["notes"],
                            base_url=settings.base_url,
                            metadata_suffixes=settings.metadata_suffixes,
                        )
                    )

                self._cached_routes = routes
                return self._cached_routes

    def is_loaded(self) -> bool:
        return bool(self.load())

    def get(self, route: str) -> RouteEntry | None:
        normalized = self._normalizer.normalize_route(route)
        return next((entry for entry in self.load() if entry.route == normalized), None)

    def filter(
        self,
        tree: str = "",
        section: str = "",
        contains: str = "",
        has_v2_counterpart: str = "",
        exclude_trees: Iterable[str] | None = None,
        include_artifacts: bool = False,
    ) -> list[RouteEntry]:
        normalized_tree = normalize_tree_name(tree) if tree else ""
        normalized_section = clean_text(section) if section else ""
        normalized_contains = clean_text(contains) if contains else ""
        normalized_counterpart = clean_text(has_v2_counterpart) if has_v2_counterpart else ""
        excluded = set(normalize_tree_list(exclude_trees))

        rows = self.load()

        # Filter out artifact routes unless explicitly requested.
        if not include_artifacts:
            rows = [
                row for row in rows
                if not self._normalizer.classify_artifact(row.route)[0]
            ]

        if excluded:
            rows = [row for row in rows if row.tree not in excluded]
        if normalized_tree:
            rows = [row for row in rows if row.tree == normalized_tree]
        if normalized_section:
            rows = [row for row in rows if row.section == normalized_section]
        if normalized_counterpart:
            rows = [
                row
                for row in rows
                if row.has_v2_counterpart == normalized_counterpart
            ]
        if normalized_contains:
            haystack_terms = [term for term in normalized_contains.lower().split() if term]
            rows = [
                row
                for row in rows
                if (
                    normalized_contains.lower()
                    in f"{row.route} {row.section} {row.notes}".lower()
                    or all(
                        term in f"{row.route} {row.section} {row.notes}".lower()
                        for term in haystack_terms
                    )
                )
            ]
        return rows

    def summary(self) -> dict[str, object]:
        rows = self.load()
        if not rows:
            return {
                "csv_path": str(self.csv_path),
                "loaded": False,
                "message": (
                    "No route inventory was loaded. Generate routes.csv with "
                    "normalize_fastmcp_scrape.py or set FASTMCP_ROUTES_CSV."
                ),
            }

        trees: dict[str, int] = {}
        sections: dict[str, int] = {}
        for row in rows:
            trees[row.tree] = trees.get(row.tree, 0) + 1
            section_key = f"{row.tree}:{row.section}"
            sections[section_key] = sections.get(section_key, 0) + 1

        return {
            "csv_path": str(self.csv_path),
            "loaded": True,
            "total_routes": len(rows),
            "trees": dict(sorted(trees.items())),
            "sections": dict(sorted(sections.items())),
        }

    def filtered_payload(
        self,
        tree: str = "",
        section: str = "",
        contains: str = "",
        has_v2_counterpart: str = "",
        exclude_trees: Iterable[str] | None = None,
        include_artifacts: bool = False,
        limit: int | None = None,
    ) -> dict[str, object]:
        if not self.is_loaded():
            return {
                "csv_path": str(self.csv_path),
                "loaded": False,
                "message": (
                    "No route inventory was loaded. Generate routes.csv with "
                    "normalize_fastmcp_scrape.py or set FASTMCP_ROUTES_CSV."
                ),
                "results": [],
            }

        matches = self.filter(
            tree=tree,
            section=section,
            contains=contains,
            has_v2_counterpart=has_v2_counterpart,
            exclude_trees=exclude_trees,
            include_artifacts=include_artifacts,
        )
        effective_limit = clamp_limit(limit, len(matches))
        excluded = normalize_tree_list(exclude_trees)
        return {
            "csv_path": str(self.csv_path),
            "loaded": True,
            "source": "inventory",
            "excluded_trees": excluded,
            "include_artifacts": include_artifacts,
            "total_matches": len(matches),
            "returned": min(len(matches), effective_limit),
            "results": [entry.to_dict() for entry in matches[:effective_limit]],
        }


class FastMCPDocsBackend:
    def __init__(
        self,
        settings: BackendSettings | None = None,
        index: DocsIndex | None = None,
        fetcher: HttpFetcher | None = None,
    ):
        self.settings = settings or BackendSettings.from_env()
        self.normalizer = RouteNormalizer(self.settings)
        self.fetcher = fetcher or HttpFetcher(self.settings)
        self.index = index or DocsIndex.from_settings(self.settings)
        self._llms_cache: TTLCache[list[LlmsTxtEntry]] = TTLCache(
            self.settings.llms_cache_ttl_seconds
        )

    async def _fetch_text(self, url: str, timeout_seconds: float = 20.0) -> str:
        if hasattr(self.fetcher, "fetch_text_async"):
            return await self.fetcher.fetch_text_async(url, timeout_seconds)
        if hasattr(self.fetcher, "fetch_text"):
            return await asyncio.to_thread(self.fetcher.fetch_text, url, timeout_seconds)
        raise TypeError("Fetcher must provide fetch_text_async() or fetch_text().")

    @staticmethod
    def _run_sync(coro: object) -> object:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        raise RuntimeError(
            "Synchronous route listing cannot perform async network work from inside a "
            "running event loop. Use list_routes_payload_async() instead."
        )

    def _resolve_source(self, source: str | None) -> str:
        requested_source = normalize_source_name(source)
        if requested_source in {"", "none", "null"}:
            return "inventory" if self.index.is_loaded() else "llms_txt"
        return requested_source

    @staticmethod
    def _route_payload(
        *,
        source: str,
        results: list[dict[str, object]],
        limit: int | None,
        extra: dict[str, object] | None = None,
    ) -> dict[str, object]:
        effective_limit = clamp_limit(limit, len(results))
        payload: dict[str, object] = {
            "loaded": True,
            "source": source,
            "total_matches": len(results),
            "returned": min(len(results), effective_limit),
            "results": results[:effective_limit],
        }
        if extra:
            payload.update(extra)
        return payload

    def parse_llms_txt(self, text: str) -> list[LlmsTxtEntry]:
        heading_stack: list[str] = []
        inventory = self.index.load() if self.index.is_loaded() else []
        inventory_by_route = {entry.route: entry for entry in inventory}
        entries: list[LlmsTxtEntry] = []

        for raw_line in text.splitlines():
            heading_match = HEADING_RE.match(raw_line)
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                if title:
                    heading_stack[:] = heading_stack[: level - 1]
                    heading_stack.append(title)
                continue

            bullet_match = LINK_BULLET_RE.match(raw_line)
            if not bullet_match:
                continue

            title = clean_text(bullet_match.group("title"))
            url = clean_text(bullet_match.group("url"))
            description = clean_text(bullet_match.group("description") or "")
            route, canonical_url, md_url = self.normalizer.normalize_docs_route(url)
            tree = self.normalizer.classify_corpus(route)
            section_path = " > ".join(heading_stack)
            inventory_match = inventory_by_route.get(route)
            is_artifact, artifact_type = self.normalizer.classify_artifact(route)
            section = (
                inventory_match.section
                if inventory_match is not None
                else self.normalizer.infer_section(route, tree)
            )
            has_v2_counterpart = (
                inventory_match.has_v2_counterpart
                if inventory_match is not None
                else ("yes" if route.startswith("/v2/") else "unknown")
            )
            notes = description or (
                "llms.txt artifact entry" if is_artifact else "llms.txt sitemap entry"
            )

            entries.append(
                LlmsTxtEntry(
                    title=title,
                    url=canonical_url,
                    route=route,
                    md_url=md_url,
                    tree=tree,
                    section=section,
                    section_path=section_path,
                    description=description,
                    has_v2_counterpart=has_v2_counterpart,
                    notes=notes,
                    is_artifact=is_artifact,
                    artifact_type=artifact_type,
                )
            )

        return entries

    async def get_llms_entries_async(self, force_refresh: bool = False) -> list[LlmsTxtEntry]:
        if force_refresh:
            self._llms_cache.clear()

        cached = self._llms_cache.get()
        if cached is not None:
            return cached

        text = await self._fetch_text(self.settings.llms_txt_url)
        entries = self.parse_llms_txt(text)
        if not entries:
            raise ValueError("Parsed llms.txt successfully but found no entries.")
        self._llms_cache.set(entries)
        return entries

    def list_routes_payload(
        self,
        source: str | None = None,
        tree: str = "",
        section: str = "",
        contains: str = "",
        has_v2_counterpart: str = "",
        exclude_trees: Iterable[str] | None = None,
        include_artifacts: bool = False,
        limit: int | None = None,
        force_refresh: bool = False,
    ) -> dict[str, object]:
        requested_source = normalize_source_name(source)
        source_selection = (
            "auto" if requested_source in {"", "none", "null"} else "explicit"
        )
        effective_source = self._resolve_source(source)

        if effective_source == "inventory":
            payload = self.index.filtered_payload(
                tree=tree,
                section=section,
                contains=contains,
                has_v2_counterpart=has_v2_counterpart,
                exclude_trees=exclude_trees,
                include_artifacts=include_artifacts,
                limit=limit,
            )
            payload["source_selection"] = source_selection
            return payload

        payload = self._run_sync(
            self.list_routes_payload_async(
                source=source,
                tree=tree,
                section=section,
                contains=contains,
                has_v2_counterpart=has_v2_counterpart,
                exclude_trees=exclude_trees,
                include_artifacts=include_artifacts,
                limit=limit,
                force_refresh=force_refresh,
            )
        )
        return payload  # type: ignore[return-value]

    @staticmethod
    def filter_llms_entries(
        entries: list[LlmsTxtEntry],
        tree: str = "",
        section: str = "",
        contains: str = "",
        has_v2_counterpart: str = "",
        exclude_trees: Iterable[str] | None = None,
        include_artifacts: bool = False,
    ) -> list[LlmsTxtEntry]:
        normalized_tree = normalize_tree_name(tree) if tree else ""
        normalized_section = clean_text(section) if section else ""
        normalized_contains = clean_text(contains) if contains else ""
        normalized_counterpart = clean_text(has_v2_counterpart) if has_v2_counterpart else ""
        excluded = set(normalize_tree_list(exclude_trees))

        rows = entries
        if not include_artifacts:
            rows = [row for row in rows if not row.is_artifact]
        if excluded:
            rows = [row for row in rows if row.tree not in excluded]
        if normalized_tree:
            rows = [row for row in rows if row.tree == normalized_tree]
        if normalized_section:
            section_needle = normalized_section.lower()
            rows = [
                row
                for row in rows
                if section_needle == row.section.lower()
                or section_needle in row.section_path.lower()
            ]
        if normalized_counterpart:
            rows = [row for row in rows if row.has_v2_counterpart == normalized_counterpart]
        if normalized_contains:
            terms = [term for term in normalized_contains.lower().split() if term]
            rows = [
                row
                for row in rows
                if (
                    normalized_contains.lower()
                    in f"{row.route} {row.title} {row.description} {row.section_path}".lower()
                    or all(
                        term
                        in f"{row.route} {row.title} {row.description} {row.section_path}".lower()
                        for term in terms
                    )
                )
            ]
        return rows

    async def list_routes_from_llms_txt_async(
        self,
        tree: str = "",
        section: str = "",
        contains: str = "",
        has_v2_counterpart: str = "",
        exclude_trees: Iterable[str] | None = None,
        include_artifacts: bool = False,
        limit: int | None = None,
        force_refresh: bool = False,
    ) -> dict[str, object]:
        try:
            entries = await self.get_llms_entries_async(force_refresh=force_refresh)
        except Exception as exc:
            logger.exception("Failed to load llms.txt routes")
            return {
                "loaded": False,
                "source": "llms_txt",
                "source_url": self.settings.llms_txt_url,
                "error": str(exc),
                "error_type": type(exc).__name__,
                "results": [],
            }

        matches = self.filter_llms_entries(
            entries,
            tree=tree,
            section=section,
            contains=contains,
            has_v2_counterpart=has_v2_counterpart,
            exclude_trees=exclude_trees,
            include_artifacts=include_artifacts,
        )
        excluded = normalize_tree_list(exclude_trees)
        return self._route_payload(
            source="llms_txt",
            results=[entry.to_dict() for entry in matches],
            limit=limit,
            extra={
                "source_url": self.settings.llms_txt_url,
                "excluded_trees": excluded,
                "include_artifacts": include_artifacts,
            },
        )

    async def list_routes_from_both_async(
        self,
        tree: str = "",
        section: str = "",
        contains: str = "",
        has_v2_counterpart: str = "",
        exclude_trees: Iterable[str] | None = None,
        include_artifacts: bool = False,
        limit: int | None = None,
        force_refresh: bool = False,
    ) -> dict[str, object]:
        inventory_payload = self.index.filtered_payload(
            tree=tree,
            section=section,
            contains=contains,
            has_v2_counterpart=has_v2_counterpart,
            exclude_trees=exclude_trees,
            include_artifacts=include_artifacts,
            limit=limit,
        )
        llms_payload = await self.list_routes_from_llms_txt_async(
            tree=tree,
            section=section,
            contains=contains,
            has_v2_counterpart=has_v2_counterpart,
            exclude_trees=exclude_trees,
            include_artifacts=include_artifacts,
            limit=limit,
            force_refresh=force_refresh,
        )
        if not inventory_payload.get("loaded"):
            return {
                "source": "both",
                "loaded": False,
                "inventory": inventory_payload,
                "llms_txt": llms_payload,
                "error": "Inventory source is unavailable.",
            }
        if not llms_payload.get("loaded"):
            return {
                "source": "both",
                "loaded": False,
                "inventory": inventory_payload,
                "llms_txt": llms_payload,
                "error": "llms.txt source is unavailable.",
            }

        # Reuse the entries already fetched for inventory_payload to avoid a
        # redundant index.filter() call.
        inventory_routes = {
            entry["route"]
            for entry in inventory_payload.get("results", [])
        }
        try:
            llms_entries = await self.get_llms_entries_async(force_refresh=force_refresh)
        except Exception as exc:
            logger.exception("Failed to refresh llms.txt routes for diff")
            return {
                "source": "both",
                "loaded": False,
                "inventory": inventory_payload,
                "llms_txt": llms_payload,
                "error": str(exc),
            }
        llms_routes = {
            entry.route
            for entry in self.filter_llms_entries(
                llms_entries,
                tree=tree,
                section=section,
                contains=contains,
                has_v2_counterpart=has_v2_counterpart,
                exclude_trees=exclude_trees,
                include_artifacts=include_artifacts,
            )
        }

        return {
            "source": "both",
            "loaded": True,
            "include_artifacts": include_artifacts,
            "inventory_total": inventory_payload["total_matches"],
            "llms_total": llms_payload["total_matches"],
            "inventory": inventory_payload,
            "llms_txt": llms_payload,
            "missing_in_inventory": sorted(llms_routes - inventory_routes),
            "missing_in_llms_txt": sorted(inventory_routes - llms_routes),
        }

    async def list_routes_payload_async(
        self,
        source: str | None = None,
        tree: str = "",
        section: str = "",
        contains: str = "",
        has_v2_counterpart: str = "",
        exclude_trees: Iterable[str] | None = None,
        include_artifacts: bool = False,
        limit: int | None = None,
        force_refresh: bool = False,
    ) -> dict[str, object]:
        requested_source = normalize_source_name(source)
        source_selection = (
            "auto" if requested_source in {"", "none", "null"} else "explicit"
        )
        effective_source = self._resolve_source(source)

        if effective_source == "inventory":
            payload = self.index.filtered_payload(
                tree=tree,
                section=section,
                contains=contains,
                has_v2_counterpart=has_v2_counterpart,
                exclude_trees=exclude_trees,
                include_artifacts=include_artifacts,
                limit=limit,
            )
        elif effective_source == "llms_txt":
            payload = await self.list_routes_from_llms_txt_async(
                tree=tree,
                section=section,
                contains=contains,
                has_v2_counterpart=has_v2_counterpart,
                exclude_trees=exclude_trees,
                include_artifacts=include_artifacts,
                limit=limit,
                force_refresh=force_refresh,
            )
        elif effective_source == "both":
            payload = await self.list_routes_from_both_async(
                tree=tree,
                section=section,
                contains=contains,
                has_v2_counterpart=has_v2_counterpart,
                exclude_trees=exclude_trees,
                include_artifacts=include_artifacts,
                limit=limit,
                force_refresh=force_refresh,
            )
        else:
            return {
                "loaded": False,
                "source": effective_source,
                "source_selection": source_selection,
                "error": "Unsupported source. Use 'inventory', 'llms_txt', or 'both'.",
                "results": [],
            }

        payload["source_selection"] = source_selection
        return payload

    async def search_upstream(
        self,
        query: str,
        tree: str = "",
        search_limit: int = 6,
    ) -> list[tuple[str, str, str]]:
        arguments: dict[str, object] = {"query": clean_text(query)}
        if normalize_tree_name(tree) == "v2":
            arguments["version"] = "v2"

        async with Client(self.settings.upstream_mcp_url) as client:
            result = await client.call_tool(DEFAULT_UPSTREAM_TOOL_CALL, arguments)

        content = getattr(result, "content", None) or []
        matches: list[tuple[str, str, str]] = []
        for item in content[:search_limit]:
            text = getattr(item, "text", "")
            if not text:
                continue
            title, link, snippet = parse_search_result_text(text)
            if link.startswith(self.settings.base_url):
                matches.append((title, link, snippet))
        return matches

    def filter_search_matches(
        self,
        parsed_matches: list[tuple[str, str, str]],
        tree: str = "",
        section: str = "",
        exclude_trees: Iterable[str] | None = None,
    ) -> list[SearchMatch]:
        excluded = set(normalize_tree_list(exclude_trees))
        allowed = {
            row.route: row
            for row in self.index.filter(
                tree=tree,
                section=section,
                exclude_trees=excluded,
            )
        }
        all_routes = {row.route: row for row in self.index.load()}
        matches: list[SearchMatch] = []

        for title, link, snippet in parsed_matches:
            route, _, md_url = self.normalizer.normalize_route_or_url(link)
            route_info = allowed.get(route)

            if route_info is None and route in all_routes and all_routes[route].tree in excluded:
                continue
            if tree or section or excluded:
                if route_info is None:
                    continue
            elif route_info is None:
                route_info = all_routes.get(route)

            if route_info is None:
                matches.append(
                    SearchMatch(
                        title=title,
                        route=route,
                        url=link,
                        md_url=md_url,
                        section="unknown",
                        tree="unknown",
                        notes="not found in local inventory",
                        snippet=snippet,
                    )
                )
                continue

            matches.append(
                SearchMatch(
                    title=title,
                    route=route_info.route,
                    url=route_info.url,
                    md_url=route_info.md_url,
                    section=route_info.section,
                    tree=route_info.tree,
                    notes=route_info.notes,
                    snippet=snippet,
                )
            )

        return matches

    async def fetch_markdown_async(self, target: str, max_chars: int = 20_000) -> dict[str, object]:
        route, url, md_url = self.normalizer.normalize_route_or_url(target)
        max_chars = max(500, min(max_chars, 100_000))
        try:
            markdown = await self._fetch_text(md_url)
        except httpx.HTTPStatusError as exc:
            failure = FetchFailure(target=target, error_type="HTTPError", error_message=str(exc))
            return {"route": route, "url": url, "md_url": md_url, **failure.to_payload()}
        except httpx.RequestError as exc:
            failure = FetchFailure(target=target, error_type="NetworkError", error_message=str(exc))
            return {"route": route, "url": url, "md_url": md_url, **failure.to_payload()}
        except Exception as exc:
            failure = FetchFailure(target=target, error_type=type(exc).__name__, error_message=str(exc))
            return {"route": route, "url": url, "md_url": md_url, **failure.to_payload()}

        truncated = len(markdown) > max_chars
        return {
            "route": route,
            "url": url,
            "md_url": md_url,
            "found": True,
            "truncated": truncated,
            "markdown": markdown[:max_chars],
        }

    async def fetch_excerpt_async(
            self,
            target: str,
            heading_contains: str = "",
            text_contains: str = "",
            max_sections: int = 3,
            max_chars: int = 8_000,
    ) -> dict[str, object]:
        heading_needle = clean_text(heading_contains).lower()
        text_needle = clean_text(text_contains).lower()
        max_sections = max(1, min(max_sections, 10))
        max_chars = max(500, min(max_chars, 40_000))

        page = await self.fetch_markdown_async(target, max_chars=200_000)
        if not page.get("found"):
            return page

        all_sections = split_markdown_sections(page["markdown"])
        filtered = all_sections

        if heading_needle:
            filtered = [s for s in filtered if heading_needle in s["heading"].lower()]

        if text_needle:
            filtered = [
                s for s in filtered
                if text_needle in s["heading"].lower() or text_needle in s["content"].lower()
            ]

        # Fallback to the first section if no matches found
        if not filtered and all_sections:
            filtered = all_sections[:1]

        excerpt_sections: list[dict[str, object]] = []
        total_chars = 0
        for s in filtered:
            if len(excerpt_sections) >= max_sections:
                break
            remaining = max_chars - total_chars
            if remaining <= 0:
                break
            content = s["content"]
            truncated = len(content) > remaining
            excerpt_sections.append(
                {"heading": s["heading"], "content": content[:remaining], "truncated": truncated}
            )
            total_chars += len(content[:remaining])

        return {
            "route": page["route"],
            "url": page["url"],
            "md_url": page["md_url"],
            "found": True,
            "filters": {"heading_contains": heading_contains, "text_contains": text_contains},
            "sections": excerpt_sections,
        }

    def parser_self_check(self) -> dict[str, object]:
        sample = """
        # FastMCP
        
        ## Docs
        - [Calling Tools](https://gofastmcp.com/clients/tools.md): Execute server-side tools.
        - [Proxy Provider](https://gofastmcp.com/servers/providers/proxy.md)
        """
        entries = self.parse_llms_txt(sample)
        if len(entries) != 2:
            raise ValueError(
                f"parser_self_check: expected 2 entries, got {len(entries)}"
            )
        if entries[0].route != "/clients/tools":
            raise ValueError(
                f"parser_self_check: expected route '/clients/tools', got '{entries[0].route}'"
            )
        if entries[0].section_path != "FastMCP > Docs":
            raise ValueError(
                f"parser_self_check: expected section_path 'FastMCP > Docs', "
                f"got '{entries[0].section_path}'"
            )
        if entries[1].route != "/servers/providers/proxy":
            raise ValueError(
                f"parser_self_check: expected route '/servers/providers/proxy', "
                f"got '{entries[1].route}'"
            )
        return {
            "ok": True,
            "entries": [entry.to_dict() for entry in entries],
        }


_default_backend: FastMCPDocsBackend | None = None
_default_backend_lock = threading.Lock()


def get_default_backend() -> FastMCPDocsBackend:
    global _default_backend
    if _default_backend is None:
        with _default_backend_lock:
            # Double-checked locking: re-test inside the lock.
            if _default_backend is None:
                _default_backend = FastMCPDocsBackend()
    return _default_backend


def parse_llms_txt(text: str, index: DocsIndex | None = None) -> list[LlmsTxtEntry]:
    if index is not None:
        backend = FastMCPDocsBackend(
            settings=BackendSettings.from_env(),
            index=index,
        )
        return backend.parse_llms_txt(text)
    return get_default_backend().parse_llms_txt(text)


async def fetch_text_async(url: str, timeout_seconds: float = 20.0) -> str:
    """Async HTTP fetch; safe for use inside an MCP server."""
    return await get_default_backend().fetcher.fetch_text_async(url, timeout_seconds)


async def search_upstream(
    query: str,
    tree: str = "",
    search_limit: int = 6,
) -> list[tuple[str, str, str]]:
    return await get_default_backend().search_upstream(query, tree, search_limit)


def filter_search_matches(
    index: DocsIndex,
    parsed_matches: list[tuple[str, str, str]],
    tree: str = "",
    section: str = "",
    exclude_trees: Iterable[str] | None = None,
) -> list[SearchMatch]:
    backend = FastMCPDocsBackend(settings=BackendSettings.from_env(), index=index)
    return backend.filter_search_matches(parsed_matches, tree, section, exclude_trees)


async def list_routes_payload_async(
    index: DocsIndex,
    backend: FastMCPDocsBackend | None = None,
    source: str | None = None,
    tree: str = "",
    section: str = "",
    contains: str = "",
    has_v2_counterpart: str = "",
    exclude_trees: Iterable[str] | None = None,
    include_artifacts: bool = False,
    limit: int | None = None,
    force_refresh: bool = False,
) -> dict[str, object]:
    resolved_backend = backend or FastMCPDocsBackend(
        settings=BackendSettings.from_env(),
        index=index,
    )
    return await resolved_backend.list_routes_payload_async(
        source=source,
        tree=tree,
        section=section,
        contains=contains,
        has_v2_counterpart=has_v2_counterpart,
        exclude_trees=exclude_trees,
        include_artifacts=include_artifacts,
        limit=limit,
        force_refresh=force_refresh,
    )


def inventory_summary_resource(index: DocsIndex) -> str:
    return json.dumps(index.summary(), indent=2, sort_keys=True)


async def inventory_routes_resource_async(
    index: DocsIndex,
    backend: FastMCPDocsBackend | None = None,
    tree: str = "",
    section: str = "",
    contains: str = "",
    source: str = "",
    has_v2_counterpart: str = "",
    exclude_trees: str = "",
    include_artifacts: bool = False,
    limit: int | None = None,
    force_refresh: bool = False,
) -> str:
    """Async version for MCP servers."""
    excluded = [
        part.strip() for part in clean_text(exclude_trees).split(",") if part.strip()
    ]
    payload = await list_routes_payload_async(
        index=index,
        backend=backend,
        source=source,
        tree=tree,
        section=section,
        contains=contains,
        has_v2_counterpart=has_v2_counterpart,
        exclude_trees=excluded,
        include_artifacts=include_artifacts,
        limit=limit,
        force_refresh=force_refresh,
    )
    return json.dumps(payload, indent=2, sort_keys=True)


def llms_txt_parser_self_check() -> dict[str, object]:
    return get_default_backend().parser_self_check()
