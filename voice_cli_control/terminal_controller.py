"""
Terminal Controller Module
Manages terminal sessions across different platforms (Windows, macOS, Linux)
"""

import os
import sys
import platform
import subprocess
import threading
import queue
import time
import signal
from typing import Optional, Callable, List, Tuple
from pathlib import Path
import pty
import select
import termios
import tty
import fcntl
import struct


class TerminalController:
    """Controls terminal sessions across different platforms"""
    
    TERMINALS = {
        "Linux": {
            "gnome-terminal": ["gnome-terminal", "--", "bash", "-c"],
            "konsole": ["konsole", "-e", "bash", "-c"],
            "xterm": ["xterm", "-e", "bash", "-c"],
            "terminator": ["terminator", "-e", "bash", "-c"],
            "alacritty": ["alacritty", "-e", "bash", "-c"],
            "kitty": ["kitty", "bash", "-c"],
            "xfce4-terminal": ["xfce4-terminal", "-e", "bash", "-c"],
            "mate-terminal": ["mate-terminal", "-e", "bash", "-c"],
            "lxterminal": ["lxterminal", "-e", "bash", "-c"],
            "tilix": ["tilix", "-e", "bash", "-c"]
        },
        "Darwin": {  # macOS
            "Terminal": ["open", "-a", "Terminal", "--args"],
            "iTerm": ["open", "-a", "iTerm", "--args"],
            "Alacritty": ["open", "-a", "Alacritty", "--args"],
            "Kitty": ["open", "-a", "Kitty", "--args"],
            "Hyper": ["open", "-a", "Hyper", "--args"]
        },
        "Windows": {
            "cmd": ["cmd.exe", "/k"],
            "powershell": ["powershell.exe", "-NoExit", "-Command"],
            "wt": ["wt.exe", "-d", ".", "cmd.exe", "/k"],  # Windows Terminal
            "conemu": ["ConEmu64.exe", "-run"],
            "cmder": ["cmder.exe", "/START"]
        }
    }
    
    def __init__(self, terminal_type: Optional[str] = None):
        """
        Initialize the terminal controller
        
        Args:
            terminal_type: Specific terminal to use (optional)
        """
        self.system = platform.system()
        self.terminal_type = terminal_type
        self.process = None
        self.stdin = None
        self.stdout = None
        self.stderr = None
        self.output_queue = queue.Queue()
        self.input_queue = queue.Queue()
        self.running = False
        self.output_thread = None
        self.input_thread = None
        self.master_fd = None
        self.slave_fd = None
        
        # Callbacks
        self.on_output: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_exit: Optional[Callable[[int], None]] = None
    
    def get_available_terminals(self) -> List[str]:
        """
        Get list of available terminals on the current system
        
        Returns:
            List of available terminal names
        """
        if self.system not in self.TERMINALS:
            return []
        
        available = []
        for terminal, command in self.TERMINALS[self.system].items():
            if self._check_terminal_exists(command[0]):
                available.append(terminal)
        
        return available
    
    def _check_terminal_exists(self, command: str) -> bool:
        """
        Check if a terminal command exists on the system
        
        Args:
            command: Terminal command to check
        
        Returns:
            True if terminal exists, False otherwise
        """
        import shutil
        
        if self.system == "Windows":
            # Special handling for Windows
            if command in ["cmd.exe", "powershell.exe"]:
                return True
            return shutil.which(command) is not None
        else:
            return shutil.which(command) is not None
    
    def start_terminal(self, command: Optional[str] = None, 
                      terminal_type: Optional[str] = None) -> bool:
        """
        Start a new terminal session
        
        Args:
            command: Initial command to run in terminal
            terminal_type: Specific terminal type to use
        
        Returns:
            True if terminal started successfully, False otherwise
        """
        if self.running:
            return False
        
        terminal = terminal_type or self.terminal_type
        
        # Get terminal command
        if terminal and terminal in self.TERMINALS.get(self.system, {}):
            terminal_cmd = self.TERMINALS[self.system][terminal].copy()
        else:
            # Use default terminal for the system
            available = self.get_available_terminals()
            if not available:
                return False
            terminal_cmd = self.TERMINALS[self.system][available[0]].copy()
        
        # Add the command to run if provided
        if command:
            terminal_cmd.append(command)
        
        try:
            if self.system in ["Linux", "Darwin"]:
                self._start_unix_terminal(terminal_cmd)
            else:
                self._start_windows_terminal(terminal_cmd)
            
            self.running = True
            self._start_io_threads()
            return True
            
        except Exception as e:
            print(f"Error starting terminal: {e}")
            return False
    
    def _start_unix_terminal(self, command: List[str]):
        """Start a terminal on Unix-like systems (Linux/macOS)"""
        # Create a pseudo-terminal
        self.master_fd, self.slave_fd = pty.openpty()
        
        # Start the process
        self.process = subprocess.Popen(
            command,
            stdin=self.slave_fd,
            stdout=self.slave_fd,
            stderr=self.slave_fd,
            preexec_fn=os.setsid
        )
        
        # Make the master file descriptor non-blocking
        flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
        fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    
    def _start_windows_terminal(self, command: List[str]):
        """Start a terminal on Windows"""
        # Windows doesn't support pty, use pipes instead
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,
            creationflags=subprocess.CREATE_NEW_CONSOLE if self.system == "Windows" else 0
        )
        
        self.stdin = self.process.stdin
        self.stdout = self.process.stdout
        self.stderr = self.process.stderr
    
    def _start_io_threads(self):
        """Start threads for handling input/output"""
        self.output_thread = threading.Thread(target=self._output_reader)
        self.output_thread.daemon = True
        self.output_thread.start()
        
        self.input_thread = threading.Thread(target=self._input_writer)
        self.input_thread.daemon = True
        self.input_thread.start()
    
    def _output_reader(self):
        """Thread function to read output from terminal"""
        while self.running:
            try:
                if self.system in ["Linux", "Darwin"]:
                    # Unix-like systems
                    if self.master_fd:
                        ready, _, _ = select.select([self.master_fd], [], [], 0.1)
                        if ready:
                            output = os.read(self.master_fd, 4096).decode('utf-8', errors='ignore')
                            if output:
                                self.output_queue.put(output)
                                if self.on_output:
                                    self.on_output(output)
                else:
                    # Windows
                    if self.stdout:
                        output = self.stdout.readline()
                        if output:
                            self.output_queue.put(output)
                            if self.on_output:
                                self.on_output(output)
            except Exception as e:
                if self.on_error:
                    self.on_error(str(e))
                time.sleep(0.1)
    
    def _input_writer(self):
        """Thread function to write input to terminal"""
        while self.running:
            try:
                command = self.input_queue.get(timeout=0.1)
                if command:
                    self.send_command(command)
            except queue.Empty:
                continue
            except Exception as e:
                if self.on_error:
                    self.on_error(str(e))
    
    def send_command(self, command: str, add_newline: bool = True):
        """
        Send a command to the terminal
        
        Args:
            command: Command to send
            add_newline: Whether to add a newline (simulate Enter key)
        """
        if not self.running:
            return
        
        if add_newline and not command.endswith('\n'):
            command += '\n'
        
        try:
            if self.system in ["Linux", "Darwin"]:
                # Unix-like systems
                if self.master_fd:
                    os.write(self.master_fd, command.encode('utf-8'))
            else:
                # Windows
                if self.stdin:
                    self.stdin.write(command)
                    self.stdin.flush()
        except Exception as e:
            if self.on_error:
                self.on_error(f"Error sending command: {e}")
    
    def send_key(self, key: str):
        """
        Send a special key to the terminal
        
        Args:
            key: Key name (e.g., 'Enter', 'Tab', 'Ctrl+C', etc.)
        """
        key_map = {
            'Enter': '\n',
            'Tab': '\t',
            'Backspace': '\b',
            'Escape': '\x1b',
            'Ctrl+C': '\x03',
            'Ctrl+D': '\x04',
            'Ctrl+Z': '\x1a',
            'Up': '\x1b[A',
            'Down': '\x1b[B',
            'Right': '\x1b[C',
            'Left': '\x1b[D',
            'Home': '\x1b[H',
            'End': '\x1b[F',
            'PageUp': '\x1b[5~',
            'PageDown': '\x1b[6~',
            'Delete': '\x1b[3~',
            'Insert': '\x1b[2~'
        }
        
        if key in key_map:
            self.send_command(key_map[key], add_newline=False)
    
    def get_output(self, timeout: float = 0.1) -> Optional[str]:
        """
        Get output from the terminal
        
        Args:
            timeout: Timeout in seconds
        
        Returns:
            Output string or None if no output available
        """
        try:
            return self.output_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def clear_output(self):
        """Clear the output queue"""
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except queue.Empty:
                break
    
    def resize_terminal(self, rows: int = 24, cols: int = 80):
        """
        Resize the terminal window
        
        Args:
            rows: Number of rows
            cols: Number of columns
        """
        if self.system in ["Linux", "Darwin"] and self.master_fd:
            # Set terminal size for Unix-like systems
            winsize = struct.pack('HHHH', rows, cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
    
    def stop_terminal(self):
        """Stop the terminal session"""
        self.running = False
        
        if self.process:
            try:
                if self.system == "Windows":
                    self.process.terminate()
                else:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except:
                pass
            
            self.process.wait(timeout=5)
            self.process = None
        
        if self.master_fd:
            os.close(self.master_fd)
            self.master_fd = None
        
        if self.slave_fd:
            os.close(self.slave_fd)
            self.slave_fd = None
    
    def is_running(self) -> bool:
        """Check if terminal is running"""
        return self.running and self.process and self.process.poll() is None
    
    def wait_for_prompt(self, prompt_pattern: str = "$", timeout: float = 5.0) -> bool:
        """
        Wait for a specific prompt pattern in the output
        
        Args:
            prompt_pattern: Pattern to wait for
            timeout: Maximum time to wait
        
        Returns:
            True if prompt found, False if timeout
        """
        start_time = time.time()
        buffer = ""
        
        while time.time() - start_time < timeout:
            output = self.get_output(0.1)
            if output:
                buffer += output
                if prompt_pattern in buffer:
                    return True
        
        return False
    
    def execute_and_wait(self, command: str, timeout: float = 10.0) -> str:
        """
        Execute a command and wait for output
        
        Args:
            command: Command to execute
            timeout: Maximum time to wait for output
        
        Returns:
            Collected output
        """
        self.clear_output()
        self.send_command(command)
        
        output = ""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            chunk = self.get_output(0.1)
            if chunk:
                output += chunk
            elif output:  # Got some output and now it's quiet
                break
        
        return output


if __name__ == "__main__":
    # Test the terminal controller
    controller = TerminalController()
    
    print(f"System: {controller.system}")
    print(f"Available terminals: {controller.get_available_terminals()}")
    
    # Set up output callback
    def on_output(text):
        print(f"Terminal output: {text}", end='')
    
    controller.on_output = on_output
    
    # Start a terminal
    if controller.start_terminal():
        print("Terminal started successfully!")
        
        # Send a test command
        time.sleep(2)
        controller.send_command("echo 'Hello from Voice Control!'")
        
        # Wait for a bit
        time.sleep(2)
        
        # Stop the terminal
        controller.stop_terminal()
        print("Terminal stopped.")
    else:
        print("Failed to start terminal.")