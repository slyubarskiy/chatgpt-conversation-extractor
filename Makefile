# Makefile for extracted ChatGPT Settings and Privacy Portal exports.
#
# Default layout assumes this repository was cloned into:
#   User Online Activity/chatgpt-conversation-extractor/
# with the Privacy Portal zip parts next to it. The conversation shards are
# inside Conversations__*-chatgpt-*.zip and can be extracted with:
#   make extract-conversations-zip

UV ?= uv

# Override INPUT for one explicit file, or INPUT_DIR for a different export dir.
INPUT     ?=
INPUT_DIR ?= ..
OUTPUT    ?= output
FORMAT    ?= markdown
CONVERSATIONS_ZIP ?= $(firstword $(sort $(wildcard $(INPUT_DIR)/Conversations__*-chatgpt-*.zip)))

# The extractor now preserves file timestamps itself. Keep this default on so
# desktop search tools and file explorers can sort conversations chronologically.
PRESERVE_TIMESTAMPS ?= true

# Optional extractor features.
CONFIG         ?=
GPT_NAMES_XLSX ?=
ASSET_MODE     ?=
INLINE_PASTES  ?=

INPUT_PATH  = $(if $(INPUT),$(INPUT),$(INPUT_DIR))
MD_DIR      ?= $(OUTPUT)/md

EXTRACT_ARGS = --output-format "$(FORMAT)" --preserve-timestamps "$(PRESERVE_TIMESTAMPS)"
ifneq ($(CONFIG),)
EXTRACT_ARGS += --config "$(CONFIG)"
endif
ifneq ($(GPT_NAMES_XLSX),)
EXTRACT_ARGS += --gpt-names-xlsx "$(GPT_NAMES_XLSX)"
endif
ifneq ($(ASSET_MODE),)
EXTRACT_ARGS += --asset-mode "$(ASSET_MODE)"
endif
ifeq ($(INLINE_PASTES),false)
EXTRACT_ARGS += --no-inline-pastes
else ifeq ($(INLINE_PASTES),true)
EXTRACT_ARGS += --inline-pastes
endif

.PHONY: help sync install list-inputs extract-conversations-zip check-inputs extract extract-script extract-and-fix fix-timestamps test lint typecheck build clean

help:
	@echo "Usage:"
	@echo "  make sync"
	@echo "  make install"
	@echo "  make extract-conversations-zip"
	@echo "  make list-inputs"
	@echo "  make extract"
	@echo "  make extract INPUT=/path/to/conversations.json"
	@echo "  make extract INPUT_DIR=/path/to/User\\ Online\\ Activity"
	@echo "  make extract FORMAT=both OUTPUT=./output"
	@echo "  make extract GPT_NAMES_XLSX=/path/to/GPT_Names.xlsx"
	@echo "  make extract ASSET_MODE=copy INLINE_PASTES=true"
	@echo "  make extract-and-fix"
	@echo
	@echo "Current settings:"
	@echo "  INPUT              = $(INPUT)"
	@echo "  INPUT_DIR          = $(INPUT_DIR)"
	@echo "  CONVERSATIONS_ZIP  = $(CONVERSATIONS_ZIP)"
	@echo "  INPUT_PATH         = $(INPUT_PATH)"
	@echo "  OUTPUT             = $(OUTPUT)"
	@echo "  FORMAT             = $(FORMAT)"
	@echo "  PRESERVE_TIMESTAMPS= $(PRESERVE_TIMESTAMPS)"

sync:
	"$(UV)" sync --group dev

install: sync

list-inputs: sync
	"$(UV)" run chatgpt-extractor "$(INPUT_PATH)" --list-inputs

extract-conversations-zip:
	@if [ -z "$(CONVERSATIONS_ZIP)" ]; then \
		echo "No Conversations__*-chatgpt-*.zip found in $(INPUT_DIR)."; \
		echo "Override with CONVERSATIONS_ZIP=/path/to/Conversations__...-chatgpt-0001.zip."; \
		exit 1; \
	fi
	@echo "Extracting $(CONVERSATIONS_ZIP) into $(INPUT_DIR)"
	unzip -n "$(CONVERSATIONS_ZIP)" -d "$(INPUT_DIR)"

check-inputs: sync
	@"$(UV)" run chatgpt-extractor "$(INPUT_PATH)" --list-inputs > /dev/null

extract: install
	"$(UV)" run chatgpt-extractor "$(INPUT_PATH)" "$(OUTPUT)" $(EXTRACT_ARGS)

extract-script: install
	"$(UV)" run python extract.py "$(INPUT_PATH)" "$(OUTPUT)" $(EXTRACT_ARGS)

# Compatibility with the blog-post workflow. Usually unnecessary now because
# --preserve-timestamps true is the default, but useful for old output trees.
fix-timestamps:
	@echo "Updating timestamps recursively under $(MD_DIR) from YAML frontmatter"
	@find "$(MD_DIR)" -type f -name '*.md' -print | while IFS= read -r f; do \
		ts=$$(sed -n 's/^created:[[:space:]]*"\(.*\)".*/\1/p' "$$f" | head -n1); \
		if [ -z "$$ts" ]; then \
			ts=$$(sed -n 's/^updated:[[:space:]]*"\(.*\)".*/\1/p' "$$f" | head -n1); \
		fi; \
		[ -z "$$ts" ] && continue; \
		ts=$${ts%Z}; \
		ts=$${ts%%.*}; \
		touch -d "$$ts UTC" "$$f"; \
	done

extract-and-fix: extract fix-timestamps

test: sync
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "$(UV)" run pytest tests/ -q

lint: sync
	"$(UV)" run flake8 src tests --count --select=E9,F63,F7,F82 --show-source --statistics
	"$(UV)" run flake8 src tests --count --exit-zero --max-complexity=10 --max-line-length=120 --statistics
	"$(UV)" run black --fast --workers 1 --check --diff src tests extract.py

typecheck: sync
	"$(UV)" run mypy src/chatgpt_extractor

build: sync
	"$(UV)" run python -m build

clean:
	rm -rf .venv .uv-cache
