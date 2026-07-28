#!/usr/bin/env python3
"""Inventory agent-facing repository docs without printing file contents."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DOC_SUFFIXES = {".adoc", ".md", ".mdx", ".rst"}
DOC_TEXT_DIRS = {"doc", "docs", "documentation", "manuals", "notes"}
DOC_TEXT_FILENAMES = {
    "changelog.txt",
    "contributing.txt",
    "contributors.txt",
    "license.txt",
    "notice.txt",
    "readme.txt",
    "security.txt",
    "support.txt",
}
INSTRUCTION_NAMES = {"AGENTS.md", "AGENTS.override.md"}
DOC_PATHSPECS = [
    "*.adoc",
    "*.md",
    "*.mdx",
    "*.rst",
    "*.txt",
    "AGENTS.md",
    "AGENTS.override.md",
]
DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".next",
    ".next-dev",
    ".pytest_cache",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "blob-report",
    "build",
    "coverage",
    "data",
    "dist",
    "node_modules",
    "playwright-report",
    "report",
    "test-results",
    "tmp",
    "tmp_old",
    "vendor",
    "venv",
}


@dataclass(frozen=True)
class GitOutput:
    lines: list[str]
    warning: str | None = None


@dataclass(frozen=True)
class CandidateDocs:
    paths: list[Path]
    tracked: set[str]
    untracked: set[str]
    ignored: set[str]
    warnings: list[str]
    used_git: bool


def relpath(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def iter_repo_doc_files(
    root: Path,
    excluded_dirs: set[str],
    prune_generated_patterns: bool,
) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name
            for name in dirnames
            if not is_excluded_dir_name(
                name,
                excluded_dirs,
                prune_generated_patterns=prune_generated_patterns,
            )
        ]
        current = Path(dirpath)
        for filename in filenames:
            path = current / filename
            if (path.is_file() or path.is_symlink()) and is_doc_file(path, root=root):
                yield path


def is_doc_file(path: Path, include_txt: bool = False, root: Path | None = None) -> bool:
    if path.name in INSTRUCTION_NAMES:
        return True
    if path.suffix.lower() in DOC_SUFFIXES:
        return True
    if path.suffix.lower() == ".txt":
        if include_txt:
            return True
        try:
            scoped_path = path.relative_to(root) if root else path
        except ValueError:
            scoped_path = path
        lower_parts = {part.lower() for part in scoped_path.parts[:-1]}
        if lower_parts & DOC_TEXT_DIRS:
            return True
    return path.name.lower() in DOC_TEXT_FILENAMES


def is_excluded_relpath(
    rel: str,
    excluded_dirs: set[str],
    prune_generated_patterns: bool,
) -> bool:
    parts = Path(rel).parts[:-1]
    return any(
        is_excluded_dir_name(
            part,
            excluded_dirs,
            prune_generated_patterns=prune_generated_patterns,
        )
        for part in parts
    )


def is_excluded_dir_name(
    name: str,
    excluded_dirs: set[str],
    prune_generated_patterns: bool,
) -> bool:
    if name in excluded_dirs:
        return True
    if not prune_generated_patterns:
        return False
    return (
        name.startswith(".cache")
        or name.endswith(".egg-info")
        or name.endswith("_venv")
        or name.endswith("-venv")
    )


def run_git(root: Path, args: list[str], input_text: str | None = None) -> GitOutput:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError:
        return GitOutput([], "Git executable not found; ignore/untracked checks were skipped.")
    if result.returncode not in (0, 1):
        command = "git " + " ".join(args)
        return GitOutput([], f"{command} failed; ignore/untracked checks may be incomplete.")
    return GitOutput([line for line in result.stdout.splitlines() if line])


def ignored_paths(root: Path, paths: list[str]) -> tuple[set[str], str | None]:
    if not paths:
        return set(), None
    output = run_git(root, ["check-ignore", "--no-index", "--stdin"], "\n".join(paths) + "\n")
    return set(output.lines), output.warning


def git_doc_candidates(
    root: Path,
    include_txt: bool,
    excluded_dirs: set[str],
    prune_generated_patterns: bool,
) -> CandidateDocs | None:
    status = run_git(root, ["rev-parse", "--is-inside-work-tree"])
    if status.warning or status.lines != ["true"]:
        warning = status.warning or "Not inside a Git worktree; Git classification was skipped."
        return CandidateDocs([], set(), set(), set(), [warning], False)

    warnings = []
    tracked_output = run_git(root, ["ls-files", "--cached", "--", *DOC_PATHSPECS])
    untracked_output = run_git(
        root,
        ["ls-files", "--others", "--exclude-standard", "--", *DOC_PATHSPECS],
    )
    ignored_output = run_git(
        root,
        ["ls-files", "--others", "--ignored", "--exclude-standard", "--", *DOC_PATHSPECS],
    )
    for output in (tracked_output, untracked_output, ignored_output):
        if output.warning:
            warnings.append(output.warning)

    if warnings:
        return CandidateDocs([], set(), set(), set(), warnings, False)

    raw_rels = set(tracked_output.lines) | set(untracked_output.lines) | set(ignored_output.lines)
    doc_rels = [
        rel
        for rel in sorted(raw_rels)
        if not is_excluded_relpath(
            rel,
            excluded_dirs,
            prune_generated_patterns=prune_generated_patterns,
        )
        and is_doc_file(root / rel, include_txt=include_txt, root=root)
        and ((root / rel).is_file() or (root / rel).is_symlink())
    ]
    doc_rel_set = set(doc_rels)
    paths = [root / rel for rel in doc_rels]
    ignored, ignored_warning = ignored_paths(root, doc_rels)
    if ignored_warning:
        warnings.append(ignored_warning)

    return CandidateDocs(
        paths=paths,
        tracked=set(tracked_output.lines) & doc_rel_set,
        untracked=set(untracked_output.lines) & doc_rel_set,
        ignored=(set(ignored_output.lines) | ignored) & doc_rel_set,
        warnings=warnings,
        used_git=True,
    )


def symlink_info(path: Path, root: Path) -> dict:
    if not path.is_symlink():
        return {
            "is_symlink": False,
            "symlink_target": None,
            "symlink_broken": False,
            "symlink_external": False,
        }
    target = os.readlink(path)
    target_path = Path(target)
    resolved_target = target_path if target_path.is_absolute() else (path.parent / target_path)
    try:
        resolved_target = resolved_target.resolve(strict=False)
        root_resolved = root.resolve(strict=False)
        external = not resolved_target.is_relative_to(root_resolved)
    except OSError:
        external = True
    return {
        "is_symlink": True,
        "symlink_target": target,
        "symlink_broken": not path.exists(),
        "symlink_external": external,
    }


def document_record(path: Path, root: Path, tracked: set[str], untracked: set[str], ignored: set[str]) -> dict:
    rel = relpath(path, root)
    size = path.lstat().st_size if path.is_symlink() else path.stat().st_size
    record = {
        "path": rel,
        "bytes": size,
        "tracked": rel in tracked,
        "untracked": rel in untracked,
        "ignored": rel in ignored,
        "classification": "instruction" if path.name in INSTRUCTION_NAMES else "document",
    }
    record.update(symlink_info(path, root))
    if record["is_symlink"]:
        record["classification"] = "symlink"
    return record


def build_inventory(
    root: Path,
    max_doc_bytes: int,
    include_txt: bool = False,
    include_excluded_dirs: bool = False,
    exclude_dirs: list[str] | None = None,
) -> dict:
    root = root.resolve()
    warnings = []
    excluded_dirs = set() if include_excluded_dirs else set(DEFAULT_EXCLUDE_DIRS)
    prune_generated_patterns = not include_excluded_dirs
    if exclude_dirs:
        excluded_dirs.update(exclude_dirs)
    git_candidates = git_doc_candidates(
        root,
        include_txt=include_txt,
        excluded_dirs=excluded_dirs,
        prune_generated_patterns=prune_generated_patterns,
    )

    if git_candidates and git_candidates.used_git:
        doc_files = git_candidates.paths
        tracked = git_candidates.tracked
        untracked = git_candidates.untracked
        ignored = git_candidates.ignored
        warnings.extend(git_candidates.warnings)
    else:
        doc_files = list(
            iter_repo_doc_files(
                root,
                excluded_dirs,
                prune_generated_patterns=prune_generated_patterns,
            )
        )
        tracked = set()
        untracked = set()
        ignored = set()
        if git_candidates:
            warnings.extend(git_candidates.warnings)
        warnings.append("Used filesystem fallback; tracked/ignored/untracked flags are unavailable.")

    instruction_files = []
    large_documents = []
    large_ignored_documents = []
    documents = []
    for path in doc_files:
        record = document_record(path, root, tracked, untracked, ignored)
        rel = record["path"]
        size = record["bytes"]
        documents.append(record)
        if path.name in INSTRUCTION_NAMES:
            instruction_files.append({"path": rel, "bytes": size})
        if size > max_doc_bytes:
            target = large_ignored_documents if rel in ignored else large_documents
            target.append({"path": rel, "bytes": size})

    skill_dirs = []
    skills_root = root / ".agents" / "skills"
    if skills_root.is_dir():
        for skill_file in sorted(skills_root.glob("*/SKILL.md")):
            skill_dirs.append(relpath(skill_file.parent, root))

    if not instruction_files:
        warnings.append("No AGENTS.md or AGENTS.override.md files found.")
    for item in instruction_files:
        if item["bytes"] > max_doc_bytes:
            warnings.append(f"{item['path']} is larger than {max_doc_bytes} bytes.")
    hidden_instruction_surfaces = sorted(
        path
        for path in ignored
        if path.endswith("AGENTS.md")
        or path.endswith("AGENTS.override.md")
        or path.startswith(".agents/skills/")
    )
    if hidden_instruction_surfaces:
        warnings.append("Some instruction files or repo skills are ignored.")
    external_symlinks = sorted(
        record["path"]
        for record in documents
        if record["is_symlink"] and record["symlink_external"]
    )
    if external_symlinks:
        warnings.append("Some document symlinks point outside the repository.")

    return {
        "schema_version": 2,
        "root": str(root),
        "max_doc_bytes": max_doc_bytes,
        "instruction_files": sorted(instruction_files, key=lambda item: item["path"]),
        "repo_skill_dirs": skill_dirs,
        "documents": sorted(documents, key=lambda item: item["path"]),
        "large_documents": sorted(large_documents, key=lambda item: item["bytes"], reverse=True),
        "large_ignored_documents": sorted(
            large_ignored_documents,
            key=lambda item: item["bytes"],
            reverse=True,
        ),
        "ignored_documents": sorted(ignored),
        "untracked_documents": sorted(
            record["path"]
            for record in documents
            if record["untracked"]
        ),
        "warnings": warnings,
    }


def print_human(inventory: dict) -> None:
    print(f"Repository docs inventory: {inventory['root']}")
    print(f"Instruction budget threshold: {inventory['max_doc_bytes']} bytes")

    def section(title: str, rows: list) -> None:
        print()
        print(title)
        if not rows:
            print("  none")
            return
        for row in rows:
            if isinstance(row, dict):
                size = row.get("bytes")
                suffix = f" ({size} bytes)" if size is not None else ""
                print(f"  {row['path']}{suffix}")
            else:
                print(f"  {row}")

    section("Instruction files", inventory["instruction_files"])
    section("Repo skill directories", inventory["repo_skill_dirs"])
    section(
        "Documents",
        [
            {"path": record["path"], "bytes": record["bytes"]}
            for record in inventory["documents"]
        ],
    )
    section("Large documents", inventory["large_documents"])
    section("Large ignored documents", inventory["large_ignored_documents"])
    section("Ignored documents", inventory["ignored_documents"])
    section("Untracked documents", inventory["untracked_documents"])
    section(
        "Document symlinks",
        [
            (
                f"{record['path']} -> {record['symlink_target']}"
                f"{' [broken]' if record['symlink_broken'] else ''}"
                f"{' [external]' if record['symlink_external'] else ''}"
            )
            for record in inventory["documents"]
            if record["is_symlink"]
        ],
    )
    section("Warnings", inventory["warnings"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root to inspect")
    parser.add_argument(
        "--max-doc-bytes",
        type=int,
        default=32768,
        help="Threshold for always-loaded instruction or large-doc warnings",
    )
    parser.add_argument(
        "--include-txt",
        action="store_true",
        help="Treat every .txt file as a document instead of only doc-like paths and names",
    )
    parser.add_argument(
        "--include-excluded-dirs",
        action="store_true",
        help="Do not prune default generated/cache directories",
    )
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Additional directory basename to prune",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()

    inventory = build_inventory(
        Path(args.root),
        args.max_doc_bytes,
        include_txt=args.include_txt,
        include_excluded_dirs=args.include_excluded_dirs,
        exclude_dirs=args.exclude_dir,
    )
    if args.json:
        print(json.dumps(inventory, indent=2, sort_keys=True))
    else:
        print_human(inventory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
