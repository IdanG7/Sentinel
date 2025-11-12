"""PatchBot - Autonomous CI/CD Failure Resolution Agent."""

from .agent import PatchBot
from .config import PatchBotConfig, get_config

__version__ = "1.0.0"

__all__ = [
    "PatchBot",
    "PatchBotConfig",
    "get_config",
]
