import subprocess
import tempfile
import re
from pathlib import Path
from .models import CompilationError


def compile_project(editor_path: str, project_path: str) -> tuple[bool, list[CompilationError]]:
    """Compile Unity project and return success status with any errors"""
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
        log_path = f.name

    cmd = [
        editor_path,
        "-batchmode",
        "-nographics",
        "-quit",
        "-projectPath", project_path,
        "-logFile", log_path
    ]

    result = subprocess.run(cmd)

    output = ""
    if Path(log_path).exists():
        output = Path(log_path).read_text()
        Path(log_path).unlink(missing_ok=True)

    errors = parse_compilation_errors(output)
    success = result.returncode == 0 and len(errors) == 0

    return success, errors


def parse_compilation_errors(output: str) -> list[CompilationError]:
    """Parse Unity compilation output for errors (deduplicated with count)"""
    error_counts = {}
    error_data = {}
    pattern = r"([^\s]+\.cs)\((\d+),\d+\):\s*error\s+(CS\d+):\s*(.+)"

    for match in re.finditer(pattern, output):
        key = (match.group(1), int(match.group(2)), match.group(3))
        error_counts[key] = error_counts.get(key, 0) + 1
        if key not in error_data:
            error_data[key] = match.group(4).strip()

    return [
        CompilationError(file=k[0], line=k[1], code=k[2], message=error_data[k], count=v)
        for k, v in error_counts.items()
    ]
