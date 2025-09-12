#!/usr/bin/env python3
"""
Check performance metrics from extraction logs.
"""

import re
import sys
import argparse
from pathlib import Path


def parse_performance_log(log_file: str) -> dict:
    """Parse performance metrics from extraction log."""
    
    if not Path(log_file).exists():
        print(f"Log file not found: {log_file}")
        sys.exit(1)
    
    with open(log_file, 'r') as f:
        content = f.read()
    
    metrics = {}
    
    # Extract processing rate
    rate_match = re.search(r'Processing rate: ([\d.]+) conv/s', content)
    if rate_match:
        metrics['processing_rate'] = float(rate_match.group(1))
    
    # Extract success rate
    success_match = re.search(r'Success rate: ([\d.]+)%', content)
    if success_match:
        metrics['success_rate'] = float(success_match.group(1))
    
    # Extract total conversations
    total_match = re.search(r'Total conversations: (\d+)', content)
    if total_match:
        metrics['total_conversations'] = int(total_match.group(1))
    
    # Extract failed count
    failed_match = re.search(r'Failed: (\d+)', content)
    if failed_match:
        metrics['failed_conversations'] = int(failed_match.group(1))
    
    # Extract elapsed time
    time_match = re.search(r'Time elapsed: ([\d.]+)s', content)
    if time_match:
        metrics['elapsed_time'] = float(time_match.group(1))
    
    # Extract memory info from /usr/bin/time -v
    memory_match = re.search(r'Maximum resident set size \(kbytes\): (\d+)', content)
    if memory_match:
        metrics['max_memory_kb'] = int(memory_match.group(1))
        metrics['max_memory_mb'] = int(memory_match.group(1)) / 1024
    
    return metrics


def check_requirements(metrics: dict) -> bool:
    """Check if metrics meet performance requirements."""
    
    requirements = {
        'processing_rate': 30.0,  # minimum conv/s
        'success_rate': 95.0,     # minimum success rate %
        'max_memory_mb': 2048.0   # maximum memory usage in MB
    }
    
    passed = True
    
    print("Performance Requirements Check:")
    print("=" * 40)
    
    for metric, min_value in requirements.items():
        if metric in metrics:
            value = metrics[metric]
            
            if metric == 'max_memory_mb':
                status = "PASS" if value <= min_value else "FAIL"
                comparison = f"<= {min_value}"
            else:
                status = "PASS" if value >= min_value else "FAIL"
                comparison = f">= {min_value}"
            
            print(f"{metric}: {value:.1f} ({comparison}) - {status}")
            
            if status == "FAIL":
                passed = False
        else:
            print(f"{metric}: Not found in log - SKIP")
    
    print("=" * 40)
    print(f"Overall: {'PASS' if passed else 'FAIL'}")
    
    return passed


def main():
    parser = argparse.ArgumentParser(description='Check performance metrics')
    parser.add_argument('log_file', help='Performance log file to analyze')
    parser.add_argument('--strict', action='store_true',
                       help='Exit with error code if requirements not met')
    
    args = parser.parse_args()
    
    # Parse metrics
    metrics = parse_performance_log(args.log_file)
    
    if not metrics:
        print("No performance metrics found in log file")
        sys.exit(1)
    
    # Display all metrics
    print("Performance Metrics:")
    print("-" * 20)
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"{key}: {value:.1f}")
        else:
            print(f"{key}: {value}")
    print()
    
    # Check requirements
    passed = check_requirements(metrics)
    
    if args.strict and not passed:
        sys.exit(1)
    
    sys.exit(0)


if __name__ == '__main__':
    main()