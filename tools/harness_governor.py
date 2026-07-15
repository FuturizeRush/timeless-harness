#!/usr/bin/env python3
"""Run small, matched baseline versus Timeless Harness experiments.

The tool uses only the Python standard library. It keeps the experiment inputs,
raw model events, blind review, and lifecycle decision inspectable on disk.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


TOOL_ID = "timeless-harness-governor"
SCHEMA_VERSION = 1
IGNORED_NAMES = {".git", ".DS_Store", "__pycache__", ".timeless-governor"}
SENSITIVE_FILE_NAMES = {
    ".env",
    ".git-credentials",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "auth.json",
    "credentials",
    "credentials.json",
    "id_dsa",
    "id_ed25519",
    "id_ecdsa",
    "id_rsa",
    "secrets.json",
}
SENSITIVE_FILE_SUFFIXES = {".jks", ".key", ".kdbx", ".keystore", ".p12", ".pfx"}
PRIVATE_KEY_MARKER = re.compile(rb"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")
CAPTURE_FILES = ("events.jsonl", "final.txt", "prompt.txt", "result.json", "stderr.txt")


class GovernorError(RuntimeError):
    """An actionable validation or execution error."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reject_symlink_components(path: Path) -> None:
    # Canonical OS aliases such as macOS /var -> /private/var are valid. Reject
    # the user-selected object itself, then validate every entry inside copied
    # trees separately.
    if path.is_symlink():
        raise GovernorError(f"symlink path is not allowed: {path}")


def require_regular_file(path: Path, label: str) -> Path:
    reject_symlink_components(path)
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise GovernorError(f"{label} does not exist: {path}") from exc
    if not resolved.is_file() or path.is_symlink():
        raise GovernorError(f"{label} must be a regular file, not a symlink: {path}")
    return resolved


def require_directory(path: Path, label: str) -> Path:
    reject_symlink_components(path)
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise GovernorError(f"{label} does not exist: {path}") from exc
    if not resolved.is_dir() or path.is_symlink():
        raise GovernorError(f"{label} must be a directory, not a symlink: {path}")
    return resolved


def validate_tree_entries(root: Path) -> None:
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in [*dirnames, *filenames]:
            candidate = base / name
            if candidate.is_symlink():
                raise GovernorError(f"workspace symlink is not allowed: {candidate}")
            mode = candidate.stat(follow_symlinks=False).st_mode
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise GovernorError(f"workspace special file is not allowed: {candidate}")


def tree_sha256(root: Path) -> str:
    validate_tree_entries(root)
    digest = hashlib.sha256()
    root_mode = stat.S_IMODE(root.stat(follow_symlinks=False).st_mode)
    digest.update(b"d")
    digest.update((0).to_bytes(8, "big"))
    digest.update(root_mode.to_bytes(4, "big"))
    entries = sorted(root.rglob("*"))
    for path in entries:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        mode = stat.S_IMODE(path.stat(follow_symlinks=False).st_mode)
        kind = b"d" if path.is_dir() else b"f"
        digest.update(kind)
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(mode.to_bytes(4, "big"))
        if path.is_file():
            digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def write_text(path: Path, value: str, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    if private:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def write_json(path: Path, value: Any, *, private: bool = False) -> None:
    write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n", private=private)


def _copy_ignore(_: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORED_NAMES}


def reject_sensitive_workspace_files(root: Path) -> None:
    unsafe: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        name = path.name.lower()
        name_is_sensitive = (
            name in SENSITIVE_FILE_NAMES
            or name.startswith(".env.")
            or name.startswith("credentials.")
            or name.startswith("secrets.")
            or path.suffix.lower() in SENSITIVE_FILE_SUFFIXES
        )
        contains_private_key = False
        if not name_is_sensitive:
            try:
                with path.open("rb") as handle:
                    contains_private_key = PRIVATE_KEY_MARKER.search(handle.read(16 * 1024)) is not None
            except OSError as exc:
                raise GovernorError(f"Cannot inspect source workspace file: {path}") from exc
        if name_is_sensitive or contains_private_key:
            unsafe.append(path.relative_to(root).as_posix())
    if unsafe:
        shown = ", ".join(sorted(unsafe)[:8])
        suffix = " ..." if len(unsafe) > 8 else ""
        raise GovernorError(
            "Source workspace contains credential-prone files. Remove them before preparing "
            f"a persistent experiment: {shown}{suffix}"
        )


def finite_number(value: Any, *, minimum: float | None = None) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    numeric = float(value)
    if not math.isfinite(numeric):
        return False
    return minimum is None or numeric >= minimum


def validate_run_id(value: str) -> str:
    if not value or not value.replace("-", "").replace("_", "").isalnum():
        raise GovernorError("run-id may contain only letters, digits, hyphens, and underscores")
    return value


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def prepare_experiment(
    task_path: Path,
    skill_path: Path,
    rubric_path: Path,
    source_path: Path,
    output_path: Path,
    *,
    max_cost_ratio: float = 1.25,
    evaluator_path: Path | None = None,
) -> Path:
    if not finite_number(max_cost_ratio, minimum=1.0):
        raise GovernorError("max-cost-ratio must be a finite number of at least 1.0")
    task = require_regular_file(task_path, "TASK.md")
    skill = require_regular_file(skill_path, "SKILL.md")
    rubric = require_regular_file(rubric_path, "RUBRIC.md")
    source = require_directory(source_path, "source workspace")
    evaluator = (
        require_regular_file(evaluator_path, "external evaluator")
        if evaluator_path is not None
        else None
    )
    if evaluator is not None and not os.access(evaluator, os.X_OK):
        raise GovernorError("External evaluator must be executable")
    validate_tree_entries(source)
    reject_sensitive_workspace_files(source)

    reject_symlink_components(output_path)
    output = output_path.absolute()
    source_real = source.resolve()
    output_real = output.resolve(strict=False)
    if is_relative_to(output_real, source_real) or is_relative_to(source_real, output_real):
        raise GovernorError("Experiment output and source workspace must not contain each other")
    if output.exists():
        raise GovernorError(f"Output already exists; choose a new path: {output}")

    output.mkdir(parents=True, mode=0o700)
    output.chmod(0o700)
    frozen = output / "frozen"
    frozen.mkdir()
    shutil.copyfile(task, frozen / "TASK.md")
    shutil.copyfile(skill, frozen / "SKILL.md")
    shutil.copyfile(rubric, frozen / "RUBRIC.md")
    if evaluator is not None:
        shutil.copy2(evaluator, frozen / "EVALUATOR")

    templates = output / "templates"
    baseline = templates / "baseline"
    treatment = templates / "treatment"
    shutil.copytree(source, baseline, ignore=_copy_ignore)
    shutil.copyfile(frozen / "TASK.md", baseline / "TASK.md")
    shutil.copytree(baseline, treatment)
    baseline_hash = tree_sha256(baseline)
    treatment_hash = tree_sha256(treatment)
    if baseline_hash != treatment_hash:
        raise GovernorError("Prepared baseline and treatment workspaces are not identical")

    manifest = {
        "tool": TOOL_ID,
        "schema_version": SCHEMA_VERSION,
        "created_utc": utc_now(),
        "task_sha256": sha256_file(frozen / "TASK.md"),
        "skill_sha256": sha256_file(frozen / "SKILL.md"),
        "rubric_sha256": sha256_file(frozen / "RUBRIC.md"),
        "evaluator_sha256": (
            sha256_file(frozen / "EVALUATOR") if evaluator is not None else None
        ),
        "evaluator_mode": (
            stat.S_IMODE((frozen / "EVALUATOR").stat().st_mode)
            if evaluator is not None
            else None
        ),
        "template_sha256": baseline_hash,
        "source": str(source),
        "trusted_inputs_only": True,
        "tool_sha256": sha256_file(Path(__file__).resolve()),
        "max_cost_ratio_for_keep": max_cost_ratio,
    }
    write_json(output / "manifest.json", manifest)
    (output / "runs").mkdir()
    return output


def load_experiment(path: Path) -> tuple[Path, dict[str, Any]]:
    root = require_directory(path, "experiment")
    validate_tree_entries(root)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise GovernorError(f"Missing experiment manifest: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GovernorError(f"Invalid experiment manifest: {manifest_path}") from exc
    if not isinstance(manifest, dict):
        raise GovernorError(f"Experiment manifest must be a JSON object: {manifest_path}")
    if manifest.get("tool") != TOOL_ID or manifest.get("schema_version") != SCHEMA_VERSION:
        raise GovernorError(f"Unsupported experiment manifest: {manifest_path}")
    if not finite_number(manifest.get("max_cost_ratio_for_keep"), minimum=1.0):
        raise GovernorError("Frozen max-cost-ratio is missing or invalid")

    task = require_regular_file(root / "frozen" / "TASK.md", "frozen TASK.md")
    skill = require_regular_file(root / "frozen" / "SKILL.md", "frozen SKILL.md")
    rubric = require_regular_file(root / "frozen" / "RUBRIC.md", "frozen RUBRIC.md")
    if sha256_file(task) != manifest.get("task_sha256"):
        raise GovernorError("Frozen TASK.md hash no longer matches the manifest")
    if sha256_file(skill) != manifest.get("skill_sha256"):
        raise GovernorError("Frozen SKILL.md hash no longer matches the manifest")
    if sha256_file(rubric) != manifest.get("rubric_sha256"):
        raise GovernorError("Frozen RUBRIC.md hash no longer matches the manifest")
    if manifest.get("evaluator_sha256") is not None:
        evaluator = require_regular_file(root / "frozen" / "EVALUATOR", "frozen evaluator")
        if sha256_file(evaluator) != manifest.get("evaluator_sha256"):
            raise GovernorError("Frozen evaluator hash no longer matches the manifest")
        if stat.S_IMODE(evaluator.stat().st_mode) != manifest.get("evaluator_mode"):
            raise GovernorError("Frozen evaluator mode no longer matches the manifest")
        if not os.access(evaluator, os.X_OK):
            raise GovernorError("Frozen evaluator is not executable")
    elif (root / "frozen" / "EVALUATOR").exists():
        raise GovernorError("Unexpected frozen evaluator is not recorded in the manifest")
    template_hashes = [tree_sha256(root / "templates" / name) for name in ("baseline", "treatment")]
    if template_hashes[0] != template_hashes[1] or template_hashes[0] != manifest.get("template_sha256"):
        raise GovernorError("Prepared workspace hashes no longer match")
    return root, manifest


def resolve_executable(value: str) -> Path:
    candidate = shutil.which(value) if os.sep not in value else value
    if not candidate:
        raise GovernorError(f"Codex executable was not found: {value}")
    path = Path(candidate).resolve(strict=True)
    if not path.is_file() or not os.access(path, os.X_OK):
        raise GovernorError(f"Codex executable is not executable: {path}")
    return path


def codex_command(
    executable: Path,
    workspace: Path,
    output_file: Path,
    *,
    model: str,
    reasoning: str,
    sandbox: str,
) -> list[str]:
    return [
        str(executable),
        "exec",
        "--json",
        "--output-last-message",
        str(output_file),
        "--model",
        model,
        "--sandbox",
        sandbox,
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--cd",
        str(workspace),
        "--config",
        f'model_reasoning_effort="{reasoning}"',
        "--config",
        "shell_environment_policy.inherit=none",
        "-",
    ]


def condition_prompt(condition: str, task: str, skill: str) -> str:
    common = (
        "Work in the current workspace. Complete the frozen TASK.md exactly as written. "
        "Use the host Agent's normal capabilities. Do not discuss this experiment in the answer."
    )
    if condition == "baseline":
        return common + "\n\nFrozen task:\n\n" + task
    return common + "\n\nApply this frozen governance Skill only where it triggers:\n\n" + skill + "\n\nFrozen task:\n\n" + task


def parse_turn_usage(jsonl: str) -> tuple[dict[str, Any] | None, int]:
    usage = None
    invalid_lines = 0
    for raw_line in jsonl.splitlines():
        if not raw_line.strip():
            continue
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            invalid_lines += 1
            continue
        if not isinstance(event, dict):
            invalid_lines += 1
            continue
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = event["usage"]
    return usage, invalid_lines


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    source = require_regular_file(path, label)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GovernorError(f"Invalid JSON in {label}: {source}") from exc
    if not isinstance(value, dict):
        raise GovernorError(f"{label} must be a JSON object: {source}")
    return value


def validate_usage(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    cleaned: dict[str, int] = {}
    for key in ("input_tokens", "output_tokens"):
        item = value.get(key)
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            return None
        cleaned[key] = item
    return cleaned


def capture_hashes(capture: Path) -> dict[str, str]:
    validate_tree_entries(capture)
    for name in CAPTURE_FILES:
        require_regular_file(capture / name, f"capture {name}")
    sealed: dict[str, str] = {}
    for path in sorted(capture.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        digest = hashlib.sha256()
        mode = stat.S_IMODE(path.stat(follow_symlinks=False).st_mode)
        digest.update(mode.to_bytes(4, "big"))
        digest.update(bytes.fromhex(sha256_file(path)))
        sealed[path.relative_to(capture).as_posix()] = digest.hexdigest()
    return sealed


def workspace_artifact_manifest(workspace: Path) -> dict[str, Any]:
    validate_tree_entries(workspace)
    files = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        files.append(
            {
                "path": path.relative_to(workspace).as_posix(),
                "bytes": path.stat().st_size,
                "mode": f"{stat.S_IMODE(path.stat().st_mode):04o}",
                "sha256": sha256_file(path),
            }
        )
    return {"tree_sha256": tree_sha256(workspace), "files": files}


def verify_run_integrity(
    root: Path,
    experiment_manifest: dict[str, Any],
    run_id: str,
) -> tuple[Path, dict[str, Any], dict[str, dict[str, Any]]]:
    validate_run_id(run_id)
    run_root = require_directory(root / "runs" / run_id, "run")
    run = load_json_object(run_root / "run.json", "run manifest")
    if run.get("tool") != TOOL_ID or run.get("schema_version") != SCHEMA_VERSION:
        raise GovernorError("Unsupported run manifest")
    for field in ("task_sha256", "skill_sha256", "rubric_sha256", "evaluator_sha256"):
        if run.get(field) != experiment_manifest.get(field):
            raise GovernorError(f"Run {field} no longer matches the frozen experiment")
    if run.get("max_cost_ratio_for_keep") != experiment_manifest.get(
        "max_cost_ratio_for_keep"
    ):
        raise GovernorError("Run cost policy no longer matches the frozen experiment")
    seals = run.get("seals")
    if not isinstance(seals, dict):
        raise GovernorError("Run manifest is missing evidence seals")

    captures: dict[str, dict[str, Any]] = {}
    for condition in ("baseline", "treatment"):
        condition_seal = seals.get(condition)
        if not isinstance(condition_seal, dict):
            raise GovernorError(f"Run manifest is missing the {condition} seal")
        workspace = require_directory(run_root / condition / "workspace", f"{condition} workspace")
        capture = require_directory(run_root / condition / "capture", f"{condition} capture")
        if condition_seal.get("initial_workspace_sha256") != experiment_manifest.get(
            "template_sha256"
        ):
            raise GovernorError(f"{condition} initial workspace seal is invalid")
        if tree_sha256(workspace) != condition_seal.get("final_workspace_sha256"):
            raise GovernorError(f"{condition} final workspace no longer matches its seal")
        expected_capture_hashes = condition_seal.get("capture_sha256")
        if not isinstance(expected_capture_hashes, dict):
            raise GovernorError(f"{condition} capture seal is missing")
        actual_capture_hashes = capture_hashes(capture)
        if actual_capture_hashes != expected_capture_hashes:
            raise GovernorError(f"{condition} capture no longer matches its seal")

        result = load_json_object(capture / "result.json", f"{condition} result")
        if result.get("condition") != condition:
            raise GovernorError(f"{condition} result condition is invalid")
        events = (capture / "events.jsonl").read_text(encoding="utf-8")
        event_usage, invalid_lines = parse_turn_usage(events)
        if invalid_lines or result.get("invalid_jsonl_lines") not in (0, None):
            raise GovernorError(f"{condition} JSONL telemetry is malformed")
        if validate_usage(result.get("usage")) != validate_usage(event_usage):
            raise GovernorError(f"{condition} result usage does not match JSONL telemetry")
        captures[condition] = result
    return run_root, run, captures


def redact_text(value: str, secret_values: Iterable[str]) -> str:
    redacted = value
    for secret in sorted({item for item in secret_values if len(item) >= 8}, key=len, reverse=True):
        redacted = redacted.replace(secret, "[REDACTED]")
    patterns = (
        (r"\bsk-[A-Za-z0-9_-]{16,}\b", "[REDACTED_OPENAI_KEY]"),
        (r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}", "Bearer [REDACTED]"),
        (
            r'(?i)(["\']?(?:api[_-]?key|access[_-]?token|secret)["\']?\s*[:=]\s*["\']?)[^\s,"\']{8,}',
            r"\1[REDACTED]",
        ),
    )
    for pattern, replacement in patterns:
        redacted = re.sub(pattern, replacement, redacted)
    return redacted


def _auth_secret_values(value: Any, parent_key: str = "") -> list[str]:
    values: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            values.extend(_auth_secret_values(item, str(key)))
    elif isinstance(value, list):
        for item in value:
            values.extend(_auth_secret_values(item, parent_key))
    elif isinstance(value, str) and any(
        marker in parent_key.lower() for marker in ("key", "token", "secret", "auth")
    ):
        values.append(value)
    return values


def isolated_environment(
    *,
    include_codex_auth: bool = True,
) -> tuple[dict[str, str], list[str], tempfile.TemporaryDirectory[str]]:
    temporary = tempfile.TemporaryDirectory(prefix="timeless-governor-")
    isolated = Path(temporary.name)
    home = isolated / "home"
    codex_home = isolated / "codex-home"
    home.mkdir(mode=0o700)
    codex_home.mkdir(mode=0o700)

    original_codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    auth_source = original_codex_home / "auth.json"
    auth_secrets: list[str] = []
    if include_codex_auth and auth_source.is_file() and not auth_source.is_symlink():
        auth_target = codex_home / "auth.json"
        shutil.copyfile(auth_source, auth_target)
        auth_target.chmod(0o600)
        try:
            auth_secrets = _auth_secret_values(json.loads(auth_source.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            auth_secrets = []

    allowed = {
        "PATH",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TERM",
        "TMPDIR",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
    }
    environment = {name: value for name, value in os.environ.items() if name in allowed}
    environment.update(
        {
            "HOME": str(home),
            "CODEX_HOME": str(codex_home),
            "NO_COLOR": "1",
        }
    )
    secret_values = auth_secrets + [
        value
        for name, value in os.environ.items()
        if any(marker in name.upper() for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH"))
    ]
    return environment, secret_values, temporary


def run_condition(
    condition: str,
    executable: Path,
    workspace: Path,
    result_dir: Path,
    prompt: str,
    *,
    model: str,
    reasoning: str,
    sandbox: str,
    timeout: float,
    dry_run: bool,
) -> dict[str, Any]:
    result_dir.mkdir(parents=True, mode=0o700)
    result_dir.chmod(0o700)
    final_path = result_dir / "final.txt"
    command = codex_command(
        executable, workspace, final_path, model=model, reasoning=reasoning, sandbox=sandbox
    )
    write_text(result_dir / "prompt.txt", prompt)
    metadata: dict[str, Any] = {
        "condition": condition,
        "command": command,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "started_utc": utc_now(),
        "dry_run": dry_run,
    }
    if dry_run:
        write_text(result_dir / "events.jsonl", "")
        write_text(result_dir / "stderr.txt", "")
        write_text(final_path, "")
        metadata.update({"exit_code": None, "timed_out": False, "wall_seconds": 0.0, "usage": None})
        write_json(result_dir / "result.json", metadata)
        return metadata

    environment, secrets, temporary = isolated_environment()
    start = time.monotonic()
    timed_out = False
    try:
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=timeout,
                shell=False,
                check=False,
                cwd=workspace,
                env=environment,
            )
            stdout = completed.stdout
            stderr = completed.stderr
            exit_code: int | None = completed.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            exit_code = None
    finally:
        temporary.cleanup()
    stdout = redact_text(stdout, secrets)
    stderr = redact_text(stderr, secrets)
    wall_seconds = round(time.monotonic() - start, 6)
    write_text(result_dir / "events.jsonl", stdout)
    write_text(result_dir / "stderr.txt", stderr)
    if final_path.is_symlink():
        raise GovernorError("Codex final answer path became a symlink")
    if not final_path.exists():
        write_text(final_path, "")
    else:
        write_text(final_path, redact_text(final_path.read_text(encoding="utf-8"), secrets))
    usage, invalid_lines = parse_turn_usage(stdout)
    metadata.update(
        {
            "exit_code": exit_code,
            "timed_out": timed_out,
            "wall_seconds": wall_seconds,
            "usage": usage,
            "invalid_jsonl_lines": invalid_lines,
        }
    )
    write_json(result_dir / "result.json", metadata)
    validate_tree_entries(result_dir)
    return metadata


def run_evaluator(
    evaluator: Path,
    workspace: Path,
    result_dir: Path,
    *,
    timeout: float,
) -> dict[str, Any]:
    original_hash = tree_sha256(workspace)
    started = time.monotonic()
    timed_out = False
    with tempfile.TemporaryDirectory(prefix="timeless-evaluator-") as directory:
        evaluation_root = Path(directory)
        candidate = evaluation_root / "candidate"
        evaluator_copy = evaluation_root / "evaluator"
        shutil.copytree(workspace, candidate)
        shutil.copy2(evaluator, evaluator_copy)
        if tree_sha256(candidate) != original_hash:
            raise GovernorError("Detached evaluator workspace does not match the candidate")

        environment, secrets, environment_home = isolated_environment(include_codex_auth=False)
        try:
            try:
                completed = subprocess.run(
                    [str(evaluator_copy)],
                    text=True,
                    capture_output=True,
                    timeout=timeout,
                    shell=False,
                    check=False,
                    cwd=candidate,
                    env=environment,
                )
                stdout = completed.stdout
                stderr = completed.stderr
                exit_code: int | None = completed.returncode
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
                exit_code = None
        finally:
            environment_home.cleanup()
        detached_hash = tree_sha256(candidate)
        if detached_hash != original_hash:
            raise GovernorError("External evaluator modified its detached candidate copy")
    result = {
        "exit_code": exit_code,
        "timed_out": timed_out,
        "wall_seconds": round(time.monotonic() - started, 6),
        "stdout": redact_text(stdout, secrets),
        "stderr": redact_text(stderr, secrets),
        "workspace_sha256": original_hash,
    }
    write_json(result_dir / "evaluator.json", result)
    return result


def run_experiment(
    experiment: Path,
    *,
    codex: str,
    model: str,
    reasoning: str,
    sandbox: str,
    timeout: float,
    run_id: str | None = None,
    dry_run: bool = False,
    allow_live: bool = False,
    rng: random.Random | secrets.SystemRandom | None = None,
) -> Path:
    if not dry_run and not allow_live:
        raise GovernorError(
            "Live model calls are disabled. Re-run with --allow-live only after confirming all inputs are trusted and checking model, sandbox, and cost."
        )
    if sandbox not in {"read-only", "workspace-write"}:
        raise GovernorError("sandbox must be read-only or workspace-write")
    if not finite_number(timeout, minimum=0.000001):
        raise GovernorError("timeout must be a finite number greater than zero")
    root, manifest = load_experiment(experiment)
    executable = resolve_executable(codex)
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    validate_run_id(run_id)
    run_root = root / "runs" / run_id
    if run_root.exists():
        raise GovernorError(f"Run already exists: {run_root}")
    run_root.mkdir(parents=True, mode=0o700)
    run_root.chmod(0o700)

    task = (root / "frozen" / "TASK.md").read_text(encoding="utf-8")
    skill = (root / "frozen" / "SKILL.md").read_text(encoding="utf-8")
    order = ["baseline", "treatment"]
    (rng or secrets.SystemRandom()).shuffle(order)
    seals: dict[str, Any] = {}
    try:
        for condition in order:
            # Each condition runs in a separately created temporary root. The
            # first root is destroyed before the second exists, so neither path
            # exposes a baseline/treatment label or the other condition's files.
            # This reduces accidental contamination; it is not an OS-level
            # read-isolation guarantee.
            with tempfile.TemporaryDirectory(prefix="timeless-condition-") as directory:
                execution_root = Path(directory)
                workspace = execution_root / "workspace"
                result_dir = execution_root / "capture"
                shutil.copytree(root / "templates" / condition, workspace)
                initial_hash = tree_sha256(workspace)
                if initial_hash != manifest["template_sha256"]:
                    raise GovernorError(
                        f"Copied {condition} workspace is not the frozen matched template"
                    )
                prompt = condition_prompt(condition, task, skill)
                run_condition(
                    condition,
                    executable,
                    workspace,
                    result_dir,
                    prompt,
                    model=model,
                    reasoning=reasoning,
                    sandbox=sandbox,
                    timeout=timeout,
                    dry_run=dry_run,
                )
                final_hash = tree_sha256(workspace)
                if manifest.get("evaluator_sha256") is not None and not dry_run:
                    run_evaluator(
                        root / "frozen" / "EVALUATOR",
                        workspace,
                        result_dir,
                        timeout=timeout,
                    )
                    if tree_sha256(workspace) != final_hash:
                        raise GovernorError("Candidate workspace changed during external evaluation")

                validate_tree_entries(workspace)
                validate_tree_entries(result_dir)

                destination = run_root / condition
                shutil.copytree(workspace, destination / "workspace")
                shutil.copytree(result_dir, destination / "capture")
                if tree_sha256(destination / "workspace") != final_hash:
                    raise GovernorError("Persisted candidate workspace differs from the evaluated result")
                seals[condition] = {
                    "initial_workspace_sha256": initial_hash,
                    "final_workspace_sha256": final_hash,
                    "capture_sha256": capture_hashes(destination / "capture"),
                }
    except Exception:
        shutil.rmtree(run_root, ignore_errors=True)
        raise

    run_manifest = {
        "tool": TOOL_ID,
        "schema_version": SCHEMA_VERSION,
        "created_utc": utc_now(),
        "task_sha256": manifest["task_sha256"],
        "skill_sha256": manifest["skill_sha256"],
        "rubric_sha256": manifest["rubric_sha256"],
        "evaluator_sha256": manifest.get("evaluator_sha256"),
        "max_cost_ratio_for_keep": manifest["max_cost_ratio_for_keep"],
        "tool_sha256": sha256_file(Path(__file__).resolve()),
        "codex_executable_sha256": sha256_file(executable),
        "condition_order": order,
        "configuration": {
            "model": model,
            "reasoning": reasoning,
            "sandbox": sandbox,
            "timeout_seconds": timeout,
            "ephemeral": True,
            "ignore_user_config": True,
            "ignore_rules": True,
            "shell_environment_policy": "inherit=none",
            "trusted_inputs_confirmed": allow_live,
            "execution_separation": (
                "separate temporary roots destroyed between conditions; "
                "not an OS-level read-isolation guarantee"
            ),
        },
        "seals": seals,
    }
    write_json(run_root / "run.json", run_manifest)
    return run_root


def create_blind_packet(
    experiment: Path,
    run_id: str,
    *,
    rng: random.Random | secrets.SystemRandom | None = None,
) -> Path:
    root, manifest = load_experiment(experiment)
    run_root, _, captures = verify_run_integrity(root, manifest, run_id)
    grader_root = run_root / "grader"
    private_root = run_root / "private"
    if grader_root.exists() or private_root.exists():
        raise GovernorError(f"Blind packet already exists for run: {run_root}")

    outputs: dict[str, str] = {}
    artifact_manifests: dict[str, dict[str, Any]] = {}
    evaluator_results: dict[str, dict[str, Any] | None] = {}
    for condition in ("baseline", "treatment"):
        result = captures[condition]
        if result.get("exit_code") != 0 or result.get("timed_out") is not False:
            raise GovernorError(f"Cannot blind a failed or timed-out {condition} run")
        if validate_usage(result.get("usage")) is None:
            raise GovernorError(f"Cannot blind {condition} without complete token telemetry")
        if not finite_number(total_tokens(result.get("usage")), minimum=1):
            raise GovernorError(f"Cannot blind {condition} without positive token telemetry")
        if not finite_number(result.get("wall_seconds"), minimum=0.000001):
            raise GovernorError(f"Cannot blind {condition} without valid wall-time telemetry")
        path = require_regular_file(
            run_root / condition / "capture" / "final.txt", f"{condition} final answer"
        )
        value = path.read_text(encoding="utf-8").strip()
        if not value:
            raise GovernorError(f"Cannot blind an empty {condition} final answer")
        outputs[condition] = value
        artifact_manifests[condition] = workspace_artifact_manifest(
            run_root / condition / "workspace"
        )
        evaluator_path = run_root / condition / "capture" / "evaluator.json"
        evaluator_results[condition] = (
            load_json_object(evaluator_path, f"{condition} evaluator result")
            if evaluator_path.exists()
            else None
        )

    labels = ["A", "B"]
    conditions = ["baseline", "treatment"]
    (rng or secrets.SystemRandom()).shuffle(conditions)
    mapping = dict(zip(labels, conditions))
    task = (root / "frozen" / "TASK.md").read_text(encoding="utf-8").strip()
    rubric = (root / "frozen" / "RUBRIC.md").read_text(encoding="utf-8").strip()
    packet_parts = [
        "# Blind quality review\n\n"
        f"Frozen task SHA-256: `{manifest['task_sha256']}`\n\n"
        f"Frozen rubric SHA-256: `{manifest['rubric_sha256']}`\n\n"
        "## Task\n\n"
        f"{task}\n\n"
        "## Rubric\n\n"
        f"{rubric}\n\n"
        "## Output A\n\n"
        f"{outputs[mapping['A']]}\n\n",
        "## Artifact summary A\n\n"
        "See `artifact-A.json`, which contains the final workspace tree hash and per-file hashes.\n\n",
        "## Output B\n\n"
        f"{outputs[mapping['B']]}\n\n",
        "## Artifact summary B\n\n"
        "See `artifact-B.json`, which contains the final workspace tree hash and per-file hashes.\n\n",
    ]
    if evaluator_results[mapping["A"]] is not None or evaluator_results[mapping["B"]] is not None:
        packet_parts.append(
            "## External evaluator\n\nSee `evaluator-A.json` and `evaluator-B.json`.\n\n"
        )
    packet_parts.append(
        "## Verdict\n\n"
        "Copy `verdict-template.json`, then set `winner` to `A`, `B`, or `tie`. Set "
        "`material_improvement` only when the preferred output improves the claimed behavior, not style alone.\n"
    )
    packet = "".join(packet_parts)
    grader_root.mkdir(mode=0o700)
    private_root.mkdir(mode=0o700)
    write_text(grader_root / "packet.md", packet)
    for label in labels:
        condition = mapping[label]
        write_json(grader_root / f"artifact-{label}.json", artifact_manifests[condition])
        if evaluator_results[condition] is not None:
            write_json(grader_root / f"evaluator-{label}.json", evaluator_results[condition])
    write_json(
        grader_root / "verdict-template.json",
        {
            "winner": "A|B|tie",
            "material_improvement": False,
            "supported_scope": "",
            "correctable_hypothesis": "",
            "notes": "",
        },
    )
    write_json(
        private_root / "blind-mapping.json",
        {
            "mapping": mapping,
            "created_utc": utc_now(),
            "grader_files_sha256": {
                path.name: sha256_file(path)
                for path in sorted(grader_root.iterdir())
                if path.is_file()
            },
        },
        private=True,
    )
    return grader_root


def total_tokens(usage: Any) -> int | None:
    cleaned = validate_usage(usage)
    if cleaned is None:
        return None
    return cleaned["input_tokens"] + cleaned["output_tokens"]


def ratio(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if (
        not finite_number(numerator, minimum=0)
        or not finite_number(denominator, minimum=0.000001)
    ):
        return None
    return float(numerator) / float(denominator)


def decide_lifecycle(
    experiment: Path,
    run_id: str,
    verdict_path: Path,
) -> Path:
    root, manifest = load_experiment(experiment)
    max_cost_ratio = manifest.get("max_cost_ratio_for_keep")
    if not finite_number(max_cost_ratio, minimum=1.0):
        raise GovernorError("Frozen max-cost-ratio is missing or invalid")
    run_root, _, captures = verify_run_integrity(root, manifest, run_id)
    mapping_record = load_json_object(
        run_root / "private" / "blind-mapping.json", "private blind mapping"
    )
    mapping = mapping_record.get("mapping")
    if (
        not isinstance(mapping, dict)
        or set(mapping) != {"A", "B"}
        or set(mapping.values()) != {"baseline", "treatment"}
    ):
        raise GovernorError("Private blind mapping is malformed")
    expected_grader_hashes = mapping_record.get("grader_files_sha256")
    if not isinstance(expected_grader_hashes, dict):
        raise GovernorError("Private blind mapping is missing grader packet seals")
    grader_root = require_directory(run_root / "grader", "grader packet")
    if any(Path(name).name != name for name in expected_grader_hashes):
        raise GovernorError("Grader packet seal contains an unsafe filename")
    actual_grader_files = {
        path.name for path in grader_root.iterdir() if path.is_file() and not path.is_symlink()
    }
    if actual_grader_files != set(expected_grader_hashes):
        raise GovernorError("Grader packet file set no longer matches its seal")
    actual_grader_hashes = {
        name: sha256_file(require_regular_file(grader_root / name, f"grader file {name}"))
        for name in expected_grader_hashes
    }
    if actual_grader_hashes != expected_grader_hashes:
        raise GovernorError("Grader packet no longer matches its seal")
    verdict = load_json_object(verdict_path, "blind verdict")
    winner = verdict.get("winner")
    if winner not in {"A", "B", "tie"}:
        raise GovernorError("Verdict winner must be A, B, or tie")
    material = verdict.get("material_improvement")
    if not isinstance(material, bool):
        raise GovernorError("Verdict material_improvement must be true or false")
    text_fields: dict[str, str] = {}
    for field in ("supported_scope", "correctable_hypothesis", "notes"):
        value = verdict.get(field, "")
        if not isinstance(value, str):
            raise GovernorError(f"Verdict {field} must be a string")
        text_fields[field] = value.strip()
    if material and not text_fields["supported_scope"]:
        raise GovernorError(
            "Verdict supported_scope must name the bounded benefit when material_improvement is true"
        )
    actual_winner = "tie" if winner == "tie" else mapping[winner]

    invalid_conditions = []
    for condition, capture in captures.items():
        usage = capture.get("usage")
        wall = capture.get("wall_seconds")
        if (
            capture.get("exit_code") != 0
            or capture.get("timed_out") is not False
            or validate_usage(usage) is None
            or not finite_number(total_tokens(usage), minimum=1)
            or not finite_number(wall, minimum=0.000001)
        ):
            invalid_conditions.append(condition)
    baseline_tokens = total_tokens(captures["baseline"].get("usage"))
    treatment_tokens = total_tokens(captures["treatment"].get("usage"))
    token_ratio = ratio(treatment_tokens, baseline_tokens)
    wall_ratio = ratio(
        captures["treatment"].get("wall_seconds"), captures["baseline"].get("wall_seconds")
    )
    known_ratios = [value for value in (token_ratio, wall_ratio) if value is not None]
    costly = any(value > max_cost_ratio for value in known_ratios)
    any_extra_cost = any(value > 1.0 for value in known_ratios)
    hypothesis = text_fields["correctable_hypothesis"]
    supported_scope = text_fields["supported_scope"]

    if invalid_conditions:
        decision = "unresolved"
        reason = (
            "Decision is unresolved because required run telemetry is missing or invalid for: "
            + ", ".join(invalid_conditions)
            + "."
        )
    elif actual_winner == "treatment" and material:
        decision = "narrow" if costly else "keep"
        reason = (
            "Treatment materially won, but a measured cost exceeded the allowed ratio."
            if costly
            else "Treatment materially won within the allowed measured cost ratio."
        )
    elif actual_winner == "tie":
        if material and supported_scope:
            decision = "narrow"
            reason = "Overall quality tied, but the verdict identifies a bounded material benefit."
        else:
            decision = "retire"
            reason = (
                "Quality tied and treatment cost more. A tie with more process is a loss."
                if any_extra_cost
                else "Quality tied without a bounded material benefit."
            )
    elif actual_winner == "baseline":
        decision = "revise" if hypothesis else "retire"
        reason = (
            "Baseline won, but the verdict supplies a bounded corrective hypothesis to retest."
            if hypothesis
            else "Baseline won and no bounded corrective hypothesis was supplied."
        )
    else:
        decision = "retire"
        reason = "Treatment did not show a material improvement."

    output = {
        "decision": decision,
        "provisional": True,
        "scope": "single matched pair screening result; not general lifecycle proof",
        "reason": reason,
        "blind_winner": winner,
        "resolved_winner": actual_winner,
        "material_improvement": material,
        "supported_scope": supported_scope,
        "correctable_hypothesis": hypothesis,
        "cost_rule": {
            "max_cost_ratio_for_keep": max_cost_ratio,
            "tie_with_more_process_is_loss": True,
        },
        "cost": {
            "baseline_total_tokens": baseline_tokens,
            "treatment_total_tokens": treatment_tokens,
            "treatment_to_baseline_token_ratio": token_ratio,
            "treatment_to_baseline_wall_ratio": wall_ratio,
        },
        "created_utc": utc_now(),
    }
    decision_root = run_root / "decision"
    if decision_root.exists():
        raise GovernorError(f"Decision already exists: {decision_root}")
    decision_root.mkdir()
    write_json(decision_root / "decision.json", output)
    write_text(
        decision_root / "decision.md",
        f"# Provisional screen: {decision.upper()} candidate\n\n{reason}\n\n"
        f"Token ratio: `{token_ratio}`. Wall-time ratio: `{wall_ratio}`.\n",
    )
    return decision_root


def verify_bundle_hashes(bundle: Path) -> int:
    checksum_file = require_regular_file(bundle / "SHA256SUMS", "bundle SHA256SUMS")
    expected: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        checksum_file.read_text(encoding="utf-8").splitlines(), start=1
    ):
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", raw_line)
        if not match:
            raise GovernorError(f"Malformed SHA256SUMS line {line_number}")
        digest, relative = match.groups()
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts or relative in expected:
            raise GovernorError(f"Unsafe or duplicate SHA256SUMS path: {relative}")
        expected[relative] = digest
    actual_files = {
        path.relative_to(bundle).as_posix()
        for path in bundle.rglob("*")
        if path.is_file() and not path.is_symlink() and path != checksum_file
    }
    if actual_files != set(expected):
        missing = sorted(set(expected) - actual_files)
        extra = sorted(actual_files - set(expected))
        raise GovernorError(f"Bundle file set differs from SHA256SUMS; missing={missing}, extra={extra}")
    for relative, digest in expected.items():
        if sha256_file(bundle / relative) != digest:
            raise GovernorError(f"Bundle checksum mismatch: {relative}")
    return len(expected)


def parse_evaluation_mapping(path: Path) -> dict[tuple[str, int], dict[str, str]]:
    mapping: dict[tuple[str, int], dict[str, str]] = {}
    identifiers: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        parts = [part.strip() for part in raw_line.strip().strip("|").split("|")]
        if len(parts) != 5 or not parts[1].isdigit():
            continue
        case, trial_text, baseline_id, treatment_id, _ = parts
        key = (case, int(trial_text))
        if (
            key in mapping
            or baseline_id == treatment_id
            or baseline_id in identifiers
            or treatment_id in identifiers
        ):
            raise GovernorError("Evaluation mapping contains a duplicate pair or output ID")
        mapping[key] = {baseline_id: "baseline", treatment_id: "treatment"}
        identifiers.update((baseline_id, treatment_id))
    return mapping


def validate_grader_manifest(
    path: Path,
    mapping: dict[tuple[str, int], dict[str, str]],
) -> None:
    seen: set[tuple[str, int]] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        parts = [part.strip() for part in raw_line.strip().strip("|").split("|")]
        if len(parts) != 4 or not parts[1].isdigit():
            continue
        case, trial_text, first_id, second_id = parts
        key = (case, int(trial_text))
        if (
            key not in mapping
            or key in seen
            or {first_id, second_id} != set(mapping[key])
        ):
            raise GovernorError(f"Invalid pair in grader manifest {path.name}: {key}")
        seen.add(key)
    if seen != set(mapping):
        raise GovernorError(f"Grader manifest does not contain every pair: {path.name}")


def read_csv_rows(path: Path, required_fields: set[str]) -> list[dict[str, str]]:
    source = require_regular_file(path, path.name)
    with source.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if (
            reader.fieldnames is None
            or len(reader.fieldnames) != len(required_fields)
            or len(set(reader.fieldnames)) != len(reader.fieldnames)
            or set(reader.fieldnames) != required_fields
        ):
            raise GovernorError(f"Unexpected CSV schema: {path}")
        rows: list[dict[str, str]] = []
        for line_number, row in enumerate(reader, start=2):
            if None in row or any(not isinstance(value, str) for value in row.values()):
                raise GovernorError(f"Missing or extra CSV cell in {path} at line {line_number}")
            rows.append(dict(row))
        return rows


def audit_self_evidence(evidence_path: Path, output: Path) -> Path:
    bundle = require_directory(evidence_path, "self-audit evidence bundle")
    validate_tree_entries(bundle)
    verified_files = verify_bundle_hashes(bundle)
    manifest = load_json_object(bundle / "manifest.json", "self-audit manifest")
    if manifest.get("schema_version") != 1:
        raise GovernorError("Unsupported self-audit bundle schema")
    expected_counts = manifest.get("expected_counts")
    if not isinstance(expected_counts, dict):
        raise GovernorError("Self-audit manifest is missing expected_counts")

    mapping = parse_evaluation_mapping(
        require_regular_file(bundle / "mapping.md", "self-audit mapping")
    )
    output_ids = {identifier for pair in mapping.values() for identifier in pair}
    case_names = {case for case, _ in mapping}
    case_files = {
        path.stem for path in (bundle / "cases").glob("*.md") if path.is_file()
    }
    published_outputs = {
        path.stem for path in (bundle / "outputs").glob("*.md") if path.is_file()
    }
    if case_files != case_names or published_outputs != output_ids:
        raise GovernorError("Published cases or outputs do not match the frozen mapping")
    grader_manifests = sorted((bundle / "graders").glob("grader-manifest-*.md"))
    for grader_manifest in grader_manifests:
        validate_grader_manifest(grader_manifest, mapping)

    dimensions = (
        "outcome_correctness",
        "material_completeness",
        "evidence_discipline",
        "actionability",
        "proportionality",
        "communication",
    )
    score_fields = {"case", "trial", "id", *dimensions, "fatal_omission", "unnecessary_process"}
    winner_fields = {"case", "trial", "winner", "reason"}
    preference_counts = {"baseline": 0, "treatment": 0, "tie": 0}
    score_totals = {"baseline": 0, "treatment": 0}
    score_observations = {"baseline": 0, "treatment": 0}
    fatal_flags = {"baseline": 0, "treatment": 0}
    process_flags = {"baseline": 0, "treatment": 0}
    score_rows_total = 0
    preference_rows_total = 0

    for grader in ("g1", "g2", "g3"):
        score_rows = read_csv_rows(bundle / "grades" / f"{grader}-scores.csv", score_fields)
        winner_rows = read_csv_rows(
            bundle / "grades" / f"{grader}-winners.csv", winner_fields
        )
        seen_scores: set[tuple[str, int, str]] = set()
        for row in score_rows:
            try:
                key = (row["case"], int(row["trial"]))
            except ValueError as exc:
                raise GovernorError(f"Invalid trial in {grader} scores") from exc
            identifier = row["id"]
            record_key = (key[0], key[1], identifier)
            if key not in mapping or identifier not in mapping[key] or record_key in seen_scores:
                raise GovernorError(f"Invalid or duplicate score row in {grader}: {record_key}")
            seen_scores.add(record_key)
            condition = mapping[key][identifier]
            for dimension in dimensions:
                try:
                    score = int(row[dimension])
                except ValueError as exc:
                    raise GovernorError(f"Non-integer {dimension} score in {grader}") from exc
                if not 0 <= score <= 4:
                    raise GovernorError(f"Out-of-range {dimension} score in {grader}")
                score_totals[condition] += score
                score_observations[condition] += 1
            if row["fatal_omission"] not in {"yes", "no"} or row["unnecessary_process"] not in {"yes", "no"}:
                raise GovernorError(f"Invalid flag value in {grader} scores")
            fatal_flags[condition] += int(row["fatal_omission"] == "yes")
            process_flags[condition] += int(row["unnecessary_process"] == "yes")
        expected_score_keys = {
            (case, trial, identifier)
            for (case, trial), pair in mapping.items()
            for identifier in pair
        }
        if seen_scores != expected_score_keys:
            raise GovernorError(f"{grader} does not score every mapped output exactly once")

        seen_winners: set[tuple[str, int]] = set()
        for row in winner_rows:
            try:
                key = (row["case"], int(row["trial"]))
            except ValueError as exc:
                raise GovernorError(f"Invalid trial in {grader} preferences") from exc
            if key not in mapping or key in seen_winners or not row["reason"].strip():
                raise GovernorError(f"Invalid or duplicate preference row in {grader}: {key}")
            seen_winners.add(key)
            winner = row["winner"]
            if winner == "tie":
                preference_counts["tie"] += 1
            elif winner in mapping[key]:
                preference_counts[mapping[key][winner]] += 1
            else:
                raise GovernorError(f"Unknown winner ID in {grader}: {winner}")
        if seen_winners != set(mapping):
            raise GovernorError(f"{grader} does not judge every mapped pair exactly once")
        score_rows_total += len(score_rows)
        preference_rows_total += len(winner_rows)

    means = {
        condition: score_totals[condition] / score_observations[condition]
        for condition in ("baseline", "treatment")
    }
    actual_counts = {
        "case_files": len(case_files),
        "paired_trials": len(mapping),
        "opaque_outputs": len(output_ids),
        "grader_manifests": len(grader_manifests),
        "score_rows": score_rows_total,
        "pair_preferences": preference_rows_total,
        "grader_note_files": len(list((bundle / "grades").glob("g*-notes.md"))),
    }
    if actual_counts != expected_counts:
        raise GovernorError(
            f"Bundle counts do not match manifest: actual={actual_counts}, expected={expected_counts}"
        )

    recorded = manifest.get("recomputed_aggregate")
    if not isinstance(recorded, dict):
        raise GovernorError("Self-audit manifest is missing recomputed_aggregate")
    recorded_preferences = recorded.get("preference_counts")
    recorded_means = recorded.get("mean_dimension_score")
    recorded_fatal_flags = recorded.get("fatal_omission_flags")
    recorded_flags = recorded.get("unnecessary_process_flags")
    expected_preferences = {
        "baseline_wins": preference_counts["baseline"],
        "treatment_wins": preference_counts["treatment"],
        "ties": preference_counts["tie"],
    }
    if (
        recorded_preferences != expected_preferences
        or recorded_fatal_flags != fatal_flags
        or recorded_flags != process_flags
    ):
        raise GovernorError("Recomputed preferences or safety flags do not match manifest")
    if not isinstance(recorded_means, dict) or any(
        not finite_number(recorded_means.get(condition))
        or not math.isclose(means[condition], float(recorded_means[condition]), rel_tol=0, abs_tol=1e-12)
        for condition in ("baseline", "treatment")
    ):
        raise GovernorError("Recomputed mean scores do not match manifest")

    if (
        preference_counts["baseline"] > preference_counts["treatment"]
        and means["baseline"] > means["treatment"]
        and fatal_flags["baseline"] <= fatal_flags["treatment"]
        and process_flags["baseline"] < process_flags["treatment"]
    ):
        decision = "retire tested general wrapper"
        reason = (
            "The native baseline won more blind preferences, scored higher, and incurred fewer "
            "unnecessary-process flags in the published evaluation."
        )
    else:
        decision = "unresolved"
        reason = "The published measures do not point to one supported lifecycle action."
    reject_symlink_components(output)
    if output.exists():
        raise GovernorError(f"Output already exists; choose a new path: {output}")
    output.mkdir(parents=True, mode=0o700)
    output.chmod(0o700)
    aggregate = {
        "verified_bundle_files": verified_files,
        "counts": actual_counts,
        "preference_counts": expected_preferences,
        "mean_dimension_score": means,
        "fatal_omission_flags": fatal_flags,
        "unnecessary_process_flags": process_flags,
    }
    result = {
        "decision": decision,
        "reason": reason,
        "current_governor_effectiveness": "unresolved",
        "evidence_boundary": manifest.get("evidence_boundary"),
        "aggregate": aggregate,
    }
    write_json(output / "aggregate.json", aggregate)
    write_json(output / "decision.json", result)
    write_text(
        output / "report.md",
        "# Timeless self-audit\n\n"
        f"**Decision:** {decision}.\n\n{reason}\n\n"
        f"Verified `{verified_files}` bundle files, `{actual_counts['paired_trials']}` paired trials, "
        f"`{actual_counts['opaque_outputs']}` outputs, `{score_rows_total}` score rows, and "
        f"`{preference_rows_total}` blind preferences.\n\n"
        f"Native baseline: `{preference_counts['baseline']}` wins, `{means['baseline']:.3f}` mean, "
        f"`{fatal_flags['baseline']}` fatal-omission flags, and "
        f"`{process_flags['baseline']}` unnecessary-process flags.\n\n"
        f"Timeless wrapper: `{preference_counts['treatment']}` wins, `{means['treatment']:.3f}` mean, "
        f"`{fatal_flags['treatment']}` fatal-omission flags, and "
        f"`{process_flags['treatment']}` unnecessary-process flags.\n\n"
        f"Ties: `{preference_counts['tie']}`.\n\n"
        "The narrower Governor is a new design. Its effectiveness remains unresolved.\n",
    )
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser(
        "prepare", help="Freeze trusted inputs and create matched workspaces"
    )
    prepare.add_argument("--task", type=Path, required=True)
    prepare.add_argument("--skill", type=Path, required=True)
    prepare.add_argument("--rubric", type=Path, required=True)
    prepare.add_argument("--source", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument(
        "--max-cost-ratio",
        type=float,
        required=True,
        help="Precommitted maximum treatment-to-baseline cost ratio for a KEEP screen",
    )
    prepare.add_argument(
        "--evaluator",
        type=Path,
        help="Optional trusted executable evaluated after each candidate without modifying it",
    )

    run = subparsers.add_parser("run", help="Run both conditions through Codex CLI")
    run.add_argument("--experiment", type=Path, required=True)
    run.add_argument("--codex", default="codex")
    run.add_argument("--model", required=True)
    run.add_argument("--reasoning", required=True)
    run.add_argument("--sandbox", choices=("read-only", "workspace-write"), required=True)
    run.add_argument("--timeout", type=float, default=900)
    run.add_argument("--run-id")
    run.add_argument("--dry-run", action="store_true", help="Write commands without invoking Codex")
    run.add_argument(
        "--allow-live",
        action="store_true",
        help="Confirm inputs are trusted and allow two credit-consuming Codex runs",
    )

    blind = subparsers.add_parser("blind", help="Randomize outputs for blind review")
    blind.add_argument("--experiment", type=Path, required=True)
    blind.add_argument("--run-id", required=True)

    decide = subparsers.add_parser("decide", help="Resolve a blind verdict to a lifecycle decision")
    decide.add_argument("--experiment", type=Path, required=True)
    decide.add_argument("--run-id", required=True)
    decide.add_argument("--verdict", type=Path, required=True)

    self_audit = subparsers.add_parser(
        "self-audit",
        help="Verify and recompute the complete published self-audit bundle",
    )
    self_audit.add_argument(
        "--evidence",
        type=Path,
        required=True,
        help="Path to the published examples/self-audit evidence bundle",
    )
    self_audit.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            path = prepare_experiment(
                args.task,
                args.skill,
                args.rubric,
                args.source,
                args.output,
                max_cost_ratio=args.max_cost_ratio,
                evaluator_path=args.evaluator,
            )
        elif args.command == "run":
            path = run_experiment(
                args.experiment,
                codex=args.codex,
                model=args.model,
                reasoning=args.reasoning,
                sandbox=args.sandbox,
                timeout=args.timeout,
                run_id=args.run_id,
                dry_run=args.dry_run,
                allow_live=args.allow_live,
            )
        elif args.command == "blind":
            path = create_blind_packet(args.experiment, args.run_id)
        elif args.command == "decide":
            path = decide_lifecycle(args.experiment, args.run_id, args.verdict)
        else:
            path = audit_self_evidence(args.evidence, args.output)
    except (GovernorError, OSError, ValueError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.command == "decide":
        report = json.loads((path / "decision.json").read_text(encoding="utf-8"))
        print(
            f"STATUS: PROVISIONAL SCREEN\n"
            f"CANDIDATE: {report['decision'].upper()}\n"
            f"REASON: {report['reason']}\nARTIFACTS: {path}"
        )
    elif args.command == "self-audit":
        report = json.loads((path / "decision.json").read_text(encoding="utf-8"))
        aggregate = report["aggregate"]
        preferences = aggregate["preference_counts"]
        means = aggregate["mean_dimension_score"]
        fatal_flags = aggregate["fatal_omission_flags"]
        flags = aggregate["unnecessary_process_flags"]
        print(
            f"EVIDENCE: VERIFIED {aggregate['verified_bundle_files']} FILES\n"
            f"PREFERENCES: NATIVE {preferences['baseline_wins']} | TIMELESS "
            f"{preferences['treatment_wins']} | TIES {preferences['ties']}\n"
            f"MEAN SCORE: NATIVE {means['baseline']:.3f} | TIMELESS {means['treatment']:.3f}\n"
            f"FATAL OMISSIONS: NATIVE {fatal_flags['baseline']} | TIMELESS {fatal_flags['treatment']}\n"
            f"UNNECESSARY PROCESS: NATIVE {flags['baseline']} | TIMELESS {flags['treatment']}\n"
            f"DECISION: {report['decision'].upper()}\n"
            f"CURRENT GOVERNOR: {report['current_governor_effectiveness'].upper()}\n"
            f"ARTIFACTS: {path}"
        )
    else:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
