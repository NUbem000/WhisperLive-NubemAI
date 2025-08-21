#!/bin/bash

# Voice CLI Control Installation Script
# For WhisperLive-NubemAI

set -e

echo "🎙️  Voice CLI Control Installer"
echo "================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check Python version
echo -e "${BLUE}Checking Python version...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is not installed!${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo -e "${GREEN}Python $PYTHON_VERSION found${NC}"

# Check for virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}Warning: Not in a virtual environment${NC}"
    read -p "Do you want to create a virtual environment? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Creating virtual environment...${NC}"
        python3 -m venv venv
        source venv/bin/activate
        echo -e "${GREEN}Virtual environment activated${NC}"
    fi
fi

# Install system dependencies based on OS
OS="$(uname -s)"
case "${OS}" in
    Linux*)
        echo -e "${BLUE}Installing Linux dependencies...${NC}"
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y portaudio19-dev python3-dev ffmpeg
        elif command -v yum &> /dev/null; then
            sudo yum install -y portaudio-devel python3-devel ffmpeg
        elif command -v pacman &> /dev/null; then
            sudo pacman -S --noconfirm portaudio python ffmpeg
        fi
        ;;
    Darwin*)
        echo -e "${BLUE}Installing macOS dependencies...${NC}"
        if command -v brew &> /dev/null; then
            brew install portaudio ffmpeg
        else
            echo -e "${YELLOW}Homebrew not found. Please install Homebrew first.${NC}"
            echo "Visit: https://brew.sh"
            exit 1
        fi
        ;;
    MINGW*|CYGWIN*|MSYS*)
        echo -e "${BLUE}Windows detected${NC}"
        echo -e "${YELLOW}Please ensure you have installed:${NC}"
        echo "  1. Visual Studio Build Tools or Visual Studio"
        echo "  2. FFmpeg (add to PATH)"
        echo "  3. Git Bash or WSL for better compatibility"
        read -p "Press Enter to continue..."
        ;;
    *)
        echo -e "${YELLOW}Unknown OS: ${OS}${NC}"
        ;;
esac

# Upgrade pip
echo -e "${BLUE}Upgrading pip...${NC}"
pip install --upgrade pip setuptools wheel

# Install Python dependencies
echo -e "${BLUE}Installing Python dependencies...${NC}"
pip install -r requirements/voice-cli.txt

# Download Whisper model
echo -e "${BLUE}Downloading Whisper model (base)...${NC}"
python -c "import whisper; whisper.load_model('base')"

# Create config directory
echo -e "${BLUE}Creating configuration directory...${NC}"
mkdir -p ~/.voice_cli_control

# Detect installed CLIs
echo -e "${BLUE}Detecting installed AI CLIs...${NC}"
python -m voice_cli_control.cli_detector

# Create desktop entry (Linux only)
if [[ "$OS" == "Linux"* ]]; then
    DESKTOP_FILE="$HOME/.local/share/applications/voice-cli-control.desktop"
    echo -e "${BLUE}Creating desktop entry...${NC}"
    mkdir -p "$HOME/.local/share/applications"
    cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Voice CLI Control
Comment=Control AI CLIs with your voice
Exec=$(pwd)/venv/bin/python -m voice_cli_control.main
Icon=$(pwd)/assets/voice-cli-icon.png
Terminal=true
Categories=Development;Utility;
EOF
    chmod +x "$DESKTOP_FILE"
    echo -e "${GREEN}Desktop entry created${NC}"
fi

# Create launcher script
echo -e "${BLUE}Creating launcher script...${NC}"
cat > voice-cli-control << 'EOF'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

python -m voice_cli_control.main "$@"
EOF

chmod +x voice-cli-control

echo ""
echo -e "${GREEN}✅ Installation complete!${NC}"
echo ""
echo "To run Voice CLI Control:"
echo -e "  ${BLUE}./voice-cli-control${NC}"
echo ""
echo "Or with options:"
echo -e "  ${BLUE}./voice-cli-control --model small --language en --cli claude${NC}"
echo ""
echo "For help:"
echo -e "  ${BLUE}./voice-cli-control --help${NC}"
echo ""
echo "Detected AI CLIs will be shown when you run the application."
echo ""
echo -e "${YELLOW}Note: Make sure your microphone is connected and working.${NC}"
echo ""
echo "Enjoy controlling AI CLIs with your voice! 🎤"