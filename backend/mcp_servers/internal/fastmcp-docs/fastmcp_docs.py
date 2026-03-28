
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "fastmcp==3.0.2",
# ]
# ///

from __future__ import annotations
import os
import asyncio
import json
from typing import Optional, Annotated, Literal
from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan
from fastmcp_docs_backend import (
    FastMCPDocsBackend,
    clean_text,
    inventory_summary_resource,
    normalize_tree_list,
    normalize_tree_name,
    semantic_match_sort_key,
)


def build_server(backend: Optional[FastMCPDocsBackend] = None) -> FastMCP:
    """
    Build and configure the FastMCP server.
    If a backend is provided, the caller owns its lifecycle.
    Otherwise, the server creates and manages its own backend.
    """

    resolved_backend = backend or FastMCPDocsBackend()
    owns_backend = backend is None

    index = resolved_backend.index

    @lifespan
    async def app_lifespan(server: FastMCP):
        # Optional warm-up (loads CSV into memory)
        index.load()

        server_state = {"backend": resolved_backend, "index": index}

        try:
            yield server_state
        finally:
            # Always run on shutdown, even if startup or runtime errors occurred.
            if owns_backend:
                await resolved_backend.fetcher.aclose()

    mcp = FastMCP("fastmcp-docs", lifespan=app_lifespan)

    async def with_markdown(matches: list[dict[str, object]], *, max_markdown_chars: int) -> list[dict[str, object]]:
        if not matches:
            return []

        payloads = await asyncio.gather(
            *(resolved_backend.fetch_markdown_async(str(m["route"]), max_chars=max_markdown_chars) for m in matches)
        )

        return [
            {**m, "markdown": p} for m, p in zip(matches, payloads, strict=True)
        ]

    @mcp.resource("docs://inventory/summary", mime_type="application/json")
    def docs_summary() -> str:
        """
        Get a high-level overview of the FastMCP documentation pages (paths under gofastmcp.com).
        Use this to see which 'trees' (projects/versions) and 'sections' are currently indexed.
        """
        return inventory_summary_resource(index)

    @mcp.resource(
        "docs://inventory/routes{?tree,section,contains,source,has_v2_counterpart,"
        "exclude_trees,include_artifacts,limit,force_refresh}", mime_type="application/json",
    )
    async def docs_routes(
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
        """
        Browse the FastMCP documentation index (gofastmcp.com) using filters.
        Useful for discovering specific page paths (routes) without a semantic search.
        """
        excluded = [
            part.strip() for part in clean_text(exclude_trees).split(",") if part.strip()
        ]
        payload = await resolved_backend.list_routes_payload_async(
            source=source,
            tree=_clean_tree(tree),
            section=_clean_opt_text(section),
            contains=_clean_opt_text(contains),
            has_v2_counterpart=_clean_opt_text(has_v2_counterpart),
            exclude_trees=excluded,
            include_artifacts=include_artifacts,
            limit=limit,
            force_refresh=force_refresh,
        )
        return json.dumps(payload, indent=2, sort_keys=True)

    def _clean_opt_text(s: str) -> str:
        return clean_text(s) if s else ""

    def _clean_tree(s: str) -> str:
        return normalize_tree_name(s) if s else ""

    def _clean_exclude_trees(exclude: list[str] | None, *, default: list[str] | None = None) -> list[str]:
        if exclude is None:
            exclude = default or []
        return normalize_tree_list(exclude)

    def _clamp_int(value: int, lo: int, hi: int) -> int:
        return max(lo, min(value, hi))

    @mcp.tool(
        description="""
        List docs routes from local inventory (endpoint discovery csv), the official llms.txt sitemap, or both.
    
        If `source` is omitted, the server uses local csv inventory first and falls
        back to `llms.txt` when no inventory is available. Use `source="inventory"`
        to force the local inventory, `source="llms_txt"` to force the official sitemap,
        or `source="both"` to compare the two. If `limit` is omitted,
        all matches are returned. `llms.txt` machine artifacts are excluded by
        default unless `include_artifacts=True`.
        """
    )
    async def list_docs(
            contains: Annotated[str, "Substring search across route/path/title."] = "",
            tree: Annotated[str, "Limit results to a docs subtree (e.g., 'servers', 'clients')."] = "",
            section: Annotated[str, "Optional section/category filter (backend-defined)."] = "",
            source: Annotated[str | None, "Route source: 'inventory', 'llms_txt', or 'both'. None = fallback."] = None,
            exclude_trees: Annotated[list[str] | None, "List of subtrees to exclude from results."] = None,
            include_artifacts: Annotated[bool, "Include machine artifacts from llms.txt (default false)."] = False,
            limit: Annotated[int | None, "Max results to return. Omit for all matches."] = None,
            force_refresh: Annotated[bool, "Re-fetch/rebuild sources (use when results may be stale)."] = False,
    ) -> dict[str, object]:
        return await resolved_backend.list_routes_payload_async(
            source=source,
            tree=_clean_tree(tree),
            section=_clean_opt_text(section),
            contains=_clean_opt_text(contains),
            exclude_trees=_clean_exclude_trees(exclude_trees),
            include_artifacts=include_artifacts,
            limit=limit,
            force_refresh=force_refresh,
        )

    @mcp.tool(
        description="""
        Fetch a known docs page (route/id/URL) as either an excerpt or full markdown.

        Use `mode="excerpt"` for token-efficient section retrieval or
        `mode="markdown"` for the full page markdown.
        """
    )
    async def fetch_doc(
            target: Annotated[str, "Docs page identifier (route/id/URL) to fetch."],
            mode: Annotated[Literal["markdown", "excerpt"], "Fetch full .md page or relevant sections"] = "markdown",
            heading_contains: Annotated[str, "Optional substring filter on section headings (excerpt mode only)."] = "",
            text_contains: Annotated[str, "Optional substring filter on section body text (excerpt mode only)."] = "",
            max_sections: Annotated[int, "Maximum number of sections to return in excerpt mode."] = 3,
            max_chars: Annotated[int, "Hard cap on returned characters (applies to excerpt/markdown)."] = 8000,
    ) -> dict[str, object]:
        normalized_mode = _clean_opt_text(mode).lower() or "excerpt"
        if normalized_mode == "markdown":
            return await resolved_backend.fetch_markdown_async(
                target=target,
                max_chars=max_chars,
            )
        if normalized_mode != "excerpt":
            return {
                "found": False,
                "error_type": "ValueError",
                "error": "Unsupported mode. Use 'excerpt' or 'markdown'.",
            }
        return await resolved_backend.fetch_excerpt_async(
            target=target,
            heading_contains=_clean_opt_text(heading_contains),
            text_contains=_clean_opt_text(text_contains),
            max_sections=max_sections,
            max_chars=max_chars,
        )

    async def _single_match_response(
            *,
            mode: str,
            query: str,
            excluded_trees: list[str],
            include_markdown: bool,
            force_upstream_search: bool,
            chosen: dict[str, object],
            prefer_excerpt: bool,
            max_markdown_chars: int,
    ) -> dict[str, object]:
        match = chosen
        if include_markdown:
            match = (await with_markdown([match], max_markdown_chars=max_markdown_chars))[0]

        response: dict[str, object] = {
            "mode": mode,
            "query": query,
            "excluded_trees": excluded_trees,
            "include_markdown": include_markdown,
            "force_upstream_search": force_upstream_search,
            "match": match,
        }

        if prefer_excerpt:
            response["excerpt"] = await resolved_backend.fetch_excerpt_async(str(match["route"]))

        return response

    @mcp.tool(
        description="""
        Search FastMCP documentation using a two-stage strategy and return the best route(s)
        (and optionally the relevant text).
    
        Strategy (in order):
        1) Deterministic local resolution (fast): tries to match `query` against known routes
        in the local index (optionally narrowed by `tree` / `section`).
        2) Upstream semantic search (fallback): if local matching is ambiguous or empty, queries
        the upstream docs search and ranks results (set `force_upstream_search=True` to guarantee).
    
        Set `prefer_excerpt=True` to attach a focused excerpt for a single best
        match. Set `include_markdown=True` to attach full-page markdown payloads to
        each returned match. Set a value for `max_markdown_chars` to limit the payload size.
        """
    )
    async def search_documentation(
            query: Annotated[str, "Natural-language topic, keywords, or question to find the best docs page(s)."],
            tree: Annotated[str, "Optional docs subtree filter (e.g., 'servers', 'clients'). Empty=all."] = "",
            section: Annotated[str, "Optional section/category filter (backend-defined). Empty=all."] = "",
            exclude_trees: Annotated[list[str] | None, "Subtrees to exclude (defaults to ['v2'] if omitted)."] = None,
            prefer_excerpt: Annotated[bool, "When a single best match exists, attach a focused excerpt."] = False,
            include_markdown: Annotated[bool, "Attach full-page markdown to results (large; use sparingly)."] = False,
            max_markdown_chars: Annotated[int, "Max .md characters when include_markdown=True (500–100000)."] = 20_000,
            force_upstream_search: Annotated[bool, "Skip route matching, always run upstream semantic search."] = False,
    ) -> dict[str, object]:
        cleaned_query = clean_text(query)
        cleaned_tree = _clean_tree(tree)
        cleaned_section = _clean_opt_text(section)
        cleaned_excluded = _clean_exclude_trees(exclude_trees, default=["v2"])
        max_markdown_chars = _clamp_int(max_markdown_chars, 500, 100_000)

        # Deterministic local route match (fast path)
        direct_results: list[dict[str, object]] = []
        if not force_upstream_search:
            direct_payload = index.filtered_payload(
                tree=cleaned_tree,
                section=cleaned_section,
                contains=cleaned_query,
                exclude_trees=cleaned_excluded,
                limit=5,
            )
            direct_results = list(direct_payload.get("results", []))

            if len(direct_results) == 1:
                return await _single_match_response(
                    mode="single-route-match",
                    query=cleaned_query,
                    excluded_trees=cleaned_excluded,
                    include_markdown=include_markdown,
                    force_upstream_search=force_upstream_search,
                    chosen=direct_results[0],
                    prefer_excerpt=prefer_excerpt,
                    max_markdown_chars=max_markdown_chars,
                )

        # Upstream semantic search
        upstream_error: dict[str, str] | None = None
        semantic_matches: list[dict[str, object]] = []
        try:
            parsed_matches = await resolved_backend.search_upstream(
                query=cleaned_query,
                tree=cleaned_tree,
                search_limit=6,
            )

            filtered = resolved_backend.filter_search_matches(
                parsed_matches=parsed_matches,
                tree=cleaned_tree,
                section=cleaned_section,
                exclude_trees=cleaned_excluded,
            )

            semantic_matches = [
                m.to_dict()
                for m in sorted(
                    filtered,
                    key=lambda m: semantic_match_sort_key(m, cleaned_query),
                )
            ]
        except Exception as exc:
            upstream_error = {
                "error": str(exc),
                "error_type": type(exc).__name__,
            }

        if len(semantic_matches) == 1:
            return await _single_match_response(
                mode="single-semantic-match",
                query=cleaned_query,
                excluded_trees=cleaned_excluded,
                include_markdown=include_markdown,
                force_upstream_search=force_upstream_search,
                chosen=semantic_matches[0],
                prefer_excerpt=prefer_excerpt,
                max_markdown_chars=max_markdown_chars,
            )

        # Multi-result response (optionally enrich with markdown)
        if include_markdown:
            direct_results, semantic_matches = await asyncio.gather(
                with_markdown(direct_results, max_markdown_chars=max_markdown_chars),
                with_markdown(semantic_matches, max_markdown_chars=max_markdown_chars),
            )

        response = {
            "mode": "search-results",
            "query": cleaned_query,
            "tree": cleaned_tree or "all",
            "section": cleaned_section or "all",
            "excluded_trees": cleaned_excluded,
            "include_markdown": include_markdown,
            "force_upstream_search": force_upstream_search,
            "deterministic_matches": direct_results,
            "semantic_matches": semantic_matches,
        }
        if upstream_error is not None:
            response["upstream_error"] = upstream_error
        return response

    return mcp


mcp_server = build_server()


if __name__ == "__main__":
    mcp_server.run()
