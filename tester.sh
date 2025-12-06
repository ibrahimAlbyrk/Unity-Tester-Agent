#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"

# Help message
show_help() {
    echo ""
    echo -e "${CYAN}${BOLD}Unity Test Agent${NC}"
    echo -e "${CYAN}────────────────${NC}"
    echo ""
    echo -e "${BOLD}Usage:${NC}"
    echo -e "  ./tester.sh <project-path> [options]"
    echo ""
    echo -e "${BOLD}Examples:${NC}"
    echo -e "  ${CYAN}./tester.sh /path/to/unity/project${NC}"
    echo -e "  ${CYAN}./tester.sh ./MyGame -j${NC}                    # JSON output"
    echo -e "  ${CYAN}./tester.sh ./MyGame -i${NC}                    # Interactive mode"
    echo -e "  ${CYAN}./tester.sh ./MyGame --group player${NC}        # Run test group"
    echo -e "  ${CYAN}./tester.sh ./MyGame --verify-fix TestName${NC} # Verify fix"
    echo ""
    echo -e "${BOLD}Output Modes:${NC}"
    echo -e "  ${GREEN}-j, --json${NC}           JSON output only (for agents)"
    echo -e "  ${GREEN}-i, --interactive${NC}    Interactive TUI mode"
    echo -e "  ${GREEN}--with-context${NC}       Include detailed error context"
    echo ""
    echo -e "${BOLD}Test Options:${NC}"
    echo -e "  ${GREEN}--platform${NC}           EditMode | PlayMode (default: EditMode)"
    echo -e "  ${GREEN}--filter${NC}             Test filter pattern (e.g., 'PlayerTests.*')"
    echo -e "  ${GREEN}--group${NC}              Run test group(s) (comma-separated)"
    echo -e "  ${GREEN}--list-groups${NC}        List available test groups"
    echo -e "  ${GREEN}--retries N${NC}          Retry failed tests N times"
    echo ""
    echo -e "${BOLD}Agent Features:${NC}"
    echo -e "  ${GREEN}--verify-fix TESTS${NC}   Verify fix for specific test(s)"
    echo -e "  ${GREEN}--export-deps PATH${NC}   Export dependency graph to JSON"
    echo -e "  ${GREEN}--show-deps CLASS${NC}    Show dependencies for a class"
    echo ""
    echo -e "${BOLD}Other:${NC}"
    echo -e "  ${GREEN}--junit PATH${NC}         Export JUnit XML"
    echo -e "  ${GREEN}--show-trends${NC}        Show pass rate trends"
    echo -e "  ${GREEN}--diff${NC}               Show diff vs previous run"
    echo -e "  ${GREEN}--no-cache${NC}           Disable cache"
    echo -e "  ${GREEN}--clear-cache${NC}        Clear cache before run"
    echo -e "  ${GREEN}--init${NC}               Create default config"
    echo ""
}

# Check if help requested
if [[ "$1" == "--help" || "$1" == "-h" || -z "$1" ]]; then
    show_help
    exit 0
fi

# Check if project path is provided
PROJECT_PATH="$1"
shift  # Remove first argument, keep the rest as options

# Validate project path
if [[ ! -d "$PROJECT_PATH" ]]; then
    echo -e "${RED}Error:${NC} Project path does not exist: ${PROJECT_PATH}"
    echo -e "Usage: ${CYAN}./tester.sh /path/to/unity/project [options]${NC}"
    exit 1
fi

# Check for Unity project markers
if [[ ! -d "${PROJECT_PATH}/Assets" ]]; then
    echo -e "${YELLOW}Warning:${NC} No 'Assets' folder found. Is this a Unity project?"
fi

# Activate virtual environment if exists
if [[ -d "$VENV_DIR" ]]; then
    source "${VENV_DIR}/bin/activate"
fi

# Check if dependencies are installed
if ! python3 -c "import rich" 2>/dev/null; then
    echo -e "${YELLOW}Dependencies not installed. Running setup...${NC}"
    echo ""
    "${SCRIPT_DIR}/setup.sh"
    echo ""

    # Re-activate venv after setup
    if [[ -d "$VENV_DIR" ]]; then
        source "${VENV_DIR}/bin/activate"
    fi
fi

# Run the test agent
exec python3 "${SCRIPT_DIR}/main.py" -p "$PROJECT_PATH" "$@"
