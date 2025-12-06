# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Unity Test Agent - CLI tool for compiling and running Unity project tests with rich terminal UI. Python 3.10+, uses `rich` for CLI rendering and `pyyaml` for config.

## Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Run against a Unity project
python main.py -p /path/to/unity/project

# Run with JSON output only
python main.py -p /path/to/project -j

# Run interactive TUI mode
python main.py -p /path/to/project -i

# Run tests
pytest

# Create default config in Unity project
python main.py -p /path/to/project --init
```

## Architecture

### Entry Point
`main.py` - CLI argument parsing and three run modes:
- `run_json_mode()` - JSON-only output
- `run_ui_mode()` - Rich CLI with progress/results
- `run_interactive_mode()` - Full TUI with navigation

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

### Data Flow
```
CLI Args + .unity-agent.yaml → Config → Pipeline
Pipeline → UnityResult (success, stage, errors/results, metrics)
UnityResult → CLIRenderer or JSON output
```

### Storage
Projects get `.unity-agent/` directory with:
- `cache/` - Compilation cache
- `trends/` - Historical data
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
```
