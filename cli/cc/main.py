"""Entry points for Toyota Control Center CLI commands."""

import sys
from .cli import app


def main():
    """Main entry point for cc command."""
    app()


def cc_login():
    """Entry point for cc login."""
    sys.argv = [sys.argv[0], "login"]
    app()


def cc_logout():
    """Entry point for cc logout."""
    sys.argv = [sys.argv[0], "logout"]
    app()


def cc_status():
    """Entry point for cc status."""
    sys.argv = [sys.argv[0], "status"]
    app()


def cc_jobs():
    """Entry point for cc jobs."""
    sys.argv = [sys.argv[0], "jobs"]
    app()


def cc_create():
    """Entry point for cc create."""
    sys.argv = [sys.argv[0], "create"]
    app()


def cc_run():
    """Entry point for cc run."""
    sys.argv = [sys.argv[0], "run"]
    app()


def cc_runs():
    """Entry point for cc runs."""
    sys.argv = [sys.argv[0], "runs"]
    app()


def cc_failed():
    """Entry point for cc failed."""
    sys.argv = [sys.argv[0], "failed"]
    app()


def cc_menu():
    """Entry point for cc menu."""
    sys.argv = [sys.argv[0], "menu"]
    app()
