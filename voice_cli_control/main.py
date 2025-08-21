#!/usr/bin/env python3
"""
Voice CLI Control - Main Application
Voice-controlled terminal interface for AI CLIs
"""

import sys
import os
import asyncio
import argparse
import signal
import time
from typing import Optional, Dict, List
from pathlib import Path
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich import print as rprint

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_cli_control.cli_detector import CLIDetector
from voice_cli_control.terminal_controller import TerminalController
from voice_cli_control.voice_controller import VoiceController, VoiceCommand, VoiceCommandType


class VoiceCLIApp:
    """Main application for voice-controlled CLI interface"""
    
    def __init__(self):
        """Initialize the application"""
        self.console = Console()
        self.cli_detector = CLIDetector()
        self.terminal_controller = TerminalController()
        self.voice_controller = VoiceController()
        
        self.selected_cli = None
        self.selected_terminal = None
        self.is_running = False
        self.config_file = Path.home() / ".voice_cli_control" / "config.json"
        
        # Create config directory if it doesn't exist
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.console.print("\n[yellow]Shutting down...[/yellow]")
        self.shutdown()
        sys.exit(0)
    
    def load_config(self):
        """Load configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                
                self.selected_cli = config.get("selected_cli")
                self.selected_terminal = config.get("selected_terminal")
                
                # Load voice controller settings
                voice_settings = config.get("voice_settings", {})
                self.voice_controller.model = voice_settings.get("model", "base")
                self.voice_controller.language = voice_settings.get("language", "en")
                
                self.console.print("[green]Configuration loaded successfully![/green]")
            except Exception as e:
                self.console.print(f"[red]Error loading config: {e}[/red]")
    
    def save_config(self):
        """Save configuration to file"""
        config = {
            "selected_cli": self.selected_cli,
            "selected_terminal": self.selected_terminal,
            "voice_settings": {
                "model": self.voice_controller.model,
                "language": self.voice_controller.language,
                "silence_threshold": self.voice_controller.silence_threshold
            }
        }
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            self.console.print("[green]Configuration saved![/green]")
        except Exception as e:
            self.console.print(f"[red]Error saving config: {e}[/red]")
    
    def detect_clis(self):
        """Detect installed AI CLIs"""
        self.console.print("\n[cyan]🔍 Detecting installed AI CLIs...[/cyan]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("Scanning system...", total=None)
            detected = self.cli_detector.detect_all()
            progress.update(task, completed=True)
        
        if detected:
            # Create table of detected CLIs
            table = Table(title="Detected AI CLIs", show_header=True, header_style="bold magenta")
            table.add_column("CLI", style="cyan", no_wrap=True)
            table.add_column("Name", style="green")
            table.add_column("Version", style="yellow")
            table.add_column("Command", style="blue")
            
            for cli_key, cli_info in detected.items():
                table.add_row(
                    cli_key,
                    cli_info["name"],
                    cli_info.get("version", "Unknown"),
                    cli_info["command"]
                )
            
            self.console.print(table)
            return detected
        else:
            self.console.print("[yellow]⚠️  No AI CLIs detected on this system.[/yellow]")
            self.show_installation_help()
            return {}
    
    def show_installation_help(self):
        """Show installation instructions for AI CLIs"""
        self.console.print("\n[cyan]📦 Available AI CLIs to install:[/cyan]")
        
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("CLI", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Install URL", style="yellow")
        
        for cli_key, cli_info in CLIDetector.KNOWN_CLIS.items():
            table.add_row(
                cli_key,
                cli_info["name"],
                cli_info["install_url"]
            )
        
        self.console.print(table)
    
    def select_cli(self, detected_clis: Dict) -> Optional[str]:
        """
        Let user select a CLI to use
        
        Args:
            detected_clis: Dictionary of detected CLIs
        
        Returns:
            Selected CLI key or None
        """
        if not detected_clis:
            return None
        
        cli_list = list(detected_clis.keys())
        
        if len(cli_list) == 1:
            # Only one CLI, auto-select
            self.selected_cli = cli_list[0]
            self.console.print(f"[green]Auto-selected: {detected_clis[self.selected_cli]['name']}[/green]")
            return self.selected_cli
        
        # Multiple CLIs, let user choose
        self.console.print("\n[cyan]Please select an AI CLI to use:[/cyan]")
        
        for i, cli_key in enumerate(cli_list, 1):
            cli_info = detected_clis[cli_key]
            self.console.print(f"  {i}. {cli_info['name']} ({cli_info['command']})")
        
        while True:
            choice = Prompt.ask("Enter your choice", default="1")
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(cli_list):
                    self.selected_cli = cli_list[idx]
                    self.console.print(f"[green]Selected: {detected_clis[self.selected_cli]['name']}[/green]")
                    return self.selected_cli
                else:
                    self.console.print("[red]Invalid choice. Please try again.[/red]")
            except ValueError:
                self.console.print("[red]Please enter a number.[/red]")
    
    def select_terminal(self) -> Optional[str]:
        """
        Let user select a terminal to use
        
        Returns:
            Selected terminal type or None
        """
        available = self.terminal_controller.get_available_terminals()
        
        if not available:
            self.console.print("[red]❌ No compatible terminals found on this system.[/red]")
            return None
        
        if len(available) == 1:
            # Only one terminal, auto-select
            self.selected_terminal = available[0]
            self.console.print(f"[green]Auto-selected terminal: {self.selected_terminal}[/green]")
            return self.selected_terminal
        
        # Multiple terminals, let user choose
        self.console.print("\n[cyan]Please select a terminal to use:[/cyan]")
        
        for i, terminal in enumerate(available, 1):
            self.console.print(f"  {i}. {terminal}")
        
        while True:
            choice = Prompt.ask("Enter your choice", default="1")
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(available):
                    self.selected_terminal = available[idx]
                    self.console.print(f"[green]Selected terminal: {self.selected_terminal}[/green]")
                    return self.selected_terminal
                else:
                    self.console.print("[red]Invalid choice. Please try again.[/red]")
            except ValueError:
                self.console.print("[red]Please enter a number.[/red]")
    
    def setup_voice_callbacks(self):
        """Set up callbacks for voice controller"""
        
        def on_transcription(text: str):
            """Handle transcription text"""
            self.console.print(f"[dim]📝 Heard: {text}[/dim]")
        
        def on_command(command: VoiceCommand):
            """Handle voice commands"""
            if command.type == VoiceCommandType.TEXT:
                # Send text to terminal
                self.console.print(f"[green]➤ Typing: {command.content}[/green]")
                self.terminal_controller.send_command(command.content, add_newline=False)
            
            elif command.type == VoiceCommandType.KEY:
                # Send special key
                self.console.print(f"[yellow]⌨️  Key: {command.content}[/yellow]")
                self.terminal_controller.send_key(command.content)
            
            elif command.type == VoiceCommandType.CONTROL:
                # Handle control command
                self.console.print(f"[magenta]🎛️  Control: {command.content}[/magenta]")
                self.handle_control_command(command.content)
        
        def on_error(error: str):
            """Handle errors"""
            self.console.print(f"[red]❌ Error: {error}[/red]")
        
        self.voice_controller.on_transcription = on_transcription
        self.voice_controller.on_command = on_command
        self.voice_controller.on_error = on_error
    
    def setup_terminal_callbacks(self):
        """Set up callbacks for terminal controller"""
        
        def on_output(text: str):
            """Handle terminal output"""
            # Display terminal output (already formatted)
            print(text, end='', flush=True)
        
        def on_error(error: str):
            """Handle terminal errors"""
            self.console.print(f"[red]Terminal error: {error}[/red]")
        
        self.terminal_controller.on_output = on_output
        self.terminal_controller.on_error = on_error
    
    def handle_control_command(self, command: str):
        """
        Handle control commands
        
        Args:
            command: Control command string
        """
        if command == "CLEAR":
            # Clear terminal screen
            if self.terminal_controller.system == "Windows":
                self.terminal_controller.send_command("cls")
            else:
                self.terminal_controller.send_command("clear")
        
        elif command == "START_RECORDING":
            self.voice_controller.resume()
            self.console.print("[green]🎤 Recording resumed[/green]")
        
        elif command == "STOP_RECORDING":
            self.voice_controller.pause()
            self.console.print("[yellow]⏸️  Recording paused[/yellow]")
    
    async def run_voice_control(self):
        """Run the voice control loop"""
        self.console.print("\n[bold green]🎤 Voice Control Active![/bold green]")
        self.console.print("[dim]Speak commands or text to control the terminal.[/dim]")
        self.console.print("[dim]Say 'enter' or 'press enter' to submit commands.[/dim]")
        self.console.print("[dim]Say 'stop recording' to pause, 'start recording' to resume.[/dim]")
        self.console.print("[dim]Press Ctrl+C to exit.[/dim]\n")
        
        # Start voice controller
        if not await self.voice_controller.start():
            self.console.print("[red]Failed to start voice controller![/red]")
            return
        
        # Start terminal with selected CLI
        cli_info = self.cli_detector.detected_clis[self.selected_cli]
        command = cli_info["command"]
        
        self.console.print(f"[cyan]Starting {cli_info['name']}...[/cyan]")
        
        if not self.terminal_controller.start_terminal(
            command=command,
            terminal_type=self.selected_terminal
        ):
            self.console.print("[red]Failed to start terminal![/red]")
            await self.voice_controller.stop()
            return
        
        self.is_running = True
        
        # Wait for terminal to be ready
        await asyncio.sleep(2)
        
        # Main loop
        try:
            while self.is_running:
                await asyncio.sleep(0.1)
                
                # Check if terminal is still running
                if not self.terminal_controller.is_running():
                    self.console.print("[yellow]Terminal closed.[/yellow]")
                    break
        
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Interrupted by user.[/yellow]")
        
        finally:
            # Cleanup
            await self.voice_controller.stop()
            self.terminal_controller.stop_terminal()
            self.is_running = False
    
    def show_dashboard(self):
        """Show application dashboard"""
        layout = Layout()
        
        # Create panels
        header = Panel(
            "[bold cyan]🎙️  Voice CLI Control[/bold cyan]\n"
            "[dim]Voice-controlled terminal for AI CLIs[/dim]",
            style="cyan"
        )
        
        # Status information
        status_text = ""
        if self.selected_cli and self.selected_cli in self.cli_detector.detected_clis:
            cli_info = self.cli_detector.detected_clis[self.selected_cli]
            status_text += f"[green]CLI:[/green] {cli_info['name']}\n"
            status_text += f"[green]Command:[/green] {cli_info['command']}\n"
        else:
            status_text += "[yellow]No CLI selected[/yellow]\n"
        
        if self.selected_terminal:
            status_text += f"[green]Terminal:[/green] {self.selected_terminal}\n"
        else:
            status_text += "[yellow]No terminal selected[/yellow]\n"
        
        status_text += f"[green]Voice Model:[/green] {self.voice_controller.model}\n"
        status_text += f"[green]Language:[/green] {self.voice_controller.language}"
        
        status = Panel(status_text, title="Status", style="green")
        
        # Commands help
        commands = Panel(
            "[cyan]Voice Commands:[/cyan]\n"
            "• Say text to type it\n"
            "• 'enter' or 'press enter' - Submit command\n"
            "• 'tab' - Tab completion\n"
            "• 'control c' - Interrupt\n"
            "• 'clear screen' - Clear terminal\n"
            "• 'up arrow' / 'down arrow' - Navigate history\n"
            "• 'stop recording' - Pause voice\n"
            "• 'start recording' - Resume voice\n\n"
            "[cyan]Keyboard:[/cyan]\n"
            "• Ctrl+C - Exit application",
            title="Commands",
            style="blue"
        )
        
        layout.split_column(
            Layout(header, size=5),
            Layout(status, size=8),
            Layout(commands, size=15)
        )
        
        self.console.print(layout)
    
    def shutdown(self):
        """Shutdown the application cleanly"""
        self.is_running = False
        
        if self.terminal_controller.is_running():
            self.terminal_controller.stop_terminal()
        
        # Save configuration
        self.save_config()
    
    async def main_async(self):
        """Main application flow (async)"""
        # Show welcome
        self.console.print(Panel.fit(
            "[bold cyan]🎙️  Welcome to Voice CLI Control![/bold cyan]\n"
            "[dim]Control AI CLIs with your voice[/dim]",
            style="cyan"
        ))
        
        # Load configuration
        self.load_config()
        
        # Detect CLIs
        detected = self.detect_clis()
        
        if not detected:
            if Confirm.ask("No AI CLIs detected. Would you like to see installation instructions?"):
                self.show_installation_help()
            return
        
        # Select CLI
        if not self.selected_cli or self.selected_cli not in detected:
            self.selected_cli = self.select_cli(detected)
            if not self.selected_cli:
                return
        
        # Select terminal
        if not self.selected_terminal:
            self.selected_terminal = self.select_terminal()
            if not self.selected_terminal:
                return
        
        # Set up callbacks
        self.setup_voice_callbacks()
        self.setup_terminal_callbacks()
        
        # Show dashboard
        self.show_dashboard()
        
        # Ask to start
        if Confirm.ask("\n[cyan]Ready to start voice control?[/cyan]"):
            await self.run_voice_control()
        
        # Cleanup
        self.shutdown()
        self.console.print("[green]✅ Application terminated gracefully.[/green]")
    
    def main(self):
        """Main application entry point"""
        try:
            asyncio.run(self.main_async())
        except Exception as e:
            self.console.print(f"[red]Fatal error: {e}[/red]")
            self.shutdown()


def main():
    """Command-line entry point"""
    parser = argparse.ArgumentParser(
        description="Voice CLI Control - Control AI CLIs with your voice"
    )
    
    parser.add_argument(
        "--model",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model to use (default: base)"
    )
    
    parser.add_argument(
        "--language",
        default="en",
        help="Language code for transcription (default: en)"
    )
    
    parser.add_argument(
        "--cli",
        help="Specific CLI to use (e.g., claude, gemini)"
    )
    
    parser.add_argument(
        "--terminal",
        help="Specific terminal to use"
    )
    
    parser.add_argument(
        "--list-clis",
        action="store_true",
        help="List available AI CLIs and exit"
    )
    
    parser.add_argument(
        "--list-terminals",
        action="store_true",
        help="List available terminals and exit"
    )
    
    args = parser.parse_args()
    
    app = VoiceCLIApp()
    
    # Handle list commands
    if args.list_clis:
        detected = app.detect_clis()
        if not detected:
            app.show_installation_help()
        sys.exit(0)
    
    if args.list_terminals:
        terminals = app.terminal_controller.get_available_terminals()
        app.console.print("[cyan]Available terminals:[/cyan]")
        for terminal in terminals:
            app.console.print(f"  • {terminal}")
        sys.exit(0)
    
    # Set configuration from arguments
    if args.model:
        app.voice_controller.model = args.model
    
    if args.language:
        app.voice_controller.language = args.language
    
    if args.cli:
        app.selected_cli = args.cli
    
    if args.terminal:
        app.selected_terminal = args.terminal
    
    # Run the application
    app.main()


if __name__ == "__main__":
    main()