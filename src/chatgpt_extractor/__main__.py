"""
CLI entry point for ChatGPT Conversation Extractor.
"""

import sys
import argparse
from pathlib import Path

from .extractor import ConversationExtractorV2


def run_failure_analysis(input_file: str, output_dir: str) -> None:
    """Run failure analysis if extraction had failures."""
    log_file = Path(output_dir) / 'conversion_log.log'
    if not log_file.exists():
        print("\nNo failures to analyze (conversion_log.log not found)")
        return
    
    # Check if we have failures
    with open(log_file, 'r') as f:
        content = f.read()
        if 'Failed conversations: 0' in content or 'FAILURE CATEGORIES' not in content:
            print("\nNo failures to analyze (0 failures recorded)")
            return
    
    print("\n" + "="*60)
    print("RUNNING FAILURE ANALYSIS")
    print("="*60)
    
    try:
        # Try to import analyze_failures if available
        from .analyze_failures import analyze_failures
        analyze_failures(input_file, sample_size=20)
        print("\nFailure analysis complete. See failure_analysis_report.json")
    except ImportError:
        print("\nNote: analyze_failures module not found. Skipping detailed analysis.")
        print("Basic failure information available in conversion_log.log")


def main() -> None:
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description='Extract ChatGPT conversations to markdown files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Use default paths
  %(prog)s input.json output_dir/       # Custom paths
  %(prog)s --analyze-failures           # Run with failure analysis
        """
    )
    
    parser.add_argument('input_file', nargs='?', 
                       default='data/raw/conversations.json',
                       help='Path to conversations.json (default: data/raw/conversations.json)')
    
    parser.add_argument('output_dir', nargs='?',
                       default='data/output_md',
                       help='Output directory for markdown files (default: data/output_md)')
    
    parser.add_argument('--analyze-failures', action='store_true',
                       help='Run failure analysis after extraction if failures occur')
    
    parser.add_argument('--version', action='version',
                       version='ChatGPT Conversation Extractor v2.0')
    
    args = parser.parse_args()
    
    # Check input file exists
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: Input file '{args.input_file}' not found")
        sys.exit(1)
    
    # Run extraction
    extractor = ConversationExtractorV2(args.input_file, args.output_dir)
    extractor.extract_all()
    
    # Run failure analysis if requested
    if args.analyze_failures:
        run_failure_analysis(args.input_file, args.output_dir)


if __name__ == '__main__':
    main()