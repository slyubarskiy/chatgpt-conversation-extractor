"""Recover named export assets and associate them with conversation messages."""

import filecmp
import json
import logging
import mimetypes
import os
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set
from urllib.parse import quote

from .inputs import contained_file

logger = logging.getLogger(__name__)


def file_id(value: str) -> str:
    value = value.rsplit("://", 1)[-1]
    value = re.sub(r"^file[-_]", "", value)
    return re.sub(r"\.dat$", "", value)


def safe_name(value: str) -> str:
    value = value.replace("\\", "/").rsplit("/", 1)[-1]
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip().rstrip(". ")
    if not value or value in {".", ".."}:
        return "attachment"
    stem, suffix = os.path.splitext(value)
    if stem.upper() in {"CON", "PRN", "AUX", "NUL"} or re.fullmatch(
        r"(?:COM|LPT)[1-9]", stem.upper()
    ):
        stem = "_" + stem
    suffix = suffix.encode("utf-8", errors="replace")[:32].decode(
        "utf-8", errors="ignore"
    )
    available = 200 - len(suffix.encode("utf-8"))
    stem = stem.encode("utf-8", errors="replace")[:available].decode(
        "utf-8", errors="ignore"
    )
    return stem + suffix


def markdown_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def asset_url(output_root: Path, relative_path: str, markdown_parent: Path) -> str:
    # Do not resolve the symlink: links should point at the restored filename.
    path = os.path.abspath(output_root / relative_path)
    try:
        relative = Path(os.path.relpath(path, markdown_parent)).as_posix()
    except ValueError:
        # Windows cannot represent a relative path across drives.
        return Path(path).as_uri()
    return quote(relative, safe="/")


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        logger.warning("Cannot read asset metadata %s", path.name)
        return default


def _signature(path: Path) -> str:
    """Recognize common raw payloads when neither metadata nor suffix helps."""
    try:
        with path.open("rb") as handle:
            head = handle.read(4096)
        for magic, mime in (
            (b"%PDF-", "application/pdf"),
            (b"\x89PNG\r\n\x1a\n", "image/png"),
            (b"\xff\xd8\xff", "image/jpeg"),
            (b"GIF8", "image/gif"),
        ):
            if head.startswith(magic):
                return mime
        if head.startswith(b"PK\x03\x04"):
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
            for prefix, kind in (
                ("word/", "wordprocessingml.document"),
                ("xl/", "spreadsheetml.sheet"),
            ):
                if any(name.startswith(prefix) for name in names):
                    return "application/vnd.openxmlformats-officedocument." + kind
            return "application/zip"
        if head[4:8] == b"ftyp":
            return "video/quicktime" if head[8:12] == b"qt  " else "video/mp4"
        if b"\x00" not in head:
            head.decode("utf-8")
            return "text/plain"
    except (OSError, UnicodeError, zipfile.BadZipFile):
        pass
    return "application/octet-stream"


@dataclass
class Asset:
    source: Path
    name: str
    mime_type: str = ""
    aliases: Set[str] = field(default_factory=set)
    exported: Optional[str] = None


class AssetManager:
    """One shared catalog per extraction, with stable names across all shards."""

    def __init__(self, root: Path, sources: Iterable[Path], output: Path, mode: str):
        self.root = root.resolve()
        self.output = output
        self.mode = mode
        self.assets: Dict[Path, Asset] = {}
        self.aliases: Dict[str, List[Asset]] = {}
        self.origins: Dict[str, List[Asset]] = {}
        self.projects: Dict[str, List[Asset]] = {}
        roots = sorted({self.root, *(p.parent.resolve() for p in sources)})
        for folder in roots:
            self._load_folder(folder)
        # Library aliases are added after scanning every folder, so a metadata
        # file at the export root may describe an asset beside a nested shard.
        for folder in roots:
            self._load_library(folder)
        for asset in self.assets.values():
            if not asset.mime_type:
                asset.mime_type = mimetypes.guess_type(asset.name)[0] or _signature(
                    asset.source
                )
            if asset.name.endswith(".dat"):
                suffix = mimetypes.guess_extension(asset.mime_type) or ".dat"
                asset.name = asset.name[:-4] + suffix
        self._reindex()

    def _register(self, path: Path, name: Optional[str] = None) -> Asset:
        asset = self.assets.get(path)
        if asset is None:
            asset = Asset(path, safe_name(name or path.name))
            asset.aliases.update(
                {path.name, path.stem, file_id(path.name), file_id(path.stem)}
            )
            self.assets[path] = asset
        elif name:
            asset.name = safe_name(name)
        return asset

    def _load_folder(self, folder: Path) -> None:
        for path in sorted(folder.iterdir()):
            if path.name.startswith(("file_", "file-")) and path.is_file():
                try:
                    self._register(
                        contained_file(
                            self.root, path.relative_to(self.root).as_posix()
                        )
                    )
                except (OSError, ValueError):
                    logger.warning(
                        "Skipping unavailable or external asset %s", path.name
                    )
        manifest = _read_json(folder / "export_manifest.json", {})
        if isinstance(manifest, dict):
            for entry in manifest.get("export_files", []) or []:
                name = entry.get("path") if isinstance(entry, dict) else None
                if not isinstance(name, str) or not Path(name).name.startswith(
                    ("file_", "file-")
                ):
                    continue
                try:
                    self._register(contained_file(folder, name))
                except (OSError, ValueError):
                    logger.warning("Manifest asset is unavailable: %s", name)
        names = _read_json(folder / "conversation_asset_file_names.json", {})
        if isinstance(names, dict):
            for filename, name in names.items():
                if not isinstance(name, str):
                    continue
                try:
                    path = contained_file(
                        self.root, (folder / filename).relative_to(self.root).as_posix()
                    )
                    self._register(path, name)
                except (OSError, ValueError):
                    logger.warning("Named asset is unavailable: %s", filename)

    def _find(self, identifier: Any) -> Optional[Asset]:
        if not isinstance(identifier, str):
            return None
        key = file_id(identifier)
        matches = (
            self.aliases.get(key, [])
            if self.aliases
            else [
                a
                for a in self.assets.values()
                if identifier in a.aliases or key in a.aliases
            ]
        )
        if not matches:
            # Older archives embed the original filename after the file ID.
            matches = [
                a
                for a in self.assets.values()
                if a.source.name.startswith((f"file-{key}-", f"file_{key}-"))
            ]
        return matches[0] if len(matches) == 1 else None

    def _load_library(self, folder: Path) -> None:
        records = _read_json(folder / "library_files.json", [])
        if not isinstance(records, list):
            return
        for record in records:
            if not isinstance(record, dict):
                continue
            asset = self._find(record.get("file_id"))
            if asset is None:
                continue
            # Prefer the original-name map to a Library display name.
            if asset.name == safe_name(asset.source.name) and isinstance(
                record.get("file_name"), str
            ):
                asset.name = safe_name(record["file_name"])
            if isinstance(record.get("mime_type"), str):
                asset.mime_type = record["mime_type"]
            library_id = record.get("id")
            if isinstance(library_id, dict):
                library_id = library_id.get("id")
            if isinstance(library_id, str):
                asset.aliases.add(library_id)
            origin = record.get("origination_message_id")
            if isinstance(origin, str):
                self.origins.setdefault(origin, []).append(asset)
            project = record.get("gizmo_id")
            if (
                isinstance(project, str)
                and project.startswith("g-p-")
                and record.get("is_project") is not False
            ):
                self.projects.setdefault(project, []).append(asset)

    def _reindex(self) -> None:
        for asset in self.assets.values():
            for alias in {file_id(a) for a in asset.aliases}:
                self.aliases.setdefault(alias, []).append(asset)

    def export_all(self) -> None:
        if not self.assets:
            return
        directory = self.output / "assets"
        if directory.is_symlink():
            raise ValueError("The output assets directory must not be a symlink")
        directory.mkdir(parents=True, exist_ok=True)
        used: Set[str] = set()
        for source, asset in sorted(self.assets.items()):
            name = asset.name
            stem, suffix = os.path.splitext(name)
            counter = 1
            while True:
                candidate = directory / name
                occupied = candidate.exists() or candidate.is_symlink()
                reusable = False
                if occupied:
                    if self.mode == "symlink":
                        reusable = (
                            candidate.is_symlink() and candidate.resolve() == source
                        )
                    elif candidate.is_file() and not candidate.is_symlink():
                        reusable = filecmp.cmp(source, candidate, shallow=False)
                # casefold makes naming consistent on case-insensitive systems.
                if name.casefold() not in used and (not occupied or reusable):
                    break
                counter += 1
                name = f"{stem} ({counter}){suffix}"
            used.add(name.casefold())
            try:
                if not occupied:
                    if self.mode == "copy":
                        shutil.copy2(source, candidate)
                    else:
                        try:
                            target = os.path.relpath(source, directory.resolve())
                        except ValueError:
                            target = str(source)
                        candidate.symlink_to(target)
                asset.exported = candidate.relative_to(self.output).as_posix()
            except OSError:
                logger.warning("Cannot export asset %s; try --asset-mode copy", name)
        logger.info(
            "Exported %d named assets using %s",
            sum(a.exported is not None for a in self.assets.values()),
            self.mode,
        )

    def for_message(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        metadata = message.get("metadata") or {}
        references = []
        for attachment in metadata.get("attachments") or []:
            if isinstance(attachment, dict):
                references.append((attachment, attachment.get("is_big_paste") is True))
        for part in (message.get("content") or {}).get("parts") or []:
            if isinstance(part, dict) and part.get("asset_pointer"):
                references.append(({"id": part["asset_pointer"]}, False))
        for ref in metadata.get("content_references") or []:
            if isinstance(ref, dict) and ref.get("type") == "file":
                references.append((ref, False))
        found: Dict[Path, Dict[str, Any]] = {}
        for ref, big_paste in references:
            asset = self._find(ref.get("id")) or self._find(ref.get("library_file_id"))
            if asset is None:
                logger.debug("Referenced asset is unavailable")
                continue
            found.setdefault(asset.source, self._record(asset))
            if big_paste:
                found[asset.source]["is_big_paste"] = True
        for asset in self.origins.get(message.get("id"), []):
            found.setdefault(asset.source, self._record(asset))
        return list(found.values())

    def for_project(self, project: str) -> List[Dict[str, Any]]:
        """Return exported files explicitly associated with this project.

        This is project-level context, not evidence that a particular message
        uploaded or used a file. Custom GPT knowledge stays out of this list.
        """
        assets = {a.source: a for a in self.projects.get(project, [])}
        return [
            self._record(a)
            for a in sorted(
                assets.values(), key=lambda a: (a.name.casefold(), a.source)
            )
        ]

    @staticmethod
    def _record(asset: Asset) -> Dict[str, Any]:
        return {
            "id": file_id(asset.source.stem),
            "name": asset.name,
            "path": asset.exported,
            "mime_type": asset.mime_type,
        }

    def include_pastes(self, content: str, records: List[Dict[str, Any]]) -> str:
        for record in records:
            if not record.get("is_big_paste"):
                continue
            asset = self._find(record["id"])
            if asset is None:
                continue
            try:
                raw = asset.source.read_bytes()
                encoding = (
                    "utf-16"
                    if raw.startswith((b"\xff\xfe", b"\xfe\xff"))
                    else "utf-8-sig"
                )
                text = raw.decode(encoding)
                if "\x00" in text:
                    raise UnicodeError("Not a text attachment")
            except (OSError, UnicodeError):
                logger.warning("Cannot read pasted text from %s", asset.name)
                continue
            normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
            existing = content.replace("\r\n", "\n").replace("\r", "\n")
            if not normalized or normalized in existing:
                continue
            # A fence longer than any run in the paste preserves embedded code
            # fences and Markdown verbatim, without truncation.
            fence = "`" * max(
                3, max((len(m) + 1 for m in re.findall(r"`+", text)), default=0)
            )
            if content:
                content += "\n\n"
            content += (
                f"**Pasted text: {markdown_label(asset.name)}**\n\n{fence}text\n{text}"
            )
            if not text.endswith("\n"):
                content += "\n"
            content += fence
        return content
