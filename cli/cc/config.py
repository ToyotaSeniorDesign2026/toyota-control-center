"""Configuration management for Toyota Control Center CLI."""

import os
import json
from pathlib import Path
from typing import Optional


class ConfigManager:
    """Manages CLI configuration including auth tokens and backend URL."""
    
    CONFIG_DIR = Path.home() / ".cc"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    
    DEFAULT_BACKEND_URL = "http://localhost:8000"
    
    def __init__(self):
        self._ensure_config_dir()
    
    @classmethod
    def _ensure_config_dir(cls):
        """Create config directory if it doesn't exist."""
        cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def load_config(cls) -> dict:
        """Load configuration from file."""
        if cls.CONFIG_FILE.exists():
            try:
                with open(cls.CONFIG_FILE, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return cls._default_config()
        return cls._default_config()
    
    @classmethod
    def save_config(cls, config: dict):
        """Save configuration to file."""
        cls._ensure_config_dir()
        with open(cls.CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        # Set restrictive permissions for security
        os.chmod(cls.CONFIG_FILE, 0o600)
    
    @classmethod
    def _default_config(cls) -> dict:
        """Return default configuration."""
        return {
            "backend_url": cls.DEFAULT_BACKEND_URL,
            "token": None,
            "email": None,
            "username": None,
            "role": None,
            "domain": None,
        }
    
    @classmethod
    def get_token(cls) -> Optional[str]:
        """Get stored access token."""
        config = cls.load_config()
        return config.get("token")
    
    @classmethod
    def set_token(cls, token: str, email: str, username: str, role: str = None, domain: str = None):
        """Store access token and user info."""
        config = cls.load_config()
        config["token"] = token
        config["email"] = email
        config["username"] = username
        config["role"] = role
        config["domain"] = domain
        cls.save_config(config)
    
    @classmethod
    def get_backend_url(cls) -> str:
        """Get backend URL from config or environment."""
        url = os.getenv("CC_BACKEND_URL")
        if url:
            return url
        
        config = cls.load_config()
        return config.get("backend_url", cls.DEFAULT_BACKEND_URL)
    
    @classmethod
    def set_backend_url(cls, url: str):
        """Set backend URL."""
        config = cls.load_config()
        config["backend_url"] = url
        cls.save_config(config)
    
    @classmethod
    def clear_token(cls):
        """Clear stored token and user info (logout)."""
        config = cls.load_config()
        config["token"] = None
        config["email"] = None
        config["username"] = None
        config["role"] = None
        config["domain"] = None
        cls.save_config(config)
    
    @classmethod
    def is_logged_in(cls) -> bool:
        """Check if user is logged in."""
        return bool(cls.get_token())
    
    @classmethod
    def get_user_info(cls) -> dict:
        """Get stored user information."""
        config = cls.load_config()
        return {
            "email": config.get("email"),
            "username": config.get("username"),
            "token": config.get("token"),
            "role": config.get("role"),
            "domain": config.get("domain"),
        }
    
    @classmethod
    def is_admin(cls) -> bool:
        """Check if logged-in user is an admin."""
        config = cls.load_config()
        role = config.get("role")
        return role in ("root", "domain_admin")
