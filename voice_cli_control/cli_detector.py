"""
CLI Detector Module
Detects installed AI CLIs on the system (Claude, Gemini, ChatGPT, etc.)
"""

import os
import platform
import subprocess
import shutil
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import json


class CLIDetector:
    """Detects and manages AI CLI tools installed on the system"""
    
    # Known AI CLI tools and their commands
    KNOWN_CLIS = {
        "claude": {
            "commands": ["claude", "claude-code", "claude-cli"],
            "name": "Claude CLI",
            "description": "Anthropic's Claude AI CLI",
            "install_url": "https://github.com/anthropics/claude-cli",
            "test_command": "--version"
        },
        "gemini": {
            "commands": ["gemini", "gemini-cli", "gcloud ai"],
            "name": "Google Gemini CLI",
            "description": "Google's Gemini AI CLI",
            "install_url": "https://cloud.google.com/sdk",
            "test_command": "--version"
        },
        "openai": {
            "commands": ["openai", "gpt", "chatgpt-cli"],
            "name": "OpenAI CLI",
            "description": "OpenAI's ChatGPT CLI",
            "install_url": "https://github.com/openai/openai-cli",
            "test_command": "--version"
        },
        "copilot": {
            "commands": ["github-copilot-cli", "copilot"],
            "name": "GitHub Copilot CLI",
            "description": "GitHub Copilot in the CLI",
            "install_url": "https://github.com/github/copilot-cli",
            "test_command": "--version"
        },
        "bard": {
            "commands": ["bard", "bard-cli"],
            "name": "Google Bard CLI",
            "description": "Google Bard AI CLI",
            "install_url": "https://github.com/google/bard-cli",
            "test_command": "--version"
        },
        "llama": {
            "commands": ["llama", "llama-cli", "ollama"],
            "name": "Llama/Ollama CLI",
            "description": "Meta's Llama or Ollama CLI",
            "install_url": "https://ollama.ai",
            "test_command": "--version"
        },
        "mistral": {
            "commands": ["mistral", "mistral-cli"],
            "name": "Mistral CLI",
            "description": "Mistral AI CLI",
            "install_url": "https://mistral.ai",
            "test_command": "--version"
        },
        "perplexity": {
            "commands": ["perplexity", "pplx"],
            "name": "Perplexity CLI",
            "description": "Perplexity AI CLI",
            "install_url": "https://www.perplexity.ai",
            "test_command": "--version"
        },
        "anthropic": {
            "commands": ["anthropic", "claude-api"],
            "name": "Anthropic API CLI",
            "description": "Official Anthropic API CLI",
            "install_url": "https://docs.anthropic.com/claude/docs/cli",
            "test_command": "--version"
        },
        "palm": {
            "commands": ["palm", "palm-cli"],
            "name": "Google PaLM CLI",
            "description": "Google PaLM API CLI",
            "install_url": "https://developers.generativeai.google",
            "test_command": "--version"
        }
    }
    
    def __init__(self):
        self.system = platform.system()
        self.detected_clis = {}
        self.cli_paths = {}
    
    def detect_all(self) -> Dict[str, Dict]:
        """
        Detect all installed AI CLIs on the system
        
        Returns:
            Dictionary of detected CLIs with their information
        """
        detected = {}
        
        for cli_key, cli_info in self.KNOWN_CLIS.items():
            for command in cli_info["commands"]:
                path, version = self._check_command(command, cli_info.get("test_command", "--version"))
                if path:
                    detected[cli_key] = {
                        "name": cli_info["name"],
                        "command": command,
                        "path": path,
                        "version": version,
                        "description": cli_info["description"],
                        "install_url": cli_info["install_url"]
                    }
                    break
        
        self.detected_clis = detected
        return detected
    
    def _check_command(self, command: str, version_flag: str = "--version") -> Tuple[Optional[str], Optional[str]]:
        """
        Check if a command exists and get its version
        
        Args:
            command: Command to check
            version_flag: Flag to get version information
        
        Returns:
            Tuple of (path, version) or (None, None) if not found
        """
        # Check if command exists using shutil.which
        path = shutil.which(command)
        if not path:
            return None, None
        
        # Try to get version
        version = None
        try:
            result = subprocess.run(
                [command, version_flag],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            version = "Unknown"
        
        return path, version
    
    def check_specific_cli(self, cli_name: str) -> Optional[Dict]:
        """
        Check if a specific CLI is installed
        
        Args:
            cli_name: Name of the CLI to check
        
        Returns:
            CLI information if found, None otherwise
        """
        if cli_name in self.detected_clis:
            return self.detected_clis[cli_name]
        
        if cli_name in self.KNOWN_CLIS:
            cli_info = self.KNOWN_CLIS[cli_name]
            for command in cli_info["commands"]:
                path, version = self._check_command(command, cli_info.get("test_command", "--version"))
                if path:
                    return {
                        "name": cli_info["name"],
                        "command": command,
                        "path": path,
                        "version": version,
                        "description": cli_info["description"],
                        "install_url": cli_info["install_url"]
                    }
        
        return None
    
    def get_install_instructions(self, cli_name: str) -> str:
        """
        Get installation instructions for a specific CLI
        
        Args:
            cli_name: Name of the CLI
        
        Returns:
            Installation instructions string
        """
        if cli_name not in self.KNOWN_CLIS:
            return f"Unknown CLI: {cli_name}"
        
        cli_info = self.KNOWN_CLIS[cli_name]
        instructions = f"""
Installation Instructions for {cli_info['name']}:
{'=' * 50}

1. Visit: {cli_info['install_url']}
"""
        
        # Platform-specific instructions
        if self.system == "Darwin":  # macOS
            instructions += """
2. For macOS, you can typically use Homebrew:
   brew install <package-name>
   
   Or download the macOS binary from the official website.
"""
        elif self.system == "Linux":
            instructions += """
2. For Linux, you can use:
   - Package manager (apt, yum, dnf, etc.)
   - Snap: snap install <package-name>
   - Download Linux binary from the official website
   - Build from source
"""
        elif self.system == "Windows":
            instructions += """
2. For Windows, you can use:
   - Windows Package Manager: winget install <package-name>
   - Chocolatey: choco install <package-name>
   - Download Windows installer from the official website
"""
        
        instructions += f"""
3. After installation, verify with:
   {cli_info['commands'][0]} --version

4. Configure API keys if required (check documentation)
"""
        
        return instructions
    
    def get_cli_config_path(self, cli_name: str) -> Optional[Path]:
        """
        Get the configuration directory path for a specific CLI
        
        Args:
            cli_name: Name of the CLI
        
        Returns:
            Path to configuration directory if it exists
        """
        home = Path.home()
        
        # Common config locations
        config_paths = {
            "claude": [
                home / ".claude",
                home / ".config" / "claude",
                home / ".claude-cli"
            ],
            "gemini": [
                home / ".config" / "gcloud",
                home / ".gemini"
            ],
            "openai": [
                home / ".openai",
                home / ".config" / "openai"
            ],
            "ollama": [
                home / ".ollama",
                home / ".config" / "ollama"
            ]
        }
        
        if cli_name in config_paths:
            for path in config_paths[cli_name]:
                if path.exists():
                    return path
        
        # Generic config paths
        generic_paths = [
            home / f".{cli_name}",
            home / ".config" / cli_name,
            home / f".{cli_name}-cli"
        ]
        
        for path in generic_paths:
            if path.exists():
                return path
        
        return None
    
    def test_cli_connection(self, cli_name: str) -> bool:
        """
        Test if a CLI is properly configured and can connect to its service
        
        Args:
            cli_name: Name of the CLI to test
        
        Returns:
            True if connection successful, False otherwise
        """
        cli_info = self.check_specific_cli(cli_name)
        if not cli_info:
            return False
        
        # Try a simple test command
        test_commands = {
            "claude": ["claude", "list-models"],
            "openai": ["openai", "api", "models.list"],
            "ollama": ["ollama", "list"],
            "gemini": ["gcloud", "ai", "models", "list"]
        }
        
        if cli_name in test_commands:
            try:
                result = subprocess.run(
                    test_commands[cli_name],
                    capture_output=True,
                    timeout=10
                )
                return result.returncode == 0
            except:
                return False
        
        return True
    
    def save_detected_clis(self, filepath: str = "detected_clis.json"):
        """
        Save detected CLIs to a JSON file
        
        Args:
            filepath: Path to save the JSON file
        """
        with open(filepath, 'w') as f:
            json.dump(self.detected_clis, f, indent=2)
    
    def load_detected_clis(self, filepath: str = "detected_clis.json") -> Dict:
        """
        Load previously detected CLIs from a JSON file
        
        Args:
            filepath: Path to the JSON file
        
        Returns:
            Dictionary of detected CLIs
        """
        try:
            with open(filepath, 'r') as f:
                self.detected_clis = json.load(f)
                return self.detected_clis
        except FileNotFoundError:
            return {}


if __name__ == "__main__":
    # Test the CLI detector
    detector = CLIDetector()
    
    print(f"System: {detector.system}")
    print("\nDetecting installed AI CLIs...")
    print("=" * 60)
    
    detected = detector.detect_all()
    
    if detected:
        print("\n✅ Detected CLIs:")
        for cli_key, cli_info in detected.items():
            print(f"\n{cli_info['name']}:")
            print(f"  Command: {cli_info['command']}")
            print(f"  Path: {cli_info['path']}")
            print(f"  Version: {cli_info['version']}")
            print(f"  Description: {cli_info['description']}")
    else:
        print("\n❌ No AI CLIs detected on this system.")
        print("\nAvailable CLIs to install:")
        for cli_key, cli_info in CLIDetector.KNOWN_CLIS.items():
            print(f"  - {cli_info['name']}: {cli_info['install_url']}")
    
    # Save results
    detector.save_detected_clis()
    print(f"\n💾 Results saved to detected_clis.json")