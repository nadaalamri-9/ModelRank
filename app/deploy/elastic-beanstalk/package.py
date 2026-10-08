"""Build the Elastic Beanstalk source bundle for the ModelRank backend.

Usage (from the app/ directory):

    python deploy/elastic-beanstalk/package.py

Writes deploy/elastic-beanstalk/build/modelrank-backend.zip, ready to upload
in the Elastic Beanstalk console. The bundle contains:

    Dockerfile        (copied from backend/Dockerfile)
    requirements.txt
    backend/          (without caches or generated data)
    .platform/        (nginx timeouts)

docker-compose.yml, the frontend and .env are deliberately left out:
Elastic Beanstalk would use docker-compose.yml over the Dockerfile, and
secrets belong in the environment's properties, not in the bundle.
"""

import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "build" / "modelrank-backend.zip"

EXCLUDED_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".pdf"}


def include(path: Path) -> bool:
    if any(part in EXCLUDED_DIRS for part in path.parts):
        return False

    if path.suffix in EXCLUDED_SUFFIXES:
        return False

    # Generated evaluation data (including job directories) is written at
    # runtime
    if path.relative_to(ROOT / "backend").parts[0] == "data":
        return False

    return path.is_file()


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    entries: list[tuple[Path | None, str]] = [
        (ROOT / "backend" / "Dockerfile", "Dockerfile"),
        (ROOT / "requirements.txt", "requirements.txt"),
    ]

    for path in sorted((ROOT / "backend").rglob("*")):
        if include(path) and path.name != "Dockerfile":
            entries.append((path, path.relative_to(ROOT).as_posix()))

    platform_dir = HERE / ".platform"
    for path in sorted(platform_dir.rglob("*")):
        if path.is_file():
            entries.append((path, path.relative_to(HERE).as_posix()))

    # Keep backend/data/ in the bundle so the directory exists at runtime
    entries.append((None, "backend/data/"))

    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as bundle:
        for source, name in entries:
            if source is None:
                bundle.writestr(name, "")
            else:
                # Forward-slash names: backslashes break the bundle on Linux
                bundle.write(source, name)

    print(f"Wrote {OUTPUT.relative_to(ROOT).as_posix()}")
    for _, name in entries:
        print(f"  {name}")


if __name__ == "__main__":
    main()
