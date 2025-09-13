"""
CLI entry point for ChatGPT Conversation Extractor.
"""

import sys
import argparse
from pathlib import Path

from .extractor import ConversationExtractorV2
from .logging_config import configure_production_logging, get_logger, log_exception


def run_failure_analysis(input_file: str, output_dir: str) -> None:
    """Run failure analysis if extraction had failures."""
    logger = get_logger(__name__)
    log_file = Path(output_dir) / 'conversion_log.log'
    if not log_file.exists():
        logger.info("No failures to analyze (conversion_log.log not found)")
        return
    
    # Analyze failures if any occurred to identify patterns for future improvements
    with open(log_file, 'r') as f:
        content = f.read()
        if 'Failed conversations: 0' in content or 'FAILURE CATEGORIES' not in content:
            logger.info("No failures to analyze (0 failures recorded)")
            return
    
    logger.info("="*60)
    logger.info("RUNNING FAILURE ANALYSIS")
    logger.info("="*60)
    
    try:
        # Import failure analyzer dynamically since it's an optional diagnostic tool
        from .analyze_failures import analyze_failures
        analyze_failures(input_file, sample_size=20)
        logger.info("Failure analysis complete. See failure_analysis_report.json")
    except ImportError:
        logger.debug("analyze_failures module not found. Skipping detailed analysis.")
        logger.info("Basic failure information available in conversion_log.log")


def validate_cli_arguments(args: argparse.Namespace) -> None:
    """Validate CLI argument combinations for consistency.
    
    Ensures mutually exclusive options aren't used together and that
    format-specific arguments are only used with appropriate output formats.
    JSON-specific validations prevent configuration conflicts early.
    """
    logger = get_logger(__name__)
    
    # Prevent conflicting JSON output specifications that would create ambiguous behavior
    if args.json_dir and args.json_file:
        logger.error("Cannot specify both --json-dir and --json-file")
        sys.exit(1)
    
    # Ensure format selection aligns with output type to prevent configuration errors
    # Only validate if JSON output is actually being used (via json_dir or json_file)
    if (args.json_dir or args.json_file) and args.output_format == 'markdown':
        logger.error("JSON output options can only be used when --output-format includes 'json' or 'both'")
        sys.exit(1)
    
    # Single file path only makes sense for consolidated output, not individual files
    if args.json_file and args.json_format != 'single':
        logger.error("--json-file can only be used with --json-format single")
        sys.exit(1)
    
    # Directory path needed for individual files, not meaningful for single file output
    if args.json_dir and args.json_format == 'single':
        logger.error("--json-dir can only be used with --json-format multiple")
        sys.exit(1)


def main() -> None:
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description='Extract ChatGPT conversations to markdown and/or JSON files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                      # Default: markdown to data/output/md/
  %(prog)s input.json output_dir/               # Custom paths (markdown)
  %(prog)s --output-format json                 # JSON only to data/output/json/
  %(prog)s --output-format both                 # Both formats to data/output/
  %(prog)s --json-format single                 # Single consolidated JSON file
  %(prog)s --markdown-dir custom/md/            # Override markdown output location
  %(prog)s --json-dir custom/json/              # Override JSON output location
  %(prog)s --preserve-timestamps false          # Disable timestamp synchronization
  %(prog)s --analyze-failures                   # Run failure analysis if errors occur
  
Migration note for v3.1:
  Default output directory changed from 'data/output_md' to 'data/output'.
  Markdown files now go to 'data/output/md/' subdirectory by default.
  Use --markdown-dir to specify custom location without subdirectory.
        """
    )
    
    # Positional arguments with updated default
    parser.add_argument('input_file', nargs='?', 
                       default='data/raw/conversations.json',
                       help='Path to conversations.json (default: data/raw/conversations.json)')
    
    parser.add_argument('output_dir', nargs='?',
                       default='data/output',  # Changed from data/output_md
                       help='Output directory for files (default: data/output)')
    
    # Output format options
    parser.add_argument('--output-format', 
                       choices=['markdown', 'json', 'both'],
                       default='markdown',
                       help='Output format(s) to generate (default: markdown)')
    
    parser.add_argument('--json-format',
                       choices=['single', 'multiple'],
                       default='multiple',
                       help='JSON output structure: single consolidated file or multiple individual files (default: multiple)')
    
    # Directory override options
    parser.add_argument('--markdown-dir',
                       help='Override markdown output directory (bypasses md/ subdirectory creation)')
    
    parser.add_argument('--json-dir',
                       help='Override JSON output directory for multiple format (bypasses json/ subdirectory creation)')
    
    parser.add_argument('--json-file',
                       help='Override JSON output file path for single format')
    
    # Timestamp synchronization
    parser.add_argument('--preserve-timestamps',
                       type=lambda x: x.lower() in ['true', '1', 'yes'],
                       default=True,
                       help='Sync file timestamps with conversation metadata (default: true)')
    
    # Existing options
    parser.add_argument('--analyze-failures', action='store_true',
                       help='Run failure analysis after extraction if failures occur')
    
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    
    parser.add_argument('--version', action='version',
                       version='ChatGPT Conversation Extractor v3.1')
    
    args = parser.parse_args()
    
    # Initialize logging before any operations for complete diagnostic coverage
    logger = configure_production_logging(debug=args.debug)
    
    # Ensure CLI arguments are logically consistent before processing
    validate_cli_arguments(args)
    
    try:
        logger.info("Starting ChatGPT Conversation Extractor v3.1")
        logger.info(f"Output format: {args.output_format}")
        if args.output_format in ['json', 'both']:
            logger.info(f"JSON format: {args.json_format}")
        
        # Verify input accessibility early to fail fast with clear error message
        input_path = Path(args.input_file)
        if not input_path.exists():
            logger.critical(f"Input file '{args.input_file}' not found")
            sys.exit(1)
        
        # Execute extraction with format-aware configuration and timestamp preservation
        extractor = ConversationExtractorV2(
            input_file=args.input_file,
            output_dir=args.output_dir,
            output_format=args.output_format,
            json_format=args.json_format,
            markdown_dir=args.markdown_dir,
            json_dir=args.json_dir,
            json_file=args.json_file,
            preserve_timestamps=args.preserve_timestamps
        )
        extractor.extract_all()
        
        # Perform diagnostic analysis on failures to aid debugging and schema evolution
        if args.analyze_failures:
            run_failure_analysis(args.input_file, args.output_dir)
            
        logger.info("Extraction completed successfully")
        
    except KeyboardInterrupt:
        logger.info("Extraction cancelled by user")
        sys.exit(0)
    except Exception as e:
        log_exception(logger, e, "main extraction process")
        sys.exit(1)


if __name__ == '__main__':
    main()