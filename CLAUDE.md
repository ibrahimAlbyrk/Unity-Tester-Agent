# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Unity Test Agent - CLI tool for compiling and running Unity project tests with rich terminal UI. Python 3.10+, uses `rich` for CLI rendering and `pyyaml` for config.

## Commands

```bash
# Setup (one-time)
./setup.sh

# Run tests via shell script
./tester.sh /path/to/unity/project
./tester.sh /path/to/project -j    # JSON
./tester.sh /path/to/project -i    # Interactive

# Or via Python directly
pip install -e ".[dev]"
python main.py -p /path/to/unity/project

# Run with JSON output only
python main.py -p /path/to/project -j

# Run interactive TUI mode
python main.py -p /path/to/project -i

# Run tests
pytest

# Create default config in Unity project
python main.py -p /path/to/project --init

# Test groups
python main.py -p /path/to/project --group player
python main.py -p /path/to/project --group player,inventory
python main.py -p /path/to/project --list-groups

# Dependency graph
python main.py -p /path/to/project --export-deps deps.json
python main.py -p /path/to/project --show-deps PlayerController

# Fix verification (for agents)
python main.py -p /path/to/project --verify-fix "PlayerMoveTest"
python main.py -p /path/to/project --verify-fix "Test1,Test2" -j

# Detailed error context (for agents)
python main.py -p /path/to/project --with-context
python main.py -p /path/to/project --with-context -j
```

## Architecture

### Entry Point
`main.py` - CLI argument parsing and run modes:
- `run_json_mode()` - JSON-only output
- `run_ui_mode()` - Rich CLI with progress/results
- `run_interactive_mode()` - Full TUI with navigation
- `run_verify_fix()` - Fix verification mode
- `run_list_groups()` - Show test groups
- `run_export_deps()` - Export dependency graph
- `run_show_deps()` - Show class dependencies

### Core Pipeline (`run_pipeline`)
1. **Editor Detection** - `version.py:detect_unity_editor()` reads `ProjectSettings/ProjectVersion.txt`
2. **Compilation** - `compiler.py:compile_project()` runs Unity in batchmode, parses CS errors
3. **Test Execution** - `test_runner.py:run_tests()` runs Unity tests, parses NUnit XML

### Module Structure (`unity_agent/`)
- `models.py` - Dataclasses: `UnityResult`, `TestResults`, `CompilationError`, `PerformanceMetrics`
- `config.py` - YAML config loading from `.unity-agent.yaml` (project or global)
- `cache.py` - Compilation result caching in `.unity-agent/cache/`
- `trends.py` - Historical pass rate tracking in `.unity-agent/trends/`
- `retry.py` - Flaky test detection with configurable retries
- `cli.py` - `CLIRenderer` class for rich terminal output
- `interactive.py` - TUI navigation for results exploration
- `reports/` - JUnit export (`junit.py`) and diff comparison (`diff.py`)
- `groups.py` - Semantic test grouping by feature
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

`.unity-agent.yaml` in project root:
```yaml
project:
  editor_path: null  # auto-detect from ProjectVersion.txt

test:
  platform: "EditMode"  # EditMode | PlayMode
  filter: null          # e.g., "PlayerTests.*"
  retries: 0
  flaky_threshold: 0.3

cache:
  enabled: true
  ttl: 3600

test_groups:
  player:
    - "PlayerTests.*"
    - "InputTests.Player*"
  inventory:
    - "InventoryTests.*"
```

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
After fixing a test, verify with:
```bash
python main.py -p /project --verify-fix "TestName" -j
```
Returns:
```json
{
  "verify_results": [{
    "test_name": "TestName",
    "passed": true,
    "is_fixed": true
  }],
  "all_fixed": true
}
```

### Dependency Graph
Export for impact analysis:
```bash
python main.py -p /project --export-deps deps.json
```
Query affected tests:
```python
from unity_agent.deps import get_affected_tests_for_files
tests = get_affected_tests_for_files(project, ["Assets/Scripts/Player.cs"])
```
