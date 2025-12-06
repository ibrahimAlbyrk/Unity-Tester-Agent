import re
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal


@dataclass
class ErrorContext:
    error_type: str
    file: str | None = None
    line: int | None = None
    code_snippet: str | None = None
    related_tests: list[str] = field(default_factory=list)
    error_history: list[dict] = field(default_factory=list)
    suggested_fix: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# Common fix suggestions by error type
FIX_SUGGESTIONS = {
    "NullReferenceException": "Add null check before accessing the object",
    "ArgumentNullException": "Validate input parameter is not null",
    "IndexOutOfRangeException": "Check array/list bounds before access",
    "KeyNotFoundException": "Use TryGetValue or ContainsKey before dictionary access",
    "InvalidOperationException": "Check object state before operation",
    "MissingReferenceException": "Ensure Unity object reference is assigned in Inspector",
    "MissingComponentException": "Add RequireComponent attribute or null check for GetComponent",
    "CS0103": "Check spelling or add missing using directive",
    "CS0246": "Add using directive or install missing package/assembly",
    "CS0117": "Method/property does not exist - check API docs for correct name",
    "CS0029": "Type mismatch - add explicit cast or convert types",
    "CS0266": "Cannot implicitly convert - use explicit cast",
    "CS1061": "Type does not contain method - check type and available methods",
    "CS0019": "Operator cannot be applied - check operand types",
}


def extract_code_snippet(file_path: str, line: int, context: int = 5) -> str | None:
    """Read source file and return lines around the error"""
    try:
        path = Path(file_path)
        if not path.exists():
            return None

        lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()

        start = max(0, line - context - 1)
        end = min(len(lines), line + context)

        snippet_lines = []
        for i in range(start, end):
            marker = ">>>" if i == line - 1 else "   "
            snippet_lines.append(f"{marker} {i + 1:4d} | {lines[i]}")

        return "\n".join(snippet_lines)
    except Exception:
        return None


def find_related_tests(project_path: str, class_name: str) -> list[str]:
    """Find tests that reference the given class"""
    assets_path = Path(project_path) / "Assets"
    test_dirs = ["Tests", "Editor/Tests", "PlayModeTests", "EditModeTests"]
    related = []

    pattern = re.compile(rf"\b{re.escape(class_name)}\b")

    for test_dir in test_dirs:
        test_path = assets_path / test_dir
        if not test_path.exists():
            continue

        for cs_file in test_path.rglob("*.cs"):
            try:
                content = cs_file.read_text(encoding='utf-8', errors='ignore')
                if pattern.search(content):
                    # Extract test method names
                    for match in re.finditer(r"\[(?:Unity)?Test\][^\n]*\n\s*public\s+\w+\s+(\w+)\s*\(", content):
                        related.append(match.group(1))
            except Exception:
                continue

    return list(set(related))


def get_error_history(project_path: str, error_signature: str, limit: int = 5) -> list[dict]:
    """Get past occurrences of similar errors from trends"""
    history_path = Path(project_path) / ".unity-agent" / "trends" / "history.json"
    if not history_path.exists():
        return []

    try:
        data = json.loads(history_path.read_text())
        matches = []

        for entry in reversed(data[-50:]):
            failed_names = entry.get("failed_test_names", [])
            for name in failed_names:
                if error_signature.lower() in name.lower():
                    matches.append({
                        "timestamp": entry.get("timestamp"),
                        "commit": entry.get("commit_hash"),
                        "test": name
                    })
                    break

            if len(matches) >= limit:
                break

        return matches
    except Exception:
        return []


def suggest_fix(error_type: str, message: str = "") -> str | None:
    """Suggest fix based on error type and message"""
    # Direct match
    if error_type in FIX_SUGGESTIONS:
        return FIX_SUGGESTIONS[error_type]

    # Partial match for exception types
    for key, suggestion in FIX_SUGGESTIONS.items():
        if key in error_type:
            return suggestion

    # Message-based suggestions
    msg_lower = message.lower()
    if "null" in msg_lower:
        return "Add null check before accessing the object"
    if "not found" in msg_lower or "does not exist" in msg_lower:
        return "Check spelling and ensure the resource/type exists"
    if "cannot convert" in msg_lower or "type mismatch" in msg_lower:
        return "Check types and add explicit cast if needed"

    return None


def extract_error_type(message: str) -> str:
    """Extract exception type from error message"""
    # Match patterns like "NullReferenceException:" or "[NullReferenceException]"
    patterns = [
        r"(\w+Exception):",
        r"\[(\w+Exception)\]",
        r"^(\w+Exception)",
        r"error\s+(CS\d+):",
    ]

    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            return match.group(1)

    return "Unknown"


def extract_file_location(stack_trace: str, project_path: str) -> tuple[str | None, int | None]:
    """Extract file path and line number from stack trace"""
    # Unity stack trace format: "at Namespace.Class.Method () [0x00000] in /path/file.cs:123"
    pattern = r"in\s+([^\s:]+\.cs):(\d+)"
    match = re.search(pattern, stack_trace)

    if match:
        file_path = match.group(1)
        line = int(match.group(2))

        # Make path relative to project if possible
        if project_path and file_path.startswith(project_path):
            file_path = str(Path(file_path).relative_to(project_path))

        return file_path, line

    return None, None


def build_error_context(
    message: str,
    stack_trace: str,
    project_path: str
) -> ErrorContext:
    """Build complete error context from test failure"""
    error_type = extract_error_type(message)
    file_path, line = extract_file_location(stack_trace, project_path)

    code_snippet = None
    related_tests = []

    if file_path:
        full_path = Path(project_path) / file_path if not Path(file_path).is_absolute() else file_path
        if line:
            code_snippet = extract_code_snippet(str(full_path), line)

        # Extract class name from file
        class_match = re.search(r"(\w+)\.cs$", str(file_path))
        if class_match:
            class_name = class_match.group(1)
            related_tests = find_related_tests(project_path, class_name)

    error_sig = f"{error_type}:{file_path or 'unknown'}"
    history = get_error_history(project_path, error_sig)

    return ErrorContext(
        error_type=error_type,
        file=file_path,
        line=line,
        code_snippet=code_snippet,
        related_tests=related_tests[:10],
        error_history=history,
        suggested_fix=suggest_fix(error_type, message)
    )


def build_compilation_error_context(
    error_code: str,
    file_path: str,
    line: int,
    message: str,
    project_path: str
) -> ErrorContext:
    """Build error context for compilation errors"""
    code_snippet = None
    full_path = Path(project_path) / file_path if not Path(file_path).is_absolute() else Path(file_path)

    if full_path.exists():
        code_snippet = extract_code_snippet(str(full_path), line)

    # Find class name
    class_match = re.search(r"(\w+)\.cs$", str(file_path))
    class_name = class_match.group(1) if class_match else None
    related_tests = find_related_tests(project_path, class_name) if class_name else []

    return ErrorContext(
        error_type=error_code,
        file=file_path,
        line=line,
        code_snippet=code_snippet,
        related_tests=related_tests[:10],
        error_history=[],
        suggested_fix=suggest_fix(error_code, message)
    )
