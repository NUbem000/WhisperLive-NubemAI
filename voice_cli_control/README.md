# 🎙️ Voice CLI Control

**Voice-controlled terminal interface for AI CLIs** - Control Claude, Gemini, ChatGPT and other AI CLIs using your voice!

## ✨ Features

- 🎤 **Voice Control**: Speak commands naturally to control any AI CLI
- 🤖 **Multi-CLI Support**: Works with Claude, Gemini, ChatGPT, Copilot, Ollama, and more
- 💻 **Cross-Platform**: Supports Windows, macOS, and Linux
- 🔄 **Real-time Transcription**: Powered by OpenAI Whisper for accurate speech recognition
- ⚡ **Smart Triggers**: Say "enter" to submit commands, "tab" for completion, etc.
- 🎯 **Terminal Selection**: Choose your preferred terminal emulator
- 🔧 **Customizable**: Add custom voice triggers and commands
- 💾 **Persistent Settings**: Saves your preferences between sessions

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/NUbem000/WhisperLive-NubemAI.git
cd WhisperLive-NubemAI

# Switch to voice control branch
git checkout feature/voice-cli-control

# Install dependencies
pip install -r requirements/voice-cli.txt
```

### Basic Usage

```bash
# Run the voice CLI control
python -m voice_cli_control.main

# With specific options
python -m voice_cli_control.main --model base --language en --cli claude

# List available CLIs
python -m voice_cli_control.main --list-clis

# List available terminals
python -m voice_cli_control.main --list-terminals
```

## 🎯 Voice Commands

### Basic Commands
- **Text Input**: Simply speak what you want to type
- **"enter"** or **"press enter"**: Submit the command (↵)
- **"tab"** or **"press tab"**: Tab completion
- **"backspace"**: Delete last character
- **"clear screen"**: Clear the terminal

### Navigation
- **"up arrow"**: Previous command in history
- **"down arrow"**: Next command in history
- **"left arrow"**: Move cursor left
- **"right arrow"**: Move cursor right
- **"home"**: Go to beginning of line
- **"end"**: Go to end of line

### Control Commands
- **"control c"**: Interrupt current operation (Ctrl+C)
- **"control d"**: Exit/EOF (Ctrl+D)
- **"control z"**: Suspend process (Ctrl+Z)
- **"escape"**: Escape key

### Recording Control
- **"stop recording"**: Pause voice recognition
- **"start recording"**: Resume voice recognition
- **"pause recording"**: Temporarily pause

### Punctuation
- **"period"** or **"dot"**: .
- **"comma"**: ,
- **"question mark"**: ?
- **"exclamation mark"**: !
- **"colon"**: :
- **"semicolon"**: ;
- **"quote"**: "
- **"single quote"**: '
- **"slash"**: /
- **"backslash"**: \
- **"space"**: (space character)

## 📋 Supported AI CLIs

| CLI | Description | Installation |
|-----|-------------|--------------|
| **Claude** | Anthropic's Claude AI | [GitHub](https://github.com/anthropics/claude-cli) |
| **Gemini** | Google's Gemini AI | [Cloud SDK](https://cloud.google.com/sdk) |
| **ChatGPT** | OpenAI's ChatGPT | [GitHub](https://github.com/openai/openai-cli) |
| **Copilot** | GitHub Copilot CLI | [GitHub](https://github.com/github/copilot-cli) |
| **Ollama** | Local LLM runner | [Ollama.ai](https://ollama.ai) |
| **Mistral** | Mistral AI | [Mistral.ai](https://mistral.ai) |
| **Perplexity** | Perplexity AI | [Perplexity.ai](https://perplexity.ai) |

## 🖥️ Supported Terminals

### Linux
- GNOME Terminal
- Konsole (KDE)
- xterm
- Terminator
- Alacritty
- Kitty
- Tilix

### macOS
- Terminal.app
- iTerm2
- Alacritty
- Kitty
- Hyper

### Windows
- Command Prompt (cmd)
- PowerShell
- Windows Terminal
- ConEmu
- Cmder

## ⚙️ Configuration

Configuration is saved in `~/.voice_cli_control/config.json`:

```json
{
  "selected_cli": "claude",
  "selected_terminal": "gnome-terminal",
  "voice_settings": {
    "model": "base",
    "language": "en",
    "silence_threshold": 2.0
  }
}
```

### Whisper Models

| Model | Size | RAM | Speed | Accuracy |
|-------|------|-----|-------|----------|
| tiny | 39M | ~1GB | ⚡⚡⚡⚡⚡ | ★★☆☆☆ |
| base | 74M | ~1GB | ⚡⚡⚡⚡ | ★★★☆☆ |
| small | 244M | ~2GB | ⚡⚡⚡ | ★★★★☆ |
| medium | 769M | ~5GB | ⚡⚡ | ★★★★★ |
| large | 1550M | ~10GB | ⚡ | ★★★★★ |

## 🔧 Advanced Usage

### Custom Voice Triggers

```python
from voice_cli_control import VoiceController

controller = VoiceController()

# Add custom trigger
controller.add_custom_trigger("submit", "Enter")
controller.add_custom_trigger("cancel", "Ctrl+C")
controller.add_custom_trigger("save", "Ctrl+S")

# Save settings
controller.save_settings()
```

### Programmatic Control

```python
from voice_cli_control import VoiceCLIApp

app = VoiceCLIApp()

# Configure
app.selected_cli = "claude"
app.selected_terminal = "gnome-terminal"
app.voice_controller.model = "small"
app.voice_controller.language = "es"

# Run
app.main()
```

## 🐛 Troubleshooting

### No CLIs Detected
1. Ensure the CLI is installed and in PATH
2. Try running the CLI command manually
3. Check installation with `which claude` (Linux/Mac) or `where claude` (Windows)

### Voice Not Working
1. Check microphone permissions
2. Ensure PyAudio is installed: `pip install pyaudio`
3. Test microphone: `python -m speech_recognition`

### Terminal Not Opening
1. Verify terminal is installed
2. Check terminal command works manually
3. Try a different terminal emulator

### Poor Transcription
1. Use a better Whisper model (small/medium)
2. Reduce background noise
3. Speak clearly and at normal pace
4. Check language setting matches your speech

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Ensure all tests pass
5. Submit a pull request

## 📝 License

MIT License - see [LICENSE](../LICENSE) file

## 🙏 Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) for speech recognition
- [Rich](https://github.com/Textualize/rich) for beautiful terminal UI
- All the AI CLI tools that make this integration possible

## 📞 Support

- 🐛 Issues: [GitHub Issues](https://github.com/NUbem000/WhisperLive-NubemAI/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/NUbem000/WhisperLive-NubemAI/discussions)
- 📧 Email: support@nubem.ai

---

Built with ❤️ by NubemAI Team