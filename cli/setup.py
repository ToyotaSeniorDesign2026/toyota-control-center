"""Setup configuration for Toyota Control Center CLI package."""

from setuptools import setup, find_packages

setup(
    name="toyota-control-center-cli",
    version="0.1.0",
    description="Command-line interface for Toyota Control Center job management",
    author="Toyota",
    python_requires=">=3.8",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            # Main command
            "cc=cc.cli:app",
        ],
    },
    install_requires=[
        "typer>=0.12.0",
        "rich>=13.0.0",
        "requests>=2.31.0",
        "pydantic>=2.0.0",
        "openai>=1.0.0",
        "pyfiglet>=0.8.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
    },
)
