from dataclasses import dataclass
from typing import Callable
from .models import UnityResult
from .version import detect_unity_editor
from .compiler import compile_project
from .test_runner import run_tests


@dataclass
class PipelineCallbacks:
    on_step_start: Callable[[int, int, str], None] | None = None
    on_step_complete: Callable[[int, int, str, bool], None] | None = None
    on_editor_detected: Callable[[str], None] | None = None


def run_pipeline(
    project_path: str,
    editor_path: str | None = None,
    callbacks: PipelineCallbacks | None = None
) -> UnityResult:
    """Run full Unity compile + test pipeline"""
    cb = callbacks or PipelineCallbacks()

    # Step 1: Detect editor
    if cb.on_step_start:
        cb.on_step_start(1, 3, "Detecting Unity Editor...")

    if editor_path is None:
        editor_path = detect_unity_editor(project_path)
        if editor_path is None:
            if cb.on_step_complete:
                cb.on_step_complete(1, 3, "Editor not found", False)
            return UnityResult(
                success=False,
                stage="compilation",
                compilation_errors=[],
            )

    # Extract version from path
    version = extract_version(editor_path)
    if cb.on_editor_detected:
        cb.on_editor_detected(version)
    if cb.on_step_complete:
        cb.on_step_complete(1, 3, f"Editor detected ({version})", True)

    # Step 2: Compile
    if cb.on_step_start:
        cb.on_step_start(2, 3, "Compiling scripts...")

    compile_success, errors = compile_project(editor_path, project_path)

    if not compile_success:
        if cb.on_step_complete:
            cb.on_step_complete(2, 3, f"Compilation failed ({len(errors)} errors)", False)
        return UnityResult(
            success=False,
            stage="compilation",
            compilation_errors=errors,
        )

    if cb.on_step_complete:
        cb.on_step_complete(2, 3, "Compilation successful", True)

    # Step 3: Run tests
    if cb.on_step_start:
        cb.on_step_start(3, 3, "Running EditMode tests...")

    test_results = run_tests(editor_path, project_path)

    success = test_results.failed == 0
    msg = f"Tests completed ({test_results.passed}/{test_results.total} passed)"
    if cb.on_step_complete:
        cb.on_step_complete(3, 3, msg, success)

    return UnityResult(
        success=success,
        stage="tests",
        test_results=test_results,
    )


def extract_version(editor_path: str) -> str:
    """Extract Unity version from editor path"""
    import re
    match = re.search(r"(\d{4}\.\d+\.\d+[a-z]\d+)", editor_path)
    return match.group(1) if match else "Unknown"
