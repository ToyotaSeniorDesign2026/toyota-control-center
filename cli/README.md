# Toyota Control Center CLI

**Command-line interface for managing Toyota Control Center jobs and runs from your terminal.**

The CLI works globally from any directory after installation, with secure local configuration storage for authentication.

---

## Installation

### Using pip (Development)

Install in editable mode for development:

```bash
pip install -e ./cli
```

Or with development dependencies:

```bash
pip install -e "./cli[dev]"
```

### Using pipx (Recommended for Users)

For isolated installation without affecting your Python environment:

```bash
pipx install ./cli
```

This installs the CLI in an isolated virtual environment and makes commands available globally.

### Verify Installation

```bash
cc --help
```

You should see the main help menu with available commands.

---

## Quick Start

### 1. Login

```bash
cc login
```

You'll be prompted for:
- **Email**: Your Control Center email
- **Backend URL** (optional): If different from default `http://localhost:8000`

Your credentials are securely stored in `~/.cc/config.json` (permissions: `0600`).

### 2. Check Your Status

```bash
cc status
```

Shows your login status, username, and configured backend URL.

### 3. View Your Jobs

```bash
cc jobs
```

Lists all your jobs in a formatted table.

### 4. Create a Job

```bash
cc create "My Job Name"
```

### 5. Run a Job

```bash
cc run <job-id>
```

### 6. View Run History

```bash
cc runs                    # All runs
cc runs --status failed    # Only failed runs
cc runs --job <job-id>     # Runs for specific job
```

### 7. Open Interactive Menu

```bash
cc menu
```

Opens an interactive menu with 7 options:
1. View Jobs
2. Create Job
3. Run Job
4. View Run History
5. View Failed Runs
6. Talk to AI Assistant
7. Logout

### 8. Logout

```bash
cc logout
```

Clears your stored credentials.

---

## Available Commands

```
cc login           # Log in with your email
cc logout          # Log out and clear credentials
cc status          # Show current login status
cc jobs            # List all jobs
cc create <name>   # Create a new job
cc run <job-id>    # Execute a job
cc runs            # List all runs
cc failed          # List failed runs
cc menu            # Open interactive menu
cc --help          # Show help for all commands
```

### Command Options

```bash
# Filter jobs by status
cc jobs --status active

# Filter runs by status
cc runs --status failed

# Filter runs by job
cc runs --job abc123

# Set backend URL for this session
cc login --backend http://your-backend:8000
```

---

## Configuration

### Config File Location

```
~/.cc/config.json
```

Example:
```json
{
  "backend_url": "http://localhost:8000",
  "token": "your-access-token",
  "email": "user@example.com",
  "username": "user"
}
```

### Environment Variables

Override configuration via environment variables:

```bash
# Set custom backend URL
export CC_BACKEND_URL=http://your-backend:8000
cc jobs

# Or pass as option
cc login --backend http://your-backend:8000
```

### Security

- Config file permissions are set to `0600` (read/write for user only)
- Never commit `~/.cc/config.json` to version control
- Access tokens are stored locally for convenience during development

---

## AI Assistant

The CLI includes an AI assistant that can answer questions about your jobs and runs:

```bash
cc menu
# Then select option 6: Talk to AI Assistant
```

Or access directly via the menu. The assistant:
- Knows about your current jobs and runs
- Answers questions about your Control Center state
- Helps with job management tasks
- Uses OpenAI's GPT-4-mini model

**Setup**: Requires `OPENAI_API_KEY` environment variable:
```bash
export OPENAI_API_KEY=sk-...
cc menu
```

---

## Development

### Install with Dev Dependencies

```bash
pip install -e "./cli[dev]"
```

### Project Structure

```
cli/
├── setup.py              # Package configuration with entry points
├── README.md             # This file
├── requirements.txt      # Legacy requirements file
└── cc/                   # Main package
    ├── __init__.py       # Package init
    ├── main.py           # Entry point functions
    ├── cli.py            # CLI commands and menu
    ├── config.py         # Configuration management
    └── client.py         # REST API client
```

### Run from Source

For development without installing:

```bash
cd cli
python -m cc.cli
```

---

## Troubleshooting

### "Command not found: cc"

**Problem**: CLI not installed or not in PATH

**Solution**:
```bash
# Reinstall
pip install -e ./cli

# Or use pipx
pipx install ./cli

# Verify
which cc
```

### "You are not logged in"

**Problem**: Need to authenticate first

**Solution**:
```bash
cc login
```

### "Backend connection refused"

**Problem**: Backend server not running at configured URL

**Solution**:
```bash
# Check configured backend
cc status

# Start your backend server
cd backend
docker compose up

# Or set custom backend URL
cc login --backend http://localhost:8000
```

### "Token expired"

**Problem**: Your session token is invalid

**Solution**:
```bash
cc logout
cc login
```

### "OPENAI_API_KEY not set"

**Problem**: AI Assistant requires OpenAI key

**Solution**:
```bash
export OPENAI_API_KEY=sk-...
cc menu
```

---

## How It Works

### Local Installation

1. `setup.py` defines entry points for global commands
2. When installed (pip/pipx), creates scripts in your Python environment
3. Commands are available anywhere in your terminal

### Authentication Flow

1. `cc login` → prompts for email
2. Email sent to backend → receives access token
3. Token saved to `~/.cc/config.json` with secure permissions
4. Future commands read token from config automatically
5. Requests to backend include `Authorization: Bearer <token>` header

### Configuration Management

- `ConfigManager` class handles all config operations
- Config stored in `~/.cc/config.json` (not in repo)
- Supports environment variable overrides
- Graceful fallback to defaults

---

## Next Steps

- **Local Development**: See [backend README](../backend/README.md) for running the backend
- **Frontend**: See [frontend README](../frontend/README.md) for the web UI
- **API Documentation**: Backend exposes OpenAPI at `/docs`

---

## License

Toyota Control Center CLI - Part of the Toyota Control Center project.

### Authentication

Login with your Toyota Control Center credentials:

```bash
cc-cli login
```

You'll be prompted for your email address. The CLI will authenticate with the backend, store your access token, and cache your CLI token for future use.

### Job Management

List all jobs:
```bash
cc-cli jobs
```

Create a new job:
```bash
cc-cli create-job --name "My Job"
```

Run a job:
```bash
cc-cli run-job --job-id "job_123"
```

### Run History

View recent job runs:
```bash
cc-cli runs
```

View failed runs:
```bash
cc-cli failed-runs
```

### Promotion Management

View promotion requests:
```bash
cc-cli promotions
```

Request job promotion:
```bash
cc-cli request-promotion --job-id "job_123" --environment "prod"
```

## Configuration

The CLI stores configuration in `~/.cc/config.json` including:
- `access_token`: Bearer token for API authentication
- `cli_token`: CLI-specific token from user profile

### Environment Variables

- `CC_BACKEND_URL`: Backend API URL (default: `http://localhost:8000`)

Example:
```bash
export CC_BACKEND_URL=https://api.example.com
cc-cli jobs
```

## Development

Run tests:
```bash
pytest
```

Format code:
```bash
black cli/
```

Lint:
```bash
flake8 cli/
```

## Architecture

The CLI uses a `RestClient` class to communicate with the Toyota Control Center backend API. All job, run, and promotion data is stored in the backend database, not locally.

### Phases

- **Phase 1**: ✅ Add CLI token support to backend User model
- **Phase 2**: 🟡 Refactor CLI to use backend API (in progress)
- **Phase 3**: ⏳ Full project integration and documentation

## Troubleshooting

### "Not authenticated" error

Run `cc-cli login` to authenticate with the backend.

### "Cannot connect to backend"

Verify the backend is running:
```bash
curl http://localhost:8000/docs
```

Or set `CC_BACKEND_URL` to the correct backend URL.

## License

Proprietary - Toyota
