# ChatGPT Extractor - Quick Reference Card

## 🚀 Command Line

```bash
# Basic usage
python extract_conversations_v2.py

# Custom paths
python extract_conversations_v2.py input.json output_dir/

# With logging
python extract_conversations_v2.py 2>&1 | tee log.txt
```

## 📁 File Structure

```
Input:  data/raw/conversations.json
Output: data/output_md/*.md
Logs:   data/output_md/schema_evolution.log
        data/output_md/conversion_log.log
```

## 🔑 Key Classes & Methods

```python
# Main extractor
extractor = ConversationExtractorV2(input_file, output_dir)
extractor.extract_all()

# Key methods
extract_metadata(conv) → Dict
backward_traverse(mapping, current_node, conv_id) → List[Dict]
process_messages(messages, conv_id, conv_data) → List[Dict]
generate_markdown(metadata, messages) → str
save_to_file(metadata, content) → None

# Message processor
processor = MessageProcessor(schema_tracker)
processor.should_filter_message(msg) → bool
processor.extract_message_content(msg, conv_id) → Optional[str]
processor.extract_web_urls(msg, conv_data) → List[str]
processor.extract_citations(msg) → List[Dict]
processor.merge_continuations(messages) → List[Dict]
```

## 📊 Content Types

| Type | Extract Method | Filter? |
|------|---------------|---------|
| `text` | Join parts[] | No |
| `code` | Format with lang | No |
| `multimodal_text` | Process parts[] | No |
| `execution_output` | Format as output | No |
| `user_editable_context` | Extract instructions | No |
| `model_editable_context` | - | Yes |
| `thoughts` | - | Yes |
| `reasoning_recap` | - | Yes |

## 🔍 URL Extraction Sources

1. `message.metadata.citations[].metadata.url`
2. `conversation.safe_urls[]`
3. `content.url` (tether_quote, sonic_webpage)
4. `content.domain` (add https://)
5. `content.result` (regex parse)
6. `parts[]` text (regex extract)

## ⚠️ Critical Checks

```python
# ALWAYS check None before 'in'
if metadata and 'key' in metadata:

# ALWAYS check parts is list
if parts and isinstance(parts, list):

# ALWAYS handle None parts
if part is None:
    continue

# ALWAYS use .get() with defaults
value = dict.get('key', default)
```

## 📈 Progress Indicators

```
Normal:  Progress: 3000/6885 (43.6%) | Failed: 0 | Rate: 83.9/s | ETA: 46s
Warning: Failed: >10 | Rate: <30/s | ETA: increasing
```

## 🐛 Quick Debugging

```bash
# Check failures
grep "Failed:" log.txt | tail -1

# View error categories
grep "FAILURE CATEGORIES" conversion_log.log -A 10

# Check unknown patterns
grep "Unknown" schema_evolution.log

# Count output files
ls data/output_md/*.md | wc -l

# Validate JSON
python -c "import json; json.load(open('conversations.json'))"
```

## 📝 Output Format

```markdown
---
id: uuid
title: "Title"
created: 2024-01-01T12:00:00Z
model: gpt-4
chat_url: https://chatgpt.com/c/uuid
---

# Title

## User
Message [File: doc.pdf]

## Assistant
Response
```

## 🔧 Common Fixes

| Error | Fix |
|-------|-----|
| No module 'yaml' | `pip install pyyaml` |
| NoneType not iterable | Check None before 'in' |
| Memory error | Split file or add RAM |
| 0% success | Check JSON validity |

## 📊 Performance Targets

- **Success Rate**: >99%
- **Speed**: 65-100 conv/s
- **Memory**: <2GB for 500MB input
- **Time**: ~100s for 6,000 convs

## 🗂️ Log Files

### schema_evolution.log
- Unknown content types
- New author roles
- Unknown part types
- New metadata fields

### conversion_log.log
- Failed conversation IDs
- Error categories
- Structural issues
- Debug traces

### conversion_failures.json
- Machine-readable failures
- Full error details
- Problematic nodes

## 🔄 Message Flow

```
1. Load JSON
2. For each conversation:
   a. Extract metadata
   b. Backward traverse graph
   c. Filter messages
   d. Process content
   e. Extract URLs/citations
   f. Merge continuations
   g. Generate markdown
   h. Save to file
3. Generate reports
```

## 🎯 Filtering Rules

**Include:**
- ✅ User messages
- ✅ Assistant messages  
- ✅ User system prompts

**Exclude:**
- ❌ Tool messages (except DALL-E)
- ❌ Hidden messages
- ❌ Thoughts/reasoning
- ❌ Empty placeholders

## 💡 Pro Tips

1. **SSD > HDD** for 2-3x speed
2. **Close other apps** to free RAM
3. **Don't interrupt** - let it complete
4. **Check logs** for insights
5. **99% success** is normal
6. **Projects** auto-organize
7. **URLs** from 6+ sources
8. **Graph indices** ensure proper merging

---
*v2.0 | Python 3.8+ | PyYAML required*