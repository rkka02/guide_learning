from __future__ import annotations

from pathlib import Path
import os


def find_dotenv(start_dir: Path | None = None, *, max_parents: int = 8) -> Path | None:
    """
    Find a .env file by walking upwards from start_dir (or cwd).

    This is intentionally small and dependency-free (works even without python-dotenv).
    """
    current = (start_dir or Path.cwd()).resolve()
    for _ in range(max_parents + 1):
        candidate = current / ".env"
        if candidate.exists():
            return candidate
        if current.parent == current:
            break
        current = current.parent
    return None


def resolve_env_path(
    dotenv_path: Path | None = None,
    *,
    env_var: str = "GUIDE_ENV_PATH",
) -> Path | None:
    """
    Resolve .env path with priority:
      1) explicit dotenv_path
      2) environment variable (GUIDE_ENV_PATH)
      3) auto-discovery upwards from cwd
    """
    if dotenv_path:
        return Path(dotenv_path)

    env_path = os.getenv(env_var)
    if env_path:
        return Path(env_path).expanduser()

    return find_dotenv()


def load_env(dotenv_path: Path | None = None, *, override: bool = False) -> bool:
    """
    Load environment variables from a .env file.

    - If python-dotenv is installed, it will be used.
    - Otherwise, a minimal parser is used (KEY=VALUE, optional quotes, optional 'export ' prefix).
    """
    path = resolve_env_path(dotenv_path)
    if not path:
        return False

    # Prefer python-dotenv if available.
    try:
        from dotenv import load_dotenv as _load_dotenv  # type: ignore

        return bool(_load_dotenv(path, override=override))
    except Exception:
        pass

    # Minimal fallback parser
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("export "):
                line = line[len("export ") :].strip()

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if not key:
                continue

            if not override and key in os.environ:
                continue

            os.environ[key] = value

        return True
    except Exception:
        return False
