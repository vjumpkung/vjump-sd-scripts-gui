"""Server configuration resolved from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
VERSION_FILE = REPO_ROOT / "VERSION"
FALLBACK_VERSION = "0.0.0-dev"

WORKSPACE_SUBDIRS = ("models", "datasets", "outputs", "logs")
DEFAULT_MAX_UPLOAD_BYTES = 2 * 1024**3
# The frontend is served by this app (same origin); enable CORS explicitly for a dev server.
DEFAULT_CORS_ORIGINS = ""


def read_version(path: Path | None = None) -> str:
    """Read the app version from the root VERSION file (fallback when unreadable)."""
    try:
        text = (path or VERSION_FILE).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return FALLBACK_VERSION
    return text or FALLBACK_VERSION


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    return Path(raw).resolve() if raw else default.resolve()


def _env_exe(name: str, default: Path) -> Path:
    """Like _env_path but without resolving symlinks (venv pythons are symlinks)."""
    raw = os.environ.get(name, "").strip()
    return Path(os.path.abspath(raw if raw else default))


def _env_positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer") from error
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _env_csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(
        item.strip()
        for item in os.environ.get(name, default).split(",")
        if item.strip()
    )


def _default_sd_python(sd_dir: Path) -> Path:
    if os.name == "nt":
        return sd_dir / "venv" / "Scripts" / "python.exe"
    return sd_dir / "venv" / "bin" / "python"


@dataclass(frozen=True)
class Settings:
    # SQLite database, job folders, schema cache.
    data_root: Path = field(
        default_factory=lambda: _env_path(
            "SD_SCRIPTS_GUI_DATA_ROOT", BACKEND_ROOT / "data"
        )
    )
    # Models, datasets, outputs and logs. Every write path is confined here and it
    # is also the training subprocess cwd.
    workspace_root: Path = field(
        default_factory=lambda: _env_path(
            "SD_SCRIPTS_GUI_WORKSPACE_ROOT", REPO_ROOT / "workspace"
        )
    )
    # Built Vite frontend served in production when index.html exists.
    web_dir: Path = field(
        default_factory=lambda: _env_path(
            "SD_SCRIPTS_GUI_WEB_DIR", BACKEND_ROOT / "web"
        )
    )
    sd_dir: Path = field(
        default_factory=lambda: _env_path(
            "SD_SCRIPTS_GUI_SD_SCRIPTS_DIR", REPO_ROOT / "sd-scripts"
        )
    )
    sd_python: Path | None = field(default=None)
    # None disables HTTP Basic auth.
    password: str | None = field(
        default_factory=lambda: os.environ.get("SD_SCRIPTS_GUI_PASSWORD") or None
    )
    allowed_hosts: tuple[str, ...] = field(
        default_factory=lambda: _env_csv("SD_SCRIPTS_GUI_ALLOWED_HOSTS", "*")
    )
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: _env_csv(
            "SD_SCRIPTS_GUI_CORS_ORIGINS", DEFAULT_CORS_ORIGINS
        )
    )
    max_upload_bytes: int = field(
        default_factory=lambda: _env_positive_int(
            "SD_SCRIPTS_GUI_MAX_UPLOAD_BYTES", DEFAULT_MAX_UPLOAD_BYTES
        )
    )
    desktop: bool = field(
        default_factory=lambda: os.environ.get("SD_SCRIPTS_GUI_DESKTOP", "") == "1"
    )
    # Read once when the settings are loaded (startup).
    version: str = field(default_factory=read_version)

    def __post_init__(self) -> None:
        if self.sd_python is None:
            object.__setattr__(
                self,
                "sd_python",
                _env_exe("SD_SCRIPTS_GUI_SD_PYTHON", _default_sd_python(self.sd_dir)),
            )

    @property
    def database_path(self) -> Path:
        return self.data_root / "sd_scripts_gui.db"

    @property
    def jobs_dir(self) -> Path:
        return self.data_root / "jobs"

    @property
    def schema_path(self) -> Path:
        return self.data_root / "schema.json"

    @property
    def datasets_dir(self) -> Path:
        return self.workspace_root / "datasets"

    @property
    def sd_python_ok(self) -> bool:
        return self.sd_python is not None and self.sd_python.is_file()

    def ensure_directories(self) -> None:
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        for name in WORKSPACE_SUBDIRS:
            (self.workspace_root / name).mkdir(parents=True, exist_ok=True)

    def resolve_inside_workspace(self, raw: str) -> Path:
        """Resolve a client-supplied path against the workspace root.

        Raises ValueError when the result escapes the configured root.
        """
        candidate = Path(raw)
        if raw.replace("\\", "/").startswith("//"):
            # UNC and device paths (two leading slashes or backslashes, "//x/y",
            # extended "\\?\" prefixes): decide purely lexically so that resolving
            # never touches the network or a device.
            lexical = Path(os.path.normpath(candidate))
            if lexical != self.workspace_root and self.workspace_root not in (
                lexical.parents
            ):
                raise ValueError(
                    f"Path is outside the configured workspace root: {raw}"
                )
            return lexical
        resolved = (
            candidate if candidate.is_absolute() else self.workspace_root / candidate
        ).resolve()
        if (
            resolved != self.workspace_root
            and self.workspace_root not in resolved.parents
        ):
            raise ValueError(f"Path is outside the configured workspace root: {raw}")
        return resolved


def load_settings() -> Settings:
    return Settings()
