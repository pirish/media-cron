#!/usr/bin/env python3
"""Automated Semantic Versioning and Release Management for Media-Cron.

Inspects git history and conventional commit messages since the most recent
version tag to calculate the next semantic version, creates the git tag, and
publishes the GitHub release.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


def run_cmd(
    cmd: list[str], cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Execute a subprocess command returning completed process with text output."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def get_latest_tag(cwd: Path | None = None) -> str:
    """Find the latest semver git tag (e.g. v0.1.1). Defaults to v0.0.0 if none exist."""
    try:
        res = run_cmd(["git", "tag", "--sort=-v:refname"], cwd=cwd, check=False)
        if res.returncode == 0:
            tags = [t.strip() for t in res.stdout.splitlines() if t.strip()]
            for tag in tags:
                if re.match(r"^v?\d+\.\d+\.\d+$", tag):
                    return tag
    except Exception:
        pass
    return "v0.0.0"


def parse_semver(tag: str) -> tuple[int, int, int]:
    """Parse a semver string (vX.Y.Z or X.Y.Z) into (major, minor, patch)."""
    clean = tag.lstrip("v")
    parts = clean.split(".")
    major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return major, minor, patch


def get_commits_since(tag: str, cwd: Path | None = None) -> list[dict[str, str]]:
    """Retrieve commits between tag and HEAD with hash, subject, and body."""
    rev_range = f"{tag}..HEAD" if tag and tag != "v0.0.0" else "HEAD"
    try:
        res = run_cmd(
            ["git", "log", rev_range, "--format=%H%x00%s%x00%b%x00---COMMIT-END---"],
            cwd=cwd,
            check=False,
        )
        if res.returncode != 0:
            return []

        commits: list[dict[str, str]] = []
        blocks = [b.strip() for b in res.stdout.split("---COMMIT-END---") if b.strip()]
        for block in blocks:
            parts = block.split("\x00")
            if len(parts) >= 2:
                commit_hash = parts[0].strip()
                subject = parts[1].strip()
                body = parts[2].strip() if len(parts) > 2 else ""
                commits.append(
                    {
                        "hash": commit_hash[:7],
                        "full_hash": commit_hash,
                        "subject": subject,
                        "body": body,
                    }
                )
        return commits
    except Exception:
        return []


def determine_bump(commits: list[dict[str, str]]) -> str:
    """Determine semver bump level ('major', 'minor', 'patch', or 'none')."""
    if not commits:
        return "none"

    bump = "patch"
    for c in commits:
        subj = c.get("subject", "")
        body = c.get("body", "")

        # Breaking change detection
        if "BREAKING CHANGE:" in body or "BREAKING CHANGE:" in subj:
            return "major"
        if re.search(r"^[a-zA-Z]+(\([^\)]+\))?!:", subj):
            return "major"
        if "#major" in subj.lower():
            return "major"

        # Feature (minor) detection
        if re.search(r"^feat(\([^\)]+\))?:", subj, re.IGNORECASE) or "#minor" in subj.lower():
            bump = "minor"

    return bump


def calculate_next_version(current_tag: str, bump: str) -> tuple[str, str]:
    """Given a current tag and bump level, calculate next (tag, version)."""
    major, minor, patch = parse_semver(current_tag)

    if bump == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump == "minor":
        minor += 1
        patch = 0
    elif bump == "patch":
        patch += 1
    # If bump == 'none', keep same

    version_str = f"{major}.{minor}.{patch}"
    tag_str = f"v{version_str}"
    return tag_str, version_str


def generate_changelog(new_tag: str, commits: list[dict[str, str]], bump: str) -> str:
    """Generate markdown release notes from commits."""
    lines = [f"## Release {new_tag}\n"]

    features = []
    fixes = []
    other = []

    for c in commits:
        subj = c.get("subject", "")
        short_hash = c.get("hash", "")
        entry = f"- {subj} ({short_hash})"
        if re.search(r"^feat(\([^\)]+\))?:", subj, re.IGNORECASE):
            features.append(entry)
        elif re.search(r"^(fix|patch)(\([^\)]+\))?:", subj, re.IGNORECASE):
            fixes.append(entry)
        else:
            other.append(entry)

    if features:
        lines.append("### Features\n")
        lines.extend(features)
        lines.append("")

    if fixes:
        lines.append("### Bug Fixes\n")
        lines.extend(fixes)
        lines.append("")

    if other:
        lines.append("### Maintenance & Other Changes\n")
        lines.extend(other)
        lines.append("")

    return "\n".join(lines).strip()


def write_github_outputs(tag: str, version: str, output_file: str | None = None) -> None:
    """Write outputs to GITHUB_OUTPUT environment file."""
    target = output_file or os.getenv("GITHUB_OUTPUT")
    if not target:
        return

    with open(target, "a", encoding="utf-8") as f:
        f.write(f"tag={tag}\n")
        f.write(f"version={version}\n")
        f.write(f"new_tag={tag}\n")
        f.write(f"new_version={version}\n")


def create_git_tag(tag: str, message: str, cwd: Path | None = None) -> None:
    """Create annotated git tag and push to origin."""
    name_check = run_cmd(["git", "config", "user.name"], cwd=cwd, check=False)
    if name_check.returncode != 0 or not name_check.stdout.strip():
        run_cmd(["git", "config", "user.name", "github-actions[bot]"], cwd=cwd, check=True)
        run_cmd(
            ["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"],
            cwd=cwd,
            check=True,
        )

    tag_check = run_cmd(
        ["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"], cwd=cwd, check=False
    )
    if tag_check.returncode != 0:
        run_cmd(["git", "tag", "-a", tag, "-m", message], cwd=cwd, check=True)
        print(f"Created local tag {tag}")

    push_res = run_cmd(["git", "push", "origin", tag], cwd=cwd, check=False)
    if push_res.returncode == 0:
        print(f"Successfully pushed tag {tag} to origin")
    else:
        print(
            f"Note: git push tag returned {push_res.returncode} (tag may already exist on remote): {push_res.stderr.strip()}"
        )


def create_github_release(
    tag: str,
    title: str,
    body: str,
    repo: str,
    token: str,
    cwd: Path | None = None,
) -> None:
    """Create a GitHub release using gh CLI or fallback to GitHub REST API."""
    gh_check = run_cmd(["which", "gh"], cwd=cwd, check=False)
    if gh_check.returncode == 0:
        print(f"Creating GitHub release {tag} using gh CLI...")
        cmd = [
            "gh",
            "release",
            "create",
            tag,
            "--title",
            title,
            "--notes",
            body,
            "--generate-notes",
        ]
        res = run_cmd(cmd, cwd=cwd, check=False)
        if res.returncode == 0:
            print(f"GitHub release {tag} created successfully via gh CLI.")
            return
        print(f"gh release create returned {res.returncode}: {res.stderr.strip()}")

    if not token or not repo:
        print(
            "Warning: GITHUB_TOKEN or GITHUB_REPOSITORY not set; skipping release creation via REST API."
        )
        return

    print(f"Creating GitHub release {tag} using GitHub REST API...")
    url = f"https://api.github.com/repos/{repo}/releases"
    payload = {
        "tag_name": tag,
        "name": title,
        "body": body,
        "draft": False,
        "prerelease": False,
        "generate_release_notes": True,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "media-cron-semantic-release",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status in (200, 201):
                print(f"GitHub release {tag} created successfully via REST API.")
            else:
                print(f"REST API release creation status: {resp.status}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        if e.code == 422:
            print(f"GitHub release {tag} already exists.")
        else:
            print(f"Failed to create release via REST API (HTTP {e.code}): {err_body}")
    except Exception as e:
        print(f"Failed to create release via REST API: {e}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Media-Cron Semantic Release CLI")
    parser.add_argument(
        "--dry-run", action="store_true", help="Calculate release without tagging or releasing"
    )
    parser.add_argument(
        "--repo",
        default=os.getenv("GITHUB_REPOSITORY", "pirish/media-cron"),
        help="GitHub repository (owner/repo)",
    )
    parser.add_argument(
        "--token", default=os.getenv("GITHUB_TOKEN", ""), help="GitHub authentication token"
    )
    parser.add_argument(
        "--output-file",
        default=os.getenv("GITHUB_OUTPUT"),
        help="Path to write GitHub Actions output variables",
    )
    args = parser.parse_args()

    ref_type = os.getenv("GITHUB_REF_TYPE", "")
    ref_name = os.getenv("GITHUB_REF_NAME", "")

    # If triggered by explicit tag push
    if ref_type == "tag" and ref_name:
        tag = ref_name
        version = tag.lstrip("v")
        print(f"Triggered by tag push: {tag} (version {version})")
        write_github_outputs(tag=tag, version=version, output_file=args.output_file)
        if not args.dry_run:
            create_github_release(
                tag=tag,
                title=f"Release {tag}",
                body=f"Release {tag}",
                repo=args.repo,
                token=args.token,
            )
        return 0

    # Otherwise, inspect commits since last tag
    latest_tag = get_latest_tag()
    print(f"Current latest tag: {latest_tag}")

    commits = get_commits_since(latest_tag)
    print(f"Found {len(commits)} commit(s) since {latest_tag}:")
    for c in commits:
        print(f"  {c['hash']} {c['subject']}")

    bump = determine_bump(commits)
    print(f"Determined bump: {bump}")

    # If no commits and already on tagged commit, reuse tag
    if bump == "none":
        tag = latest_tag
        version = tag.lstrip("v")
        print(f"No new commits; retaining version {version} ({tag})")
    else:
        tag, version = calculate_next_version(latest_tag, bump)
        print(f"Calculated next version: {version} (tag: {tag})")

    changelog = generate_changelog(tag, commits, bump)
    print("\n--- Generated Release Notes ---")
    print(changelog)
    print("-------------------------------\n")

    write_github_outputs(tag=tag, version=version, output_file=args.output_file)

    if args.dry_run:
        print("Dry-run mode enabled; skipping tag creation and release publication.")
        return 0

    if bump != "none":
        create_git_tag(tag, f"Release {tag}")

    create_github_release(
        tag=tag,
        title=f"Release {tag}",
        body=changelog,
        repo=args.repo,
        token=args.token,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
