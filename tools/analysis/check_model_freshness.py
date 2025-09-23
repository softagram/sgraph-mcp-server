#!/usr/bin/env python3
"""
Model freshness checker utility.

Analyzes a sgraph model to check for fresh content, modular structure,
and recent analysis outputs. Useful for validating model updates.
"""

import sys
import os
import asyncio
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.model_manager import ModelManager
from src.services.search_service import SearchService
from src.services.overview_service import OverviewService


async def check_model_freshness(model_path: str, project_name: str = "sgraph-and-mcp"):
    """
    Check a sgraph model for freshness and content analysis.
    
    Args:
        model_path: Path to the sgraph model file
        project_name: Name of the project to analyze within the model
    
    Returns:
        dict: Analysis results including freshness indicators
    """
    
    result = {
        "file_info": {},
        "model_stats": {},
        "freshness_indicators": {},
        "architecture_analysis": {},
        "error": None
    }
    
    try:
        # Check file information
        if os.path.exists(model_path):
            stat = os.stat(model_path)
            result["file_info"] = {
                "path": model_path,
                "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "size_mb": round(stat.st_size / (1024*1024), 2),
                "exists": True
            }
        else:
            result["error"] = f"Model file not found: {model_path}"
            return result
        
        # Load and analyze the model
        manager = ModelManager()
        start_time = time.time()
        
        model_id = await manager.load_model(model_path)
        load_time = time.time() - start_time
        
        model = manager.get_model(model_id)
        if not model:
            result["error"] = "Failed to retrieve model from manager"
            return result
        
        # Get model overview
        overview = OverviewService.get_model_overview(model, max_depth=6)
        result["model_stats"] = {
            "total_elements": overview['summary']['total_elements'],
            "max_depth": max(overview['summary']['depth_counts'].keys()),
            "load_time_seconds": round(load_time, 2),
            "type_distribution": overview['summary']['type_distribution']
        }
        
        # Check for freshness indicators
        analysis_files = SearchService.search_elements_by_name(
            model, ".*analysis.*|.*test.*|.*performance.*", element_type="file"
        )
        
        throwaway_files = SearchService.get_elements_by_type(
            model, "file", 
            scope_path=f"/{project_name}/{project_name.split('-')[0]}-mcp-server/throwaway-ai-code"
        )
        
        result["freshness_indicators"] = {
            "analysis_related_files": len(analysis_files),
            "throwaway_ai_files": len(throwaway_files),
            "has_recent_analysis": len(analysis_files) > 0,
            "has_throwaway_workspace": len(throwaway_files) > 0
        }
        
        # Check for modular architecture
        base_path = f"/{project_name}/{project_name.split('-')[0]}-mcp-server/src"
        
        core_elements = SearchService.get_elements_by_type(
            model, "file", scope_path=f"{base_path}/core"
        )
        service_elements = SearchService.get_elements_by_type(
            model, "file", scope_path=f"{base_path}/services"
        )
        tool_elements = SearchService.get_elements_by_type(
            model, "file", scope_path=f"{base_path}/tools"
        )
        
        result["architecture_analysis"] = {
            "core_modules": len(core_elements),
            "service_modules": len(service_elements),
            "tool_modules": len(tool_elements),
            "has_modular_structure": len(core_elements) > 0 and len(service_elements) > 0,
            "modular_completeness": len(core_elements) + len(service_elements) + len(tool_elements)
        }
        
        return result
        
    except Exception as e:
        result["error"] = str(e)
        return result


def print_freshness_report(result: dict):
    """Print a formatted freshness report."""
    
    print("🔍 MODEL FRESHNESS ANALYSIS REPORT")
    print("=" * 50)
    
    if result.get("error"):
        print(f"❌ Error: {result['error']}")
        return
    
    # File info
    file_info = result["file_info"]
    print(f"📁 File: {file_info['path']}")
    print(f"📅 Modified: {file_info['last_modified']}")
    print(f"📊 Size: {file_info['size_mb']} MB")
    
    # Model stats
    stats = result["model_stats"]
    print(f"\n📈 Model Statistics:")
    print(f"  Total elements: {stats['total_elements']}")
    print(f"  Max depth: {stats['max_depth']}")
    print(f"  Load time: {stats['load_time_seconds']}s")
    
    print(f"\n🏷️  Type distribution:")
    for element_type, count in sorted(stats['type_distribution'].items(), 
                                    key=lambda x: x[1], reverse=True)[:8]:
        print(f"  {element_type}: {count}")
    
    # Freshness indicators
    fresh = result["freshness_indicators"]
    print(f"\n🔍 Freshness Indicators:")
    print(f"  Analysis files: {fresh['analysis_related_files']}")
    print(f"  Throwaway files: {fresh['throwaway_ai_files']}")
    print(f"  Recent analysis: {'✅' if fresh['has_recent_analysis'] else '❌'}")
    print(f"  AI workspace: {'✅' if fresh['has_throwaway_workspace'] else '❌'}")
    
    # Architecture analysis
    arch = result["architecture_analysis"]
    print(f"\n🏗️  Architecture Analysis:")
    print(f"  Core modules: {arch['core_modules']}")
    print(f"  Service modules: {arch['service_modules']}")
    print(f"  Tool modules: {arch['tool_modules']}")
    print(f"  Modular structure: {'✅' if arch['has_modular_structure'] else '❌'}")
    print(f"  Completeness score: {arch['modular_completeness']}")
    
    # Overall assessment
    print(f"\n🎯 Overall Assessment:")
    is_fresh = (fresh['has_recent_analysis'] and 
                fresh['has_throwaway_workspace'] and 
                arch['has_modular_structure'])
    
    if is_fresh:
        print("✅ MODEL IS FRESH with recent analysis and modular structure!")
    else:
        print("⚠️  Model may be outdated - missing freshness indicators")


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Check sgraph model freshness")
    parser.add_argument(
        "model_path", 
        nargs="?",
        default="/opt/softagram/output/projects/sgraph-and-mcp/latest.xml.zip",
        help="Path to the sgraph model file"
    )
    parser.add_argument(
        "--project", 
        default="sgraph-and-mcp",
        help="Project name to analyze"
    )
    parser.add_argument(
        "--json", 
        action="store_true",
        help="Output results as JSON"
    )
    
    args = parser.parse_args()
    
    result = await check_model_freshness(args.model_path, args.project)
    
    if args.json:
        import json
        print(json.dumps(result, indent=2))
    else:
        print_freshness_report(result)


if __name__ == "__main__":
    asyncio.run(main())
