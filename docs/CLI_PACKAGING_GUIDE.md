# Toyota Control Center CLI - Packaging & Installation Guide

## Overview

The CLI has been completely refactored into a proper Python package that installs globally on your system. After installation, users can run `cc` commands from anywhere in their terminal.

---

## What Changed

### Before (Development-Only)
```bash
cd /repo/cli
python cc_cli.py login
python cc_cli.py jobs
```

### After (Global Installation)
```bash
# Works from ANYWHERE
cc login
cc jobs
cc create "My Job"
cc runs
cc menu
```

---

## New Package Structure

```
cli/
├── setup.py                 # Package metadata & entry points
├── requirements.txt         # Legacy reference (use pip install -e .)
├── README.md               # User documentation
├── cc_cli.py               # OLD FILE - can be removed after testing
└── cc/                     # NEW PACKAGE (replaces cc_cli.py)
    ├── __init__.py
    ├── main.py             # Entry point functions
    ├── cli.py              # All CLI commands & menu logic
    ├── config.py           # Configuration management (NEW!)
    └── client.py           # REST API client (extracted from cli.py)
```

---

## Key Improvements

### 1. **Global Installation**
- Single `pip install -e ./cli` command
- Creates `cc` command in your PATH
- Works from any directory
- No need to cd into project

### 2. **Configuration Management** (`cc/config.py`)
- Stores config in `~/.cc/config.json` (not in repo)
- Secure permissions: `0600` (read/write for user only)
- Environment variable overrides supported
- Separate backend URL, token, email, username

### 3. **Modular Architecture**
- `client.py`: Pure API client (testable, reusable)
- `config.py`: Configuration system (secure storage)
- `cli.py`: Command definitions & interactive menu
- `main.py`: Entry point wrappers

### 4. **Enhanced Commands**
```bash
cc login                          # Authenticate
cc login --backend http://...     # Custom backend URL
cc status                         # Show login status & config
cc jobs                           # List jobs
cc jobs --status active           # Filter by status
cc create "Job Name"              # Create job
cc run <job-id>                   # Execute job
cc runs                           # List all runs
cc runs --status failed           # Failed runs only
cc runs --job <job-id>            # Runs for specific job
cc failed                         # Shortcut for failed runs
cc menu                           # Interactive menu
cc logout                         # Clear credentials
```

### 5. **Secure Token Storage**
- Tokens stored in `~/.cc/config.json` (outside repo)
- File permissions: `0600` (user read/write only)
- Never committed to version control
- Environment variable can override

### 6. **User-Friendly Help**
```bash
cc --help              # Show all commands
cc login --help        # Help for login command
cc create --help       # Help for create command
```

---

## Installation Instructions

### For Development

```bash
# From repo root
pip install -e ./cli

# Verify
cc --help
```

### For Users (Using pipx - Recommended)

```bash
# Install in isolated environment
pipx install ./cli

# Verify
cc status
```

### For Users (Using pip)

```bash
# Install in your Python environment
pip install ./cli

# Verify
cc status
```

---

## Configuration

### Config File Location
```
~/.cc/config.json
```

### Example Config
```json
{
  "backend_url": "http://localhost:8000",
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "email": "user@example.com",
  "username": "user"
}
```

### Environment Variable Override
```bash
export CC_BACKEND_URL=http://production-backend:8000
cc jobs  # Uses production backend
```

---

## Usage Examples

### First Time Setup
```bash
# Login
cc login

# You'll be prompted for:
# Email: user@example.com
# Backend URL: (press Enter for default http://localhost:8000)

# Check status
cc status

# Shows: ✓ Logged In as user@example.com
#        Backend: http://localhost:8000
```

### Daily Workflow
```bash
# List your jobs
cc jobs

# Create a new job
cc create "Data Processing"

# Run a job
cc run abc123

# Check recent runs
cc runs

# See failed runs
cc failed

# Open interactive menu
cc menu
```

### Connect to Custom Backend
```bash
# During login
cc login --backend http://your-backend:8000

# Or after login
export CC_BACKEND_URL=http://your-backend:8000
cc status  # Will show new backend URL
```

---

## Code Organization

### `cc/cli.py` - Command Definitions

All Typer commands live here:
- `login()` - Authenticate with email
- `logout()` - Clear credentials
- `status()` - Show auth status
- `jobs()` - List jobs
- `create()` - Create job
- `run()` - Execute job
- `runs()` - List runs
- `failed()` - List failed runs
- `menu()` - Interactive menu loop

### `cc/config.py` - Configuration Manager

```python
from cc.config import ConfigManager

# Load config
config = ConfigManager.load_config()

# Get/set token
token = ConfigManager.get_token()
ConfigManager.set_token(token, email, username)

# Get/set backend URL
url = ConfigManager.get_backend_url()
ConfigManager.set_backend_url(url)

# Check login status
if ConfigManager.is_logged_in():
    print("Logged in")
else:
    print("Not logged in")

# Clear token (logout)
ConfigManager.clear_token()
```

### `cc/client.py` - REST API Client

```python
from cc.client import RestClient

# Create client (uses stored token automatically)
client = RestClient()

# Or with specific token
client = RestClient(token="abc123")

# Make API calls
jobs = client.get_jobs()
job = client.create_job("My Job")
run = client.run_job(job_id)
runs = client.get_runs(status="failed")
```

---

## Testing the Installation

### Test 1: Command in Different Directory
```bash
cd /tmp
cc status
# Should work without errors
```

### Test 2: Login Flow
```bash
cc login
# Enter any email (backend will accept it)
# Check ~/.cc/config.json was created
ls -la ~/.cc/config.json
```

### Test 3: Commands
```bash
cc jobs
cc status
cc failed
cc menu  # Interactive menu
```

### Test 4: Help System
```bash
cc --help
cc login --help
cc create --help
```

---

## Migration from Old CLI

### Remove Old Entry Point (if needed)
```bash
# If cc-cli command still exists from old setup
pip uninstall toyota-control-center-cli --yes
pip install -e ./cli
```

### Old vs New Commands
| Old | New |
|-----|-----|
| `python cc_cli.py login` | `cc login` |
| `python cc_cli.py jobs` | `cc jobs` |
| `cd repo && python cc_cli.py` | `cc menu` |

### Old Session File
```bash
# Session saved in .cc_session.json in old CLI directory
# New CLI uses ~/.cc/config.json in home directory
# Both can coexist (old one will be ignored)
```

---

## Dependencies

### Production
- `typer>=0.12.0` - CLI framework
- `rich>=13.0.0` - Pretty output
- `requests>=2.31.0` - HTTP client
- `pydantic>=2.0.0` - Data validation
- `openai>=1.0.0` - AI assistant
- `pyfiglet>=0.8.0` - ASCII banners

### Development
- `pytest>=7.0.0` - Testing
- `black>=23.0.0` - Code formatting
- `flake8>=6.0.0` - Linting

---

## Troubleshooting

### "command not found: cc"

**Problem**: Package not installed

**Solution**:
```bash
cd /repo/cli
pip install -e .
which cc  # Verify
```

### "You are not logged in"

**Problem**: Need to authenticate

**Solution**:
```bash
cc login
# Or check status
cc status
```

### Config File Issues

**Problem**: Config corrupted or missing

**Solution**:
```bash
# See current config
cc status

# Clear and re-login
rm ~/.cc/config.json
cc login
```

### Backend Connection Failed

**Problem**: Backend not running

**Solution**:
```bash
# Check backend URL
cc status

# Start backend
cd backend && docker compose up

# Try again
cc jobs
```

---

## Next Steps

1. **Install**: `pip install -e ./cli`
2. **Login**: `cc login`
3. **Explore**: `cc --help`
4. **Use**: `cc menu` for interactive mode
5. **Integrate**: Backend + CLI working together

---

## Files to Delete (After Testing)

Once you confirm the new package works, you can remove the old CLI file:

```bash
# This file is replaced by the cc/ package
rm cli/cc_cli.py

# Optionally: Old __init__.py and requirements.txt (setup.py is still needed)
# rm cli/__init__.py
```

But keep them for now if you want to fall back to the old version during testing.

---

## Architecture Decision: pip vs npm

### Why pip (not npm)?
1. **Python native** - CLI written in pure Python
2. **No Node.js dependency** - Lighter install footprint
3. **Virtual environment support** - Using pipx for isolation
4. **Conda compatible** - Works with conda environments
5. **Easier for Python developers** - Familiar package manager

### npm Alternative (not recommended)
- Would require Node.js as a dependency
- Extra complexity for Python developers
- Slower installation
- Less natural for Python code

---

## Summary

✅ **Global Installation**: `pip install -e ./cli` creates `cc` command
✅ **Secure Config**: Tokens stored in `~/.cc/config.json` (0600 perms)
✅ **Modular Code**: Separated concerns (cli, config, client)
✅ **User-Friendly**: Help text, status checks, error messages
✅ **Backward Compatible**: Old cc_cli.py still works during transition
✅ **Production Ready**: Can be installed on user machines easily

---

## For Package Distribution

To publish to PyPI (future):

```bash
# Build
python -m build

# Upload to PyPI
twine upload dist/*

# Then users can install with:
pip install toyota-control-center-cli
# or
pipx install toyota-control-center-cli
```
