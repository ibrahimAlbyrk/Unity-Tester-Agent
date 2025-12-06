import os
import sys
from pathlib import Path


def detect_unity_editor(project_path: str) -> str | None:
    """Detect Unity editor path from project's ProjectVersion.txt"""
    version_file = Path(project_path) / "ProjectSettings" / "ProjectVersion.txt"

    if not version_file.exists():
        return None

    version = None
    with open(version_file) as f:
        for line in f:
            if line.startswith("m_EditorVersion:"):
                version = line.split(":")[1].strip()
                break

    if not version:
        return None

    # Platform-specific editor paths
    if sys.platform == "darwin":
        editor_path = f"/Applications/Unity/Hub/Editor/{version}/Unity.app/Contents/MacOS/Unity"
    elif sys.platform == "win32":
        editor_path = f"C:\\Program Files\\Unity\\Hub\\Editor\\{version}\\Editor\\Unity.exe"
    else:  # Linux
        editor_path = f"~/Unity/Hub/Editor/{version}/Editor/Unity"
        editor_path = os.path.expanduser(editor_path)

    if os.path.exists(editor_path):
        return editor_path

    return None
