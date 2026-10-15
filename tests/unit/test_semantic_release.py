"""Unit tests for semantic_release.py script."""

import importlib.util
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / ".github" / "scripts" / "semantic_release.py"
)

# Dynamically import semantic_release.py
spec = importlib.util.spec_from_file_location("semantic_release", SCRIPT_PATH)
assert spec and spec.loader
semver_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(semver_mod)


def test_parse_semver():
    assert semver_mod.parse_semver("v1.2.3") == (1, 2, 3)
    assert semver_mod.parse_semver("0.1.0") == (0, 1, 0)
    assert semver_mod.parse_semver("v10.20.30") == (10, 20, 30)
    assert semver_mod.parse_semver("invalid") == (0, 0, 0)


def test_determine_bump_empty():
    assert semver_mod.determine_bump([]) == "none"


def test_determine_bump_features():
    commits = [
        {"subject": "feat: add user authentication", "body": ""},
        {"subject": "fix: resolve login bug", "body": ""},
    ]
    assert semver_mod.determine_bump(commits) == "minor"

    scoped_commits = [
        {"subject": "feat(auth): add oauth support", "body": ""},
    ]
    assert semver_mod.determine_bump(scoped_commits) == "minor"


def test_determine_bump_fixes_and_defaults():
    fix_commits = [
        {"subject": "fix: correct typo in output", "body": ""},
        {"subject": "chore: bump dependencies", "body": ""},
    ]
    assert semver_mod.determine_bump(fix_commits) == "patch"

    misc_commits = [
        {"subject": "Random commit message without prefix", "body": ""},
    ]
    assert semver_mod.determine_bump(misc_commits) == "patch"


def test_determine_bump_breaking_changes():
    breaking_in_body = [
        {
            "subject": "fix: correct api contract",
            "body": "BREAKING CHANGE: change payload structure",
        },
    ]
    assert semver_mod.determine_bump(breaking_in_body) == "major"

    breaking_in_subject = [
        {"subject": "feat(api)!: redesign endpoints", "body": ""},
    ]
    assert semver_mod.determine_bump(breaking_in_subject) == "major"

    breaking_with_hash = [
        {"subject": "refactor: drop python 3.10 support #major", "body": ""},
    ]
    assert semver_mod.determine_bump(breaking_with_hash) == "major"


def test_calculate_next_version():
    assert semver_mod.calculate_next_version("v0.1.1", "minor") == ("v0.2.0", "0.2.0")
    assert semver_mod.calculate_next_version("v0.1.1", "patch") == ("v0.1.2", "0.1.2")
    assert semver_mod.calculate_next_version("v0.1.1", "major") == ("v1.0.0", "1.0.0")
    assert semver_mod.calculate_next_version("v0.1.1", "none") == ("v0.1.1", "0.1.1")


def test_generate_changelog():
    commits = [
        {"hash": "abc1234", "subject": "feat: add subtitle sync", "body": ""},
        {"hash": "def5678", "subject": "fix: handle empty dir error", "body": ""},
        {"hash": "9998887", "subject": "docs: update readme badges", "body": ""},
    ]
    changelog = semver_mod.generate_changelog("v0.2.0", commits, "minor")
    assert "## Release v0.2.0" in changelog
    assert "### Features" in changelog
    assert "- feat: add subtitle sync (abc1234)" in changelog
    assert "### Bug Fixes" in changelog
    assert "- fix: handle empty dir error (def5678)" in changelog
    assert "### Maintenance & Other Changes" in changelog
    assert "- docs: update readme badges (9998887)" in changelog


def test_write_github_outputs(tmp_path: Path):
    out_file = tmp_path / "github_output.txt"
    semver_mod.write_github_outputs(tag="v1.2.3", version="1.2.3", output_file=str(out_file))

    content = out_file.read_text(encoding="utf-8")
    assert "tag=v1.2.3\n" in content
    assert "version=1.2.3\n" in content
    assert "new_tag=v1.2.3\n" in content
    assert "new_version=1.2.3\n" in content
