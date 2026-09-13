# Contract: Pre-Commit Quality & Test Hooks

**Feature Branch**: `008-precommit-cicd-publishing`
**Date**: 2026-09-13
**Spec**: [spec.md](../spec.md)

---

## 1. Scope & Location

- **File**: `.pre-commit-config.yaml` in the repository root.
- **Hook Trigger Stage**: `commit` (default git pre-commit stage before git writes commit object).

---

## 2. Hook Definitions & Specifications

### 2.1 Standard Hygiene Hooks (`pre-commit/pre-commit-hooks`)

| Hook ID | Name | Description | Arguments / Rules |
|---|---|---|---|
| `trailing-whitespace` | Trim Trailing Whitespace | Strips trailing whitespace characters from all staged files | None |
| `end-of-file-fixer` | Fix End of Files | Ensures files end with a newline character and no trailing blank lines | None |
| `check-yaml` | Check YAML | Parses all YAML files (`.yml`, `.yaml`) and validates syntax | None |
| `check-toml` | Check TOML | Parses all TOML files (`pyproject.toml`, `ruff.toml`) and validates syntax | None |
| `check-added-large-files` | Check Large Files | Prevents accidental staging of binary or oversized files | `['--maxkb=500']` |

### 2.2 Python Quality Hooks (`astral-sh/ruff-pre-commit`)

| Hook ID | Name | Description | Arguments / Rules |
|---|---|---|---|
| `ruff` | ruff linter | Runs fast linting rules based on project `ruff.toml` | `[--fix]` (auto-fixes safe errors, stages modifications) |
| `ruff-format` | ruff formatter | Enforces project code formatting standards | None (formats Python files in-place) |

### 2.3 Automated Test Hook (Local System Hook)

| Hook Field | Value | Rationale |
|---|---|---|
| `id` | `pytest` | Unique identifier for test runner |
| `name` | `pytest` | Human-readable terminal output display |
| `entry` | `pytest` | Invokes the pytest binary available in the active virtual environment |
| `language` | `system` | Reuses local `.venv` dependencies; avoids duplicate downloads |
| `pass_filenames` | `false` | Executes full repository test suite rather than passing staged file paths |
| `always_run` | `true` | Ensures tests run even when non-Python files are committed |

---

## 3. Exit Codes & Gating Behavior

- **Exit Code 0**: All hooks passed (or auto-fixed files cleanly). The git commit proceeds.
- **Non-zero Exit Code**: One or more hooks reported violations (e.g. failing unit tests, unfixable lint errors, syntax errors). Git aborts the commit, printing diagnostic output to stderr.
- **Bypass Mechanism**: Developers can bypass verification in emergency work-in-progress rebases using native git flag: `git commit --no-verify`. Remote CI workflows strictly enforce all checks regardless of local bypass.
