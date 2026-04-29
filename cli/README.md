# Toyota Control Center CLI

Command-line interface for Toyota Control Center job management and automation.

## Installation

Install the CLI as an editable package:

```bash
pip install -e ./cli
```

Or install with development dependencies:

```bash
pip install -e "./cli[dev]"
```

## Usage

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
