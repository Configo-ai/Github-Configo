from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RepoSpec:
    alias: str
    directory: str
    default_branch: str
    knowledge_path: str


def manifest_path(root: Path) -> Path:
    return root / "tools" / "workspace_runtime.yaml"


def load_manifest(root: Path) -> dict[str, Any]:
    path = manifest_path(root)
    return json.loads(path.read_text(encoding="utf-8"))


def repo_specs(root: Path) -> list[RepoSpec]:
    manifest = load_manifest(root)
    repos = []
    for item in manifest["repos"]:
        repos.append(
            RepoSpec(
                alias=item["alias"],
                directory=item["directory"],
                default_branch=item["default_branch"],
                knowledge_path=item["knowledge_path"],
            )
        )
    return repos


def qmd_knowledge_collections(root: Path) -> list[dict[str, str]]:
    return list(load_manifest(root)["qmd"]["knowledge_collections"])


def qmd_conversation_collections(root: Path) -> list[dict[str, str]]:
    return list(load_manifest(root)["qmd"]["conversation_collections"])


def server_names(root: Path) -> dict[str, str]:
    return dict(load_manifest(root)["mcp"]["server_names"])


def skills_allow(root: Path) -> list[str]:
    return list(load_manifest(root)["skills_allow"])


def plugins(root: Path) -> list[str]:
    return list(load_manifest(root)["plugins"])


def session_store(root: Path) -> dict[str, str]:
    return dict(load_manifest(root)["session_store"])


def opencode_version(root: Path) -> str:
    return str(load_manifest(root)["opencode_version"])
