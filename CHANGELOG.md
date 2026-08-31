# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Per-type `web_urls` config overlay for URL extraction control.
  Accepts a preset string (`off | citations | rich`) or an explicit
  per-type map at YAML key `web_urls`, with per-type levels
  `off | minimal | rich`. `off` skips the source, `minimal` extracts
  URLs only (feeding the `**Web Search URLs:**` block), `rich`
  extracts URL + title + snippet/quote (feeding the existing
  `**Citations:**` block for `citations`, or a new `**Sources:**`
  block for `search_result_groups` / `content_references`). Default
  preserves the pre-PR-#17 behavior for backward compatibility:
  `citations: rich`, `conv_safe_urls: minimal`, and the newer
  metadata paths off. The `rich` preset is aimed at operators
  indexing rendered markdown into BM25/embedding search engines
  where inline title + snippet content is more valuable than URL
  bulk. Markdown output applies cross-block URL dedup at render
  time (a URL in Citations or Sources is not repeated in Web
  Search URLs); JSON output keeps `citations`, `web_urls`, and
  `web_sources` whole so downstream indexers don't silently lose
  data. `_isolated_config_env` fixture promoted to conftest for
  shared use.
- Extract URLs from newer message metadata sources (PR #17,
  contributor @cs224). Adds coverage for `metadata.safe_urls`,
  `metadata.search_result_groups`, `metadata.content_references`,
  and nested `supporting_websites`, plus a `_normalize_web_url`
  helper that strips `?utm_source=chatgpt.com` and `#:~:text=…`
  fragments so dedup catches near-variants across all sources.
- Custom GPT / per-turn model / plugin metadata in output (PR #6).
  Frontmatter gains `gizmo_id`, `gizmo_type`, `models_used` (deduped
  per-message slug set). Per-turn italic line gains `· model_slug`,
  `· plugin:<namespace>`, and `· gpt:<id>` (the last only when the
  per-message gizmo differs from the conversation default — the
  @mention case). JSON per-message dicts mirror the same fields.
- `GPT_Names.xlsx` sidecar reader (PR #7). When `--gpt-names-xlsx <path>`
  (or `config.gpt_names_xlsx`) points at a 2- or 3-column xlsx mapping
  `gizmo_id → name`, frontmatter gains `gpt_name:` for Custom GPT
  conversations and the per-turn `gpt:<id>` substitutes
  `gpt:<Pretty Name>` with id fallback when the name is unknown.
  Missing / unreadable sidecar silently degrades to id-only output.
- Per-message timestamps in markdown + JSON output (PR #5). Italic
  ISO-8601 UTC line beneath each role heading; `timestamp` field on
  every JSON message. Gated by `--per-turn-timestamps` /
  `--no-per-turn-timestamps` (default on).
- Layered YAML config (PR #5). Built-in defaults → file (explicit
  path → `$CHATGPT_EXTRACTOR_CONFIG` → `./chatgpt_extractor.yaml` →
  `~/.config/chatgpt_extractor/config.yaml`) → CLI args. Malformed
  YAML falls back silently. Keys: `per_turn_timestamps`,
  `gpt_metadata`, `gpt_names_xlsx`.
- `ConversationExtractorV2(input_file=None)` allowed (PR #4) for
  callers that only use the per-conversation methods on in-memory
  dicts (e.g. the live-sync renderer).

### Changed
- Black formatting is now enforced in CI rather than advisory. The
  tree was reformatted in one sweep (#21, no logic changes), a
  `pyproject.toml` now pins `line-length = 88`, and the CI format
  check no longer runs with `continue-on-error`, so an unformatted
  tree fails the build. `setup.py` was added to the checked paths.
  The Black requirement is pinned to the 25.x stable-style series:
  `line-length` fixes the width but not the style, and Black changes
  its stable style at calendar-year releases. Contributors should run
  `black src tests extract.py setup.py` before pushing — see
  CONTRIBUTING.md.
- `extract_metadata` now emits `models_used:` (the deduped per-
  message `model_slug` set) — the legacy `model:` field still emits
  `default_model_slug` unchanged for backwards compatibility.
- `merge_continuations` inherits `model_slug` / `gizmo_id` /
  `plugin_namespace` from the earliest segment alongside
  `create_time`, matching "the assistant began replying" semantics.

### Fixed
- URL extraction no longer captures surrounding markdown as part of the
  URL. The regex stops only at whitespace, `<`, `>` and `"`, so a link
  written as `[https://x.com](https://x.com)` was captured whole as
  `https://x.com](https://x.com)` and emitted into the
  `**Web Search URLs:**` block. Captures are now truncated at their first
  *unbalanced* closing delimiter, which leaves URLs that legitimately
  contain balanced ones intact — Wikipedia disambiguation paths
  (`/wiki/Python_(programming_language)`) and bracketed IPv6 hosts
  (`http://[::1]:8080/`). Measured over 54 real conversations: 17 changed,
  1,476 captures trimmed, every one removing markup rather than URL
  content, and no trimmed result left invalid.
- A malformed URL no longer aborts rendering of the entire
  conversation. The URL-extraction regex (`https?://[^\s<>"]+`) does not
  exclude `]` or `)`, so a markdown link written as
  `[https://x.com](https://x.com)` is captured whole as
  `https://x.com](https://x.com`. `urlsplit` raises
  `ValueError: Invalid IPv6 URL` on a netloc containing an unmatched
  bracket, and that propagated out of `_normalize_web_url` and killed the
  whole conversation over one junk capture — observed on 3 of 41
  conversations in a live incremental sync. Unparseable URLs are now
  dropped, which is how every caller already treats a `None` return.
  Well-formed bracketed IPv6 hosts (`http://[::1]:8080/`) still parse.
- Frontmatter `created:` and `updated:` are now emitted as true UTC
  regardless of host timezone. Prior to this change, `extract_metadata`
  called `datetime.fromtimestamp(t).isoformat() + "Z"`, which returns
  local wall time and then falsely labelled it UTC — outputs were off
  by the host's local UTC offset (e.g. +1h under BST). Per-turn body
  timestamps were already correct; this restores file-internal
  consistency between the two surfaces. Parametric test coverage
  across UTC, Europe/London, US/Pacific, and Asia/Kolkata asserts
  the byte-level output is identical to what a UTC-set host produces.
- `g-p-*` (project) ids no longer leak into the per-turn `gpt:`
  segment of project conversations (PR #8). Per-message metadata in
  project convs echoes the project id as `gizmo_id`; the segment now
  filters those out, leaving real Custom GPT @mentions
  (`g-XXXX` form) emitting cleanly.

### Architecture
- New module `src/chatgpt_extractor/gpt_metadata.py` (pure functions
  + the `load_gpt_names_xlsx` sidecar reader) isolates the
  Custom-GPT logic from the extractor's main class. The companion
  writer lives in the private `online_sync` package; the live sync
  inherits the read path via `OnlineRenderer` wrapping
  `ConversationExtractorV2` unchanged.
- New module `src/chatgpt_extractor/config.py` (`load_config` +
  `DEFAULTS`) implements the layered config loader.

## [3.1] - 2025-09-12

### Changed
- Default output directory changed from `data/output_md` to
  `data/output`. Markdown files now land in `data/output/md/` by
  default; pass `--markdown-dir <path>` to override without the
  subdirectory.
- Added `--output-format {markdown,json,both}`,
  `--json-format {single,multiple}`, `--markdown-dir`, `--json-dir`,
  `--json-file` for multi-format output configuration.

## [2.0.0] - 2025-01-12

### Added
- Complete modular architecture with separate components
- Schema evolution tracking for unknown patterns
- Real-time progress indication with ETA
- Comprehensive error logging and failure analysis
- Project folder organization for conversations
- Web URL extraction from 6+ sources
- Citation validation and deduplication
- Graph index tracking for proper message merging
- Support for 11 content types
- Backward traversal algorithm (O(n) complexity)
- YAML frontmatter in markdown output
- Automatic branch exclusion in conversations
- Support for multimodal content (images, audio, video)
- Custom instructions extraction
- DALL-E image prompt preservation

### Changed
- Refactored into modular package structure
- Improved message continuation merging with validation
- Enhanced URL extraction with multiple sources
- Better handling of None values throughout
- Optimized performance to 65-100 conversations/second

### Fixed
- NoneType error in DALL-E metadata checking (10% of failures)
- Python 're' module scoping issue (89% of failures)
- Message merging validation using graph indices
- Custom instructions extraction from multiple wrapper formats
- Empty parts array handling in multimodal content

### Performance
- Success rate: 99-100%
- Processing speed: 65-100 conversations/second
- Memory usage: <2GB for 500MB input files
- Tested with 6,885 conversations

## [1.0.0] - 2025-01-01

### Added
- Initial release
- Basic extraction functionality
- Simple markdown output
- 92% success rate before fixes

---

For detailed release notes, see the [GitHub Releases](https://github.com/yourusername/chatgpt-conversation-extractor/releases) page.