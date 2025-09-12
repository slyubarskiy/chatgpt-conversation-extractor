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
    
    # Check if we have failures
    with open(log_file, 'r') as f:
        content = f.read()
        if 'Failed conversations: 0' in content or 'FAILURE CATEGORIES' not in content:
            logger.info("No failures to analyze (0 failures recorded)")
            return
    
    logger.info("="*60)
    logger.info("RUNNING FAILURE ANALYSIS")
    logger.info("="*60)
    
    try:
        # Try to import analyze_failures if available
        from .analyze_failures import analyze_failures
        analyze_failures(input_file, sample_size=20)
        logger.info("Failure analysis complete. See failure_analysis_report.json")
    except ImportError:
        logger.debug("analyze_failures module not found. Skipping detailed analysis.")
        logger.info("Basic failure information available in conversion_log.log")


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
    
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    
    parser.add_argument('--version', action='version',
                       version='ChatGPT Conversation Extractor v2.0')
    
    args = parser.parse_args()
    
    # Set up logging first
    logger = configure_production_logging(debug=args.debug)
    
    try:
        logger.info("Starting ChatGPT Conversation Extractor")
        
        # Check input file exists
        input_path = Path(args.input_file)
        if not input_path.exists():
            logger.critical(f"Input file '{args.input_file}' not found")
            sys.exit(1)
        
        # Run extraction
        extractor = ConversationExtractorV2(args.input_file, args.output_dir)
        extractor.extract_all()
        
        # Run failure analysis if requested
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