# agent-tally: universal AI agent cost tracker

from setuptools import setup, find_packages

setup(
    name="agent-tally",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "rich>=13.0",
        "pyyaml>=6.0",
    ],
    entry_points={
        "console_scripts": [
            "agent-tally=agent_tally.cli:cli",
        ],
    },
    python_requires=">=3.9",
)
