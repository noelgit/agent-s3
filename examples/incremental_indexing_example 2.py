"""
Example script demonstrating how to use the incremental indexing system.

This script shows how to integrate the incremental indexing system with
the existing CodeAnalysisTool and StaticAnalyzer classes.

Usage:
    python examples/incremental_indexing_example.py /path/to/repository
"""

import os
import sys
import time
import argparse
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("incremental_indexing_example")

# Add the parent directory to the path to import agent_s3
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import required modules
try:
    from agent_s3.tools.code_analysis_tool import CodeAnalysisTool
    from agent_s3.tools.static_analyzer import StaticAnalyzer
    from agent_s3.tools.file_tool import FileTool
    from agent_s3.tools.embedding_client import EmbeddingClient
    from agent_s3.tools.incremental_indexing_adapter import install_incremental_indexing
except ImportError as e:
    logger.error(f"Error importing Agent-S3 modules: {e}")
    logger.error("Make sure you're running this script from the root of the Agent-S3 repository")
    sys.exit(1)

def progress_callback(progress: Dict[str, Any]) -> None:
    """Callback function for indexing progress updates."""
    percentage = progress.get('percentage', 0)
    message = progress.get('message', '')
    current = progress.get('current', 0)
    total = progress.get('total', 1)
    
    sys.stdout.write(f"\r{message} ({current}/{total}) - {percentage}%")
    sys.stdout.flush()
    
    if current >= total:
        sys.stdout.write("\n")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Incremental indexing example for Agent-S3')
    parser.add_argument('repo_path', help='Path to the repository to index')
    parser.add_argument('--full', action='store_true', help='Force full reindexing')
    parser.add_argument('--watch', action='store_true', help='Enable watch mode')
    parser.add_argument('--search', help='Search query (if provided)')
    args = parser.parse_args()
    
    # Validate repository path
    if not os.path.isdir(args.repo_path):
        logger.error(f"Repository path does not exist or is not a directory: {args.repo_path}")
        sys.exit(1)
    
    # Create dependencies
    try:
        logger.info("Initializing components...")
        file_tool = FileTool(args.repo_path)
        embedding_client = EmbeddingClient()  # Will use default OpenAI settings
        
        # Create code analysis tool and static analyzer
        code_analysis_tool = CodeAnalysisTool(
            file_tool=file_tool,
            embedding_client=embedding_client
        )
        static_analyzer = StaticAnalyzer(
            file_tool=file_tool, 
            project_root=args.repo_path
        )
        
        # Install incremental indexing
        logger.info("Installing incremental indexing system...")
        adapter = install_incremental_indexing(
            code_analysis_tool=code_analysis_tool,
            static_analyzer=static_analyzer,
            config={
                'max_indexing_workers': 4,
                'extensions': ['.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.java', '.go', '.php']
            }
        )
        
        # Perform initial indexing
        logger.info(f"{'Full' if args.full else 'Incremental'} indexing of repository: {args.repo_path}")
        start_time = time.time()
        result = adapter.update_index(
            force_full=args.full,
            progress_callback=progress_callback
        )
        duration = time.time() - start_time
        
        # Display results
        logger.info(f"Indexing completed in {duration:.2f} seconds")
        logger.info(f"Files indexed: {result.get('files_indexed', 0)}")
        logger.info(f"Files skipped: {result.get('files_skipped', 0)}")
        
        # Get index stats
        stats = adapter.get_index_stats()
        if 'partitions' in stats:
            partition_stats = stats['partitions']
            logger.info(f"Total partitions: {partition_stats.get('total_partitions', 0)}")
            logger.info(f"Total files in index: {partition_stats.get('total_files', 0)}")
        
        # Enable watch mode if requested
        if args.watch:
            logger.info(f"Enabling watch mode for repository: {args.repo_path}")
            watch_id = adapter.enable_watch_mode(args.repo_path)
            if watch_id:
                logger.info(f"Watch mode enabled with ID: {watch_id}")
                logger.info("Press Ctrl+C to stop watching")
            else:
                logger.error("Failed to enable watch mode")
        
        # Perform search if query provided
        if args.search:
            logger.info(f"Searching for: {args.search}")
            results = code_analysis_tool.search_code(args.search, top_k=5)
            
            # Display results
            logger.info(f"Found {len(results)} results:")
            for i, result in enumerate(results):
                logger.info(f"Result {i+1}:")
                logger.info(f"  File: {result.get('file', 'Unknown')}")
                logger.info(f"  Score: {result.get('score', 0):.4f}")
                
                # Display a snippet of content
                content = result.get('content', '')
                snippet = content[:200] + "..." if len(content) > 200 else content
                logger.info(f"  Snippet: {snippet}")
                logger.info("-----")
        
        # If watch mode is enabled, keep the script running
        if args.watch:
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Stopping watch mode")
                adapter.disable_watch_mode()
    
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
