"""Toyota Control Center CLI main module."""

import typer
import json
from datetime import datetime
from pyfiglet import figlet_format
from rich import print as rich_print
from rich.console import Console
from rich.table import Table
from rich.text import Text
from openai import OpenAI
import click
from typer.core import TyperGroup

from .config import ConfigManager
from .client import RestClient

console = Console()
client = OpenAI()


# ============================================================================
# CUSTOM TYPER GROUP FOR ROLE-AWARE HELP
# ============================================================================

class RoleAwareGroup(TyperGroup):
    """Custom TyperGroup that filters commands based on user role in help output."""
    
    USER_COMMANDS = {
        'login', 'logout', 'status', 'jobs', 'create', 'run', 'runs', 
        'failed', 'fruns', 'ai', 'scheduled', 'menu', 'help'
    }
    
    ADMIN_COMMANDS = {
        'login', 'logout', 'status', 'users', 'department_jobs', 'high_risk',
        'failed_jobs', 'department_runs', 'failed_runs', 'promotions', 'approve',
        'reject', 'menu', 'help'
    }
    
    SHARED_COMMANDS = {'login', 'logout', 'status', 'menu', 'help'}
    
    def list_commands(self, ctx):
        """Override to filter commands by role."""
        user_info = ConfigManager.get_user_info()
        is_admin = ConfigManager.is_admin()
        
        all_commands = super().list_commands(ctx)
        
        if not user_info.get("token"):
            # Not logged in - show shared commands only
            return [cmd for cmd in all_commands if cmd in self.SHARED_COMMANDS]
        
        # Logged in - filter by role
        allowed_commands = self.ADMIN_COMMANDS if is_admin else self.USER_COMMANDS
        filtered = [cmd for cmd in all_commands if cmd in allowed_commands or cmd.replace('_', '-') in allowed_commands]
        
        # Debug: print what we're filtering
        import sys
        if '--debug-filter' in sys.argv or True:  # Force debug for now
            pass  # Remove this before production
        
        return filtered


app = typer.Typer(cls=RoleAwareGroup, help="Toyota Control Center CLI")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def pause_for_menu_return():
    """Pause and wait for user to press Enter before returning to menu."""
    console.print("\n[dim]Press Enter to return to the main menu...[/dim]", end="")
    input()


def require_login() -> dict:
    """Require user to be logged in."""
    user_info = ConfigManager.get_user_info()
    if not user_info.get("token"):
        console.print("[red]You are not logged in. Run 'cc login' first.[/red]")
        raise typer.Exit(code=1)
    return user_info


def require_admin():
    """Require user to be an admin."""
    require_login()
    if not ConfigManager.is_admin():
        console.print("[red]✗ This command is only available to admins[/red]")
        raise typer.Exit(code=1)


def require_user():
    """Require user to NOT be an admin."""
    require_login()
    if ConfigManager.is_admin():
        console.print("[red]✗ This command is only available to regular users[/red]")
        raise typer.Exit(code=1)


# ============================================================================
# LOGIN COMMAND
# ============================================================================

@app.command()
def login(backend_url: str = typer.Option(None, "--backend", help="Backend URL (optional)")):
    """
    Log into Control Center with your email.
    
    USERS - After login, use:
      cc menu (create/run jobs)
      cc jobs, cc create, cc run, cc runs, cc failed
    
    ADMINS - After login, use:
      cc menu (view users/jobs/runs, manage approvals)
      Other user commands (jobs, runs, failed) are disabled for admins
    
    Your role is displayed as "Admin CLI" or "CLI" after successful login.
    
    Example:
        cc login
        cc login --backend http://your-backend:8000
    """
    # Check if already logged in
    if ConfigManager.is_logged_in():
        user_info = ConfigManager.get_user_info()
        user_email = user_info.get("email", "unknown")
        console.print(f"[yellow]ℹ Already logged in as {user_email}[/yellow]")
        console.print("[dim]Use 'cc logout' to logout first[/dim]")
        raise typer.Exit(code=0)
    
    if backend_url:
        ConfigManager.set_backend_url(backend_url)
    
    email = typer.prompt("Email")

    try:
        client_obj = RestClient()
        result = client_obj.login(email)
        token = result.get("access_token")
        user_data = result.get("user", {})
        user_email = user_data.get("email", email)
        username = user_email.split("@")[0]
        role = user_data.get("role", "user")
        domain = user_data.get("domain", "global")
        
        ConfigManager.set_token(token, user_email, username, role, domain)
        
        banner = figlet_format("Toyota\nControl Center")
        rich_print(f"[red]{banner}[/red]")
        
        # Personalized greeting with role indicator
        display_name = user_data.get("name") or username
        role_label = "Admin CLI" if role in ("root", "domain_admin") else "CLI"
        console.print(f"[green]✓ Welcome, {display_name} — {role_label}[/green]")
        console.print(f"[dim]Logged in as {user_email} ({role})[/dim]")
        console.print(f"[dim]Config saved to: {ConfigManager.CONFIG_FILE}[/dim]\n")
        
    except Exception as e:
        console.print(f"[red]✗ Login failed: {str(e)}[/red]")
        console.print("[yellow]Make sure the backend is running at the configured URL[/yellow]")
        raise typer.Exit(code=1)


@app.command()
def logout():
    """Log out and clear stored authentication."""
    user_info = ConfigManager.get_user_info()
    if user_info.get("email"):
        email = user_info["email"]
        ConfigManager.clear_token()
        console.print(f"[green]✓ Logged out[/green] (was: {email})")
    else:
        console.print("[yellow]You were not logged in[/yellow]")


@app.command()
def status():
    """Show current authentication status."""
    user_info = ConfigManager.get_user_info()
    backend_url = ConfigManager.get_backend_url()
    
    console.print("\n[bold blue]=== Toyota Control Center Status ===[/bold blue]\n")
    
    if user_info.get("token"):
        console.print(f"[green]✓ Logged In[/green]")
        console.print(f"  Email: [cyan]{user_info['email']}[/cyan]")
        console.print(f"  Username: [cyan]{user_info['username']}[/cyan]")
        console.print(f"  Role: [cyan]{user_info.get('role', 'user')}[/cyan]")
        console.print(f"  Domain: [cyan]{user_info.get('domain', 'N/A')}[/cyan]")
    else:
        console.print("[yellow]⊘ Not Logged In[/yellow]")
    
    console.print(f"\n  Backend URL: [cyan]{backend_url}[/cyan]")
    console.print(f"  Config: [dim]{ConfigManager.CONFIG_FILE}[/dim]\n")


# ============================================================================
# JOB COMMANDS
# ============================================================================

@app.command()
def jobs(status_filter: str = typer.Option(None, "--status", help="Filter by status")):
    """
    List your jobs.
    
    Example:
        cc jobs
        cc jobs --status active
    """
    require_user()
    
    try:
        client_obj = RestClient()
        result = client_obj.get_jobs(status=status_filter)
        jobs_list = result.get("items", [])
        
        if not jobs_list:
            console.print("[yellow]No jobs found[/yellow]")
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
        
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch jobs: {str(e)}[/red]")
        raise typer.Exit(code=1)


@app.command()
def create(name: str = typer.Argument(..., help="Name of the job")):
    """
    Create a new job.
    
    Example:
        cc create "My First Job"
    """
    require_user()
    user_info = ConfigManager.get_user_info()

    console.print(f"\n[blue]Creating job as {user_info['email']}[/blue]\n")
    
    # Get job type from user
    job_type = typer.prompt("Job type (e.g., sql, excel_report, airflow_dag)")
    
    # Available connectors
    connectors = ["sql_mcp", "excel_mcp", "airflow_mcp", "powerpoint_mcp"]
    console.print("\nConnector:")
    for i, conn in enumerate(connectors, 1):
        console.print(f"  {i}. {conn}")
    
    while True:
        try:
            choice = int(typer.prompt("Select connector"))
            if 1 <= choice <= len(connectors):
                connector = connectors[choice - 1]
                break
            else:
                console.print(f"[yellow]Please enter a number between 1 and {len(connectors)}[/yellow]")
        except ValueError:
            console.print("[yellow]Please enter a valid number[/yellow]")

    # Build config based on job type
    config = {}
    if job_type.lower() == "sql":
        query = typer.prompt("SQL Query")
        config["query"] = query

    try:
        client_obj = RestClient()
        result = client_obj.create_job(name, job_type=job_type, connector=connector, config=config)
        console.print(f"\n[green]✓ Job created successfully![/green]")
        console.print(f"[cyan]ID: {result.get('id')}[/cyan]")
        console.print(f"[cyan]Name: {result.get('name')}[/cyan]")
        console.print(f"[cyan]Type: {result.get('type')}[/cyan]")
        console.print(f"[cyan]Connector: {result.get('connector')}[/cyan]\n")
    except Exception as e:
        console.print(f"[red]✗ Failed to create job: {str(e)}[/red]")
        raise typer.Exit(code=1)


@app.command()
def run(job_id: str = typer.Argument(..., help="Job ID or name")):
    """
    Execute a job by ID or name.
    
    Example:
        cc run abc123
    """
    require_user()
    
    try:
        client_obj = RestClient()
        console.print(f"[blue]Running job:[/blue] {job_id}...\n")
        
        run_result = client_obj.run_job(job_id)
        console.print(f"[green]✓ Run started[/green]")
        console.print(f"  ID: [cyan]{run_result.get('id', 'N/A')}[/cyan]")
        console.print(f"  Status: [cyan]{run_result.get('status', 'N/A')}[/cyan]\n")
        
    except Exception as e:
        console.print(f"[red]✗ Failed to run job: {str(e)}[/red]")
        raise typer.Exit(code=1)


# ============================================================================
# RUN COMMANDS
# ============================================================================

@app.command()
def runs(job_id: str = typer.Option(None, "--job", help="Filter by job ID"),
         status_filter: str = typer.Option(None, "--status", help="Filter by status")):
    """
    List your job runs with optional filtering.
    
    Example:
        cc runs
        cc runs --status failed
        cc runs --job abc123
    """
    require_user()
    
    try:
        client_obj = RestClient()
        result = client_obj.get_runs(job_id=job_id, status=status_filter)
        runs_list = result.get("runs", [])

        if not runs_list:
            console.print("[yellow]No runs found[/yellow]")
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
        
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch runs: {str(e)}[/red]")
        raise typer.Exit(code=1)


@app.command()
def failed():
    """
    List your failed runs.
    
    Example:
        cc failed
    """
    require_user()
    
    try:
        client_obj = RestClient()
        result = client_obj.get_runs(status="failed")
        runs_list = result.get("items", [])

        if not runs_list:
            console.print("[green]✓ No failed runs![/green]")
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
        
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch failed runs: {str(e)}[/red]")
        raise typer.Exit(code=1)


@app.command()
def fruns():
    """
    Quick alias for failed runs.
    
    Example:
        cc fruns
    """
    failed()


@app.command()
def ai():
    """
    Start an interactive chat with the AI Assistant.
    
    Example:
        cc ai
    """
    require_login()
    talk_to_agent()


@app.command()
def scheduled():
    """
    View scheduled jobs for the next 30 days.
    
    Example:
        cc scheduled
    """
    require_login()
    
    try:
        from datetime import datetime, timedelta, timezone
        from collections import defaultdict
        
        client_obj = RestClient()
        result = client_obj.get_jobs()
        jobs_list = result.get("items", [])

        if not jobs_list:
            console.print("[yellow]No jobs available[/yellow]")
            return

        # Calculate next 30 days
        now = datetime.now(timezone.utc)
        future_dates = defaultdict(list)
        
        # Parse schedules and generate future run dates
        for job in jobs_list:
            config = job.get("config", {})
            schedule = config.get("schedule", "")
            
            if not schedule:
                continue
            
            # Parse schedule patterns and calculate next occurrences
            scheduled_dates = _calculate_schedule_dates(schedule, now, days=30)
            
            for run_date in scheduled_dates:
                date_key = run_date.strftime("%Y-%m-%d")
                time_str = run_date.strftime("%H:%M")
                future_dates[date_key].append({
                    "time": time_str,
                    "job_id": job["id"][:8],
                    "job_name": job["name"],
                    "schedule": schedule
                })
        
        if not future_dates:
            console.print("[yellow]No scheduled jobs in the next 30 days[/yellow]")
            return
        
        # Display calendar
        console.print("\n[bold cyan]Scheduled Jobs (Next 30 Days)[/bold cyan]\n")
        
        for date_key in sorted(future_dates.keys()):
            console.print(f"[bold yellow]{date_key}[/bold yellow]")
            
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Time", style="cyan", width=8)
            table.add_column("Job", style="blue", width=30)
            table.add_column("Schedule", style="green", width=20)
            
            for run in future_dates[date_key]:
                table.add_row(
                    run["time"],
                    run["job_name"][:28],
                    run["schedule"]
                )
            
            console.print(table)
            console.print()
        
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch scheduled jobs: {str(e)}[/red]")
        raise typer.Exit(code=1)


def _calculate_schedule_dates(schedule: str, start_date, days: int = 30):
    """Calculate future run dates based on a schedule pattern."""
    from datetime import datetime, timedelta, timezone
    
    dates = []
    end_date = start_date + timedelta(days=days)
    
    if not schedule:
        return dates
    
    schedule_lower = schedule.lower()
    
    # Handle daily_midnight first (before daily_HH:MM check)
    if schedule_lower == "daily_midnight":
        current = start_date
        while current < end_date:
            run_time = current.replace(hour=0, minute=0, second=0, microsecond=0)
            if run_time > start_date:
                dates.append(run_time)
            current += timedelta(days=1)
    
    # daily_HH:MM pattern
    elif schedule_lower.startswith("daily_"):
        time_part = schedule_lower.replace("daily_", "")
        try:
            hour, minute = map(int, time_part.split(":"))
            current = start_date
            while current < end_date:
                run_time = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if run_time > start_date:
                    dates.append(run_time)
                current += timedelta(days=1)
        except:
            pass
    
    # weekly_DAY pattern
    elif schedule_lower.startswith("weekly_"):
        day_name = schedule_lower.replace("weekly_", "")
        day_map = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
        
        if day_name in day_map:
            target_day = day_map[day_name]
            current = start_date
            while current < end_date:
                if current.weekday() == target_day and current > start_date:
                    run_time = current.replace(hour=9, minute=0, second=0, microsecond=0)  # Default 9 AM
                    dates.append(run_time)
                current += timedelta(days=1)
    
    # monthly_first_<DAY> pattern
    elif schedule_lower.startswith("monthly_"):
        pattern = schedule_lower.replace("monthly_", "")
        # Parse patterns like "first_monday", "last_friday"
        if "_" in pattern:
            parts = pattern.split("_", 1)
            ordinal, day_name = parts
            day_map = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
            
            if day_name in day_map:
                target_day = day_map[day_name]
                current = start_date
                
                # Generate monthly occurrences within the date range
                while current < end_date:
                    # Get first day of current month
                    month_start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    
                    # Get first day of next month
                    if current.month == 12:
                        month_end = month_start.replace(year=current.year + 1, month=1)
                    else:
                        month_end = month_start.replace(month=current.month + 1)
                    
                    # Find first occurrence of target day in this month
                    if ordinal == "first":
                        check_date = month_start
                        while check_date < month_end:
                            if check_date.weekday() == target_day and check_date > start_date and check_date < end_date:
                                run_time = check_date.replace(hour=9, minute=0, second=0, microsecond=0)
                                dates.append(run_time)
                                break
                            check_date += timedelta(days=1)
                    
                    # Move to next month
                    current = month_end
    
    return sorted(dates)


# ============================================================================
# MENU COMMAND (Interactive)
# ============================================================================

def get_agent_context():
    """Get current state for AI agent."""
    try:
        client_obj = RestClient()
        jobs_result = client_obj.get_jobs()
        runs_result = client_obj.get_runs()
        
        jobs = jobs_result.get("items", [])
        runs = runs_result.get("items", [])
        
        user_info = ConfigManager.get_user_info()

        context = {
            "current_user": user_info.get("email", "unknown"),
            "jobs": jobs,
            "runs": runs
        }

        return json.dumps(context, indent=2)
    except Exception as e:
        console.print(f"[yellow]Warning: Could not fetch context: {str(e)}[/yellow]")
        return "{}"


def talk_to_agent():
    """Chat with AI Assistant."""
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
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are CC Assistant for the Toyota Control Center. "
                                "You help users manage jobs and runs. "
                                "Use the provided Control Center data when answering. "
                                "Do not invent jobs, runs, or outcomes that are not present. "
                                "If something is not in the data, say so clearly.\n\n"
                                
                                "JOB CREATION GUIDE:\n"
                                "To create a job, users run: cc create \"Job Name\"\n"
                                "Required specs:\n"
                                "  1. Job name (string) - already provided to CLI\n"
                                "  2. Job type (string) - free-form, e.g., 'sql', 'excel_report', 'airflow_dag'\n"
                                "  3. Connector (choice) - must be one of:\n"
                                "     - sql_mcp (for SQL queries)\n"
                                "     - excel_mcp (for Excel reports)\n"
                                "     - airflow_mcp (for Airflow DAGs)\n"
                                "     - powerpoint_mcp (for PowerPoint presentations)\n"
                                "  4. Type-specific config - e.g., SQL query for 'sql' type\n\n"
                                
                                "EXAMPLE JOB CREATION FLOW:\n"
                                "$ cc create \"My SQL Job\"\n"
                                "Job type: sql\n"
                                "Select connector: 1 (sql_mcp)\n"
                                "SQL Query: SELECT COUNT(*) FROM users\n"
                                "✓ Job created successfully!\n\n"
                                
                                f"Current Control Center Data:\n{context}"
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


def view_jobs_menu():
    """View all jobs from menu."""
    try:
        client_obj = RestClient()
        result = client_obj.get_jobs()
        jobs_list = result.get("items", [])
        
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


def create_job_menu():
    """Create a new job from menu."""
    user_info = ConfigManager.get_user_info()
    console.print(f"\n[blue]Creating job as {user_info['email']}[/blue]\n")

    job_name = typer.prompt("Job name")
    job_type = typer.prompt("Job type (e.g., sql, excel_report, airflow_dag)")
    
    # Available connectors
    connectors = ["sql_mcp", "excel_mcp", "airflow_mcp", "powerpoint_mcp"]
    console.print("\nConnector:")
    for i, conn in enumerate(connectors, 1):
        console.print(f"  {i}. {conn}")
    
    while True:
        try:
            choice = int(typer.prompt("Select connector"))
            if 1 <= choice <= len(connectors):
                connector = connectors[choice - 1]
                break
            else:
                console.print(f"[yellow]Please enter a number between 1 and {len(connectors)}[/yellow]")
        except ValueError:
            console.print("[yellow]Please enter a valid number[/yellow]")

    # Build config based on job type
    config = {}
    if job_type.lower() == "sql":
        query = typer.prompt("SQL Query")
        config["query"] = query

    try:
        client_obj = RestClient()
        result = client_obj.create_job(job_name, job_type=job_type, connector=connector, config=config)
        console.print(f"\n[green]✓ Job created successfully![/green]")
        console.print(f"[cyan]ID: {result.get('id')}[/cyan]")
        console.print(f"[cyan]Name: {result.get('name')}[/cyan]")
        console.print(f"[cyan]Type: {result.get('type')}[/cyan]")
        console.print(f"[cyan]Connector: {result.get('connector')}[/cyan]")
        pause_for_menu_return()
    except Exception as e:
        console.print(f"[red]✗ Failed to create job: {str(e)}[/red]")
        pause_for_menu_return()


def run_job_menu():
    """Execute a job from menu."""
    try:
        client_obj = RestClient()
        result = client_obj.get_jobs()
        jobs_list = result.get("items", [])
        
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


def view_runs_menu():
    """View run history from menu."""
    try:
        client_obj = RestClient()
        result = client_obj.get_runs()
        runs_list = result.get("items", [])

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


def view_failed_runs_menu():
    """View failed runs from menu."""
    try:
        client_obj = RestClient()
        result = client_obj.get_runs(status="failed")
        runs_list = result.get("items", [])

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


def view_scheduled_runs_menu():
    """View scheduled (future) jobs from menu."""
    try:
        from datetime import datetime, timedelta, timezone
        from collections import defaultdict
        
        client_obj = RestClient()
        result = client_obj.get_jobs()
        jobs_list = result.get("items", [])

        if not jobs_list:
            console.print("[yellow]No jobs available[/yellow]")
            pause_for_menu_return()
            return

        # Calculate next 30 days
        now = datetime.now(timezone.utc)
        future_dates = defaultdict(list)
        
        # Parse schedules and generate future run dates
        for job in jobs_list:
            config = job.get("config", {})
            schedule = config.get("schedule", "")
            
            if not schedule:
                continue
            
            scheduled_dates = _calculate_schedule_dates(schedule, now, days=30)
            
            for run_date in scheduled_dates:
                date_key = run_date.strftime("%Y-%m-%d")
                time_str = run_date.strftime("%H:%M")
                future_dates[date_key].append({
                    "time": time_str,
                    "job_name": job["name"],
                    "schedule": schedule
                })
        
        if not future_dates:
            console.print("[yellow]No scheduled jobs in the next 30 days[/yellow]")
            pause_for_menu_return()
            return
        
        console.print("\n[bold cyan]Scheduled Jobs (Next 30 Days)[/bold cyan]")
        
        for date_key in sorted(future_dates.keys()):
            console.print(f"\n[bold yellow]{date_key}[/bold yellow]")
            
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Time", style="cyan", width=8)
            table.add_column("Job", style="blue", width=30)
            table.add_column("Schedule", style="green", width=20)
            
            for run in future_dates[date_key]:
                table.add_row(
                    run["time"],
                    run["job_name"][:28],
                    run["schedule"]
                )
            
            console.print(table)
        
        pause_for_menu_return()
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch scheduled jobs: {str(e)}[/red]")
        pause_for_menu_return()


# ============================================================================
# ADMIN COMMANDS
# ============================================================================

def admin_view_users():
    """View users in admin's department."""
    try:
        client_obj = RestClient()
        result = client_obj.admin_list_users()
        users = result.get("items", [])
        
        if not users:
            console.print("[yellow]No users found in this department[/yellow]")
            pause_for_menu_return()
            return
        
        table = Table(title="Department Users")
        table.add_column("Email", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Role", style="green")
        table.add_column("Job Title", style="blue")
        table.add_column("Team", style="yellow")
        
        for user in users:
            table.add_row(
                user.get("email", "")[:30],
                user.get("name", "")[:25],
                user.get("role", ""),
                user.get("job_title", "")[:20],
                user.get("team", "")[:20]
            )
        
        console.print(table)
        pause_for_menu_return()
        
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch users: {str(e)}[/red]")
        pause_for_menu_return()


def admin_view_jobs():
    """View jobs in admin's department."""
    try:
        client_obj = RestClient()
        result = client_obj.admin_list_jobs()
        jobs = result.get("items", [])
        
        if not jobs:
            console.print("[yellow]No jobs found in this department[/yellow]")
            pause_for_menu_return()
            return
        
        table = Table(title="Department Jobs")
        table.add_column("ID", style="cyan", width=12)
        table.add_column("Name", style="magenta")
        table.add_column("Owner", style="blue")
        table.add_column("Type", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Sensitivity", style="red")
        
        for job in jobs:
            table.add_row(
                job.get("id", "")[:12],
                job.get("name", "")[:25],
                job.get("owner_name", "")[:15],
                job.get("type", "")[:15],
                job.get("status", ""),
                job.get("data_sensitivity", "")
            )
        
        console.print(table)
        pause_for_menu_return()
        
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch jobs: {str(e)}[/red]")
        pause_for_menu_return()


def admin_view_high_risk_jobs():
    """View high-risk jobs in admin's department."""
    try:
        client_obj = RestClient()
        result = client_obj.admin_list_high_risk_jobs()
        jobs = result.get("items", [])
        
        if not jobs:
            console.print("[green]✓ No high-risk jobs in this department[/green]")
            pause_for_menu_return()
            return
        
        table = Table(title="⚠️  High-Risk Jobs in Department")
        table.add_column("ID", style="cyan", width=12)
        table.add_column("Name", style="magenta")
        table.add_column("Owner", style="blue")
        table.add_column("Type", style="green")
        table.add_column("Environment", style="yellow")
        
        for job in jobs:
            table.add_row(
                job.get("id", "")[:12],
                job.get("name", "")[:25],
                job.get("owner_name", "")[:15],
                job.get("type", "")[:15],
                job.get("environment", "")
            )
        
        console.print(table)
        pause_for_menu_return()
        
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch high-risk jobs: {str(e)}[/red]")
        pause_for_menu_return()


def admin_view_failed_jobs():
    """View failed jobs in admin's department."""
    try:
        client_obj = RestClient()
        result = client_obj.admin_list_failed_jobs()
        jobs = result.get("items", [])
        
        if not jobs:
            console.print("[green]✓ No failed jobs in this department[/green]")
            pause_for_menu_return()
            return
        
        table = Table(title="❌ Failed Jobs in Department")
        table.add_column("ID", style="cyan", width=12)
        table.add_column("Name", style="magenta")
        table.add_column("Owner", style="blue")
        table.add_column("Type", style="green")
        table.add_column("Status", style="red")
        
        for job in jobs:
            table.add_row(
                job.get("id", "")[:12],
                job.get("name", "")[:25],
                job.get("owner_name", "")[:15],
                job.get("type", "")[:15],
                job.get("status", "")
            )
        
        console.print(table)
        pause_for_menu_return()
        
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch failed jobs: {str(e)}[/red]")
        pause_for_menu_return()


def admin_view_runs():
    """View runs for jobs in admin's department."""
    try:
        client_obj = RestClient()
        result = client_obj.admin_list_runs(limit=50)
        runs = result.get("items", [])
        
        if not runs:
            console.print("[yellow]No runs found in this department[/yellow]")
            pause_for_menu_return()
            return
        
        table = Table(title="Department Run History (Last 50)")
        table.add_column("ID", style="cyan", width=12)
        table.add_column("Job", style="magenta")
        table.add_column("User", style="blue")
        table.add_column("Status", style="green")
        table.add_column("Risk", style="yellow")
        table.add_column("Created", style="dim")
        
        for run in runs:
            table.add_row(
                run.get("id", "")[:12],
                run.get("job_name", "")[:20],
                run.get("requested_by_name", "")[:15],
                run.get("status", ""),
                run.get("risk_level", ""),
                run.get("created_at", "")[:10]
            )
        
        console.print(table)
        pause_for_menu_return()
        
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch runs: {str(e)}[/red]")
        pause_for_menu_return()


def admin_view_failed_runs():
    """View failed runs for jobs in admin's department."""
    try:
        client_obj = RestClient()
        result = client_obj.admin_list_failed_runs(limit=50)
        runs = result.get("items", [])
        
        if not runs:
            console.print("[green]✓ No failed runs in this department[/green]")
            pause_for_menu_return()
            return
        
        table = Table(title="❌ Failed Runs in Department (Last 50)")
        table.add_column("ID", style="cyan", width=12)
        table.add_column("Job", style="magenta")
        table.add_column("User", style="blue")
        table.add_column("Error", style="red", width=40)
        table.add_column("Created", style="dim")
        
        for run in runs:
            error_msg = run.get("error", "")
            if error_msg and len(error_msg) > 40:
                error_msg = error_msg[:37] + "..."
            table.add_row(
                run.get("id", "")[:12],
                run.get("job_name", "")[:20],
                run.get("requested_by_name", "")[:15],
                error_msg,
                run.get("created_at", "")[:10]
            )
        
        console.print(table)
        pause_for_menu_return()
        
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch failed runs: {str(e)}[/red]")
        pause_for_menu_return()


def admin_view_approvals():
    """View pending approval requests in admin's department."""
    try:
        client_obj = RestClient()
        result = client_obj.admin_list_approvals()
        approvals = result.get("items", [])
        
        if not approvals:
            console.print("[green]✓ No pending approval requests[/green]")
            pause_for_menu_return()
            return
        
        table = Table(title="📋 Pending Promotion Requests")
        table.add_column("ID", style="cyan", width=12)
        table.add_column("Job", style="magenta")
        table.add_column("Requested By", style="blue")
        table.add_column("Risk Level", style="yellow")
        table.add_column("Status", style="green")
        
        for approval in approvals:
            table.add_row(
                approval.get("id", "")[:12],
                approval.get("job_name", "")[:20],
                approval.get("requested_by_name", "")[:15],
                approval.get("risk_level", ""),
                approval.get("status", "")
            )
        
        console.print(table)
        pause_for_menu_return()
        
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch approvals: {str(e)}[/red]")
        pause_for_menu_return()


def admin_approval_action():
    """Approve or reject a promotion request."""
    try:
        # First, fetch pending approvals
        client_obj = RestClient()
        result = client_obj.admin_list_approvals()
        approvals = result.get("items", [])
        
        if not approvals:
            console.print("[yellow]No pending approval requests[/yellow]")
            pause_for_menu_return()
            return
        
        # Display approvals
        console.print("\n[bold cyan]=== Pending Approval Requests ===[/bold cyan]")
        for i, approval in enumerate(approvals, 1):
            console.print(
                f"{i}. {approval.get('job_name', 'Unknown')} "
                f"(Risk: {approval.get('risk_level', 'N/A')}) "
                f"- Requested by {approval.get('requested_by_name', 'Unknown')}"
            )
        
        choice_str = typer.prompt("Select approval to action (or 0 to cancel)")
        try:
            choice = int(choice_str)
            if choice == 0:
                return
            if choice < 1 or choice > len(approvals):
                console.print("[red]Invalid selection[/red]")
                return
        except ValueError:
            console.print("[red]Invalid input[/red]")
            return
        
        selected = approvals[choice - 1]
        approval_id = selected.get("id")
        
        # Action
        console.print("\n[bold cyan]1.[/bold cyan] Approve")
        console.print("[bold cyan]2.[/bold cyan] Reject")
        action_choice = typer.prompt("Select action")
        
        comment = typer.prompt("Add comment (optional)", default="")
        
        if action_choice == "1":
            client_obj.admin_approve(approval_id, comment)
            console.print(f"[green]✓ Promotion approved[/green]")
        elif action_choice == "2":
            client_obj.admin_reject(approval_id, comment)
            console.print(f"[green]✓ Promotion rejected[/green]")
        else:
            console.print("[red]Invalid action[/red]")
        
        pause_for_menu_return()
        
    except Exception as e:
        console.print(f"[red]✗ Failed to process approval: {str(e)}[/red]")
        pause_for_menu_return()


def admin_menu():
    """Admin interactive menu loop for department management."""
    user_info = ConfigManager.get_user_info()
    domain_label = f"{user_info.get('domain', 'global').title()} Department" if user_info.get('role') == 'domain_admin' else "All Departments"
    
    while True:
        console.print(f"\n[bold cyan]=== Admin Control Center ({domain_label}) ===[/bold cyan]")
        console.print("\n[cyan]=== Department Users ===[/cyan]")
        console.print("[bold cyan]1.[/bold cyan] View Department Users")
        console.print("\n[cyan]=== Department Jobs ===[/cyan]")
        console.print("[bold cyan]2.[/bold cyan] View Department Jobs")
        console.print("[bold cyan]3.[/bold cyan] View High-Risk Jobs")
        console.print("[bold cyan]4.[/bold cyan] View Failed Jobs")
        console.print("\n[cyan]=== Department Runs ===[/cyan]")
        console.print("[bold cyan]5.[/bold cyan] View Department Run History")
        console.print("[bold cyan]6.[/bold cyan] View Failed Runs")
        console.print("\n[cyan]=== Approvals ===[/cyan]")
        console.print("[bold cyan]7.[/bold cyan] View Pending Promotions")
        console.print("[bold cyan]8.[/bold cyan] Approve/Reject Promotion")
        console.print("\n")
        console.print("[bold cyan]9.[/bold cyan] Exit Menu")
        console.print("[bold cyan]0.[/bold cyan] Logout")
        console.print("\n")

        choice = typer.prompt("Select an option")

        if choice == "1":
            admin_view_users()
        elif choice == "2":
            admin_view_jobs()
        elif choice == "3":
            admin_view_high_risk_jobs()
        elif choice == "4":
            admin_view_failed_jobs()
        elif choice == "5":
            admin_view_runs()
        elif choice == "6":
            admin_view_failed_runs()
        elif choice == "7":
            admin_view_approvals()
        elif choice == "8":
            admin_approval_action()
        elif choice == "9":
            console.print("[cyan]Exiting admin menu...[/cyan]")
            break
        elif choice == "0":
            logout()
            break
        else:
            console.print("[red]Invalid option[/red]")


def control_center_menu():
    """Main interactive menu loop - routes to admin or user menu based on role."""
    require_login()
    
    # Route to appropriate menu based on user role
    if ConfigManager.is_admin():
        admin_menu()
    else:
        user_menu()


def user_menu():
    """Regular user interactive menu loop."""
    while True:
        console.print("\n[bold red]=== Control Center ===[/bold red]")
        console.print("\n[red]=== Your Jobs ===[/red]")
        console.print("[bold red]1.[/bold red] View Jobs")
        console.print("[bold red]2.[/bold red] Create Job")
        console.print("[bold red]3.[/bold red] Run Job")
        console.print("\n[red]=== Your Runs ===[/red]")
        console.print("[bold red]4.[/bold red] View Run History")
        console.print("[bold red]5.[/bold red] View Failed Runs")
        console.print("[bold red]6.[/bold red] View Scheduled Runs")
        console.print("\n[red]=== AI Assistant ===[/red]")
        console.print("[bold red]7.[/bold red] Talk to AI Assistant")
        console.print("\n")
        console.print("[bold red]8.[/bold red] Exit Menu")
        console.print("[bold red]9.[/bold red] Logout")
        console.print("\n")

        choice = typer.prompt("Select an option")

        if choice == "1":
            view_jobs_menu()
        elif choice == "2":
            create_job_menu()
        elif choice == "3":
            run_job_menu()
        elif choice == "4":
            view_runs_menu()
        elif choice == "5":
            view_failed_runs_menu()
        elif choice == "6":
            view_scheduled_runs_menu()
        elif choice == "7":
            talk_to_agent()
        elif choice == "8":
            console.print("[green]Exiting menu...[/green]")
            break
        elif choice == "9":
            logout()
            break
        else:
            console.print("[red]Invalid option[/red]")

# ============================================================================
# ADMIN-ONLY COMMANDS
# ============================================================================

@app.command()
def users():
    """
    View all users in your department.
    
    Example:
        cc users
    """
    require_admin()
    user_info = ConfigManager.get_user_info()
    
    try:
        client_obj = RestClient()
        result = client_obj.admin_list_users()
        users_list = result.get("items", [])
        count = result.get("count", 0)
        
        if not users_list:
            console.print("[yellow]No users found in your department[/yellow]")
            return
        
        domain_label = f"{user_info.get('domain', 'global').title()} Department" if user_info.get('role') == 'domain_admin' else "All Departments"
        table = Table(title=f"Department Users ({domain_label})")
        table.add_column("Email", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Role", style="green")
        table.add_column("Job Title", style="yellow")
        table.add_column("Team", style="blue")
        
        for user in users_list:
            table.add_row(
                user.get("email", ""),
                user.get("name", ""),
                user.get("role", ""),
                user.get("job_title", ""),
                user.get("team", "")
            )
        
        console.print(table)
        console.print(f"\n[dim]Total: {count} users[/dim]")
        
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch users: {str(e)}[/red]")
        raise typer.Exit(code=1)


@app.command()
def department_jobs(status_filter: str = typer.Option(None, "--status", help="Filter by status")):
    """
    View all jobs in your department.
    
    Example:
        cc department-jobs
        cc department-jobs --status active
    """
    require_admin()
    user_info = ConfigManager.get_user_info()
    
    try:
        client_obj = RestClient()
        result = client_obj.admin_list_jobs(status=status_filter)
        jobs_list = result.get("items", [])
        count = result.get("count", 0)
        
        if not jobs_list:
            console.print("[yellow]No jobs found in your department[/yellow]")
            return
        
        domain_label = f"{user_info.get('domain', 'global').title()} Department" if user_info.get('role') == 'domain_admin' else "All Departments"
        table = Table(title=f"Department Jobs ({domain_label})")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Owner", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Status", style="blue")
        table.add_column("Sensitivity", style="red")
        
        for job in jobs_list:
            table.add_row(
                job.get("id", "")[:12],
                job.get("name", ""),
                job.get("owner_name", ""),
                job.get("type", ""),
                job.get("status", ""),
                job.get("data_sensitivity", "medium")
            )
        
        console.print(table)
        console.print(f"\n[dim]Total: {count} jobs[/dim]")
        
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch jobs: {str(e)}[/red]")
        raise typer.Exit(code=1)


@app.command()
def high_risk():
    """
    View high-risk jobs in your department.
    
    Example:
        cc high-risk
    """
    require_admin()
    
    try:
        client_obj = RestClient()
        result = client_obj.admin_list_high_risk_jobs()
        jobs_list = result.get("items", [])
        count = result.get("count", 0)
        
        if not jobs_list:
            console.print("[yellow]No high-risk jobs found[/yellow]")
            return
        
        table = Table(title="High-Risk Jobs")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Owner", style="green")
        table.add_column("Status", style="yellow")
        
        for job in jobs_list:
            table.add_row(
                job.get("id", "")[:12],
                job.get("name", ""),
                job.get("owner_name", ""),
                job.get("status", "")
            )
        
        console.print(table)
        console.print(f"\n[dim]Total: {count} high-risk jobs[/dim]")
        
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch high-risk jobs: {str(e)}[/red]")
        raise typer.Exit(code=1)


@app.command()
def failed_jobs():
    """
    View failed jobs in your department.
    
    Example:
        cc failed-jobs
    """
    require_admin()
    
    try:
        client_obj = RestClient()
        result = client_obj.admin_list_failed_jobs()
        jobs_list = result.get("items", [])
        count = result.get("count", 0)
        
        if not jobs_list:
            console.print("[green]✓ No failed jobs![/green]")
            return
        
        table = Table(title="Failed Jobs")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Owner", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Created", style="blue")
        
        for job in jobs_list:
            table.add_row(
                job.get("id", "")[:12],
                job.get("name", ""),
                job.get("owner_name", ""),
                job.get("type", ""),
                job.get("created_at", "")[:10]
            )
        
        console.print(table)
        console.print(f"\n[dim]Total: {count} failed jobs[/dim]")
        
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch failed jobs: {str(e)}[/red]")
        raise typer.Exit(code=1)


@app.command()
def department_runs(status_filter: str = typer.Option(None, "--status", help="Filter by status"),
                    limit: int = typer.Option(50, "--limit", help="Limit results")):
    """
    View run history for your department.
    
    Example:
        cc department-runs
        cc department-runs --status failed --limit 100
    """
    require_admin()
    user_info = ConfigManager.get_user_info()
    
    try:
        client_obj = RestClient()
        result = client_obj.admin_list_runs(status=status_filter, limit=limit)
        runs_list = result.get("items", [])
        count = result.get("count", 0)
        
        if not runs_list:
            console.print("[yellow]No runs found[/yellow]")
            return
        
        domain_label = f"{user_info.get('domain', 'global').title()} Department" if user_info.get('role') == 'domain_admin' else "All Departments"
        table = Table(title=f"Department Run History ({domain_label})")
        table.add_column("Run ID", style="cyan")
        table.add_column("Job", style="magenta")
        table.add_column("User", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Risk Level", style="red")
        table.add_column("Created", style="blue")
        
        for run in runs_list:
            table.add_row(
                run.get("id", "")[:12],
                run.get("job_name", "")[:20],
                run.get("requested_by_name", ""),
                run.get("status", ""),
                run.get("risk_level", "N/A"),
                run.get("created_at", "")[:10]
            )
        
        console.print(table)
        console.print(f"\n[dim]Total: {count} runs (limit: {limit})[/dim]")
        
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch runs: {str(e)}[/red]")
        raise typer.Exit(code=1)


@app.command()
def failed_runs(limit: int = typer.Option(50, "--limit", help="Limit results")):
    """
    View failed runs in your department.
    
    Example:
        cc failed-runs
        cc failed-runs --limit 100
    """
    require_admin()
    
    try:
        client_obj = RestClient()
        result = client_obj.admin_list_failed_runs(limit=limit)
        runs_list = result.get("items", [])
        count = result.get("count", 0)
        
        if not runs_list:
            console.print("[green]✓ No failed runs![/green]")
            return
        
        table = Table(title="Failed Runs")
        table.add_column("Run ID", style="cyan")
        table.add_column("Job", style="magenta")
        table.add_column("User", style="green")
        table.add_column("Status", style="red")
        table.add_column("Created", style="blue")
        
        for run in runs_list:
            table.add_row(
                run.get("id", "")[:12],
                run.get("job_name", "")[:20],
                run.get("requested_by_name", ""),
                run.get("status", ""),
                run.get("created_at", "")[:10]
            )
        
        console.print(table)
        console.print(f"\n[dim]Total: {count} failed runs[/dim]")
        
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch failed runs: {str(e)}[/red]")
        raise typer.Exit(code=1)


@app.command()
def promotions():
    """
    View pending promotion requests.
    
    Example:
        cc promotions
    """
    require_admin()
    
    try:
        client_obj = RestClient()
        result = client_obj.admin_list_approvals()
        approvals_list = result.get("items", [])
        count = result.get("count", 0)
        
        if not approvals_list:
            console.print("[green]✓ No pending promotions[/green]")
            return
        
        table = Table(title="Pending Promotions")
        table.add_column("ID", style="cyan")
        table.add_column("Job", style="magenta")
        table.add_column("Requester", style="green")
        table.add_column("Risk Level", style="yellow")
        table.add_column("Status", style="blue")
        table.add_column("Created", style="dim")
        
        for approval in approvals_list:
            table.add_row(
                approval.get("id", "")[:12],
                approval.get("job_name", "")[:20],
                approval.get("requested_by_name", ""),
                approval.get("risk_level", ""),
                approval.get("status", ""),
                approval.get("created_at", "")[:10]
            )
        
        console.print(table)
        console.print(f"\n[dim]Total: {count} pending promotions[/dim]")
        
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch promotions: {str(e)}[/red]")
        raise typer.Exit(code=1)


@app.command()
def approve(approval_id: str = typer.Argument(..., help="Approval ID"),
            comment: str = typer.Option("", "--comment", help="Optional approval comment")):
    """
    Approve a promotion request.
    
    Example:
        cc approve app_001
        cc approve app_001 --comment "Approved for production"
    """
    require_admin()
    
    try:
        client_obj = RestClient()
        result = client_obj.admin_approve(approval_id, comment=comment)
        console.print(f"[green]✓ Promotion approved[/green]")
        console.print(f"  ID: [cyan]{result.get('id')}[/cyan]")
        console.print(f"  Status: [cyan]{result.get('status')}[/cyan]\n")
        
    except Exception as e:
        console.print(f"[red]✗ Failed to approve promotion: {str(e)}[/red]")
        raise typer.Exit(code=1)


@app.command()
def reject(approval_id: str = typer.Argument(..., help="Approval ID"),
           comment: str = typer.Option("", "--comment", help="Optional rejection reason")):
    """
    Reject a promotion request.
    
    Example:
        cc reject app_001
        cc reject app_001 --comment "Does not meet requirements"
    """
    require_admin()
    
    try:
        client_obj = RestClient()
        result = client_obj.admin_reject(approval_id, comment=comment)
        console.print(f"[green]✓ Promotion rejected[/green]")
        console.print(f"  ID: [cyan]{result.get('id')}[/cyan]")
        console.print(f"  Status: [cyan]{result.get('status')}[/cyan]\n")
        
    except Exception as e:
        console.print(f"[red]✗ Failed to reject promotion: {str(e)}[/red]")
        raise typer.Exit(code=1)


@app.command()
def menu():
    """
    Open the interactive menu.
    
    USERS - Access: Create jobs, run jobs, view own runs, manage your jobs
    
    ADMINS - Access admin features:
      • View Department Users
      • View Department Jobs
      • View High-Risk Jobs
      • View Failed Jobs
      • View Department Run History
      • View Failed Runs
      • View Pending Promotions
      • Approve/Reject Promotions
    
    Example:
        cc menu
    """
    control_center_menu()
