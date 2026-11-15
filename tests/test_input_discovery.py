"""Discovery and validation for synthetic legacy and manifest-based bundles."""

import gc
import json
import weakref

import pytest

from chatgpt_extractor import inputs
from chatgpt_extractor.inputs import ConversationStream, discover_export


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def manifest(*files):
    return {
        "version": 1,
        "logical_files": {"conversations.json": {"files": list(files)}},
    }


def test_manifest_order_duplicates_and_unrelated_files(tmp_path):
    write_json(tmp_path / "payload/second.json", [])
    write_json(tmp_path / "payload/first.json", [])
    write_json(tmp_path / "conversations.json", [])
    (tmp_path / "conversations-999.json").write_text("not JSON")
    write_json(
        tmp_path / "export_manifest.json",
        manifest("payload/second.json", "payload/first.json", "payload/second.json"),
    )
    for path in (tmp_path, tmp_path / "export_manifest.json"):
        bundle = discover_export(path)
        assert bundle.root == tmp_path
        assert bundle.files == (
            tmp_path / "payload/second.json",
            tmp_path / "payload/first.json",
        )


def test_legacy_file_precedes_shards_and_shards_sort_numerically(tmp_path):
    for n in (10, 2):
        write_json(tmp_path / f"conversations-{n}.json", [])
    write_json(tmp_path / "conversations-other.json", [])
    write_json(tmp_path / "library_files.json", [])
    assert [p.name for p in discover_export(tmp_path).files] == [
        "conversations-2.json",
        "conversations-10.json",
    ]
    write_json(tmp_path / "conversations.json", [])
    assert discover_export(tmp_path).files == (tmp_path / "conversations.json",)


def test_extracted_privacy_portal_category(tmp_path):
    category = tmp_path / "User Online Activity"
    write_json(category / "conversations-000.json", [])
    assert discover_export(tmp_path) == discover_export(category)


def test_explicit_json_file_ignores_siblings_and_manifest(tmp_path):
    path = tmp_path / "custom.json"
    write_json(path, [])
    (tmp_path / "export_manifest.json").write_text("invalid manifest")
    assert discover_export(path).files == (path,)


@pytest.mark.parametrize("name", ["missing", "."])
def test_no_input_files_gives_an_actionable_error(tmp_path, name):
    with pytest.raises(FileNotFoundError, match="not found|No conversation files"):
        discover_export(tmp_path / name)


@pytest.mark.parametrize(
    "data",
    [
        [],
        None,
        {},
        {"version": True, "logical_files": {}},
        {"version": 2, "logical_files": {}},
        {"version": 1, "logical_files": []},
        {"version": 1, "logical_files": {}},
        {"version": 1, "logical_files": {"conversations.json": []}},
        {"version": 1, "logical_files": {"conversations.json": {"files": "a.json"}}},
        manifest(),
        manifest(""),
        manifest(None),
    ],
)
def test_invalid_manifest_never_falls_back_to_stale_files(tmp_path, data):
    write_json(tmp_path / "export_manifest.json", data)
    write_json(tmp_path / "conversations.json", [])
    with pytest.raises(ValueError):
        discover_export(tmp_path)


@pytest.mark.parametrize(
    "name",
    [
        "../outside.json",
        "/absolute.json",
        "C:/absolute.json",
        "C:relative.json",
        "nested\\file.json",
        "\\\\server\\file.json",
    ],
)
def test_manifest_rejects_paths_that_can_escape_the_export(tmp_path, name):
    write_json(tmp_path / "export_manifest.json", manifest(name))
    with pytest.raises(ValueError, match="Unsafe export path"):
        discover_export(tmp_path)


@pytest.mark.parametrize("mode", ["manifest", "legacy", "shard"])
def test_directory_discovery_rejects_external_symlinks(tmp_path, mode):
    root = tmp_path / "export"
    root.mkdir()
    outside = tmp_path / "outside.json"
    write_json(outside, [])
    name = {
        "manifest": "payload.json",
        "legacy": "conversations.json",
        "shard": "conversations-000.json",
    }[mode]
    try:
        (root / name).symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable on this platform")
    if mode == "manifest":
        write_json(root / "export_manifest.json", manifest(name))
    with pytest.raises(ValueError, match="leaves the export directory"):
        discover_export(root)


def test_missing_manifest_shard_does_not_use_other_files(tmp_path):
    write_json(tmp_path / "export_manifest.json", manifest("missing.json"))
    write_json(tmp_path / "conversations-000.json", [])
    with pytest.raises(FileNotFoundError, match="missing.json"):
        discover_export(tmp_path)


def test_malformed_manifest_is_not_ignored(tmp_path):
    (tmp_path / "export_manifest.json").write_text("not JSON")
    write_json(tmp_path / "conversations.json", [])
    with pytest.raises(json.JSONDecodeError):
        discover_export(tmp_path)


@pytest.mark.parametrize("data", [{}, "text", 7, [7]])
def test_non_conversation_json_is_rejected(tmp_path, data):
    path = tmp_path / "conversations.json"
    write_json(path, data)
    with pytest.raises(ValueError, match="JSON array|non-object"):
        ConversationStream((path,))


def test_empty_arrays_and_null_entries_remain_supported(tmp_path):
    path = tmp_path / "conversations.json"
    write_json(path, [])
    stream = ConversationStream((path,))
    assert len(stream) == 0
    assert list(stream) == []
    write_json(path, [None, {}])
    stream = ConversationStream((path,))
    assert len(stream) == 2
    assert list(stream) == [None, {}]


def test_stream_does_not_retain_previous_raw_shards(tmp_path, monkeypatch):
    files = tuple(tmp_path / f"part-{n}.json" for n in range(3))
    for n, path in enumerate(files):
        write_json(path, [{"id": str(n)}])
    original_load = inputs.load_conversations
    previous = None

    class TrackableList(list):
        pass

    def checked_load(path):
        nonlocal previous
        gc.collect()
        assert previous is None or previous() is None
        data = TrackableList(original_load(path))
        previous = weakref.ref(data)
        return data

    monkeypatch.setattr(inputs, "load_conversations", checked_load)
    stream = ConversationStream(files)
    assert len(stream) == 3
    assert [c["id"] for c in stream] == ["0", "1", "2"]


def test_single_file_is_not_reloaded_after_validation(tmp_path):
    path = tmp_path / "conversations.json"
    write_json(path, [{"id": "first"}])
    stream = ConversationStream((path,))
    path.write_text("no longer readable JSON")
    assert list(stream) == [{"id": "first"}]
