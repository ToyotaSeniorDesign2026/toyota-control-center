#!/usr/bin/env python3

import typer
import json
import os
import pyfiglet
import openai
import random
import requests
from getpass import getpass
from rich import print as rich_print
from pyfiglet import figlet_format
from rich.console import Console
from rich.table import Table
from datetime import datetime
from openai import OpenAI

client = OpenAI()

app = typer.Typer()
job_app = typer.Typer()
app.add_typer(job_app, name="job")

SESSION_FILE = ".cc_session.json"
BACKEND_URL = os.getenv("CC_BACKEND_URL", "http://localhost:8000")

console = Console()


# ============================================================================
# REST CLIENT - BACKEND API INTEGRATION
# ============================================================================

class RestClient:
    """API client for communicating with Toyota Control Center backend."""

    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url
        self.token = load_session().get("token") if load_session() else None

    def _get_headers(self) -> dict:
        """Get authorization headers."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def login(self, email: str) -> dict:
        """Login with email and get access token."""
        response = requests.post(
            f"{self.base_url}/auth/login",
            json={"email": email},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()

    def get_jobs(self, q: str = None, status: str = None, page: int = 1, page_size: int = 50) -> dict:
        """List all jobs with optional filtering."""
        params = {"page": page, "page_size": page_size}
        if q:
            params["q"] = q
        if status:
            params["status"] = status
        
        response = requests.get(
            f"{self.base_url}/jobs",
            params=params,
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def get_job(self, job_id: str) -> dict:
        """Get a specific job by ID."""
        response = requests.get(
            f"{self.base_url}/jobs/{job_id}",
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def create_job(self, name: str, config: dict = None) -> dict:
        """Create a new job."""
        payload = {"name": name}
        if config:
            payload.update(config)
        
        response = requests.post(
            f"{self.base_url}/jobs",
            json=payload,
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def update_job(self, job_id: str, config: dict) -> dict:
        """Update an existing job."""
        response = requests.patch(
            f"{self.base_url}/jobs/{job_id}",
            json=config,
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        response = requests.delete(
            f"{self.base_url}/jobs/{job_id}",
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.status_code == 204

    def run_job(self, job_id: str, action: str = "default", params: dict = None) -> dict:
        """Execute a job."""
        payload = {"action": action}
        if params:
            payload["params"] = params
        
        response = requests.post(
            f"{self.base_url}/jobs/{job_id}/runs",
            json=payload,
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def get_runs(self, job_id: str = None, status: str = None, limit: int = 200) -> dict:
        """List job runs with optional filtering."""
        params = {"limit": limit}
        if job_id:
            params["job_id"] = job_id
        if status:
            params["status"] = status
        
        response = requests.get(
            f"{self.base_url}/runs",
            params=params,
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def get_run(self, run_id: str) -> dict:
        """Get a specific run by ID."""
        response = requests.get(
            f"{self.base_url}/runs/{run_id}",
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def pause_for_menu_return():
    """Pause and wait for user to press Enter before returning to menu."""
    console.print("\n[dim]Press Enter to return to the main menu...[/dim]", end="")
    input()


def save_session(data):
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f)


def load_session():
    if not os.path.exists(SESSION_FILE):
        return None
    with open(SESSION_FILE, "r") as f:
        return json.load(f)


def require_login():
    session = load_session()
    if not session:
        console.print("[red]You are not logged in. Run 'cc login' first.[/red]")
        raise typer.Exit()
    return session


# ============================================================================
# LOGIN COMMAND
# ============================================================================

@app.command()
def login():
    """
    Log into Control Center
    """
    email = typer.prompt("Email")

    try:
        client_obj = RestClient()
        result = client_obj.login(email)
        token = result.get("access_token")
        user_email = result.get("user", {}).get("email", email)
        
        session = {
            "email": user_email,
            "token": token,
            "username": user_email.split("@")[0]
        }
        save_session(session)
        
        banner2 = figlet_format("               Toyota \n Control Center")
        rich_print(f"[red]{banner2}[/red]")
        console.print(f"[green]✓ Logged in as {user_email}[/green]\n")
        
        control_center_menu(session)    
    except Exception as e:
        console.print(f"[red]Login failed: {str(e)}[/red]")
        console.print("[yellow]Make sure the backend is running at http://localhost:8000[/yellow]")


# ============================================================================
# MAIN MENU
# ============================================================================

def control_center_menu(session):
    """Main control center loop"""

    while True:
        console.print("\n[bold red]=== Control Center ===[/bold red]")
        console.print("\n[red]=== Your Jobs ===[/red]")
        console.print("[bold red]1.[/bold red] View Jobs")
        console.print("[bold red]2.[/bold red] Create Job")
        console.print("[bold red]3.[/bold red] Run Job")
        console.print("\n[red]=== Your Runs ===[/red]")
        console.print("[bold red]4.[/bold red] View Run History")
        console.print("[bold red]5.[/bold red] View Failed Runs")
        console.print("\n[red]=== AI Assistant ===[/red]")
        console.print("[bold red]6.[/bold red] Talk to AI Assistant")
        console.print("\n")
        console.print("[bold red]7.[/bold red] Logout")
        console.print("\n")

        choice = typer.prompt("Select an option")

        if choice == "1":
            view_jobs()

        elif choice == "2":
            create_job()

        elif choice == "3":
            run_job()

        elif choice == "4":
            view_runs()

        elif choice == "5":
            view_failed_runs()

        elif choice == "6":
            talk_to_agent()

        elif choice == "7":
            logout()
            break

        else:
            console.print("[red]Invalid option[/red]")


# ============================================================================
# JOB MANAGEMENT
# ============================================================================

def view_jobs():
    """View all jobs from backend"""
    session = require_login()
    
    try:
        client_obj = RestClient()
        result = client_obj.get_jobs()
        jobs_list = result.get("jobs", [])
        
        if not jobs_list:
            console.print("[yellow]No jobs found[/yellow]")
            pause_for_menu_return()
            return
        
        table = Table(title="Your Jobs")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Created", style="blue")
        
        for job in jobs_list:
            table.add_row(
                job.get("id", "")[:12],
                job.get("name", ""),
                job.get("status", ""),
                job.get("created_at", "")[:10]
            )
        
        console.print(table)
        pause_for_menu_return()
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch jobs: {str(e)}[/red]")
        pause_for_menu_return()


def create_job():
    """Create a new job"""
    session = require_login()

    console.print(f"\n[blue]Creating job as {session['email']}[/blue]\n")

    job_name = typer.prompt("Job name")

    try:
        client_obj = RestClient()
        result = client_obj.create_job(job_name)
        console.print(f"\n[green]✓ Job created successfully![/green]")
        console.print(f"[cyan]ID: {result.get('id')}[/cyan]")
        console.print(f"[cyan]Name: {result.get('name')}[/cyan]")
        pause_for_menu_return()
    except Exception as e:
        console.print(f"[red]✗ Failed to create job: {str(e)}[/red]")
        pause_for_menu_return()


def run_job():
    """Execute a job"""
    session = require_login()
    
    try:
        client_obj = RestClient()
        result = client_obj.get_jobs()
        jobs_list = result.get("jobs", [])
        
        if not jobs_list:
            console.print("[yellow]No jobs available to run[/yellow]")
            pause_for_menu_return()
            return

        console.print("\n[bold]Select a job to run:[/bold]")

        for i, job in enumerate(jobs_list):
            console.print(f"{i+1}. {job['id'][:8]} | {job['name']}")

        choice = typer.prompt("Enter number")

        try:
            index = int(choice) - 1
            selected_job = jobs_list[index]
        except:
            console.print("[red]Invalid selection[/red]")
            pause_for_menu_return()
            return

        console.print(f"\n[blue]Running job:[/blue] {selected_job['name']}...")

        run_result = client_obj.run_job(selected_job["id"])
        console.print(f"[green]✓ Run started:[/green] {run_result.get('id', 'N/A')}")
        console.print(f"[cyan]Status: {run_result.get('status', 'N/A')}[/cyan]")
        pause_for_menu_return()
        
    except Exception as e:
        console.print(f"[red]✗ Failed to run job: {str(e)}[/red]")
        pause_for_menu_return()


# ============================================================================
# RUN MANAGEMENT
# ============================================================================

def view_runs():
    """View run history"""
    session = require_login()
    
    try:
        client_obj = RestClient()
        result = client_obj.get_runs()
        runs_list = result.get("runs", [])

        if not runs_list:
            console.print("[yellow]No runs yet[/yellow]")
            pause_for_menu_return()
            return

        table = Table(title="Run History")
        table.add_column("Run ID", style="cyan")
        table.add_column("Job ID", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Created", style="yellow")

        for run in runs_list:
            table.add_row(
                run["id"][:8],
                run.get("job_id", "")[:8],
                run["status"],
                run.get("created_at", "")[:10]
            )

        console.print(table)
        pause_for_menu_return()
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch runs: {str(e)}[/red]")
        pause_for_menu_return()


def view_failed_runs():
    """View failed runs"""
    session = require_login()
    
    try:
        client_obj = RestClient()
        result = client_obj.get_runs(status="failed")
        runs_list = result.get("runs", [])

        if not runs_list:
            console.print("[green]✓ No failed runs![/green]")
            pause_for_menu_return()
            return

        table = Table(title="Failed Runs")
        table.add_column("Run ID", style="cyan")
        table.add_column("Job ID", style="magenta")
        table.add_column("Status", style="red")
        table.add_column("Created", style="yellow")

        for run in runs_list:
            table.add_row(
                run["id"][:8],
                run.get("job_id", "")[:8],
                run["status"],
                run.get("created_at", "")[:10]
            )

        console.print(table)
        pause_for_menu_return()
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch failed runs: {str(e)}[/red]")
        pause_for_menu_return()


# ============================================================================
# AI ASSISTANT
# ============================================================================

def get_agent_context():
    """Get current state for AI agent"""
    session = load_session()
    
    try:
        client_obj = RestClient()
        jobs_result = client_obj.get_jobs()
        runs_result = client_obj.get_runs()
        
        jobs = jobs_result.get("jobs", [])
        runs = runs_result.get("runs", [])
        
        username = session["email"] if session else "unknown"

        context = {
            "current_user": username,
            "jobs": jobs,
            "runs": runs
        }

        return json.dumps(context, indent=2)
    except Exception as e:
        console.print(f"[yellow]Warning: Could not fetch context: {str(e)}[/yellow]")
        return "{}"


def talk_to_agent():
    """Chat with AI Assistant"""
    console.print("\n[bold green]CC Assistant[/bold green]")
    console.print("[dim]You can ask me things about your jobs and runs.[/dim]\n")
    console.print("[bold]Try things like:[/bold]")
    console.print("• What jobs do I have?")
    console.print("• Which jobs have run recently?")
    console.print("• Show me failed runs")
    console.print("• What's the status of run X?\n")
    console.print("[yellow]Type 'exit', 'quit', 'back', or press Ctrl+C to return.[/yellow]\n")

    while True:
        try:
            user_input = typer.prompt("You")

            if user_input.lower() in ["exit", "quit", "back"]:
                console.print("[yellow]Leaving AI Assistant chat...[/yellow]")
                pause_for_menu_return()
                return

            try:
                context = get_agent_context()
                
                response = client.messages.create(
                    model="gpt-4-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are CC Assistant for the Toyota Control Center. "
                                "You help users manage jobs and runs. "
                                "Use the provided Control Center data when answering. "
                                "Do not invent jobs, runs, or outcomes that are not present. "
                                "If something is not in the data, say so clearly."
                                f"\n\nCurrent Control Center Data:\n{context}"
                            ),
                        },
                        {
                            "role": "user",
                            "content": user_input,
                        },
                    ],
                )

                reply = response.choices[0].message.content
                console.print(f"\n[bold magenta]Agent:[/bold magenta] {reply}\n")

            except Exception as e:
                console.print(f"[red]Agent error:[/red] {e}")

        except KeyboardInterrupt:
            console.print("\n[yellow]Leaving AI Assistant chat...[/yellow]")
            pause_for_menu_return()
            return


# ============================================================================
# LOGOUT
# ============================================================================

@app.command()
def logout():
    """
    Log out
    """
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
        console.print("[yellow]Logged out[/yellow]")
    else:
        console.print("[red]No active session[/red]")


# ============================================================================
# RUN APP
# ============================================================================

if __name__ == "__main__":
    app()
