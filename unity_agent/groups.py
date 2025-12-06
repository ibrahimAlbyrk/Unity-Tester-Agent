import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TestGroup:
    name: str
    patterns: list[str] = field(default_factory=list)
    test_count: int = 0


class GroupManager:
    def __init__(self, groups_config: dict[str, list[str]] | None = None):
        self.groups: dict[str, TestGroup] = {}
        if groups_config:
            for name, patterns in groups_config.items():
                self.groups[name] = TestGroup(name=name, patterns=patterns)

    def get_filter_pattern(self, group_names: list[str]) -> str:
        """Combine patterns from groups into Unity testFilter format"""
        all_patterns = []
        for name in group_names:
            if name in self.groups:
                all_patterns.extend(self.groups[name].patterns)
        return ",".join(all_patterns) if all_patterns else ""

    def list_groups(self) -> list[TestGroup]:
        return list(self.groups.values())

    def has_group(self, name: str) -> bool:
        return name in self.groups

    @staticmethod
    def auto_detect_groups(project_path: str) -> dict[str, list[str]]:
        """Scan test files and suggest groupings based on folder structure"""
        assets_path = Path(project_path) / "Assets"
        test_dirs = ["Tests", "Editor/Tests", "PlayModeTests", "EditModeTests"]

        groups: dict[str, set[str]] = {}

        for test_dir in test_dirs:
            test_path = assets_path / test_dir
            if not test_path.exists():
                continue

            for cs_file in test_path.rglob("*.cs"):
                rel_path = cs_file.relative_to(test_path)

                # Group by first folder level
                if len(rel_path.parts) > 1:
                    group_name = rel_path.parts[0].lower()
                else:
                    # Group by file prefix (PlayerTests.cs -> player)
                    group_name = _extract_group_from_filename(cs_file.stem)

                if group_name:
                    if group_name not in groups:
                        groups[group_name] = set()

                    # Extract test class names from file
                    test_classes = _extract_test_classes(cs_file)
                    for tc in test_classes:
                        groups[group_name].add(f"{tc}.*")

        return {k: list(v) for k, v in groups.items()}


def _extract_group_from_filename(filename: str) -> str | None:
    """Extract group name from test filename"""
    # PlayerTests -> player, InventoryTest -> inventory
    match = re.match(r"([A-Z][a-z]+)Tests?$", filename)
    if match:
        return match.group(1).lower()

    # PlayerMoveTests -> player
    match = re.match(r"([A-Z][a-z]+)", filename)
    if match:
        return match.group(1).lower()

    return None


def _extract_test_classes(cs_file: Path) -> list[str]:
    """Extract test class names from C# file"""
    try:
        content = cs_file.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return []

    classes = []
    # Find classes with [TestFixture] or containing [Test] methods
    class_pattern = r"(?:\[TestFixture\][^\n]*\n\s*)?(?:public\s+)?class\s+(\w+)"

    for match in re.finditer(class_pattern, content):
        class_name = match.group(1)
        # Verify it's a test class by checking for Test attributes
        if "[Test]" in content or "[UnityTest]" in content:
            classes.append(class_name)

    return classes


def get_group_manager(config) -> GroupManager:
    """Create GroupManager from config"""
    groups_config = getattr(config, 'test_groups', None)
    if groups_config and hasattr(groups_config, 'groups'):
        return GroupManager(groups_config.groups)
    return GroupManager()
