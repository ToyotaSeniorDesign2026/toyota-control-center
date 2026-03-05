# FastMCP Documentation MCP Server

An MCP server for navigating the FastMCP docs with a small, agent-oriented tool surface.

The server is optimized for LLM use:
- `list_docs`: list routes from the local inventory, `llms.txt`, or both
- `fetch_doc`: fetch a known docs page as an excerpt or full markdown
- `search_documentation`: ask a question in natural language and get back the relevant documentation paths or excerpts needed to answer it.

The runtime is split cleanly:
- [fastmcp_docs.py](/fastmcp-docs-mcp/fastmcp_docs.py): thin MCP entrypoint
- [fastmcp_docs_backend.py](/fastmcp-docs-mcp/fastmcp_docs_backend.py): normalization, parsing, caching, inventory, and fetch logic
- [utils/normalize_fastmcp_scrape.py](/fastmcp-docs-mcp/utils/normalize_fastmcp_scrape.py): route inventory generation

Primary Tools
- `list_docs`: Discover available routes. Filters by source (inventory, llms_txt, or both).

`fetch_doc`: Retrieve specific page content. Use mode="excerpt" for a concise, token-efficient summary of a targeted section.

`search_documentation`: The "Router." Resolves natural language queries into specific documentation routes.

---

# QUICK START (<2 MINUTES)

The fastest way to run the FastMCP Documentation MCP Server is standalone mode using `uv --with fastmcp`.

No virtualenv. No install step. No project setup.

---

## 1️⃣ Download Required Files

At minimum, download:

* `fastmcp_docs.py`
* `fastmcp_docs_backend.py`

Optional but recommended:

* `routes.csv` (for deterministic route resolution)

* `run_fastmcp_docs.sh` (convenient launcher script)

Optional for regenerating `routes.csv` in the future:

* `util/normalize_fastmcp_scrape.py`

Place them in the same folder.

---

## 2️⃣ Install `uv` (If Needed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify:

```bash
uv --version
```

---

## 3️⃣ Run the Server

From the directory containing `fastmcp_docs.py`:

```bash
uv run --with fastmcp python fastmcp_docs.py
```

That’s it!

The server will start using stdio transport, which is ideal for MCP clients like Claude Desktop, Cursor, etc.

Or, for an even easier way, you can just run the launcher script with zero config:

```
./run_fastmcp_docs.sh
# If that doesn't work, you may need to make it executable first:
chmod +x run_fastmcp_docs.sh
```

To launch it with its own testing UI (MCP Inspector), run:

```
npx -y @modelcontextprotocol/inspector uv run --with fastmcp fastmcp_docs.py
```

---

## ⚡ Quick Start for MCP Client Config

If your MCP client supports direct command execution, use:

```json
{
  "mcpServers": {
    "fastmcp-docs": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "fastmcp",
        "python",
        "/ABSOLUTE/PATH/TO/fastmcp_docs.py"
      ]
    }
  }
}
```

Replace `/ABSOLUTE/PATH/TO/` with the real file path.

---

## What Happens Under the Hood?

* `uv` creates an ephemeral environment
* `fastmcp` is installed on-the-fly
* No global installs
* No venv activation required

If `routes.csv` is present → deterministic local routing
If not → server falls back to live `llms.txt`

---

# 🧩 Optional: Deterministic Routing

If you want fully deterministic route resolution:

1. Download `routes.csv`
2. Place it next to `fastmcp_docs.py`
3. Or set:

```bash
FASTMCP_ROUTES_CSV=/path/to/routes.csv
```

---

If you'd like, I can also:

* Rewrite this into an ultra-minimal 10-line “Zero Friction” version
* Or add a **“For AI Engineers”** Quick Start variant tailored to your MCP gateway ecosystem
* Or integrate this seamlessly into your full README without redundancy

# LESS-QUICK START (>2 MINUTES)

There are two good sharing modes.

### Option A: Repo-Managed Mode

Best when you want reproducible installs and pinned dependencies.

Necessary files:

- `fastmcp_docs.py`
- `fastmcp_docs_backend.py`
- `normalize_fastmcp_scrape.py`
- `routes.csv`
- `run_fastmcp_docs.sh`
- `README.md`

### Option B: Standalone `--with fastmcp` Mode

Best when you want the lightest possible handoff and only need `fastmcp` at runtime.

Necessary files:

- `fastmcp_docs.py`
- `fastmcp_docs_backend.py`
- `routes.csv`
- `run_fastmcp_docs.sh`
- `README.md`

Optional:

- `normalize_fastmcp_scrape.py`
  - only needed if someone wants to regenerate `routes.csv`

If `routes.csv` is omitted, the server can still work by falling back to `https://gofastmcp.com/llms.txt`, but keeping `routes.csv` is recommended because:

- it makes route resolution deterministic
- it avoids relying on the network for route inventory
- it enables better comparisons against `llms.txt`

## Requirements

- Python 3.12+
- `uv`

Install `uv` if needed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## One-Command Run

Use the included launcher:

```bash
./run_fastmcp_docs.sh
```

By default, this runs in repo-managed mode:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python fastmcp_docs.py
```

To force lightweight standalone mode:

```bash
FASTMCP_RUNTIME_MODE=standalone ./run_fastmcp_docs.sh
```

That runs:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --with fastmcp==3.0.2 python fastmcp_docs.py
```

Optional environment variables:

- `FASTMCP_ROUTES_CSV`
  - override the default local `routes.csv` path
- `FASTMCP_DOCS_BASE_URL`
  - override the docs site base URL
- `FASTMCP_DOCS_UPSTREAM_MCP_URL`
  - override the upstream FastMCP docs MCP endpoint
- `FASTMCP_DOCS_LLMS_CACHE_TTL_SECONDS`
  - cache lifetime for fetched `llms.txt` entries
- `UV_CACHE_DIR`
  - override the uv cache location
- `FASTMCP_RUNTIME_MODE`
  - `project` or `standalone`
- `FASTMCP_RUNTIME_DEP`
  - dependency spec used in standalone mode
  - default: `fastmcp==3.0.2`

Example:

```bash
FASTMCP_ROUTES_CSV=/path/to/routes.csv ./run_fastmcp_docs.sh
```

Standalone example:

```bash
FASTMCP_RUNTIME_MODE=standalone FASTMCP_ROUTES_CSV=/path/to/routes.csv ./run_fastmcp_docs.sh
```

Show launcher help:

```bash
./run_fastmcp_docs.sh --help
```

## Common MCP Config Snippets

Replace `/ABSOLUTE/PATH/TO/REPO` with the real repo path on each machine.

### Claude Desktop / Claude Code Style JSON

Repo-managed mode:

```json
{
  "mcpServers": {
    "fastmcp-docs": {
      "command": "/ABSOLUTE/PATH/TO/REPO/run_fastmcp_docs.sh",
      "args": []
    }
  }
}
```

Repo-managed direct `uv` call:

```json
{
  "mcpServers": {
    "fastmcp-docs": {
      "command": "uv",
      "args": [
        "run",
        "python",
        "/ABSOLUTE/PATH/TO/REPO/fastmcp_docs.py"
      ],
      "env": {
        "UV_CACHE_DIR": "/tmp/uv-cache",
        "FASTMCP_ROUTES_CSV": "/ABSOLUTE/PATH/TO/REPO/routes.csv"
      }
    }
  }
}
```

Standalone `--with fastmcp` mode:

```json
{
  "mcpServers": {
    "fastmcp-docs": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "fastmcp==3.0.2",
        "python",
        "/ABSOLUTE/PATH/TO/REPO/fastmcp_docs.py"
      ],
      "env": {
        "UV_CACHE_DIR": "/tmp/uv-cache",
        "FASTMCP_ROUTES_CSV": "/ABSOLUTE/PATH/TO/REPO/routes.csv"
      }
    }
  }
}
```

### Cursor Style JSON

Using the launcher:

```json
{
  "mcpServers": {
    "fastmcp-docs": {
      "command": "/ABSOLUTE/PATH/TO/REPO/run_fastmcp_docs.sh",
      "args": []
    }
  }
}
```

Standalone direct `uv` call:

```json
{
  "mcpServers": {
    "fastmcp-docs": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "fastmcp==3.0.2",
        "python",
        "/ABSOLUTE/PATH/TO/REPO/fastmcp_docs.py"
      ]
    }
  }
}
```

### Generic MCP Client Config

```json
{
  "mcpServers": {
    "fastmcp-docs": {
      "command": "/ABSOLUTE/PATH/TO/REPO/run_fastmcp_docs.sh"
    }
  }
}
```

## Main Tools

### `list_docs`

List docs routes from:

- `inventory`
- `llms_txt`
- `both`

Examples:

```python
list_docs()
```

```python
list_docs(source="llms_txt")
```

```python
list_docs(source="both")
```

```python
list_docs(source="llms_txt", include_artifacts=True)
```

Notes:

- if `source` is omitted, the server uses local inventory first, then falls back to `llms.txt`
- responses include `source_selection` so agents can tell whether routing was automatic or explicit
- if `limit` is omitted, all matches are returned
- `llms.txt` artifacts are excluded by default unless `include_artifacts=True`
- `list_docs` is async internally, so `llms.txt` fetches do not block the MCP server event loop

### `fetch_doc`

Fetch a known page as either an excerpt or full markdown:

```python
fetch_doc("/servers/providers/proxy")
```

```python
fetch_doc(
  "/servers/providers/proxy",
  mode="excerpt",
  heading_contains="Why Use Proxy Provider"
)
```

```python
fetch_doc(
  "/servers/providers/proxy",
  mode="markdown",
  max_chars=40000
)
```

Notes:

- `mode="excerpt"` is the default and is the better choice for agents
- `mode="markdown"` returns the full page markdown payload

### `search_documentation`

Resolve a natural-language query into the best route or excerpt:

```python
search_documentation("proxy providers")
```

```python
search_documentation("ProxyProvider", tree="python-sdk")
```

```python
search_documentation("proxy providers", force_upstream_search=True)
```

```python
search_documentation("proxy providers", include_markdown=True)
```

Notes:

- `prefer_excerpt=True` adds a focused excerpt only when there is a single best match
- `include_markdown=True` attaches full markdown payloads to returned match objects

## Resources

### `docs://inventory/summary`

Read-only inventory summary.

### `docs://inventory/routes{?...}`

Read-only route listing resource with the same source-switching behavior as `list_docs`.

Example:

```text
docs://inventory/routes?source=inventory&contains=proxy
```

```text
docs://inventory/routes?source=llms_txt&include_artifacts=true
```

## Regenerating `routes.csv`

If you have a fresh scrape file:

```bash
python normalize_fastmcp_scrape.py raw_scrape.txt -o routes.csv
```

## Regression Checks

Run the backend regression tests:

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

These tests cover:
- route normalization
- `llms.txt` parsing and section-path extraction
- artifact exclusion behavior
- source auto-selection and fallback
- sync/async route-listing payload behavior

## Recommended Team Workflow

### For Teams

1. Commit `routes.csv` into the repo.
2. Share the repo path and this README.
3. Have each teammate add one MCP config entry pointing to `run_fastmcp_docs.sh`.
4. Update via `git pull`.

### For Lightweight Sharing

1. Share only the standalone file set.
2. Have each person use the standalone `uv run --with fastmcp==3.0.2 ...` config.
3. Replace files manually when you publish updates.

## Troubleshooting

If the server cannot find local inventory:

- verify `routes.csv` exists
- or set `FASTMCP_ROUTES_CSV`
- otherwise it will fall back to `llms.txt`

If you want deterministic route resolution:

- keep `routes.csv` in the repo
- prefer `source="inventory"` or the default auto mode
- use `source="llms_txt"` only when you intentionally want the live official sitemap

If `uv` cache permissions cause issues:

- set `UV_CACHE_DIR=/tmp/uv-cache`

If a client sends a query but routing looks wrong:

- use explicit `source="inventory"` or `source="llms_txt"`
- use `force_upstream_search=True` in `search_documentation`
