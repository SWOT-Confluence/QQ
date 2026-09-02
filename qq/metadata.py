"""
Runtime access to QQ project metadata and software provenance.

Static project metadata comes from the installed distribution metadata,
whose authoritative source is pyproject.toml.

Git information and creation timestamps are determined at runtime.
"""

from __future__ import annotations

from datetime import datetime, timezone
from importlib.metadata import (
    PackageNotFoundError,
    metadata as distribution_metadata,
    packages_distributions,
)
import os
from pathlib import Path
import subprocess
from email.utils import getaddresses


def _load_project_metadata():
    """
    Locate the installed distribution that provides the `qq` package.

    This avoids repeating the distribution name here.
    """
    distributions = sorted(
        set(packages_distributions().get("qq", []))
    )

    if len(distributions) != 1:
        raise RuntimeError(
            "Could not uniquely identify the installed distribution "
            f"providing package 'qq': {distributions}. "
            "Install QQ with `python -m pip install -e .`."
        )

    try:
        return distribution_metadata(distributions[0])
    except PackageNotFoundError as exc:
        raise RuntimeError(
            "QQ package metadata is unavailable. "
            "Install QQ with `python -m pip install -e .`."
        ) from exc


_PROJECT_METADATA = _load_project_metadata()


PROJECT_NAME = _PROJECT_METADATA.get("Name", "")
PROJECT_VERSION = _PROJECT_METADATA.get("Version", "")
PROJECT_DESCRIPTION = _PROJECT_METADATA.get("Summary", "")

def _read_people(name_field: str, email_field: str) -> list[dict[str, str]]:
    people: list[dict[str, str]] = []

    # Entries having a name but no email.
    for raw in _PROJECT_METADATA.get_all(name_field) or []:
        for name in raw.split(","):
            name = name.strip()
            if name:
                people.append({
                    "name": name,
                    "email": "",
                })

    # Entries having an email, optionally with a name.
    for name, email in getaddresses(
        _PROJECT_METADATA.get_all(email_field) or []
    ):
        people.append({
            "name": name.strip(),
            "email": email.strip(),
        })

    return people


PROJECT_AUTHORS = _read_people(
    "Author",
    "Author-email",
)

PROJECT_MAINTAINERS = _read_people(
    "Maintainer",
    "Maintainer-email",
)

PROJECT_AUTHOR = ", ".join(
    p["name"] or p["email"]
    for p in PROJECT_AUTHORS
)

PROJECT_MAINTAINER = ", ".join(
    p["name"] or p["email"]
    for p in PROJECT_MAINTAINERS
)

# QQ project convention:
# first author entry is the owning organization.
PROJECT_OWNER = (
    PROJECT_AUTHORS[0]["name"]
    if PROJECT_AUTHORS
    else ""
)


def _read_project_urls() -> dict[str, str]:
    urls: dict[str, str] = {}

    for item in _PROJECT_METADATA.get_all("Project-URL") or []:
        if "," not in item:
            continue

        label, url = item.split(",", 1)
        urls[label.strip().lower()] = url.strip()

    return urls


PROJECT_URLS = _read_project_urls()

REPOSITORY_URL = (
    PROJECT_URLS.get("repository")
    or PROJECT_URLS.get("homepage")
    or ""
)


def utc_now_iso() -> str:
    """Current UTC timestamp in ISO-8601 format."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _run_git(*args: str) -> str:
    """Run a Git command in the repository root."""
    repo_root = Path(__file__).resolve().parents[1]

    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_git_commit() -> str:
    """
    Exact Git commit used for the run.

    Deployment can inject QQ_GIT_COMMIT when `.git` is not available
    inside the container.
    """
    return (
        os.getenv("QQ_GIT_COMMIT")
        or _run_git("rev-parse", "HEAD")
        or "unknown"
    )


def get_git_describe() -> str:
    """
    Human-readable Git version/tag and dirty state.
    """
    return (
        os.getenv("QQ_GIT_DESCRIBE")
        or _run_git("describe", "--tags", "--always", "--dirty")
        or "unknown"
    )