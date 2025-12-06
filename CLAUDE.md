# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Unity Test Agent - CLI tool for compiling and running Unity project tests with rich terminal UI. Python 3.10+, uses `rich` for CLI rendering and `pyyaml` for config.

## Commands

```bash
# Setup (one-time)
./setup.sh

# Run tests
./tester.sh /path/to/unity/project
./tester.sh /path/to/project -j    # JSON output
./tester.sh /path/to/project -i    # Interactive TUI

# Presets (shortcuts for common workflows)
./tester.sh agent                  # -j --with-context (for AI agents)
./tester.sh debug                  # -i --retries 3 --with-context
./tester.sh ci                     # -j --show-trends --junit results.xml
./tester.sh /path/to/project agent # with explicit path

# Run project tests (pytest)
pytest

# Config management
./tester.sh /path/to/project --init        # Create default config
./tester.sh /path/to/project --wizard      # Interactive setup wizard
./tester.sh /path/to/project --show-config # Show effective merged config

# Test groups
./tester.sh /path/to/project --group player
./tester.sh /path/to/project --group player,inventory
./tester.sh /path/to/project --list-groups

# Dependency graph
./tester.sh /path/to/project --export-deps deps.json
./tester.sh /path/to/project --show-deps PlayerController

# Fix verification (for agents) - MUST use full test names
./tester.sh /path/to/project --verify-fix "Namespace.Class.TestMethod" -j
./tester.sh /path/to/project --verify-fix "Tests.PlayerMoveTest,Tests.PlayerJumpTest" -j

# Detailed error context (for agents)
./tester.sh /path/to/project --with-context
./tester.sh /path/to/project --with-context -j

# Trends and diff in JSON mode
./tester.sh /path/to/project --show-trends -j  # adds "trends" array
./tester.sh /path/to/project --diff -j         # adds "diff" object

# Cache operations
./tester.sh /path/to/project --clear-cache     # prints "Cache cleared"
./tester.sh /path/to/project --clear-cache -j  # returns {"cache_cleared": true}

# Test groups (exits with error if group not found, shows available groups)
./tester.sh /path/to/project --group player    # runs player group tests
./tester.sh /path/to/project --group unknown   # error + suggestions + exit 1
```

## Architecture

### Entry Point
`main.py` - CLI argument parsing and run modes:
- `run_json_mode()` - JSON-only output
- `run_ui_mode()` - Rich CLI with progress/results
- `run_interactive_mode()` - Full TUI with navigation (shows keybindings banner)
- `run_verify_fix()` - Fix verification mode
- `run_list_groups()` - Show test groups
- `run_export_deps()` - Export dependency graph
- `run_show_deps()` - Show class dependencies
- `run_show_config()` - Show effective merged config
- `run_setup_wizard()` - Interactive config creation (in `config.py`)

Note: `main.py` supports both positional and `-p` flag for project path:
```bash
python main.py ./project        # positional
python main.py -p ./project     # flag
```

### Core Pipeline (`run_pipeline`)
1. **Editor Detection** - `version.py:detect_unity_editor()` reads `ProjectSettings/ProjectVersion.txt`
2. **Compilation** - `compiler.py:compile_project()` runs Unity in batchmode, parses CS errors
3. **Test Execution** - `test_runner.py:run_tests()` runs Unity tests, parses NUnit XML

### Module Structure (`unity_agent/`)
- `models.py` - Dataclasses: `UnityResult`, `TestResults`, `CompilationError`, `PerformanceMetrics`
- `config.py` - YAML config loading, `run_setup_wizard()` for interactive setup
- `cache.py` - Compilation result caching in `.unity-agent/cache/`
- `trends.py` - Historical pass rate tracking in `.unity-agent/trends/`
- `retry.py` - Flaky test detection with configurable retries
- `cli.py` - `CLIRenderer` class for rich terminal output
- `interactive.py` - TUI navigation for results exploration
- `reports/` - JUnit export (`junit.py`) and diff comparison (`diff.py`)
- `groups.py` - Semantic test grouping, `suggest_similar()` for typo suggestions
- `deps.py` - Dependency graph analysis and export
- `verify.py` - Fix verification for agents
- `error_context.py` - Structured error context with suggested fixes

### Data Flow
```
CLI Args + .unity-agent.yaml → Config → Pipeline
Pipeline → UnityResult (success, stage, errors/results, metrics)
UnityResult → CLIRenderer or JSON output
```

### Storage
Projects get `.unity-agent/` directory with:
- `cache/` - Compilation cache
- `trends/` - Historical data + failed_details.json
- `results/` - Test result artifacts

## Config File Format

`.unity-agent.yaml` in project root (minimal template from `--init`):
```yaml
project:
  # editor_path: null  # auto-detect from ProjectVersion.txt

test:
  platform: "EditMode"  # EditMode | PlayMode
  retries: 0

cache:
  enabled: true

trends:
  enabled: true

# test_groups:
#   player: ["PlayerTests.*"]
#   inventory: ["InventoryTests.*"]
```

Use `--wizard` for interactive config creation, `--show-config` to view merged config.

## Agent Integration

### Structured Error Context
Use `--with-context` flag for detailed error analysis:
```json
{
  "error_type": "NullReferenceException",
  "file": "Assets/Scripts/Player.cs",
  "line": 42,
  "code_snippet": ">>> 42 | obj.Method()",
  "related_tests": ["PlayerTest", "MoveTest"],
  "suggested_fix": "Add null check before access"
}
```

### Fix Verification
After fixing a test, verify with **full test name** (Namespace.Class.Method):
```bash
./tester.sh /project --verify-fix "MyGame.Tests.PlayerMoveTest" -j
```
Returns:
```json
{
  "verify_results": [{
    "test_name": "MyGame.Tests.PlayerMoveTest",
    "passed": true,
    "is_fixed": true,
    "was_failing": true
  }],
  "all_fixed": true
}
```

**Important**: Short names return "Test not found" error:
```json
{
  "verify_results": [{
    "test_name": "PlayerMoveTest",
    "passed": false,
    "current_error": "Test not found. Use full test name (e.g., Namespace.Class.Method)"
  }]
}
```

### Dependency Graph
Export for impact analysis:
```bash
./tester.sh /project --export-deps deps.json
```
Query affected tests:
```python
from unity_agent.deps import get_affected_tests_for_files
tests = get_affected_tests_for_files(project, ["Assets/Scripts/Player.cs"])
```
