# ChatGPT Conversation Extractor - Operations & Troubleshooting Guide

## Table of Contents
1. [Operational Overview](#operational-overview)
2. [Pre-Operation Checklist](#pre-operation-checklist)
3. [Standard Operating Procedures](#standard-operating-procedures)
4. [Monitoring & Observability](#monitoring--observability)
5. [Troubleshooting Guide](#troubleshooting-guide)
6. [Recovery Procedures](#recovery-procedures)
7. [Maintenance Tasks](#maintenance-tasks)
8. [Emergency Procedures](#emergency-procedures)

## Operational Overview

### System Profile
- **Type**: Batch processing ETL tool
- **Runtime**: Python 3.8+ standalone script
- **Duration**: ~100 seconds for 6,000+ conversations
- **Resource Usage**: 1-2GB RAM, minimal CPU
- **Criticality**: Non-critical, offline processing

### Key Metrics
| Metric | Normal Range | Alert Threshold |
|--------|--------------|-----------------|
| Success Rate | 99-100% | <95% |
| Processing Speed | 65-100 conv/s | <30 conv/s |
| Memory Usage | <2GB | >3GB |
| Completion Time | 60-120s | >300s |

## Pre-Operation Checklist

### System Requirements Verification

```bash
# 1. Check Python version
python --version  # Should be 3.8+

# 2. Verify dependencies
python -c "import yaml; print('PyYAML OK')"

# 3. Check disk space
df -h .  # Need 2x input file size

# 4. Verify input file
ls -lh data/raw/conversations.json
file data/raw/conversations.json  # Should be JSON

# 5. Check output directory permissions
touch data/output_md/test.txt && rm data/output_md/test.txt
```

### Input Validation

```bash
# Validate JSON structure
python -c "
import json
with open('data/raw/conversations.json') as f:
    data = json.load(f)
    print(f'Valid JSON with {len(data)} conversations')
"

# Check file size
du -h data/raw/conversations.json
```

## Standard Operating Procedures

### SOP-001: Normal Extraction

```bash
# 1. Navigate to project directory
cd /path/to/chatgpt-extractor

# 2. Verify input file is in place
ls -la data/raw/conversations.json

# 3. Clear previous output (optional)
rm -rf data/output_md/*

# 4. Run extraction with logging
python extract_conversations_v2.py 2>&1 | tee extraction_$(date +%Y%m%d_%H%M%S).log

# 5. Verify completion
echo "Exit code: $?"
ls -la data/output_md/*.md | head -5
```

### SOP-002: Large File Processing

```bash
# For files >1GB
# 1. Check available memory
free -h

# 2. Run with memory monitoring
/usr/bin/time -v python extract_conversations_v2.py

# 3. Monitor in separate terminal
watch -n 1 'ps aux | grep python | grep -v grep'
```

### SOP-003: Batch Processing Multiple Files

```bash
#!/bin/bash
# Process multiple export files

for json_file in exports/*.json; do
    echo "Processing: $json_file"
    basename=$(basename "$json_file" .json)
    output_dir="output/${basename}"
    
    mkdir -p "$output_dir"
    
    python extract_conversations_v2.py "$json_file" "$output_dir" 2>&1 | \
        tee "logs/${basename}_$(date +%Y%m%d).log"
    
    if [ $? -eq 0 ]; then
        echo "✓ Success: $basename"
    else
        echo "✗ Failed: $basename"
    fi
done
```

## Monitoring & Observability

### Real-Time Monitoring

```bash
# Watch progress in real-time
python extract_conversations_v2.py 2>&1 | while read line; do
    echo "$(date '+%H:%M:%S') $line"
done
```

### Progress Indicators

Normal progress output:
```
Progress: 3000/6885 (43.6%) | Failed: 0 | Rate: 83.9/s | ETA: 46s
```

Warning signs:
- Failed count increasing rapidly
- Rate dropping below 30/s
- ETA increasing instead of decreasing

### Log Analysis

```bash
# Check for errors
grep -i error extraction.log

# Count failures
grep "Failed:" extraction.log | tail -1

# View failure categories
grep "FAILURE CATEGORIES" data/output_md/conversion_log.log -A 10

# Check schema evolution
head -50 data/output_md/schema_evolution.log
```

## Troubleshooting Guide

### Issue Resolution Matrix

| Symptom | Likely Cause | Solution | Prevention |
|---------|--------------|----------|------------|
| Script crashes immediately | Missing dependency | `pip install pyyaml` | Use requirements.txt |
| "File not found" | Wrong path | Check file location | Use absolute paths |
| Memory error | Large file | Increase RAM or split file | Monitor memory |
| 0% success rate | Corrupted JSON | Validate JSON structure | Verify export |
| Slow processing | I/O bottleneck | Use SSD, close other apps | Optimize disk usage |
| High failure rate | Format changes | Check schema_evolution.log | Update extractor |

### Detailed Troubleshooting

#### Problem: TypeError: argument of type 'NoneType' is not iterable

```python
# Symptom in log:
TypeError: argument of type 'NoneType' is not iterable
File "extract_conversations_v2.py", line 252, in _contains_dalle_image

# Root cause:
metadata is None but code tries: 'dalle' in metadata

# Fix:
Update to latest version or patch:
if metadata and 'dalle' in metadata:

# Verification:
grep -n "in metadata" extract_conversations_v2.py
```

#### Problem: High Memory Usage

```bash
# Monitor memory
watch -n 1 free -h

# If approaching limit:
# 1. Split the input file
python -c "
import json
with open('data/raw/conversations.json') as f:
    data = json.load(f)
    mid = len(data) // 2
    
    with open('part1.json', 'w') as f1:
        json.dump(data[:mid], f1)
    with open('part2.json', 'w') as f2:
        json.dump(data[mid:], f2)
"

# 2. Process separately
python extract_conversations_v2.py part1.json output1/
python extract_conversations_v2.py part2.json output2/
```

#### Problem: Specific Conversations Failing

```python
# Analyze failures
python -c "
import json
with open('data/output_md/conversion_failures.json') as f:
    failures = json.load(f)
    
# Group by error type
from collections import Counter
categories = Counter(f['category'] for f in failures)
print('Failure categories:', categories)

# Show problematic conversation IDs
for f in failures[:5]:
    print(f\"{f['conversation_id']}: {f['error_message'][:50]}\")
"
```

## Recovery Procedures

### Partial Extraction Recovery

```bash
# If extraction interrupted:
# 1. Check what was completed
ls data/output_md/*.md | wc -l

# 2. Identify last processed
ls -lt data/output_md/*.md | head -1

# 3. Resume from checkpoint (requires code modification)
# Add to process_conversation():
# if os.path.exists(f"{output_dir}/{safe_title}.md"):
#     return  # Skip already processed
```

### Corrupted Output Recovery

```bash
# If output is corrupted:
# 1. Backup corrupted files
mkdir backup_corrupted
mv data/output_md backup_corrupted/

# 2. Clean output directory
mkdir -p data/output_md

# 3. Re-run extraction
python extract_conversations_v2.py

# 4. Compare results
diff -r backup_corrupted/output_md data/output_md
```

### Failed Conversation Extraction

```python
# Extract only failed conversations
# 1. Get failed IDs from log
import json
with open('data/output_md/conversion_failures.json') as f:
    failed_ids = [f['conversation_id'] for f in json.load(f)]

# 2. Create subset JSON
with open('data/raw/conversations.json') as f:
    all_convs = json.load(f)
    
failed_convs = [c for c in all_convs if c.get('id') in failed_ids]

with open('failed_only.json', 'w') as f:
    json.dump(failed_convs, f)

# 3. Process with debugging
python -u extract_conversations_v2.py failed_only.json debug_output/
```

## Maintenance Tasks

### Daily Maintenance

```bash
# Clean up old logs
find . -name "extraction_*.log" -mtime +7 -delete

# Check disk space
df -h data/
```

### Weekly Maintenance

```bash
# Archive processed files
tar -czf "archive_$(date +%Y%m%d).tar.gz" data/output_md/
mv archive_*.tar.gz archives/

# Update dependencies
pip install --upgrade pyyaml
```

### Monthly Maintenance

```bash
# Performance analysis
for log in logs/*.log; do
    echo "$log:"
    grep "Processing rate:" "$log" | tail -1
done

# Schema evolution review
cat data/output_md/schema_evolution.log | grep "Unknown"
```

## Emergency Procedures

### System Hang

```bash
# 1. Identify process
ps aux | grep extract_conversations

# 2. Check if actually processing
strace -p [PID] 2>&1 | head -20

# 3. If truly hung, terminate
kill -TERM [PID]
# Wait 10 seconds
kill -KILL [PID]  # Force if needed

# 4. Check partial output
ls -la data/output_md/ | tail
```

### Disk Full

```bash
# 1. Check usage
df -h
du -sh data/*

# 2. Emergency cleanup
# Remove duplicates
fdupes -dN data/output_md/

# 3. Compress output
gzip data/output_md/*.md
```

### Memory Exhaustion

```bash
# 1. Check memory
free -h
dmesg | grep -i "out of memory"

# 2. Clear cache
sync && echo 3 > /proc/sys/vm/drop_caches

# 3. Limit memory usage
ulimit -v 2097152  # Limit to 2GB
python extract_conversations_v2.py
```

## Performance Tuning

### Optimization Checklist

```bash
# 1. Use SSD for I/O
df -h  # Check mount points
lsblk  # Verify SSD

# 2. Increase file descriptors
ulimit -n 4096

# 3. Python optimizations
python -O extract_conversations_v2.py  # Run optimized

# 4. Parallel processing (future enhancement)
# Split file and process in parallel
```

### Benchmarking

```bash
# Time different phases
time python -c "
import json, time
start = time.time()
with open('data/raw/conversations.json') as f:
    data = json.load(f)
print(f'Load time: {time.time()-start:.2f}s')
"

# Full benchmark
/usr/bin/time -v python extract_conversations_v2.py 2>&1 | \
    tee benchmark_$(date +%Y%m%d).log
```

## Incident Response

### Incident Classification

| Level | Criteria | Response Time | Action |
|-------|----------|---------------|--------|
| P1 | Total failure, 0% success | Immediate | Debug and patch |
| P2 | <50% success rate | 1 hour | Investigate patterns |
| P3 | <95% success rate | 4 hours | Review logs |
| P4 | Schema changes detected | 24 hours | Plan update |

### Post-Incident Review

```markdown
## Incident Report Template

**Date**: YYYY-MM-DD
**Duration**: XX minutes
**Impact**: X conversations failed

### Summary
Brief description of issue

### Root Cause
Technical explanation

### Resolution
Steps taken to resolve

### Prevention
Changes to prevent recurrence

### Logs
- extraction_YYYYMMDD.log
- conversion_log.log
- schema_evolution.log
```

## Health Checks

### Quick Health Check

```bash
#!/bin/bash
# health_check.sh

echo "=== ChatGPT Extractor Health Check ==="

# Check Python
python --version || echo "❌ Python not found"

# Check dependencies
python -c "import yaml" 2>/dev/null && echo "✓ PyYAML installed" || echo "❌ PyYAML missing"

# Check directories
[ -d "data/raw" ] && echo "✓ Input directory exists" || echo "❌ Input directory missing"
[ -d "data/output_md" ] && echo "✓ Output directory exists" || echo "❌ Output directory missing"

# Check input file
if [ -f "data/raw/conversations.json" ]; then
    size=$(du -h data/raw/conversations.json | cut -f1)
    echo "✓ Input file present ($size)"
else
    echo "❌ Input file missing"
fi

# Check disk space
available=$(df -h . | awk 'NR==2 {print $4}')
echo "ℹ Disk space available: $available"

echo "=== Check Complete ==="
```

### Continuous Monitoring

```python
# monitor.py - Run alongside extraction
import psutil
import time

while True:
    # CPU usage
    cpu = psutil.cpu_percent(interval=1)
    
    # Memory usage
    mem = psutil.virtual_memory()
    
    # Disk I/O
    disk = psutil.disk_io_counters()
    
    print(f"CPU: {cpu}% | RAM: {mem.percent}% | Disk R: {disk.read_bytes/1e9:.1f}GB")
    time.sleep(5)
```