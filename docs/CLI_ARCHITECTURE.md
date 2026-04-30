# Toyota Control Center CLI - Architecture & Design

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Terminal                           │
│  $ cc login                                                     │
│  $ cc jobs                                                      │
│  $ cc menu                                                      │
└────────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────┐
        │      Entry Point in PATH                   │
        │   /opt/homebrew/bin/cc (created by pip)  │
        └─────────────────┬──────────────────────────┘
                          │
                          ▼
        ┌────────────────────────────────────────────┐
        │      Typer CLI Framework                   │
        │    (cc/cli.py - @app.command())            │
        │                                             │
        │  Commands:                                 │
        │  ├─ login()                                │
        │  ├─ logout()                               │
        │  ├─ status()                               │
        │  ├─ jobs()                                 │
        │  ├─ create()                               │
        │  ├─ run()                                  │
        │  ├─ runs()                                 │
        │  ├─ failed()                               │
        │  └─ menu()  (interactive)                  │
        └─────────────────┬──────────────────────────┘
                          │
         ┌────────────────┴───────────────────┐
         │                                    │
         ▼                                    ▼
  ┌─────────────────┐            ┌──────────────────────┐
  │  ConfigManager  │            │    RestClient        │
  │  (cc/config.py) │            │  (cc/client.py)      │
  │                 │            │                      │
  │ • Load config   │            │ • login()            │
  │ • Save config   │            │ • get_jobs()         │
  │ • Get token     │            │ • create_job()       │
  │ • Set token     │            │ • run_job()          │
  │ • Get URL       │            │ • get_runs()         │
  │ • Check login   │            │ • get_run()          │
  └────────┬────────┘            │ • ... (12+ methods)  │
           │                     └──────────┬───────────┘
           │                                │
           ▼                                ▼
  ┌─────────────────────────────────────────────────────┐
  │         ~/.cc/config.json                           │
  │                                                      │
  │  {                                                  │
  │    "backend_url": "http://localhost:8000",         │
  │    "token": "eyJhbGciOiJIUzI1NiIs...",            │
  │    "email": "user@example.com",                    │
  │    "username": "user"                              │
  │  }                                                  │
  │                                                      │
  │  Permissions: 0600 (user read/write only)          │
  └─────────────────────────────────────────────────────┘
           │
           ▼
  ┌─────────────────────────────────────────────────────┐
  │    Toyota Control Center Backend API                │
  │  http://localhost:8000                              │
  │                                                      │
  │  POST   /auth/login              (email → token)  │
  │  GET    /jobs                    (list jobs)       │
  │  POST   /jobs                    (create job)      │
  │  POST   /jobs/{id}/runs          (execute job)    │
  │  GET    /runs                    (list runs)       │
  │  ... (more endpoints)                               │
  └─────────────────────────────────────────────────────┘
```

---

## Package Structure

```
cli/
├── setup.py
│   └─> Defines entry point: cc=cc.cli:app
│   └─> Lists dependencies
│
├── cc/                          (NEW PACKAGE)
│
│   ├── __init__.py
│   │   └─> Package marker
│   │
│   ├── cli.py                   (850+ lines)
│   │   ├─> @app.command() login()
│   │   ├─> @app.command() logout()
│   │   ├─> @app.command() status()
│   │   ├─> @app.command() jobs()
│   │   ├─> @app.command() create()
│   │   ├─> @app.command() run()
│   │   ├─> @app.command() runs()
│   │   ├─> @app.command() failed()
│   │   ├─> @app.command() menu()
│   │   ├─> def control_center_menu()  (interactive loop)
│   │   ├─> def pause_for_menu_return()
│   │   ├─> def require_login()
│   │   └─> Helper functions
│   │
│   ├── config.py                (ConfigManager class)
│   │   ├─> def load_config()
│   │   ├─> def save_config()
│   │   ├─> def get_token()
│   │   ├─> def set_token()
│   │   ├─> def get_backend_url()
│   │   ├─> def set_backend_url()
│   │   ├─> def clear_token()
│   │   ├─> def is_logged_in()
│   │   └─> def get_user_info()
│   │
│   ├── client.py                (RestClient class)
│   │   ├─> def __init__()
│   │   ├─> def _get_headers()
│   │   ├─> def login()
│   │   ├─> def get_jobs()
│   │   ├─> def get_job()
│   │   ├─> def create_job()
│   │   ├─> def update_job()
│   │   ├─> def delete_job()
│   │   ├─> def run_job()
│   │   ├─> def get_runs()
│   │   └─> def get_run()
│   │
│   └── main.py                  (Entry points - DEPRECATED)
│       └─> Used by old entry points only
│
├── README.md                    (User documentation)
├── requirements.txt             (Legacy - use setup.py)
└── cc_cli.py                    (DEPRECATED - old monolithic file)
```

---

## Data Flow Diagram

### Login Flow
```
User Input        CLI Layer         Config Layer       API Layer
(email)              │                   │                  │
  │                  │                   │                  │
  ├────────> login() │                   │                  │
  │                  │                   │                  │
  │                  ├──> prompt email   │                  │
  │                  │                   │                  │
  │                  ├──> RestClient()──────────> POST /auth/login
  │                  │                   │          (email)
  │                  │                   │                  │
  │                  │                   │      Backend Returns
  │                  │                   │      {token, user}
  │                  │                   │                  │
  │                  ├────────────────────────────────────> ✓
  │                  │    (receives token)
  │                  │
  │                  ├──> ConfigManager.set_token()
  │                  │        │
  │                  │        ├─> Load existing config
  │                  │        ├─> Update token, email, username
  │                  │        └─> Save to ~/.cc/config.json (0600)
  │                  │
  ├────────────────────────────────────────────> ✓ Login Success
  │      (token now stored locally)
```

### Command Flow
```
User Input       CLI Layer        Config Layer       API Layer
$ cc jobs          │                   │                  │
  │                │                   │                  │
  ├────> jobs()    │                   │                  │
  │                │                   │                  │
  │                ├─> require_login()─┐                  │
  │                │                   ├─> Load config
  │                │                   ├─> Check if token exists
  │                │                   └─> Return user_info
  │                │                   │                  │
  │                ├─> RestClient()────────────────────> GET /jobs
  │                │    (auto-reads   (with Bearer token)
  │                │     token from config)
  │                │                   │                  │
  │                │                   │     Backend Returns
  │                │                   │     {jobs: [...]}
  │                │                   │                  │
  │                │    ✓ API Response ◄──────────────────┤
  │                │                   │                  │
  │                ├─> Format with Rich
  │                ├─> Display table
  │                │
  ├──────────────────────────────────────────────────> ✓ Display Jobs
```

### Config File Usage
```
ConfigManager
    │
    ├─> DEFAULT: ~/.cc/config.json
    │
    ├─> Create if not exists:
    │   {
    │     "backend_url": "http://localhost:8000",
    │     "token": null,
    │     "email": null,
    │     "username": null
    │   }
    │
    ├─> On login:
    │   {
    │     "backend_url": "http://localhost:8000",
    │     "token": "eyJhbGciOiJIUzI1NiIs...",
    │     "email": "user@example.com",
    │     "username": "user"
    │   }
    │
    ├─> Permissions: 0600 (user: rw, others: none)
    │
    ├─> Can override with env:
    │   CC_BACKEND_URL=http://custom:8000
    │   (Rest of config still read from file)
    │
    └─> On logout:
        {
          "backend_url": "http://localhost:8000",
          "token": null,
          "email": null,
          "username": null
        }
```

---

## Command Routing

```
$ cc --help
     │
     ▼
  Typer App (cc/cli.py)
     │
     ├─ login      └─> Login command
     ├─ logout     └─> Logout command
     ├─ status     └─> Show status
     ├─ jobs       └─> List jobs
     ├─ create     └─> Create job
     ├─ run        └─> Execute job
     ├─ runs       └─> List runs
     ├─ failed     └─> List failed runs
     └─ menu       └─> Interactive menu loop
           │
           ├─ Option 1: view_jobs_menu()
           ├─ Option 2: create_job_menu()
           ├─ Option 3: run_job_menu()
           ├─ Option 4: view_runs_menu()
           ├─ Option 5: view_failed_runs_menu()
           ├─ Option 6: talk_to_agent() (AI Assistant)
           └─ Option 7: logout()
```

---

## Module Responsibilities

### `config.py` - Configuration Management
- **Responsibility**: Store and retrieve user configuration
- **Concerns**: 
  - Token management
  - Backend URL configuration
  - User information (email, username)
- **Interface**:
  - `load_config()` - Get current config
  - `save_config()` - Persist config to disk
  - `get_token()` - Get stored token
  - `set_token()` - Store token
  - `get_backend_url()` - Get API endpoint
  - `is_logged_in()` - Check auth status
- **Data Store**: `~/.cc/config.json`

### `client.py` - REST API Client
- **Responsibility**: Communicate with backend API
- **Concerns**:
  - HTTP requests
  - Bearer token headers
  - API endpoint construction
  - Response parsing
- **Interface**:
  - 12+ API methods (login, jobs, runs, etc.)
  - Automatic token injection from config
  - Error handling with `.raise_for_status()`
- **External**: Calls backend REST API

### `cli.py` - User Interface
- **Responsibility**: Command definitions and user experience
- **Concerns**:
  - Command parsing
  - User prompts
  - Output formatting (Rich tables)
  - Interactive menu loop
  - Error messages
- **Interface**:
  - 9 Typer commands
  - Interactive menu with 7 options
  - Helper functions for menu operations
- **Dependencies**: RestClient, ConfigManager

### `main.py` - Entry Point
- **Responsibility**: Wire up entry points
- **Concerns**:
  - Create Typer app
  - Define commands
  - Handle CLI invocation
- **Interface**:
  - Simple: mostly just imports and app()
- **Deprecation Note**: Single entry point now, may be removed

---

## Dependency Graph

```
setup.py
    │
    ├─ entry_point: cc=cc.cli:app
    │
    └─ typer >= 0.12.0
    └─ rich >= 13.0.0
    └─ requests >= 2.31.0
    └─ pydantic >= 2.0.0
    └─ openai >= 1.0.0
    └─ pyfiglet >= 0.8.0

cc/cli.py
    │
    ├─ import typer                    (UI framework)
    ├─ import rich                     (formatting)
    ├─ from openai import OpenAI       (AI assistant)
    ├─ from cc.config import ConfigManager
    ├─ from cc.client import RestClient
    └─ from pyfiglet import figlet_format

cc/config.py
    │
    └─ Standard library only (os, json, pathlib)

cc/client.py
    │
    ├─ import requests
    ├─ from cc.config import ConfigManager
    └─ Standard library (typing)

cc/__init__.py
    │
    └─ Minimal imports
```

---

## Security Architecture

### Token Storage
```
HTTP Request
    │
    ├─> RestClient._get_headers()
    │       ├─> Read token from ConfigManager
    │       ├─> Build Authorization header
    │       └─> Bearer <token>
    │
    ├─> requests.get(headers=headers)
    │
    └─> Backend validates Bearer token
```

### File Permissions
```
ConfigManager.save_config()
    │
    ├─> Write config to ~/.cc/config.json
    │
    └─> os.chmod(config_file, 0o600)
            └─> User: rw- (read, write)
            └─> Group: --- (no access)
            └─> Others: --- (no access)
```

### Config File Location
```
Before (Insecure):
  ./.cc_session.json    (in repo directory)
                        (shared with other users/CI systems)

After (Secure):
  ~/.cc/config.json     (in user's home directory)
                        (only accessible to that user)
                        (not committed to version control)
```

---

## Extensibility Points

### Adding New Command
```python
# In cc/cli.py

@app.command()
def mycommand(param: str = typer.Option(..., help="...")):
    """Description of command."""
    require_login()
    
    try:
        client = RestClient()
        result = client.some_method(param)
        console.print(result)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
```

### Adding New API Method
```python
# In cc/client.py

def my_method(self, param: str) -> dict:
    """Get some data."""
    response = requests.get(
        f"{self.base_url}/endpoint/{param}",
        headers=self._get_headers()
    )
    response.raise_for_status()
    return response.json()
```

### Adding New Config Setting
```python
# In cc/config.py

@classmethod
def get_my_setting(cls) -> str:
    """Get my setting."""
    config = cls.load_config()
    return config.get("my_setting", "default_value")

@classmethod
def set_my_setting(cls, value: str):
    """Set my setting."""
    config = cls.load_config()
    config["my_setting"] = value
    cls.save_config(config)
```

---

## Installation & Entry Point Mechanism

### How `pip install -e ./cli` Works

```
setup.py
    │
    ├─ Reads: name, version, dependencies
    │
    ├─ Finds packages:
    │   └─ packages=['cc']
    │
    ├─ Reads entry_points:
    │   └─ 'cc=cc.cli:app'
    │        └─ Command name: cc
    │        └─ Module: cc.cli
    │        └─ Object: app (Typer instance)
    │
    └─ Creates wrapper script:
        └─ /opt/homebrew/bin/cc
            │
            └─> #!/usr/bin/python
                import sys
                from cc.cli import app
                sys.exit(app())
```

### Path Resolution

```
$ cc jobs
  │
  ├─> Shell looks in PATH
  │
  ├─> Finds /opt/homebrew/bin/cc
  │
  ├─> Executes wrapper script
  │
  ├─> Imports: from cc.cli import app
  │
  ├─> Calls: app(['jobs'])
  │
  └─> Typer parses command and routes to jobs()
```

---

## Performance Characteristics

### Login
- Time: ~500ms (one HTTP round trip)
- Storage: Token saved locally
- Subsequent commands: O(1) file read

### Jobs Listing
- Time: ~100-500ms (one API call)
- IO: Read token from config (negligible)
- Network: Single GET request

### Interactive Menu
- Startup: ~50ms
- Each operation: Same as direct command
- Storage: Token read per operation

### Config File Access
- Read: ~1ms (file I/O)
- Write: ~2ms (file I/O + chmod)
- Cached by OS filesystem

---

## Testing Architecture

### Unit Tests (Can Be Added)

```python
# tests/test_config.py
def test_config_save_and_load():
    ConfigManager.set_token("abc123", "user@test.com", "user")
    assert ConfigManager.get_token() == "abc123"

# tests/test_client.py
def test_rest_client_headers():
    client = RestClient(token="abc123")
    headers = client._get_headers()
    assert headers["Authorization"] == "Bearer abc123"

# tests/test_cli.py
def test_require_login():
    ConfigManager.clear_token()
    with pytest.raises(typer.Exit):
        require_login()
```

### Integration Tests (Can Be Added)

```python
# tests/test_integration.py
def test_login_and_list_jobs():
    # Mock backend or use test server
    cc login (mocked)
    jobs = cc jobs (mocked)
    assert len(jobs) > 0
```

---

## Summary

- **Modular**: Clear separation of concerns
- **Secure**: Tokens in home directory with proper permissions
- **Extensible**: Easy to add commands, API methods, config settings
- **Testable**: Each module can be tested independently
- **User-Friendly**: Global command, helpful error messages, interactive menu
- **Production-Ready**: Handles errors, validates input, provides feedback

