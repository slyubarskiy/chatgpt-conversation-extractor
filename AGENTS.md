# AGENTS.md

This file is policy guidance for coding agents, especially Codex, working in
this repository.

## Workflow Policy

- Never use system or base Python directly for project work.
- Use `uv run python`, `uv run <tool>`, `uv sync`, `uv add`, and
  `uv add --group dev`.
- Run `uv` and `make` commands from the repository root so
  `[tool.uv] cache-dir = "./.uv-cache"` applies consistently.
- If a package is needed for development workflows, add it to
  `pyproject.toml` under the `dev` dependency group and use it through `uv`.
- Keep dependencies declared in `pyproject.toml`; do not use ad-hoc `pip`
  installs.
- Avoid ad-hoc `uv` cache overrides for normal project work; use the
  repo-local cache configured in `pyproject.toml`.
- Library code should use `logging`; CLI presentation may use `print`.

## Documentation Policy

- When a task depends on library/tool documentation, APIs, configuration,
  migrations, or breaking changes, use Context7 instead of relying on memory.
- Prefer version-specific docs when the version can be inferred from
  `pyproject.toml`, `uv.lock`, or toolchain config.
- Keep documentation retrieval targeted to the exact API, option, or behavior
  needed.

## Required Post-Change Sequence

Run the relevant subset after making changes:

```bash
make sync
make list-inputs
make extract INPUT=tests/fixtures/sample_conversation.json OUTPUT=/tmp/chatgpt-extractor-smoke
make test
make lint
make typecheck
make build
```

For documentation-only changes, `make list-inputs` plus a README/diff review is
usually sufficient.

## Privacy Portal Export Workflow

- The default Makefile layout assumes this repository was cloned into
  `User Online Activity/chatgpt-conversation-extractor/`.
- After extracting the top-level Privacy Portal ZIP, `User Online Activity/`
  may initially contain nested ZIP files only. The chat shards are inside
  `../Conversations__*-chatgpt-*.zip`.
- `make extract-conversations-zip` extracts the nested conversations ZIP into
  `User Online Activity/` with `unzip -n`, creating shards such as
  `../conversations-000.json`, `../conversations-001.json`, etc.
- The `Ads__...zip` and `Files__...zip` archives are not required for the
  current Markdown conversation extraction workflow.
- `make extract` discovers `../conversations.json` and
  `../conversations-*.json`, then writes every run into the same `output/`
  directory.
- Treat `output/`, `logs/`, `data/`, and raw `conversations*.json` files as
  generated or private data unless a task explicitly targets them.

## Permissions Policy

- Standard project workflow commands are pre-authorized when they require
  network, cache, or sandbox escalation: `make sync`, `make extract`,
  `make test`, `make lint`, `make typecheck`, `make build`, `uv sync`, and
  `uv run ...`.
- AGENTS.md is policy guidance only; if the environment enforces escalation,
  still use the appropriate approval mechanism.
- Escalated permissions are a technical requirement when the sandbox prevents
  `uv` from writing `.uv-cache/` or when network access is needed for
  dependency resolution. They are not a request for new project-level approval.
- Use the configured repo-local `uv` cache for standard workflows instead of
  overriding it with an external cache path such as `~/.cache/uv`.

Plain language: for normal setup, run, test, lint, type-check, build, and
Privacy Portal extraction steps, proceed without re-asking unless the command is
outside the standard workflow.

## Logging

- Use Python's `logging` module for runtime output in library code instead of
  bare `print`.
- Keep CLI presentation user-facing; use `print` for deliberate command output
  and `logging` for diagnostics.
- Initialize logging centrally in CLI entrypoints or application setup code.
- Use module-level loggers or pass loggers consistently so warnings and
  milestones include enough context to debug failures.
