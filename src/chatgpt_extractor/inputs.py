"""Discover exported conversation files without depending on the request route."""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)
SHARD_PATTERN = re.compile(r"conversations-(\d+)\.json$")


def contained_file(root: Path, name: str) -> Path:
    """Resolve an export-relative path, rejecting paths outside the export."""
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name:
        raise ValueError(f"Unsafe export path: {name!r}")
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        raise ValueError(f"Export path leaves the export directory: {name!r}")
    if not path.is_file():
        raise FileNotFoundError(f"Export file not found: {root / relative}")
    return path


@dataclass(frozen=True)
class ExportBundle:
    root: Path
    files: Tuple[Path, ...]


def _manifest_bundle(manifest: Path) -> ExportBundle:
    with manifest.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError(f"Unsupported export manifest version in {manifest}")
    logical = data.get("logical_files")
    if not isinstance(logical, dict):
        raise ValueError(f"Missing logical_files in {manifest}")
    names: List[str] = []
    for name, entry in logical.items():
        if Path(name).name != "conversations.json":
            continue
        if not isinstance(entry, dict) or not isinstance(entry.get("files"), list):
            raise ValueError(f"Invalid conversation file list in {manifest}")
        for filename in entry["files"]:
            if not isinstance(filename, str) or not filename:
                raise ValueError(f"Invalid conversation filename in {manifest}")
            names.append(filename)
    if not names:
        raise ValueError(f"No conversation files declared in {manifest}")
    # A manifest is authoritative: never silently skip a declared missing shard.
    files = tuple(dict.fromkeys(contained_file(manifest.parent, n) for n in names))
    return ExportBundle(manifest.parent.resolve(), files)


def discover_export(input_path: Path) -> ExportBundle:
    """Accept an explicit JSON file, manifest, or extracted export directory.

    Directory discovery prefers a version-1 manifest, then conversations.json,
    then numbered shards. Already-extracted Privacy Portal category folders are
    supported; nested ZIP extraction remains an explicit Makefile operation.
    """
    input_path = Path(input_path).expanduser()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file or directory not found: {input_path}")
    if input_path.is_file():
        if input_path.name == "export_manifest.json":
            return _manifest_bundle(input_path)
        return ExportBundle(input_path.parent.resolve(), (input_path.resolve(),))
    manifest = input_path / "export_manifest.json"
    if manifest.is_file():
        return _manifest_bundle(manifest)
    legacy = input_path / "conversations.json"
    if legacy.is_file():
        return ExportBundle(
            input_path.resolve(), (contained_file(input_path, legacy.name),)
        )
    shards = sorted(
        (p for p in input_path.iterdir() if SHARD_PATTERN.fullmatch(p.name)),
        key=lambda p: (int(SHARD_PATTERN.fullmatch(p.name).group(1)), p.name),
    )
    if shards:
        return ExportBundle(
            input_path.resolve(),
            tuple(contained_file(input_path, p.name) for p in shards),
        )
    category = input_path / "User Online Activity"
    if category.is_dir():
        return discover_export(category)
    raise FileNotFoundError(
        f"No conversation files found in {input_path}. Expected export_manifest.json, "
        "conversations.json, or conversations-*.json. Extract the conversations ZIP first."
    )


def load_conversations(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        conversations = json.load(handle)
    if not isinstance(conversations, list):
        raise ValueError(f"Conversation input must contain a JSON array: {path}")
    if any(c is not None and not isinstance(c, dict) for c in conversations):
        raise ValueError(f"Conversation array contains a non-object entry: {path}")
    return conversations


class ConversationStream:
    """Keep at most one shard loaded while providing an aggregate progress total."""

    def __init__(self, files: Tuple[Path, ...]):
        self.files = files
        self._single: Optional[List[Dict[str, Any]]] = None
        self.total = 0
        for path in files:
            conversations = load_conversations(path)
            self.total += len(conversations)
            if len(files) == 1:
                self._single = conversations

    def __len__(self) -> int:
        return self.total

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        if self._single is not None:
            yield from self._single
            return
        for path in self.files:
            logger.info("Loading conversation shard %s", path.name)
            yield from load_conversations(path)
