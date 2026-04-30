# Toyota Control Center CLI - Quick Reference Card

## Installation (One Time)

```bash
cd /path/to/toyota-control-center
pip install -e ./cli
```

## Verify Installation

```bash
cc --help
cc status
```

---

## Authentication

```bash
# Login
cc login
# Enter email when prompted

# Check status
cc status

# Logout (clear credentials)
cc logout
```

---

## Job Management

```bash
# List all jobs
cc jobs

# List jobs filtered by status
cc jobs --status active

# Create a new job
cc create "My Job Name"

# Execute a job
cc run abc123def456
```

---

## Run Management

```bash
# List all runs
cc runs

# List failed runs
cc failed

# List runs for specific job
cc runs --job abc123

# List runs with specific status
cc runs --status failed
```

---

## Interactive Menu

```bash
cc menu
# Shows 8 options:
#   1. View Jobs
#   2. Create Job
#   3. Run Job
#   4. View Run History
#   5. View Failed Runs
#   6. Talk to AI Assistant
#   7. Exit Menu
#   8. Logout
```

---

## Configuration

### View Config
```bash
cc status
# Shows: Backend URL, login status, config file location
```

### Config File Location
```
~/.cc/config.json
```

### Use Custom Backend
```bash
# Option 1: During login
cc login --backend http://your-backend:8000

# Option 2: Environment variable
export CC_BACKEND_URL=http://your-backend:8000
cc jobs
```

---

## Global Usage

```bash
# Use from ANY directory
cd /tmp
cc jobs

cd ~/Documents
cc menu

cd /any/path
cc status
```

---

## Help

```bash
# Show all commands
cc --help

# Help for specific command
cc login --help
cc jobs --help
cc create --help
cc run --help
cc runs --help
cc menu --help
```

---

## Common Workflows

### First Time Setup
```bash
cc login              # Authenticate
cc status            # Verify setup
cc jobs              # Test it works
```

### Daily Usage
```bash
cc jobs              # See what jobs exist
cc create "New Job"  # Create a job
cc run abc123        # Execute it
cc runs              # View execution history
```

### Troubleshooting
```bash
cc status            # Check login & config
cc logout            # Clear credentials
cc login             # Re-authenticate
```

### Production Backend
```bash
# Set custom backend URL
export CC_BACKEND_URL=http://prod-backend:8000
cc login
cc jobs
```

---

## Tips

- **Global Command**: Works from any directory after `pip install -e ./cli`
- **Secure Storage**: Token stored in `~/.cc/config.json` with secure permissions
- **Environment Override**: Use `CC_BACKEND_URL` environment variable
- **Interactive Mode**: `cc menu` for a beautiful 7-option menu
- **AI Assistant**: Chat with AI in the menu (requires OPENAI_API_KEY)

---

## Contact & Support

See [README.md](cli/README.md) for full documentation.

Configuration details: [CLI_PACKAGING_GUIDE.md](CLI_PACKAGING_GUIDE.md)

Architecture details: [REFACTORING_COMPLETE.md](REFACTORING_COMPLETE.md)
