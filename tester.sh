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
PROJECT_FILE="${SCRIPT_DIR}/.current-project"

# Help message
show_help() {
    echo ""
    echo -e "${CYAN}${BOLD}Unity Test Agent${NC}"
    echo -e "${CYAN}────────────────${NC}"
    echo ""
    echo -e "${BOLD}Usage:${NC}"
    echo -e "  ./tester.sh <project-path> [options]"
    echo -e "  ./tester.sh [options]                  ${CYAN}# uses saved project${NC}"
    echo -e "  ./tester.sh <project-path> <preset>    ${CYAN}# use a preset${NC}"
    echo ""
    echo -e "${BOLD}Presets:${NC} ${CYAN}(shortcuts for common workflows)${NC}"
    echo -e "  ${GREEN}agent${NC}      JSON + error context (for AI agents)"
    echo -e "  ${GREEN}debug${NC}      Interactive + retries + context"
    echo -e "  ${GREEN}ci${NC}         JSON + trends + JUnit export"
    echo -e "  ${GREEN}quick${NC}      Default settings, minimal output"
    echo ""
    echo -e "${BOLD}Project Management:${NC}"
    echo -e "  ${GREEN}--set <path>${NC}          Save project path for future use"
    echo -e "  ${GREEN}--current${NC}             Show current saved project"
    echo -e "  ${GREEN}--clear${NC}               Clear saved project path"
    echo ""
    echo -e "${BOLD}Examples:${NC}"
    echo -e "  ${CYAN}./tester.sh ./MyProject agent${NC}            # AI agent mode"
    echo -e "  ${CYAN}./tester.sh debug${NC}                        # Debug with saved project"
    echo -e "  ${CYAN}./tester.sh ci --platform PlayMode${NC}       # CI + extra options"
    echo -e "  ${CYAN}./tester.sh --set /path/to/project${NC}       # Save project"
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

# Get saved project path
get_saved_project() {
    if [[ -f "$PROJECT_FILE" ]]; then
        cat "$PROJECT_FILE"
    fi
}

# Save project path
save_project() {
    local path="$1"
    # Convert to absolute path
    local abs_path="$(cd "$path" 2>/dev/null && pwd)"
    if [[ -n "$abs_path" ]]; then
        echo "$abs_path" > "$PROJECT_FILE"
        echo -e "${GREEN}✓${NC} Project saved: ${CYAN}${abs_path}${NC}"
        echo -e "  Now you can run ${CYAN}./tester.sh${NC} without specifying path"
    else
        echo -e "${RED}✗${NC} Invalid path: ${path}"
        exit 1
    fi
}

# Show current project
show_current() {
    local saved=$(get_saved_project)
    if [[ -n "$saved" ]]; then
        echo -e "${BOLD}Current project:${NC} ${CYAN}${saved}${NC}"
        if [[ -d "$saved" ]]; then
            echo -e "${GREEN}✓${NC} Path exists"
        else
            echo -e "${YELLOW}⚠${NC} Path no longer exists"
        fi
    else
        echo -e "${YELLOW}No project saved.${NC}"
        echo -e "Use ${CYAN}./tester.sh --set /path/to/project${NC} to save one"
    fi
}

# Clear saved project
clear_project() {
    if [[ -f "$PROJECT_FILE" ]]; then
        rm "$PROJECT_FILE"
        echo -e "${GREEN}✓${NC} Saved project cleared"
    else
        echo -e "${YELLOW}No project was saved${NC}"
    fi
}

# Handle special commands
case "$1" in
    --help|-h)
        show_help
        exit 0
        ;;
    --set)
        if [[ -z "$2" ]]; then
            echo -e "${RED}Error:${NC} Please provide a project path"
            echo -e "Usage: ${CYAN}./tester.sh --set /path/to/project${NC}"
            exit 1
        fi
        save_project "$2"
        # Check if there are more args (e.g., --wizard)
        shift 2
        if [[ -z "$1" ]]; then
            exit 0
        fi
        # Continue with remaining args using saved project
        ;;
    --current)
        show_current
        exit 0
        ;;
    --clear)
        clear_project
        exit 0
        ;;
esac

# Expand preset to flags (bash 3 compatible)
expand_preset() {
    case "$1" in
        agent) echo "-j --with-context"; return 0 ;;
        debug) echo "-i --retries 3 --with-context"; return 0 ;;
        ci)    echo "-j --show-trends --junit results.xml"; return 0 ;;
        quick) echo ""; return 0 ;;
        *)     return 1 ;;
    esac
}

# Check if argument is a preset
is_preset() {
    case "$1" in
        agent|debug|ci|quick) return 0 ;;
        *) return 1 ;;
    esac
}

# Determine project path
PROJECT_PATH=""
ARGS=()
PRESET_ARGS=""

# Check if first argument is a preset (use saved project)
if [[ -n "$1" ]] && is_preset "$1"; then
    PRESET_ARGS=$(expand_preset "$1")
    shift
    PROJECT_PATH=$(get_saved_project)
    ARGS=("$@")
# Check if first argument looks like a path (not an option)
elif [[ -n "$1" && ! "$1" =~ ^- ]]; then
    PROJECT_PATH="$1"
    shift

    # Check if second arg is a preset
    if [[ -n "$1" ]] && is_preset "$1"; then
        PRESET_ARGS=$(expand_preset "$1")
        shift
    fi
    ARGS=("$@")
else
    # No path provided, use saved project
    PROJECT_PATH=$(get_saved_project)
    ARGS=("$@")
fi

# If still no project path, show help
if [[ -z "$PROJECT_PATH" ]]; then
    echo -e "${RED}Error:${NC} No project specified"
    echo ""
    echo -e "Either provide a path:"
    echo -e "  ${CYAN}./tester.sh /path/to/unity/project${NC}"
    echo ""
    echo -e "Or save a project first:"
    echo -e "  ${CYAN}./tester.sh --set /path/to/unity/project${NC}"
    echo -e "  ${CYAN}./tester.sh${NC}  # then run without path"
    echo ""
    exit 1
fi

# Validate project path
if [[ ! -d "$PROJECT_PATH" ]]; then
    echo -e "${RED}Error:${NC} Project path does not exist: ${PROJECT_PATH}"

    # If using saved project, suggest clearing
    if [[ -f "$PROJECT_FILE" ]]; then
        echo -e "  The saved project path may be outdated."
        echo -e "  Use ${CYAN}./tester.sh --clear${NC} to clear it"
    fi
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
if [[ -n "$PRESET_ARGS" ]]; then
    exec python3 "${SCRIPT_DIR}/main.py" -p "$PROJECT_PATH" $PRESET_ARGS "${ARGS[@]}"
else
    exec python3 "${SCRIPT_DIR}/main.py" -p "$PROJECT_PATH" "${ARGS[@]}"
fi
