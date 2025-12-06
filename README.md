<p align="center">
  <img src="https://img.shields.io/badge/Unity-000000?style=for-the-badge&logo=unity&logoColor=white" alt="Unity"/>
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/CLI-Rich-FF6B6B?style=for-the-badge" alt="Rich CLI"/>
</p>

<h1 align="center">
  <br>
  Unity Test Agent
  <br>
</h1>

<h4 align="center">
  Headless Unity test runner with beautiful CLI output — perfect for AI agents & CI/CD
</h4>

<p align="center">
  <a href="#-key-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-usage">Usage</a> •
  <a href="#-for-ai-agents">For AI Agents</a> •
  <a href="#-configuration">Config</a>
</p>

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Auto Editor Detection** | Finds Unity editor from `ProjectVersion.txt` |
| **Smart Caching** | Skip recompilation when scripts unchanged |
| **Flaky Test Detection** | Auto-retry failed tests, detect inconsistent tests |
| **Trend Tracking** | Historical pass rate tracking with sparkline charts |
| **Test Grouping** | Semantic grouping by feature (player, inventory, etc.) |
| **Dependency Graph** | Know which tests are affected by code changes |
| **Fix Verification** | Binary pass/fail for agent fix validation |
| **Error Context** | Structured errors with suggested fixes |
| **JUnit Export** | CI/CD compatible test reports |
| **Rich Terminal UI** | Beautiful progress bars, tables, and panels |
| **Interactive TUI** | Navigate results, inspect failures, retry tests |
| **JSON Output** | Machine-readable output for automation |

---

## Quick Start

```bash
# Setup (one-time)
./setup.sh

# Set your project (one-time)
./tester.sh --set /path/to/unity/project

# Run tests (uses saved project)
./tester.sh

# Interactive mode
./tester.sh -i

# JSON output (for agents)
./tester.sh -j

# Show help
./tester.sh --help
```

### Project Management

```bash
# Save project path
./tester.sh --set /path/to/unity/project

# Show current project
./tester.sh --current

# Clear saved project
./tester.sh --clear

# One-time different project (doesn't change saved)
./tester.sh /other/project -j
```

### Alternative (pip)

```bash
pip install -e .
python main.py -p /path/to/unity/project
```

---

## Usage

### Basic Commands

```bash
# Run EditMode tests (default)
python main.py -p ./MyUnityProject

# Run PlayMode tests
python main.py -p ./MyUnityProject --platform PlayMode

# Filter specific tests
python main.py -p ./MyUnityProject --filter "PlayerTests.*"

# Export JUnit XML
python main.py -p ./MyUnityProject --junit ./results.xml
```

### Output Modes

| Mode | Flag | Best For |
|------|------|----------|
| **Rich UI** | (default) | Human developers |
| **Interactive** | `-i` | Exploring failures |
| **JSON** | `-j` | AI agents, scripts |

### Retry & Flaky Detection

```bash
# Retry failed tests up to 3 times
python main.py -p ./MyProject --retries 3

# Set flaky threshold (default 0.3)
python main.py -p ./MyProject --retries 3 --flaky-threshold 0.5
```

### Test Groups

Run tests by semantic group:

```bash
# Run player-related tests
python main.py -p ./MyProject --group player

# Run multiple groups
python main.py -p ./MyProject --group player,inventory

# List available groups
python main.py -p ./MyProject --list-groups
```

Configure in `.unity-agent.yaml`:
```yaml
test_groups:
  player:
    - "PlayerTests.*"
    - "InputTests.Player*"
  inventory:
    - "InventoryTests.*"
```

### Dependency Graph

Analyze which tests are affected by code changes:

```bash
# Export full dependency graph
python main.py -p ./MyProject --export-deps deps.json

# Show deps for a specific class
python main.py -p ./MyProject --show-deps PlayerController
```

Output:
```
PlayerController
File: Assets/Scripts/Player/PlayerController.cs
Namespace: Game.Player

Affected Tests (5):
  • PlayerMoveTest
  • PlayerJumpTest
  • PlayerHealthTest
  ...
```

### Caching

```bash
# Disable cache
python main.py -p ./MyProject --no-cache

# Clear cache before run
python main.py -p ./MyProject --clear-cache
```

### Trends & Diff

```bash
# Show historical pass rate trend
python main.py -p ./MyProject --show-trends

# Show diff vs previous run
python main.py -p ./MyProject --diff
```

---

## For AI Agents

Unity Test Agent is designed to work seamlessly with AI coding agents. The JSON output provides structured, parseable results perfect for autonomous workflows.

### Why It's Perfect for Agents

```
Traditional Unity Testing          Unity Test Agent
─────────────────────────────────────────────────────
  GUI-dependent                     Fully headless
  Unstructured logs                 Structured JSON
  Manual result parsing             Machine-readable
  No caching                        Smart compilation
  Flaky tests break CI              Auto-retry & detect
  No fix validation                 Verify-fix mode
  No impact analysis                Dependency graph
```

### Structured Error Context

Get detailed error analysis for intelligent fixing:

```bash
python main.py -p ./MyProject --with-context -j
```

```json
{
  "test_results": {
    "failed_tests": [{
      "name": "PlayerMoveTest",
      "message": "NullReferenceException",
      "context": {
        "error_type": "NullReferenceException",
        "file": "Assets/Scripts/Player.cs",
        "line": 42,
        "code_snippet": ">>> 42 |     player.Move(direction);",
        "related_tests": ["PlayerJumpTest", "PlayerIdleTest"],
        "suggested_fix": "Add null check before accessing the object"
      }
    }]
  }
}
```

### Fix Verification

Verify if your fix worked:

```bash
python main.py -p ./MyProject --verify-fix "PlayerMoveTest" -j
```

```json
{
  "verify_results": [{
    "test_name": "PlayerMoveTest",
    "passed": true,
    "previous_error": "NullReferenceException at line 42",
    "current_error": null,
    "is_fixed": true
  }],
  "all_fixed": true,
  "summary": "Fixed 1/1 previously failing test(s). All fixes verified!"
}
```

### Impact Analysis

Know which tests to run after code changes:

```python
from unity_agent.deps import get_affected_tests_for_files

# After modifying PlayerController.cs
affected = get_affected_tests_for_files(
    "./MyProject",
    ["Assets/Scripts/PlayerController.cs"]
)
# Returns: ["PlayerMoveTest", "PlayerJumpTest", "PlayerHealthTest"]
```

### JSON Output Example

```bash
python main.py -p ./MyProject -j
```

```json
{
  "success": false,
  "stage": "tests",
  "test_results": {
    "total": 42,
    "passed": 40,
    "failed": 2,
    "warnings": 1,
    "failed_tests": [
      {
        "name": "Tests.PlayerMovementTests.TestJump",
        "message": "Expected: 5.0, Actual: 4.8",
        "stack_trace": "...",
        "duration": 0.023
      }
    ]
  },
  "performance": {
    "editor_detect_ms": 12.5,
    "compile_ms": 3420.1,
    "test_run_ms": 8234.7,
    "total_ms": 11667.3
  }
}
```

### Agent Workflow Example

```python
import subprocess
import json

def run_tests(project_path, with_context=False):
    cmd = ["python", "main.py", "-p", project_path, "-j"]
    if with_context:
        cmd.append("--with-context")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)

def verify_fix(project_path, test_name):
    result = subprocess.run([
        "python", "main.py", "-p", project_path,
        "--verify-fix", test_name, "-j"
    ], capture_output=True, text=True)
    return json.loads(result.stdout)

# 1. Run tests with context
data = run_tests("./MyProject", with_context=True)

if not data["success"]:
    for test in data["test_results"]["failed_tests"]:
        ctx = test.get("context", {})
        print(f"Fix: {test['name']}")
        print(f"File: {ctx.get('file')}:{ctx.get('line')}")
        print(f"Suggestion: {ctx.get('suggested_fix')}")

        # ... apply fix ...

        # 2. Verify the fix
        verify = verify_fix("./MyProject", test["name"])
        if verify["all_fixed"]:
            print("Fix verified!")
```

### Use Cases for AI Agents

| Scenario | How Unity Test Agent Helps |
|----------|---------------------------|
| **Code Generation** | Validate generated code compiles & tests pass |
| **Bug Fixing** | Get structured errors with suggested fixes |
| **Refactoring** | Use dependency graph for impact analysis |
| **Fix Validation** | Binary verify-fix for autonomous confirmation |
| **CI/CD Integration** | JUnit export for pipeline reporting |
| **Feature Testing** | Run test groups by feature area |

---

## Configuration

Create `.unity-agent.yaml` in your project root:

```bash
python main.py -p ./MyProject --init
```

### Config File

```yaml
project:
  editor_path: null  # auto-detect

test:
  platform: "EditMode"  # EditMode | PlayMode
  filter: null          # e.g., "PlayerTests.*"
  retries: 0
  flaky_threshold: 0.3

cache:
  enabled: true
  ttl: 3600  # seconds

trends:
  enabled: true
  max_history: 100

test_groups:
  player:
    - "PlayerTests.*"
    - "InputTests.Player*"
  inventory:
    - "InventoryTests.*"
  combat:
    - "CombatTests.*"
```

---

## CLI Reference

```
usage: main.py -p PROJECT_PATH [options]

Required:
  -p, --project-path     Unity project path

Output:
  -j, --json             JSON output only
  -i, --interactive      Interactive TUI mode
  --with-context         Include error context

Test Options:
  --platform             EditMode | PlayMode (default: EditMode)
  --filter               Test filter pattern
  --group                Run test group(s)
  --list-groups          List available groups
  --retries N            Retry failed tests N times
  --flaky-threshold      Flaky detection threshold (0.0-1.0)

Agent Features:
  --verify-fix TESTS     Verify fix for test(s)
  --export-deps PATH     Export dependency graph
  --show-deps CLASS      Show class dependencies

Cache:
  --no-cache             Disable cache
  --clear-cache          Clear cache before run

Trends:
  --show-trends          Show pass rate trends
  --diff                 Show diff vs previous run

Other:
  --junit PATH           Export JUnit XML
  --init                 Create default config
```

---

## Project Structure

```
MyUnityProject/
├── .unity-agent.yaml      # Config file
└── .unity-agent/
    ├── cache/             # Compilation cache
    ├── trends/            # Historical data
    │   ├── history.json   # Pass rate history
    │   └── failed_details.json  # For verify-fix
    └── results/           # Test artifacts
```

---

## Requirements

- **Python** 3.10+
- **Unity** 2019.4+ (any LTS version)
- **Dependencies**: `rich`, `pyyaml`

---

## License

MIT

---

<p align="center">
  Built for developers who automate everything
</p>
