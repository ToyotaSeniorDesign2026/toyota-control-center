# .local

Machine-local runtime state for the backend. Contents are not committed and
are safe to delete and regenerate at any time.

## Layout

- `fs-sandbox/` — allowed root for the filesystem MCP server. The agent can
  read/write here freely. Don't put anything you'd be sad to lose.

Add new subdirs as needed (caches, generated fixtures, scratch outputs).
Each subdir should contain a `.gitkeep` so the empty directory survives a
fresh clone.

## Referencing from configs

MCP server configs reference paths in `.local/` via the registry's
`${BACKEND_ROOT}` substitution:

```json
{
  "args": [
    "-y", "--quiet",
    "@modelcontextprotocol/server-filesystem",
    "${BACKEND_ROOT}/.local/fs-sandbox"
  ]
}
```

## Reset

Wipe all contents while preserving the directory structure:

```bash
find backend/.local -mindepth 2 ! -name '.gitkeep' -delete
```

## Why hidden (`.`) and why one shared dir

- Hidden so it stays out of `ls` output and signals "tooling state, not source."
- Single dir avoids sprinkling `.fs-sandbox/`, `.agent-cache/`, etc. across the
  backend tree. New runtime stores get a subdir here, not a new top-level dir.
