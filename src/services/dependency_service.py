"""
Dependency analysis service for sgraph elements.

Handles dependency chain analysis and subtree dependency mapping.
"""

import logging
from typing import Dict, Any, Optional, Set, List

from sgraph import SGraph, SElement
from src.core.element_converter import ElementConverter

logger = logging.getLogger(__name__)


class DependencyService:
    """Provides dependency analysis functionality."""
    
    @staticmethod
    def get_subtree_dependencies(
        model: SGraph,
        root_path: str,
        include_external: bool = True,
        max_depth: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get all dependencies within a subtree, including both incoming and outgoing."""
        logger.debug(f"Analyzing subtree dependencies: root='{root_path}', external={include_external}, depth={max_depth}")
        
        result = {
            "subtree_elements": [],
            "internal_dependencies": [],
            "incoming_dependencies": [],
            "outgoing_dependencies": [],
        }
        
        root_element = model.findElementFromPath(root_path)
        if root_element is None:
            logger.warning(f"Root path not found: {root_path}")
            return result
        
        subtree_elements = set()
        subtree_paths = set()
        
        # Build subtree using iterative traversal
        stack = [(root_element, 0)]
        while stack:
            element, depth = stack.pop()
            
            if max_depth is not None and depth > max_depth:
                continue
                
            subtree_elements.add(element)
            subtree_paths.add(element.getPath())
            
            for child in element.children:
                stack.append((child, depth + 1))
        
        result["subtree_elements"] = [
            ElementConverter.element_to_dict(element) for element in subtree_elements
        ]
        
        # Analyze dependencies for each element in subtree
        for element in subtree_elements:
            element_path = element.getPath()
            
            # Analyze outgoing dependencies
            for association in element.outgoing:
                target_path = association.toElement.getPath()
                
                if not include_external and "/External/" in target_path:
                    continue
                
                dep_info = ElementConverter.association_to_dict(association)
                
                if target_path in subtree_paths:
                    result["internal_dependencies"].append(dep_info)
                else:
                    result["outgoing_dependencies"].append(dep_info)
            
            # Analyze incoming dependencies
            for association in element.incoming:
                source_path = association.fromElement.getPath()
                
                if not include_external and "/External/" in source_path:
                    continue
                
                if source_path not in subtree_paths:
                    dep_info = ElementConverter.association_to_dict(association)
                    result["incoming_dependencies"].append(dep_info)
        
        logger.debug(f"Subtree analysis complete: {len(subtree_elements)} elements, "
                    f"{len(result['internal_dependencies'])} internal deps, "
                    f"{len(result['incoming_dependencies'])} incoming deps, "
                    f"{len(result['outgoing_dependencies'])} outgoing deps")
        
        return result
    
    @staticmethod
    def get_dependency_chain(
        model: SGraph,
        element_path: str,
        direction: str = "outgoing",
        max_depth: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get transitive dependency chain from an element."""
        logger.debug(f"Analyzing dependency chain: element='{element_path}', direction='{direction}', depth={max_depth}")
        
        result = {
            "root_element": element_path,
            "direction": direction,
            "max_depth": max_depth,
            "chain": [],
            "all_dependencies": [],
        }
        
        root_element = model.findElementFromPath(element_path)
        if root_element is None:
            logger.warning(f"Element path not found: {element_path}")
            return result
        
        visited = set()
        chain_elements = []
        
        def traverse_dependencies(element: SElement, depth: int, path: List[str]):
            if max_depth is not None and depth > max_depth:
                return
            
            element_path = element.getPath()
            if element_path in visited:
                return
            
            visited.add(element_path)
            current_path = path + [element_path]
            
            # Get associations based on direction
            associations = []
            if direction in ["outgoing", "both"]:
                associations.extend([
                    (assoc.toElement, "outgoing", getattr(assoc, 'type', 'unknown'))
                    for assoc in element.outgoing
                ])
            if direction in ["incoming", "both"]:
                associations.extend([
                    (assoc.fromElement, "incoming", getattr(assoc, 'type', 'unknown'))
                    for assoc in element.incoming
                ])
            
            # Process each association
            for target_element, dep_direction, dep_type in associations:
                target_path = target_element.getPath()
                
                result["all_dependencies"].append({
                    "from": element_path,
                    "to": target_path,
                    "direction": dep_direction,
                    "type": dep_type,
                    "depth": depth,
                })
                
                # Recursively traverse
                traverse_dependencies(target_element, depth + 1, current_path)
            
            # Record chain path if not at root
            if len(current_path) > 1:
                chain_elements.append({
                    "path": current_path,
                    "depth": depth,
                })
        
        traverse_dependencies(root_element, 0, [])
        
        result["chain"] = chain_elements
        
        logger.debug(f"Dependency chain analysis complete: {len(result['all_dependencies'])} dependencies, "
                    f"{len(chain_elements)} chain paths")
        
        return result
    
    @staticmethod
    def get_multiple_elements(
        model: SGraph,
        element_paths: List[str],
        additional_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get information for multiple elements efficiently."""
        if additional_fields is None:
            additional_fields = []
            
        logger.debug(f"Getting multiple elements: {len(element_paths)} paths")
        
        result = {
            "requested_count": len(element_paths),
            "found_count": 0,
            "elements": [],
            "not_found": [],
        }
        
        for path in element_paths:
            element = model.findElementFromPath(path)
            if element is None:
                result["not_found"].append(path)
            else:
                element_dict = ElementConverter.element_to_dict(element, additional_fields)
                result["elements"].append(element_dict)
                result["found_count"] += 1
        
        logger.debug(f"Multiple elements retrieved: {result['found_count']}/{result['requested_count']} found")
        
        return result

    @staticmethod
    def analyze_external_usage(
        model: SGraph,
        scope_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze usage of External dependencies within an optional scope.
        
        - Detect the project's `External` subtree under the single named root.
        - Scan outgoing associations from elements in scope to External elements.
        - Aggregate by language (first child under External) and package (second child).
        """
        # Resolve project root (single named child of unnamed root)
        unnamed_root = model.rootNode
        project_root = None
        for child in unnamed_root.children:
            # Choose first child that has a non-empty name
            if getattr(child, "name", None):
                project_root = child
                break
        if project_root is None:
            logger.warning("Project root not found under unnamed root")
            return {"error": "Project root not found"}
        project_root_path = project_root.getPath()

        # Find External subtree
        external_root = None
        for child in project_root.children:
            if (child.name or "") == "External":
                external_root = child
                break
        if external_root is None:
            logger.info("External subtree not present in this model")
            return {
                "project_root": project_root_path,
                "external_root": None,
                "totals": {
                    "scanned_internal_elements": 0,
                    "external_edge_count": 0,
                    "unique_external_targets": 0,
                },
                "by_language": {},
                "by_package": {},
                "details": [],
            }

        external_root_path = external_root.getPath()

        # Build scope set
        scope_elements: Set[SElement] = set()
        if scope_path:
            scope_elem = model.findElementFromPath(scope_path)
            if scope_elem is None:
                logger.warning(f"Scope path not found: {scope_path}")
                return {"error": f"Scope not found: {scope_path}"}
            stack: List[SElement] = [scope_elem]
            while stack:
                e = stack.pop()
                scope_elements.add(e)
                stack.extend(e.children)
        else:
            # Default: whole project except External tree
            stack = [project_root]
            while stack:
                e = stack.pop()
                # Skip external subtree entirely
                if e is external_root:
                    continue
                scope_elements.add(e)
                stack.extend(e.children)

        # Aggregate external usage
        by_language: Dict[str, Dict[str, int]] = {}
        by_package: Dict[str, Dict[str, int]] = {}
        details_map: Dict[str, Dict[str, Any]] = {}
        external_edge_count = 0

        ext_prefix = external_root_path + "/"

        for elem in scope_elements:
            for assoc in elem.outgoing:
                target = assoc.toElement
                tpath = target.getPath()
                if not tpath.startswith(ext_prefix):
                    continue
                external_edge_count += 1

                # Derive language and package based on path segments after External/
                rel = tpath[len(ext_prefix):]  # e.g., Python/pandas/...
                parts = [p for p in rel.split("/") if p]
                language = parts[0] if len(parts) >= 1 else "unknown"
                package = parts[1] if len(parts) >= 2 else (parts[0] if parts else "unknown")

                lang_stats = by_language.setdefault(language, {"unique_targets": 0, "edge_count": 0})
                pkg_stats = by_package.setdefault(package, {"unique_targets": 0, "edge_count": 0})
                lang_stats["edge_count"] += 1
                pkg_stats["edge_count"] += 1

                # Track unique targets and examples per target path
                d = details_map.get(tpath)
                if d is None:
                    d = {
                        "target_path": tpath,
                        "language": language,
                        "package": package,
                        "edge_count": 0,
                        "example_sources": [],
                    }
                    details_map[tpath] = d
                    # New unique target increments language/package unique_targets
                    lang_stats["unique_targets"] += 1
                    pkg_stats["unique_targets"] += 1
                d["edge_count"] += 1
                if len(d["example_sources"]) < 3:
                    d["example_sources"].append(elem.getPath())

        details = sorted(details_map.values(), key=lambda x: (-x["edge_count"], x["target_path"]))

        result = {
            "project_root": project_root_path,
            "external_root": external_root_path,
            "scope_path": scope_path,
            "totals": {
                "scanned_internal_elements": len(scope_elements),
                "external_edge_count": external_edge_count,
                "unique_external_targets": len(details),
            },
            "by_language": by_language,
            "by_package": by_package,
            "details": details,
        }

        return result
