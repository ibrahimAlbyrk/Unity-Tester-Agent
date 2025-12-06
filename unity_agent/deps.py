import re
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class ClassInfo:
    name: str
    file: str
    namespace: str | None = None
    base_classes: list[str] = field(default_factory=list)
    used_types: list[str] = field(default_factory=list)


@dataclass
class TestInfo:
    name: str
    file: str
    depends_on: list[str] = field(default_factory=list)


@dataclass
class DependencyGraph:
    classes: dict[str, ClassInfo] = field(default_factory=dict)
    tests: dict[str, TestInfo] = field(default_factory=dict)
    reverse_deps: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "classes": {k: asdict(v) for k, v in self.classes.items()},
            "tests": {k: asdict(v) for k, v in self.tests.items()},
            "reverse_deps": self.reverse_deps
        }


class DependencyAnalyzer:
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.graph = DependencyGraph()

    def analyze(self) -> DependencyGraph:
        """Scan all .cs files and build dependency graph"""
        assets_path = Path(self.project_path) / "Assets"
        if not assets_path.exists():
            return self.graph

        # First pass: collect all classes
        for cs_file in assets_path.rglob("*.cs"):
            self._analyze_file(cs_file)

        # Build reverse dependency map
        self._build_reverse_deps()

        return self.graph

    def _analyze_file(self, cs_file: Path):
        """Analyze single C# file"""
        try:
            content = cs_file.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return

        rel_path = str(cs_file.relative_to(self.project_path))
        is_test = self._is_test_file(content)

        # Extract namespace
        namespace = self._extract_namespace(content)

        # Extract class declarations
        classes = self._extract_classes(content)

        # Extract type usages
        used_types = self._extract_used_types(content)

        for class_name, base_classes in classes:
            class_info = ClassInfo(
                name=class_name,
                file=rel_path,
                namespace=namespace,
                base_classes=base_classes,
                used_types=used_types
            )

            if is_test:
                # Store as test
                test_info = TestInfo(
                    name=class_name,
                    file=rel_path,
                    depends_on=used_types
                )
                self.graph.tests[class_name] = test_info
            else:
                self.graph.classes[class_name] = class_info

    def _extract_namespace(self, content: str) -> str | None:
        match = re.search(r"namespace\s+([\w.]+)", content)
        return match.group(1) if match else None

    def _extract_classes(self, content: str) -> list[tuple[str, list[str]]]:
        """Extract class names and their base classes"""
        results = []
        pattern = r"(?:public\s+)?(?:abstract\s+)?(?:sealed\s+)?class\s+(\w+)(?:\s*:\s*([\w\s,<>]+))?"

        for match in re.finditer(pattern, content):
            class_name = match.group(1)
            base_part = match.group(2)

            base_classes = []
            if base_part:
                # Split by comma and clean up
                bases = [b.strip().split('<')[0] for b in base_part.split(',')]
                base_classes = [b for b in bases if b]

            results.append((class_name, base_classes))

        return results

    def _extract_used_types(self, content: str) -> list[str]:
        """Extract PascalCase type names used in the file"""
        # Common Unity/C# types to exclude
        exclude = {
            'String', 'Int32', 'Boolean', 'Object', 'Type', 'Void',
            'List', 'Dictionary', 'Array', 'Action', 'Func', 'Task',
            'IEnumerator', 'IEnumerable', 'Exception', 'Math', 'Debug',
            'Console', 'File', 'Path', 'Directory', 'Stream',
            'MonoBehaviour', 'ScriptableObject', 'GameObject', 'Transform',
            'Component', 'Behaviour', 'Object', 'UnityEngine', 'UnityEditor',
            'Test', 'TestFixture', 'Setup', 'TearDown', 'Assert', 'NUnit',
        }

        # Find PascalCase identifiers
        pattern = r"\b([A-Z][a-zA-Z0-9]+)\b"
        types = set()

        for match in re.finditer(pattern, content):
            type_name = match.group(1)
            if type_name not in exclude and len(type_name) > 2:
                types.add(type_name)

        return sorted(types)

    def _is_test_file(self, content: str) -> bool:
        return "[Test]" in content or "[UnityTest]" in content or "[TestFixture]" in content

    def _build_reverse_deps(self):
        """Build reverse dependency map: class -> tests that use it"""
        for test_name, test_info in self.graph.tests.items():
            for dep in test_info.depends_on:
                if dep in self.graph.classes:
                    if dep not in self.graph.reverse_deps:
                        self.graph.reverse_deps[dep] = []
                    if test_name not in self.graph.reverse_deps[dep]:
                        self.graph.reverse_deps[dep].append(test_name)

    def get_affected_tests(self, changed_files: list[str]) -> list[str]:
        """Given changed files, return tests that might be affected"""
        affected = set()

        for file_path in changed_files:
            # Find classes in this file
            for class_name, class_info in self.graph.classes.items():
                if class_info.file == file_path or file_path.endswith(class_info.file):
                    # Add all tests that depend on this class
                    if class_name in self.graph.reverse_deps:
                        affected.update(self.graph.reverse_deps[class_name])

        return sorted(affected)

    def get_class_deps(self, class_name: str) -> dict:
        """Get detailed dependency info for a class"""
        if class_name not in self.graph.classes:
            return {"error": f"Class '{class_name}' not found"}

        info = self.graph.classes[class_name]
        tests = self.graph.reverse_deps.get(class_name, [])

        return {
            "class": class_name,
            "file": info.file,
            "namespace": info.namespace,
            "base_classes": info.base_classes,
            "used_types": info.used_types,
            "affected_tests": tests,
            "test_count": len(tests)
        }

    def export(self, output_path: str):
        """Export full graph as JSON"""
        data = self.graph.to_dict()
        Path(output_path).write_text(json.dumps(data, indent=2))


def analyze_dependencies(project_path: str) -> DependencyGraph:
    """Convenience function to analyze project dependencies"""
    analyzer = DependencyAnalyzer(project_path)
    return analyzer.analyze()


def export_dependencies(project_path: str, output_path: str):
    """Analyze and export dependencies to JSON"""
    analyzer = DependencyAnalyzer(project_path)
    analyzer.analyze()
    analyzer.export(output_path)


def get_affected_tests_for_files(project_path: str, changed_files: list[str]) -> list[str]:
    """Get tests affected by file changes"""
    analyzer = DependencyAnalyzer(project_path)
    analyzer.analyze()
    return analyzer.get_affected_tests(changed_files)
