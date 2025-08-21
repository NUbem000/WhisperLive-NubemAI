"""
Voice CLI Control for WhisperLive-NubemAI
Voice-controlled terminal interface for AI CLIs (Claude, Gemini, etc.)
"""

__version__ = "1.0.0"
__author__ = "NubemAI Team"

from .cli_detector import CLIDetector
from .terminal_controller import TerminalController
from .voice_controller import VoiceController
from .main import VoiceCLIApp

__all__ = [
    "CLIDetector",
    "TerminalController",
    "VoiceController",
    "VoiceCLIApp"
]