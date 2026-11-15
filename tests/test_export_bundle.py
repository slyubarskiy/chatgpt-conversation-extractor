"""Synthetic old/new exports: discovery, source fidelity, and asset recovery."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from chatgpt_extractor.extractor import ConversationExtractorV2
from chatgpt_extractor.inputs import discover_export, ConversationStream
from chatgpt_extractor.assets import AssetManager
from chatgpt_extractor.processors import MessageProcessor
from chatgpt_extractor.trackers import SchemaEvolutionTracker


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def conversation(identifier, text="Hello", metadata=None, project=None):
    return {
        "id": identifier,
        "title": identifier,
        "conversation_template_id": project,
        "mapping": {
            "root": {"id": "root", "parent": None, "message": None},
            "user": {
                "id": "user",
                "parent": "root",
                "message": {
                    "id": identifier + "-message",
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": [text]},
                    "metadata": metadata or {},
                },
            },
        },
        "current_node": "user",
    }


@pytest.fixture
def modern_export(tmp_path):
    """Names, IDs, text and bytes are invented, never copied from a real export."""
    root = tmp_path / "export with spaces"
    root.mkdir()
    paste = "Detailed pasted notes\n\n```python\nprint('fixture')\n```\n"
    payloads = {
        "file_a.dat": b"first uploaded file\n",
        "file_b.dat": b"second uploaded file\n",
        "file_paste.dat": paste.encode(),
        "file_image.dat": b"\x89PNG\r\n\x1a\nsynthetic image payload",
        "file_unknown.dat": b"%PDF-1.7\nsynthetic document",
    }
    for name, content in payloads.items():
        (root / name).write_bytes(content)
    write_json(
        root / "conversation_asset_file_names.json",
        {
            "file_a.dat": "notes.txt",
            "file_b.dat": "notes.txt",
            "file_paste.dat": "pasted-notes.md",
        },
    )
    write_json(
        root / "library_files.json",
        [
            {
                "id": "library-image",
                "file_id": "file-image",
                "file_name": "diagram.png",
                "mime_type": "image/png",
            },
            {
                "id": "library-paste",
                "file_id": "file-paste",
                "file_name": "display-name.md",
                "mime_type": "text/markdown",
            },
            {"file_id": "file-missing", "file_name": "missing.pdf"},
        ],
    )
    first = conversation(
        "first",
        "",
        {
            "attachments": [
                {"id": "file-paste", "name": "pasted-notes.md", "is_big_paste": True},
                {"id": "file-a", "name": "notes.txt"},
                {"id": "file-b", "name": "notes.txt"},
                {"library_file_id": "library-image", "name": "diagram.png"},
            ]
        },
        project="g-p-fixture",
    )
    second = conversation(
        "second",
        paste,
        {
            "attachments": [
                {"id": "file-paste", "is_big_paste": True, "name": "pasted-notes.md"},
            ]
        },
    )
    write_json(root / "payload" / "part-a.json", [first])
    write_json(root / "payload" / "part-b.json", [second, first])
    write_json(
        root / "export_manifest.json",
        {
            "version": 1,
            "logical_files": {
                "conversations.json": {
                    "files": ["payload/part-a.json", "payload/part-b.json"],
                    "sharded": True,
                }
            },
        },
    )
    # A manifest must win over unrelated or stale filename matches.
    (root / "conversations-999.json").write_text("not JSON")
    return root, paste, payloads


def test_manifest_order_and_explicit_file(modern_export):
    root, _, _ = modern_export
    expected = [root / "payload/part-a.json", root / "payload/part-b.json"]
    assert list(discover_export(root).files) == expected
    assert list(discover_export(root / "export_manifest.json").files) == expected
    assert discover_export(expected[0]).files == (expected[0],)
    stream = ConversationStream(discover_export(root).files)
    assert len(stream) == 3
    assert [c["id"] for c in stream] == ["first", "second", "first"]


@pytest.mark.parametrize(
    "filename",
    ["missing.json", "../outside.json", "/absolute.json", "nested\\outside.json"],
)
def test_manifest_rejects_missing_and_unsafe_paths(tmp_path, filename):
    write_json(
        tmp_path / "export_manifest.json",
        {
            "version": 1,
            "logical_files": {
                "conversations.json": {"files": [filename]},
            },
        },
    )
    write_json(tmp_path / "conversations.json", [conversation("legacy")])
    with pytest.raises((ValueError, FileNotFoundError)):
        discover_export(tmp_path)


@pytest.mark.parametrize(
    "manifest",
    [
        {"version": 2, "logical_files": {}},
        {"version": 1, "logical_files": []},
        {"version": 1, "logical_files": {"conversations.json": {"files": []}}},
    ],
)
def test_unsupported_or_incomplete_manifest_is_not_ignored(tmp_path, manifest):
    write_json(tmp_path / "export_manifest.json", manifest)
    with pytest.raises(ValueError):
        discover_export(tmp_path)


def test_legacy_directory_and_privacy_category(tmp_path):
    category = tmp_path / "User Online Activity"
    for number in (10, 2):
        write_json(
            category / f"conversations-{number}.json", [conversation(str(number))]
        )
    assert [p.name for p in discover_export(tmp_path).files] == [
        "conversations-2.json",
        "conversations-10.json",
    ]
    write_json(category / "conversations.json", [conversation("legacy")])
    assert [p.name for p in discover_export(tmp_path).files] == ["conversations.json"]


def test_manifest_cannot_follow_external_symlink(tmp_path):
    root = tmp_path / "export"
    root.mkdir()
    write_json(tmp_path / "outside.json", [])
    try:
        (root / "part.json").symlink_to(tmp_path / "outside.json")
    except OSError:
        pytest.skip("Symlinks unavailable")
    write_json(
        root / "export_manifest.json",
        {
            "version": 1,
            "logical_files": {"conversations.json": {"files": ["part.json"]}},
        },
    )
    with pytest.raises(ValueError, match="leaves"):
        discover_export(root)


@pytest.mark.parametrize("level", ["off", "minimal", "rich"])
def test_nested_source_items_respect_configuration(level):
    processor = MessageProcessor(SchemaEvolutionTracker())
    message = {
        "content": {"content_type": "text", "parts": ["Answer"]},
        "metadata": {
            "content_references": [
                {
                    "type": "grouped_webpages",
                    "items": [
                        {
                            "url": "https://example.org/paper?utm_source=chatgpt.com",
                            "title": "Paper",
                            "snippet": "Primary evidence",
                            "supporting_websites": [
                                {"url": "https://example.org/support"}
                            ],
                        },
                        None,
                        "malformed",
                        {"url": "https://[broken"},
                    ],
                },
                {
                    "type": "nav_list",
                    "items": [],
                    "fallback_items": [
                        {
                            "url": "https://example.org/paper",
                            "attribution": "Research group",
                        }
                    ],
                },
            ],
        },
    }
    urls, sources = processor._walk_url_sources(
        message, {}, {"content_references": level}
    )
    if level == "off":
        assert urls == sources == []
    else:
        assert urls == ["https://example.org/paper", "https://example.org/support"]
        if level == "minimal":
            assert sources == []
        else:
            assert sources == [
                {
                    "source": "content_references",
                    "url": "https://example.org/paper",
                    "title": "Paper",
                    "snippet": "Primary evidence",
                    "attribution": "Research group",
                }
            ]


def extract(root, output, **kwargs):
    ex = ConversationExtractorV2(
        str(root),
        str(output),
        output_format="both",
        preserve_timestamps=False,
        **kwargs,
    )
    ex.extract_all()
    assert ex.conversion_failures == []
    return ex


def test_copy_assets_pastes_collisions_and_project_links(modern_export, tmp_path):
    root, paste, payloads = modern_export
    output = tmp_path / "output"
    extract(root, output, asset_mode="copy", json_format="single")
    assert len(list((output / "assets").iterdir())) == len(payloads)
    assert (output / "assets/notes.txt").read_bytes() == payloads["file_a.dat"]
    assert (output / "assets/notes (2).txt").read_bytes() == payloads["file_b.dat"]
    assert (output / "assets/file_unknown.pdf").read_bytes().startswith(b"%PDF-")
    markdown = output / "md/g-p-fixture/first.md"
    text = markdown.read_text()
    assert paste in text
    assert "````text\n" in text
    assert "**Pasted text: pasted-notes.md**" in text
    assert "../../assets/notes%20%282%29.txt" in text
    assert "![diagram.png](../../assets/diagram.png)" in text
    assert "**Pasted text:" not in (output / "md/second.md").read_text()
    records = json.loads(next(output.glob("conversations_export_*.json")).read_text())[
        "conversations"
    ]
    assert {c["id"] for c in records} == {"first", "second"}
    first = next(c for c in records if c["id"] == "first")
    assert paste in first["messages"][0]["content"]
    for record in first["messages"][0]["assets"]:
        assert (output / record["path"]).is_file()
    assert len(list((output / "md").rglob("*.md"))) == 2
    # Re-running does not multiply attachments or overwrite unrelated files.
    extract(root, output, asset_mode="copy")
    assert len(list((output / "assets").iterdir())) == len(payloads)
    assert all((root / name).read_bytes() == data for name, data in payloads.items())


def test_relative_symlinks_are_reused(modern_export, tmp_path):
    root, _, payloads = modern_export
    probe = tmp_path / "probe"
    try:
        probe.symlink_to(root / "file_a.dat")
        probe.unlink()
    except OSError:
        pytest.skip("Symlinks unavailable")
    output = tmp_path / "output"
    for _ in range(2):
        extract(root, output, asset_mode="symlink")
    links = list((output / "assets").iterdir())
    assert len(links) == len(payloads)
    assert all(p.is_symlink() and not os.path.isabs(os.readlink(p)) for p in links)
    assert (output / "assets/notes (2).txt").resolve() == root / "file_b.dat"


def test_asset_options_and_legacy_attachment_only_message(modern_export, tmp_path):
    root, paste, _ = modern_export
    output = tmp_path / "output"
    extract(root, output, asset_mode="copy", inline_pastes=False)
    assert paste not in (output / "md/g-p-fixture/first.md").read_text()
    disabled = tmp_path / "disabled"
    extract(root, disabled, asset_mode="none")
    assert not (disabled / "assets").exists()
    assert (
        "[File: pasted-notes.md]" in (disabled / "md/g-p-fixture/first.md").read_text()
    )


def test_sanitized_names_do_not_escape_or_overwrite(tmp_path):
    root = tmp_path / "export"
    root.mkdir()
    (root / "file_a.dat").write_text("uploaded")
    (root / "file_b.dat").write_text("unicode filename")
    write_json(
        root / "conversation_asset_file_names.json",
        {
            "file_a.dat": "../../notes.txt",
            "file_b.dat": "🌍" * 100 + ".txt",
        },
    )
    output = tmp_path / "output"
    (output / "assets").mkdir(parents=True)
    (output / "assets/notes.txt").write_text("user-owned file")
    manager = AssetManager(root, [], output, "copy")
    manager.export_all()
    assert (output / "assets/notes.txt").read_text() == "user-owned file"
    assert (output / "assets/notes (2).txt").read_text() == "uploaded"
    assert not (tmp_path / "notes.txt").exists()
    unicode_file = next(
        p for p in (output / "assets").iterdir() if p.name.startswith("🌍")
    )
    assert unicode_file.read_text() == "unicode filename"


def test_cli_and_make_share_manifest_discovery(modern_export, tmp_path):
    root, _, _ = modern_export
    repo = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "chatgpt_extractor",
            str(root),
            str(tmp_path / "unused"),
            "--list-inputs",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    assert [Path(p).name for p in result.stdout.splitlines()] == [
        "part-a.json",
        "part-b.json",
    ]
    assert not (tmp_path / "unused").exists()
    if shutil.which("make") is None:
        pytest.skip("GNU make is not installed")
    output = tmp_path / "make output with spaces"
    result = subprocess.run(
        [
            "make",
            "extract",
            f"INPUT_DIR={root}",
            f"OUTPUT={output}",
            "FORMAT=both",
            "ASSET_MODE=copy",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert {p.stem for p in (output / "json").rglob("*.json")} == {"first", "second"}


def test_old_single_file_and_new_source_items_in_pipeline(tmp_path):
    conv = conversation(
        "legacy",
        "Old-style transcript",
        {
            "content_references": [
                {
                    "type": "grouped_webpages",
                    "items": [
                        {
                            "url": "https://example.org/new",
                            "title": "New source",
                            "snippet": "Searchable evidence",
                        }
                    ],
                }
            ]
        },
    )
    # The same parser accepts the older node shape with explicit children.
    conv["mapping"]["root"]["children"] = ["user"]
    conv["mapping"]["user"]["children"] = []
    write_json(tmp_path / "conversations.json", [conv])
    output = tmp_path / "output"
    extract(tmp_path / "conversations.json", output)
    text = (output / "md/legacy.md").read_text()
    assert "Old-style transcript" in text
    assert "[New source](https://example.org/new) — Searchable evidence" in text


def test_asset_survives_assistant_continuation_merge(tmp_path):
    ex = ConversationExtractorV2(output_dir=str(tmp_path))
    asset = {
        "id": "upload",
        "name": "notes.txt",
        "path": "assets/notes.txt",
        "mime_type": "text/plain",
    }
    merged = ex.merge_continuations(
        [
            {"role": "assistant", "content": "First"},
            {"role": "assistant", "content": "Second", "assets": [asset]},
        ]
    )
    assert merged[0]["assets"] == [asset]
    assert "[notes.txt](../assets/notes.txt)" in ex.generate_markdown(
        {"title": "Merged"}, merged
    )


def test_library_origin_recovers_file_only_assistant_reply(tmp_path):
    root = tmp_path / "export"
    root.mkdir()
    (root / "file_result.dat").write_text("Generated report")
    conv = conversation("generated", "")
    conv["mapping"]["user"]["message"]["author"]["role"] = "assistant"
    write_json(root / "conversations.json", [conv])
    write_json(
        root / "library_files.json",
        [
            {
                "file_id": "file-result",
                "file_name": "report.md",
                "origination_message_id": "generated-message",
            }
        ],
    )
    output = tmp_path / "output"
    extract(root, output, asset_mode="copy")
    assert (
        "[report.md](../assets/report.md)" in (output / "md/generated.md").read_text()
    )
    messages = json.loads((output / "json/generated.json").read_text())["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "assistant"
    assert messages[0]["assets"][0]["path"] == "assets/report.md"


def test_optional_metadata_errors_and_missing_attachment_do_not_lose_text(tmp_path):
    (tmp_path / "file_unknown.dat").write_bytes(b"%PDF-1.7\nfixture")
    (tmp_path / "conversation_asset_file_names.json").write_text("malformed JSON")
    write_json(tmp_path / "library_files.json", {})
    write_json(
        tmp_path / "conversations.json",
        [
            conversation(
                "missing",
                "Keep this message",
                {
                    "attachments": [{"id": "file-missing", "name": "unavailable.pdf"}],
                },
            )
        ],
    )
    output = tmp_path / "output"
    extract(tmp_path / "conversations.json", output, asset_mode="copy")
    text = (output / "md/missing.md").read_text()
    assert "Keep this message" in text
    assert "[File: unavailable.pdf]" in text
    assert (output / "assets/file_unknown.pdf").read_bytes().startswith(b"%PDF-")


def test_pastes_support_utf16_and_config_precedence(modern_export, tmp_path):
    root, paste, _ = modern_export
    (root / "file_paste.dat").write_bytes(paste.replace("\n", "\r\n").encode("utf-16"))
    config = tmp_path / "config.yaml"
    config.write_text("asset_mode: none\ninline_pastes: false\n")
    output = tmp_path / "output"
    extract(
        root, output, config_path=str(config), asset_mode="copy", inline_pastes=True
    )
    assert paste in (output / "md/g-p-fixture/first.md").read_text()
    assert "**Pasted text:" not in (output / "md/second.md").read_text()
    disabled = tmp_path / "disabled"
    extract(root, disabled, config_path=str(config))
    assert not (disabled / "assets").exists()


def test_manifest_lists_asset_in_separate_directory(tmp_path):
    write_json(
        tmp_path / "data/conversations.json",
        [
            conversation(
                "nested",
                "File attached",
                {
                    "attachments": [{"id": "file-a", "name": "notes.txt"}],
                },
            )
        ],
    )
    (tmp_path / "media").mkdir()
    (tmp_path / "media/file_a.dat").write_text("Nested attachment")
    write_json(
        tmp_path / "export_manifest.json",
        {
            "version": 1,
            "logical_files": {
                "conversations.json": {"files": ["data/conversations.json"]}
            },
            "export_files": [{"path": "media/file_a.dat"}],
        },
    )
    write_json(
        tmp_path / "library_files.json",
        [{"file_id": "file-a", "file_name": "notes.txt"}],
    )
    output = tmp_path / "output"
    extract(tmp_path, output, asset_mode="copy")
    assert (output / "assets/notes.txt").read_text() == "Nested attachment"
    assert "[notes.txt](../assets/notes.txt)" in (output / "md/nested.md").read_text()


def test_legacy_named_image_and_file_service_pointer(tmp_path):
    (tmp_path / "file-abcd-photo.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    write_json(
        tmp_path / "conversation_asset_file_names.json",
        {"file-abcd-photo.png": "photo.png"},
    )
    conv = conversation("legacy-image")
    conv["mapping"]["user"]["message"]["content"] = {
        "content_type": "multimodal_text",
        "parts": [
            {
                "content_type": "image_asset_pointer",
                "asset_pointer": "file-service://file-abcd",
            }
        ],
    }
    write_json(tmp_path / "conversations.json", [conv])
    output = tmp_path / "output"
    extract(tmp_path / "conversations.json", output, asset_mode="copy")
    assert (
        "![photo.png](../assets/photo.png)"
        in (output / "md/legacy-image.md").read_text()
    )
