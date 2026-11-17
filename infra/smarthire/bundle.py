"""Build the Lambda deployment package without Docker.

Copies `lambda/*.py` into a build folder and installs `lambda/requirements.txt`
as Linux wheels for Python 3.12 (`pip --platform`), so the package runs on the
Lambda runtime no matter which OS you synth from.
"""

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

PLATFORM = "manylinux2014_x86_64"
PYTHON_VERSION = "3.12"


def _fingerprint(src: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(src.glob("*.py")) + [src / "requirements.txt"]:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    digest.update(f"{PLATFORM}-{PYTHON_VERSION}".encode())
    return digest.hexdigest()


def build_lambda_package(src: Path, out: Path) -> str:
    """Return the path of a ready-to-zip folder; rebuilds only when sources change."""
    stamp = out / ".fingerprint"
    fingerprint = _fingerprint(src)
    if stamp.exists() and stamp.read_text() == fingerprint:
        return str(out)

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "--quiet", "--disable-pip-version-check",
            "--requirement", str(src / "requirements.txt"),
            "--target", str(out),
            "--platform", PLATFORM,
            "--python-version", PYTHON_VERSION,
            "--implementation", "cp",
            "--only-binary=:all:",
        ],
        check=True,
    )
    for path in src.glob("*.py"):
        shutil.copy2(path, out / path.name)
    for cache in out.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    stamp.write_text(fingerprint)
    return str(out)
