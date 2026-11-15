"""End-to-end directory input cases using wholly synthetic conversations."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from chatgpt_extractor.extractor import ConversationExtractorV2


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def conversation(identifier, project=None):
    return {
        "id": identifier,
        "title": identifier,
        "conversation_template_id": project,
        "mapping": {
            "user": {
                "id": "user",
                "parent": None,
                "message": {
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": [identifier]},
                },
            }
        },
        "current_node": "user",
    }


@pytest.fixture
def export_directory(tmp_path):
    root = tmp_path / "export with spaces"
    write_json(root / "conversations-010.json", [conversation("third")])
    write_json(root / "conversations-002.json", [conversation("second", "g-p-test")])
    write_json(root / "conversations-000.json", [conversation("first")])
    write_json(root / "library_files.json", [{"not": "a conversation"}])
    return root


def cli(tmp_path, *args, script=False):
    # Resolve from this test, never an installed fork, so child processes test
    # the same checkout as the parent pytest process.
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=str(root / "src"))
    prefix = [str(root / "extract.py")] if script else ["-m", "chatgpt_extractor"]
    return subprocess.run(
        [sys.executable, *prefix, *map(str, args)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )


@pytest.mark.parametrize("json_format", ["single", "multiple"])
def test_directory_extraction_combines_shards(
    export_directory, tmp_path, _isolated_config_env, json_format
):
    output = tmp_path / "output"
    extractor = ConversationExtractorV2(
        input_file=str(export_directory),
        output_dir=str(output),
        output_format="both",
        json_format=json_format,
    )
    extractor.extract_all()
    assert extractor.markdown_processed == extractor.json_processed == 3
    assert extractor.conversion_failures == []
    assert sorted(p.stem for p in (output / "md").rglob("*.md")) == [
        "first",
        "second",
        "third",
    ]
    assert (output / "md/g-p-test/second.md").is_file()
    if json_format == "single":
        data = json.loads(
            extractor.output_paths["json_file"].read_text(encoding="utf-8")
        )
        assert [c["id"] for c in data["conversations"]] == ["first", "second", "third"]
    else:
        assert len(list((output / "json").rglob("*.json"))) == 3


@pytest.mark.parametrize("script", [False, True])
def test_cli_accepts_directory_input(export_directory, tmp_path, script):
    output = tmp_path / "cli-output"
    result = cli(tmp_path, export_directory, output, script=script)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(list((output / "md").rglob("*.md"))) == 3
    assert "3/3" in result.stdout
    assert "Failed: 0" in result.stdout


def test_cli_listing_does_not_create_output_or_logs(export_directory, tmp_path):
    output = tmp_path / "never-created"
    result = cli(tmp_path, export_directory, output, "--list-inputs")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == [
        str(export_directory / f"conversations-{n:03}.json") for n in (0, 2, 10)
    ]
    assert not output.exists()
    assert not (tmp_path / "logs").exists()


def test_explicit_shard_warns_and_remains_single_file(export_directory, tmp_path):
    output = tmp_path / "single-shard-output"
    result = cli(tmp_path, export_directory / "conversations-000.json", output)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(list((output / "md").rglob("*.md"))) == 1
    assert "only" in (result.stdout + result.stderr).lower()
    assert "directory" in (result.stdout + result.stderr).lower()


def test_invalid_later_shard_fails_before_writing_conversations(
    export_directory, tmp_path, _isolated_config_env
):
    (export_directory / "conversations-010.json").write_text("invalid JSON")
    output = tmp_path / "invalid-output"
    extractor = ConversationExtractorV2(
        input_file=str(export_directory), output_dir=str(output), output_format="both"
    )
    with pytest.raises(json.JSONDecodeError):
        extractor.extract_all()
    assert not list(output.rglob("*.md"))
    assert not list(output.rglob("*.json"))


@pytest.mark.parametrize("listing", [False, True])
def test_missing_manifest_shard_is_a_cli_error(tmp_path, listing):
    root = tmp_path / "incomplete"
    write_json(root / "conversations.json", [conversation("stale")])
    write_json(
        root / "export_manifest.json",
        {
            "version": 1,
            "logical_files": {"conversations.json": {"files": ["missing.json"]}},
        },
    )
    output = tmp_path / "incomplete-output"
    args = [root, output] + (["--list-inputs"] if listing else [])
    result = cli(tmp_path, *args)
    assert result.returncode != 0
    assert "missing.json" in result.stdout + result.stderr
    assert not list(output.rglob("*.md"))


def test_manifest_extraction_uses_declared_order_only(tmp_path, _isolated_config_env):
    root = tmp_path / "manifest-export"
    write_json(root / "payload/second.json", [conversation("second")])
    write_json(root / "payload/first.json", [conversation("first")])
    write_json(root / "conversations.json", [conversation("stale")])
    write_json(
        root / "export_manifest.json",
        {
            "version": 1,
            "logical_files": {
                "conversations.json": {
                    "files": ["payload/second.json", "payload/first.json"]
                }
            },
        },
    )
    extractor = ConversationExtractorV2(
        input_file=str(root / "export_manifest.json"),
        output_dir=str(tmp_path / "manifest-output"),
        output_format="json",
        json_format="single",
    )
    extractor.extract_all()
    data = json.loads(extractor.output_paths["json_file"].read_text(encoding="utf-8"))
    assert [c["id"] for c in data["conversations"]] == ["second", "first"]


def test_conversion_failures_are_collected_across_shards(
    tmp_path, _isolated_config_env
):
    root = tmp_path / "partly-invalid-export"
    for n in range(2):
        invalid = conversation(f"invalid-{n}")
        invalid["create_time"] = "not a timestamp"
        write_json(
            root / f"conversations-{n:03}.json",
            [invalid, conversation(f"valid-{n}")],
        )
    output = tmp_path / "failure-output"
    extractor = ConversationExtractorV2(
        input_file=str(root), output_dir=str(output), output_format="both"
    )
    extractor.extract_all()
    assert extractor.markdown_processed == extractor.json_processed == 2
    assert len(extractor.conversion_failures) == 2
    report = (output / "conversion_log.log").read_text(encoding="utf-8")
    assert "invalid-0" in report
    assert "invalid-1" in report
