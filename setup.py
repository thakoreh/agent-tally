# agent-tally: universal AI agent cost tracker with real-time tracking

from setuptools import setup, find_packages

setup(
    name="agent-tally",
    version="0.4.0",
    description="Real-time cost tracking for AI coding agents with budget limits, kill switch, and TUI dashboard.",
    author="Hiren Thakore",
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "rich>=13.0",
        "pyyaml>=6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "agent-tally=agent_tally.cli:cli",
        ],
    },
    python_requires=">=3.9",
)
