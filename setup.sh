#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Symbols
CHECK="${GREEN}✓${NC}"
CROSS="${RED}✗${NC}"
ARROW="${CYAN}→${NC}"
SPINNER="⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Header
print_header() {
    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}        ${BOLD}Unity Test Agent - Setup${NC}                          ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}        Headless Unity test runner for AI agents          ${CYAN}║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Spinner animation
spin() {
    local pid=$1
    local msg=$2
    local i=0
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  ${YELLOW}${SPINNER:i++%10:1}${NC} ${msg}"
        sleep 0.1
    done
    printf "\r"
}

# Step printer
step() {
    local step_num=$1
    local total=$2
    local msg=$3
    echo -e "  ${BLUE}[${step_num}/${total}]${NC} ${ARROW} ${msg}"
}

step_done() {
    local step_num=$1
    local total=$2
    local msg=$3
    echo -e "  ${BLUE}[${step_num}/${total}]${NC} ${CHECK} ${msg}"
}

step_fail() {
    local step_num=$1
    local total=$2
    local msg=$3
    echo -e "  ${BLUE}[${step_num}/${total}]${NC} ${CROSS} ${msg}"
}

# Check command exists
check_command() {
    command -v "$1" &> /dev/null
}

# Main setup
main() {
    print_header

    local total_steps=5
    local current_step=0

    # Step 1: Check Python
    ((current_step++))
    step $current_step $total_steps "Checking Python installation..."

    if check_command python3; then
        PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
        PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
        PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)

        if [[ "$PYTHON_MAJOR" -ge 3 && "$PYTHON_MINOR" -ge 10 ]]; then
            step_done $current_step $total_steps "Python ${PYTHON_VERSION} ${GREEN}(OK)${NC}"
        else
            step_fail $current_step $total_steps "Python ${PYTHON_VERSION} ${RED}(requires 3.10+)${NC}"
            echo -e "\n  ${RED}Error:${NC} Python 3.10 or higher is required"
            echo -e "  Install: ${CYAN}https://www.python.org/downloads/${NC}\n"
            exit 1
        fi
    else
        step_fail $current_step $total_steps "Python not found"
        echo -e "\n  ${RED}Error:${NC} Python 3 is not installed"
        echo -e "  Install: ${CYAN}https://www.python.org/downloads/${NC}\n"
        exit 1
    fi

    # Step 2: Check pip
    ((current_step++))
    step $current_step $total_steps "Checking pip..."

    if check_command pip3; then
        PIP_VERSION=$(pip3 --version 2>&1 | cut -d' ' -f2)
        step_done $current_step $total_steps "pip ${PIP_VERSION} ${GREEN}(OK)${NC}"
    else
        step_fail $current_step $total_steps "pip not found"
        echo -e "\n  ${RED}Error:${NC} pip is not installed"
        echo -e "  Install: ${CYAN}python3 -m ensurepip --upgrade${NC}\n"
        exit 1
    fi

    # Step 3: Create virtual environment (optional)
    ((current_step++))
    step $current_step $total_steps "Setting up virtual environment..."

    VENV_DIR="${SCRIPT_DIR}/.venv"

    if [[ -d "$VENV_DIR" ]]; then
        step_done $current_step $total_steps "Virtual environment exists ${GREEN}(OK)${NC}"
    else
        python3 -m venv "$VENV_DIR" 2>/dev/null &
        spin $! "Creating virtual environment..."

        if [[ -d "$VENV_DIR" ]]; then
            step_done $current_step $total_steps "Virtual environment created ${GREEN}(OK)${NC}"
        else
            step_fail $current_step $total_steps "Failed to create virtual environment"
            echo -e "  ${YELLOW}Warning:${NC} Continuing without virtual environment"
        fi
    fi

    # Activate venv if exists
    if [[ -d "$VENV_DIR" ]]; then
        source "${VENV_DIR}/bin/activate"
    fi

    # Step 4: Install dependencies
    ((current_step++))
    step $current_step $total_steps "Installing dependencies..."

    cd "$SCRIPT_DIR"

    pip3 install -e . -q 2>/dev/null &
    spin $! "Installing packages..."

    # Verify installation
    if python3 -c "import rich; import yaml" 2>/dev/null; then
        step_done $current_step $total_steps "Dependencies installed ${GREEN}(OK)${NC}"
    else
        # Retry with verbose
        pip3 install rich pyyaml -q 2>/dev/null
        if python3 -c "import rich; import yaml" 2>/dev/null; then
            step_done $current_step $total_steps "Dependencies installed ${GREEN}(OK)${NC}"
        else
            step_fail $current_step $total_steps "Failed to install dependencies"
            echo -e "\n  ${RED}Error:${NC} Could not install required packages"
            echo -e "  Try manually: ${CYAN}pip3 install rich pyyaml${NC}\n"
            exit 1
        fi
    fi

    # Step 5: Make scripts executable
    ((current_step++))
    step $current_step $total_steps "Setting up scripts..."

    chmod +x "${SCRIPT_DIR}/setup.sh" 2>/dev/null
    chmod +x "${SCRIPT_DIR}/tester.sh" 2>/dev/null

    step_done $current_step $total_steps "Scripts configured ${GREEN}(OK)${NC}"

    # Summary
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}                    ${BOLD}Setup Complete!${NC}                        ${GREEN}║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${BOLD}Quick Start:${NC}"
    echo -e "  ${CYAN}./tester.sh /path/to/unity/project${NC}"
    echo ""
    echo -e "  ${BOLD}Options:${NC}"
    echo -e "  ${CYAN}./tester.sh /path/to/project -j${NC}          # JSON output"
    echo -e "  ${CYAN}./tester.sh /path/to/project -i${NC}          # Interactive mode"
    echo -e "  ${CYAN}./tester.sh /path/to/project --help${NC}      # All options"
    echo ""
}

main "$@"
