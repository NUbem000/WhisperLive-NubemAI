"""
Voice Controller Module
Integrates Whisper transcription with terminal control
Handles voice commands and special triggers like "Enter"
"""

import asyncio
import time
import re
import json
from typing import Optional, Dict, List, Callable, Any
from dataclasses import dataclass
from enum import Enum
import numpy as np

# Import from parent module
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whisper_live.client import WhisperLiveClient
from whisper_live.server import WhisperLiveServer


class VoiceCommandType(Enum):
    """Types of voice commands"""
    TEXT = "text"  # Regular text to type
    KEY = "key"    # Special key command
    CONTROL = "control"  # Control command (start/stop/pause)
    SYSTEM = "system"  # System command


@dataclass
class VoiceCommand:
    """Represents a voice command"""
    type: VoiceCommandType
    content: str
    confidence: float = 1.0
    timestamp: float = 0.0


class VoiceController:
    """Controls terminal through voice commands using Whisper"""
    
    # Special voice triggers and their corresponding actions
    VOICE_TRIGGERS = {
        # Key triggers
        "enter": "Enter",
        "press enter": "Enter",
        "hit enter": "Enter",
        "return": "Enter",
        "new line": "Enter",
        "tab": "Tab",
        "press tab": "Tab",
        "backspace": "Backspace",
        "delete": "Delete",
        "escape": "Escape",
        "press escape": "Escape",
        
        # Navigation
        "up arrow": "Up",
        "down arrow": "Down",
        "left arrow": "Left",
        "right arrow": "Right",
        "page up": "PageUp",
        "page down": "PageDown",
        "home": "Home",
        "end": "End",
        
        # Control keys
        "control c": "Ctrl+C",
        "control d": "Ctrl+D",
        "control z": "Ctrl+Z",
        "break": "Ctrl+C",
        "exit": "Ctrl+D",
        "stop": "Ctrl+C",
        
        # Control commands
        "start recording": "START_RECORDING",
        "stop recording": "STOP_RECORDING",
        "pause recording": "PAUSE_RECORDING",
        "resume recording": "RESUME_RECORDING",
        "clear terminal": "CLEAR",
        "clear screen": "CLEAR",
    }
    
    # Punctuation voice commands
    PUNCTUATION_MAP = {
        "period": ".",
        "dot": ".",
        "comma": ",",
        "question mark": "?",
        "exclamation mark": "!",
        "exclamation point": "!",
        "colon": ":",
        "semicolon": ";",
        "quote": '"',
        "single quote": "'",
        "apostrophe": "'",
        "open parenthesis": "(",
        "close parenthesis": ")",
        "open bracket": "[",
        "close bracket": "]",
        "open brace": "{",
        "close brace": "}",
        "slash": "/",
        "backslash": "\\",
        "pipe": "|",
        "ampersand": "&",
        "at sign": "@",
        "hashtag": "#",
        "dollar sign": "$",
        "percent": "%",
        "caret": "^",
        "asterisk": "*",
        "plus": "+",
        "minus": "-",
        "equals": "=",
        "underscore": "_",
        "tilde": "~",
        "backtick": "`",
        "less than": "<",
        "greater than": ">",
        "space": " ",
    }
    
    def __init__(self, 
                 whisper_model: str = "base",
                 language: str = "en",
                 server_host: str = "localhost",
                 server_port: int = 9090):
        """
        Initialize the voice controller
        
        Args:
            whisper_model: Whisper model to use
            language: Language for transcription
            server_host: WhisperLive server host
            server_port: WhisperLive server port
        """
        self.model = whisper_model
        self.language = language
        self.server_host = server_host
        self.server_port = server_port
        
        self.client = None
        self.is_recording = False
        self.is_paused = False
        
        # Callbacks
        self.on_transcription: Optional[Callable[[str], None]] = None
        self.on_command: Optional[Callable[[VoiceCommand], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        
        # Transcription buffer
        self.transcription_buffer = ""
        self.last_transcription_time = 0
        self.silence_threshold = 2.0  # seconds of silence to trigger command
        
        # Command history
        self.command_history: List[VoiceCommand] = []
        self.max_history = 100
    
    async def start(self) -> bool:
        """
        Start the voice controller
        
        Returns:
            True if started successfully, False otherwise
        """
        try:
            # Initialize WhisperLive client
            self.client = WhisperLiveClient(
                host=self.server_host,
                port=self.server_port,
                model=self.model,
                language=self.language
            )
            
            # Set up callbacks
            self.client.on_transcription = self._handle_transcription
            self.client.on_error = self._handle_error
            
            # Connect to server
            await self.client.connect()
            
            self.is_recording = True
            return True
            
        except Exception as e:
            if self.on_error:
                self.on_error(f"Failed to start voice controller: {e}")
            return False
    
    async def stop(self):
        """Stop the voice controller"""
        self.is_recording = False
        
        if self.client:
            await self.client.disconnect()
            self.client = None
    
    def pause(self):
        """Pause voice recording"""
        self.is_paused = True
    
    def resume(self):
        """Resume voice recording"""
        self.is_paused = False
    
    def _handle_transcription(self, text: str, is_final: bool = False):
        """
        Handle transcription from Whisper
        
        Args:
            text: Transcribed text
            is_final: Whether this is a final transcription
        """
        if self.is_paused:
            return
        
        # Clean up the text
        text = text.strip()
        if not text:
            return
        
        # Add to buffer
        self.transcription_buffer += " " + text if self.transcription_buffer else text
        self.last_transcription_time = time.time()
        
        # Check for immediate triggers
        command = self._check_for_triggers(text)
        if command:
            self._execute_command(command)
            self.transcription_buffer = ""  # Clear buffer after command
        elif is_final or self._should_process_buffer():
            # Process the buffer
            self._process_transcription_buffer()
    
    def _should_process_buffer(self) -> bool:
        """
        Check if we should process the transcription buffer
        
        Returns:
            True if buffer should be processed
        """
        # Process if silence threshold exceeded
        if time.time() - self.last_transcription_time > self.silence_threshold:
            return True
        
        # Process if buffer ends with a trigger word
        buffer_lower = self.transcription_buffer.lower().strip()
        for trigger in self.VOICE_TRIGGERS:
            if buffer_lower.endswith(trigger):
                return True
        
        return False
    
    def _process_transcription_buffer(self):
        """Process the accumulated transcription buffer"""
        if not self.transcription_buffer:
            return
        
        buffer = self.transcription_buffer.strip()
        self.transcription_buffer = ""
        
        # Parse the buffer for commands and text
        commands = self._parse_transcription(buffer)
        
        # Execute commands
        for command in commands:
            self._execute_command(command)
    
    def _parse_transcription(self, text: str) -> List[VoiceCommand]:
        """
        Parse transcription text into commands
        
        Args:
            text: Transcription text to parse
        
        Returns:
            List of voice commands
        """
        commands = []
        
        # Convert to lowercase for matching
        text_lower = text.lower()
        
        # Check if entire text is a trigger
        if text_lower in self.VOICE_TRIGGERS:
            key = self.VOICE_TRIGGERS[text_lower]
            if key.startswith("START_") or key.startswith("STOP_") or key.startswith("PAUSE_"):
                commands.append(VoiceCommand(VoiceCommandType.CONTROL, key))
            else:
                commands.append(VoiceCommand(VoiceCommandType.KEY, key))
            return commands
        
        # Process text with inline commands
        # Split by potential trigger phrases
        parts = self._split_by_triggers(text)
        
        for part in parts:
            if isinstance(part, VoiceCommand):
                commands.append(part)
            else:
                # Process regular text
                processed_text = self._process_text(part)
                if processed_text:
                    commands.append(VoiceCommand(VoiceCommandType.TEXT, processed_text))
        
        return commands
    
    def _split_by_triggers(self, text: str) -> List[Any]:
        """
        Split text by trigger phrases
        
        Args:
            text: Text to split
        
        Returns:
            List of text parts and VoiceCommand objects
        """
        parts = []
        remaining = text
        
        while remaining:
            # Find the earliest trigger in the remaining text
            earliest_pos = len(remaining)
            earliest_trigger = None
            earliest_key = None
            
            for trigger, key in self.VOICE_TRIGGERS.items():
                # Case-insensitive search
                pattern = re.compile(re.escape(trigger), re.IGNORECASE)
                match = pattern.search(remaining)
                if match and match.start() < earliest_pos:
                    earliest_pos = match.start()
                    earliest_trigger = trigger
                    earliest_key = key
            
            if earliest_trigger:
                # Add text before trigger
                if earliest_pos > 0:
                    parts.append(remaining[:earliest_pos].strip())
                
                # Add trigger as command
                if earliest_key.startswith("START_") or earliest_key.startswith("STOP_"):
                    parts.append(VoiceCommand(VoiceCommandType.CONTROL, earliest_key))
                else:
                    parts.append(VoiceCommand(VoiceCommandType.KEY, earliest_key))
                
                # Continue with remaining text
                trigger_end = earliest_pos + len(earliest_trigger)
                remaining = remaining[trigger_end:].strip()
            else:
                # No more triggers, add remaining text
                if remaining:
                    parts.append(remaining)
                break
        
        return parts
    
    def _process_text(self, text: str) -> str:
        """
        Process regular text, handling punctuation commands
        
        Args:
            text: Text to process
        
        Returns:
            Processed text
        """
        # Replace punctuation voice commands
        for voice_cmd, symbol in self.PUNCTUATION_MAP.items():
            # Case-insensitive replacement
            pattern = re.compile(r'\b' + re.escape(voice_cmd) + r'\b', re.IGNORECASE)
            text = pattern.sub(symbol, text)
        
        return text.strip()
    
    def _check_for_triggers(self, text: str) -> Optional[VoiceCommand]:
        """
        Check if text contains an immediate trigger
        
        Args:
            text: Text to check
        
        Returns:
            VoiceCommand if trigger found, None otherwise
        """
        text_lower = text.lower().strip()
        
        # Check for exact match triggers
        if text_lower in self.VOICE_TRIGGERS:
            key = self.VOICE_TRIGGERS[text_lower]
            if key.startswith("START_") or key.startswith("STOP_"):
                return VoiceCommand(VoiceCommandType.CONTROL, key)
            else:
                return VoiceCommand(VoiceCommandType.KEY, key)
        
        # Check for ending triggers (like "... enter")
        for trigger, key in self.VOICE_TRIGGERS.items():
            if text_lower.endswith(" " + trigger):
                # Extract the text before the trigger
                text_before = text[:-(len(trigger) + 1)].strip()
                if text_before:
                    # Return the text part, the trigger will be handled separately
                    return None
                else:
                    if key.startswith("START_") or key.startswith("STOP_"):
                        return VoiceCommand(VoiceCommandType.CONTROL, key)
                    else:
                        return VoiceCommand(VoiceCommandType.KEY, key)
        
        return None
    
    def _execute_command(self, command: VoiceCommand):
        """
        Execute a voice command
        
        Args:
            command: Command to execute
        """
        # Add to history
        command.timestamp = time.time()
        self.command_history.append(command)
        if len(self.command_history) > self.max_history:
            self.command_history.pop(0)
        
        # Call callback
        if self.on_command:
            self.on_command(command)
        
        # Handle control commands internally
        if command.type == VoiceCommandType.CONTROL:
            self._handle_control_command(command.content)
    
    def _handle_control_command(self, command: str):
        """
        Handle internal control commands
        
        Args:
            command: Control command string
        """
        if command == "START_RECORDING":
            self.resume()
        elif command == "STOP_RECORDING":
            self.pause()
        elif command == "PAUSE_RECORDING":
            self.pause()
        elif command == "RESUME_RECORDING":
            self.resume()
        elif command == "CLEAR":
            # This should be handled by the terminal controller
            pass
    
    def _handle_error(self, error: str):
        """
        Handle errors from Whisper client
        
        Args:
            error: Error message
        """
        if self.on_error:
            self.on_error(f"Whisper error: {error}")
    
    def get_command_history(self, limit: int = 10) -> List[VoiceCommand]:
        """
        Get recent command history
        
        Args:
            limit: Maximum number of commands to return
        
        Returns:
            List of recent commands
        """
        return self.command_history[-limit:]
    
    def clear_history(self):
        """Clear command history"""
        self.command_history.clear()
    
    def add_custom_trigger(self, phrase: str, action: str):
        """
        Add a custom voice trigger
        
        Args:
            phrase: Voice phrase to trigger on
            action: Action to perform (key name or command)
        """
        self.VOICE_TRIGGERS[phrase.lower()] = action
    
    def remove_custom_trigger(self, phrase: str):
        """
        Remove a custom voice trigger
        
        Args:
            phrase: Voice phrase to remove
        """
        phrase_lower = phrase.lower()
        if phrase_lower in self.VOICE_TRIGGERS:
            del self.VOICE_TRIGGERS[phrase_lower]
    
    def save_settings(self, filepath: str = "voice_settings.json"):
        """
        Save voice controller settings to file
        
        Args:
            filepath: Path to save settings
        """
        settings = {
            "model": self.model,
            "language": self.language,
            "custom_triggers": {k: v for k, v in self.VOICE_TRIGGERS.items() 
                               if k not in self.__class__.VOICE_TRIGGERS},
            "silence_threshold": self.silence_threshold
        }
        
        with open(filepath, 'w') as f:
            json.dump(settings, f, indent=2)
    
    def load_settings(self, filepath: str = "voice_settings.json"):
        """
        Load voice controller settings from file
        
        Args:
            filepath: Path to load settings from
        """
        try:
            with open(filepath, 'r') as f:
                settings = json.load(f)
            
            self.model = settings.get("model", self.model)
            self.language = settings.get("language", self.language)
            self.silence_threshold = settings.get("silence_threshold", self.silence_threshold)
            
            # Load custom triggers
            custom_triggers = settings.get("custom_triggers", {})
            for phrase, action in custom_triggers.items():
                self.add_custom_trigger(phrase, action)
        
        except FileNotFoundError:
            pass


# Simulated Whisper client for testing (replace with actual implementation)
class WhisperLiveClient:
    """Mock WhisperLive client for testing"""
    
    def __init__(self, host, port, model, language):
        self.host = host
        self.port = port
        self.model = model
        self.language = language
        self.on_transcription = None
        self.on_error = None
    
    async def connect(self):
        """Connect to server"""
        pass
    
    async def disconnect(self):
        """Disconnect from server"""
        pass


if __name__ == "__main__":
    # Test the voice controller
    controller = VoiceController()
    
    # Set up callbacks
    def on_command(cmd: VoiceCommand):
        print(f"Command: {cmd.type.value} - {cmd.content}")
    
    def on_error(error: str):
        print(f"Error: {error}")
    
    controller.on_command = on_command
    controller.on_error = on_error
    
    # Test parsing
    test_phrases = [
        "hello world enter",
        "ls dash la press enter",
        "clear screen",
        "type this text then hit enter",
        "control c",
        "cd slash home slash user tab"
    ]
    
    print("Testing voice command parsing:")
    print("=" * 50)
    
    for phrase in test_phrases:
        print(f"\nPhrase: '{phrase}'")
        commands = controller._parse_transcription(phrase)
        for cmd in commands:
            print(f"  -> {cmd.type.value}: {cmd.content}")