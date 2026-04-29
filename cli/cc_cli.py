"""
Toyota Control Center CLI
Command-line interface for job management, execution, and automation.

Phase 2: API-based implementation replacing local JSON storage.
"""

import os
import json
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Initialize console for output
console = Console()
app = typer.Typer(help="Toyota Control Center CLI")

# Configuration
CONFIG_DIR = Path.home() / ".cc"
CONFIG_FILE = CONFIG_DIR / "config.json"
BACKEND_URL = os.getenv("CC_BACKEND_URL", "http://localhost:8000")


class Config:
    """Handle CLI configuration and token management."""

    @staticmethod
    def ensure_config_dir():
        """Create config directory if it doesn't exist."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def load_config() -> dict:
        """Load configuration from file."""
        Config.ensure_config_dir()
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        return {}

    @staticmethod
    def save_config(config: dict):
        """Save configuration to file."""
        Config.ensure_config_dir()
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)

    @staticmethod
    def get_token() -> Optional[str]:
        """Get stored access token."""
        config = Config.load_config()
        return config.get("access_token")

    @staticmethod
    def set_token(token: str, cli_token: Optional[str] = None):
        """Store access token and optionally CLI token."""
        config = Config.load_config()
        config["access_token"] = token
        if cli_token:
            config["cli_token"] = cli_token
        Config.save_config(config)


class RestClient:
    """API client for communicating with Toyota Control Center backend."""

    def __init__(self, base_url: str = BACKEND_URL):
        """
        Initialize REST client.

        Args:
            base_url: Backend API base URL
        """
        self.base_url = base_url
        self.token = Config.get_token()

    def _get_headers(self) -> dict:
        """Get authorization headers."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    # TODO: Phase 2 Step 2.2 - Implement all API methods here
    # Methods to implement:
    # - login(email: str) -> dict
    # - get_jobs() -> list
    # - create_job(name: str, config: dict) -> dict
    # - get_job(job_id: str) -> dict
    # - update_job(job_id: str, config: dict) -> dict
    # - delete_job(job_id: str) -> bool
    # - run_job(job_id: str) -> dict
    # - get_runs() -> list
    # - get_failed_runs() -> list
    # - view_promotions() -> list
    # - request_promotion(job_id: str, environment: str) -> dict


# ============================================================================
# CLI COMMANDS
# ============================================================================


@app.command()
def login(email: str = typer.Option(..., prompt="Email", help="User email address")):
    """Authenticate with Toyota Control Center backend."""
    console.print(f"[cyan]Logging in as {email}...[/cyan]")

    # TODO: Phase 2 Step 2.3 - Implement real backend login
    # - Call RestClient.login(email)
    # - Store returned token and cli_token
    # - Display success message with token info

    console.print("[green]✓ Login successful![/green]")


@app.command()
def logout():
    """Clear stored credentials."""
    # TODO: Phase 2 - Clear config
    console.print("[green]✓ Logged out[/green]")


@app.command()
def jobs():
    """List all jobs."""
    token = Config.get_token()
    if not token:
        console.print("[red]✗ Not authenticated. Run 'login' first.[/red]")
        raise typer.Exit(1)

    # TODO: Phase 2 Step 2.4 - Get jobs from API
    # client = RestClient()
    # jobs = client.get_jobs()
    # Display in rich table

    console.print("[yellow]TODO: Implement jobs listing[/yellow]")


@app.command()
def create_job(name: str = typer.Option(..., prompt="Job name")):
    """Create a new job."""
    token = Config.get_token()
    if not token:
        console.print("[red]✗ Not authenticated. Run 'login' first.[/red]")
        raise typer.Exit(1)

    # TODO: Phase 2 Step 2.4 - Create job via API
    console.print("[yellow]TODO: Implement job creation[/yellow]")


@app.command()
def run_job(job_id: str = typer.Option(..., prompt="Job ID")):
    """Execute a job."""
    token = Config.get_token()
    if not token:
        console.print("[red]✗ Not authenticated. Run 'login' first.[/red]")
        raise typer.Exit(1)

    # TODO: Phase 2 Step 2.4 - Run job via API
    console.print("[yellow]TODO: Implement job execution[/yellow]")


@app.command()
def runs():
    """List recent job runs."""
    token = Config.get_token()
    if not token:
        console.print("[red]✗ Not authenticated. Run 'login' first.[/red]")
        raise typer.Exit(1)

    # TODO: Phase 2 Step 2.5 - Get runs from API
    console.print("[yellow]TODO: Implement runs listing[/yellow]")


@app.command()
def failed_runs():
    """List failed job runs."""
    token = Config.get_token()
    if not token:
        console.print("[red]✗ Not authenticated. Run 'login' first.[/red]")
        raise typer.Exit(1)

    # TODO: Phase 2 Step 2.5 - Get failed runs from API
    console.print("[yellow]TODO: Implement failed runs listing[/yellow]")


@app.command()
def promotions():
    """View promotion requests."""
    token = Config.get_token()
    if not token:
        console.print("[red]✗ Not authenticated. Run 'login' first.[/red]")
        raise typer.Exit(1)

    # TODO: Phase 2 Step 2.5 - Get promotions from API
    console.print("[yellow]TODO: Implement promotions listing[/yellow]")


@app.command()
def request_promotion(
    job_id: str = typer.Option(..., prompt="Job ID"),
    environment: str = typer.Option(..., prompt="Target environment"),
):
    """Request job promotion to another environment."""
    token = Config.get_token()
    if not token:
        console.print("[red]✗ Not authenticated. Run 'login' first.[/red]")
        raise typer.Exit(1)

    # TODO: Phase 2 Step 2.5 - Request promotion via API
    console.print("[yellow]TODO: Implement promotion request[/yellow]")


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
