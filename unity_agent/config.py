import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal
import yaml


@dataclass
class ProjectConfig:
    path: str = "."
    editor_path: str | None = None


@dataclass
class TestConfig:
    platform: Literal["EditMode", "PlayMode", "Both"] = "EditMode"
    filter: str | None = None
    retries: int = 0
    flaky_threshold: float = 0.3


@dataclass
class CacheConfig:
    enabled: bool = True
    ttl: int = 3600


@dataclass
class OutputConfig:
    junit_path: str | None = None
    coverage_path: str | None = None


@dataclass
class TrendsConfig:
    enabled: bool = True
    max_history: int = 100


@dataclass
class Config:
    project: ProjectConfig = field(default_factory=ProjectConfig)
    test: TestConfig = field(default_factory=TestConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    trends: TrendsConfig = field(default_factory=TrendsConfig)

    def to_dict(self) -> dict:
        return asdict(self)


def load_config(project_path: str) -> Config:
    """Load config from .unity-agent.yaml with fallback to defaults"""
    config = Config()

    # Check project config
    project_config_path = Path(project_path) / ".unity-agent.yaml"
    if project_config_path.exists():
        config = _merge_config(config, project_config_path)

    # Check global config
    global_config_path = Path.home() / ".unity-agent.yaml"
    if global_config_path.exists():
        config = _merge_config(config, global_config_path)

    # Set project path
    config.project.path = project_path

    return config


def _merge_config(config: Config, config_path: Path) -> Config:
    """Merge YAML config file into existing config"""
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}

    if data.get("project"):
        for k, v in data["project"].items():
            if hasattr(config.project, k) and v is not None:
                setattr(config.project, k, v)

    if data.get("test"):
        for k, v in data["test"].items():
            if hasattr(config.test, k) and v is not None:
                setattr(config.test, k, v)

    if data.get("cache"):
        for k, v in data["cache"].items():
            if hasattr(config.cache, k) and v is not None:
                setattr(config.cache, k, v)

    if data.get("output"):
        for k, v in data["output"].items():
            if hasattr(config.output, k) and v is not None:
                setattr(config.output, k, v)

    if data.get("trends"):
        for k, v in data["trends"].items():
            if hasattr(config.trends, k) and v is not None:
                setattr(config.trends, k, v)

    return config


def merge_cli_args(config: Config, args) -> Config:
    """Override config with CLI arguments"""
    if hasattr(args, 'editor_path') and args.editor_path:
        config.project.editor_path = args.editor_path

    if hasattr(args, 'filter') and args.filter:
        config.test.filter = args.filter

    if hasattr(args, 'retries') and args.retries is not None:
        config.test.retries = args.retries

    if hasattr(args, 'flaky_threshold') and args.flaky_threshold is not None:
        config.test.flaky_threshold = args.flaky_threshold

    if hasattr(args, 'no_cache') and args.no_cache:
        config.cache.enabled = False

    if hasattr(args, 'junit') and args.junit:
        config.output.junit_path = args.junit

    if hasattr(args, 'coverage') and args.coverage:
        config.output.coverage_path = args.coverage

    return config


def get_storage_dir(project_path: str) -> Path:
    """Get .unity-agent storage directory, create if needed"""
    storage = Path(project_path) / ".unity-agent"
    storage.mkdir(exist_ok=True)

    # Create subdirectories
    (storage / "cache").mkdir(exist_ok=True)
    (storage / "trends").mkdir(exist_ok=True)
    (storage / "results").mkdir(exist_ok=True)

    # Create .gitignore
    gitignore = storage / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n!.gitignore\n")

    return storage


def create_default_config(project_path: str) -> Path:
    """Create default .unity-agent.yaml in project"""
    config_path = Path(project_path) / ".unity-agent.yaml"

    default_yaml = """# Unity Test Agent Configuration

project:
  # path: "."
  # editor_path: null  # auto-detect

test:
  platform: "EditMode"  # EditMode | PlayMode | Both
  # filter: null        # e.g., "PlayerTests.*"
  retries: 0
  flaky_threshold: 0.3

cache:
  enabled: true
  ttl: 3600  # seconds

output:
  # junit_path: ".unity-agent/results/junit.xml"
  # coverage_path: null

trends:
  enabled: true
  max_history: 100
"""

    config_path.write_text(default_yaml)
    return config_path
