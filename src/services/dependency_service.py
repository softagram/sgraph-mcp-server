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
    
    @staticmethod
    def get_high_level_dependencies(
        model: SGraph,
        scope_path: Optional[str] = None,
        aggregation_level: int = 2,
        min_dependency_count: int = 1,
        include_external: bool = True,
        include_metrics: bool = True,
    ) -> Dict[str, Any]:
        """Get high-level module dependencies aggregated at directory level.
        
        Args:
            model: The sgraph model
            scope_path: Optional path to limit analysis scope
            aggregation_level: Directory depth for aggregation (2 = /Project/module)
            min_dependency_count: Minimum dependencies to include in results
            include_external: Whether to include external dependencies
            include_metrics: Whether to calculate coupling metrics
        
        Returns:
            Dictionary with module dependencies and metrics
        """
        logger.debug(f"Analyzing high-level dependencies: scope='{scope_path}', "
                    f"level={aggregation_level}, min_count={min_dependency_count}")
        
        # Determine scope
        if scope_path:
            scope_root = model.findElementFromPath(scope_path)
            if scope_root is None:
                logger.warning(f"Scope path not found: {scope_path}")
                return {"error": f"Scope path not found: {scope_path}"}
        else:
            # Use project root (first named child of root)
            scope_root = None
            for child in model.rootNode.children:
                if getattr(child, "name", None):
                    scope_root = child
                    break
            if scope_root is None:
                return {"error": "Project root not found"}
        
        # Collect all elements in scope
        all_elements = []
        stack = [scope_root]
        while stack:
            elem = stack.pop()
            all_elements.append(elem)
            stack.extend(elem.children)
        
        # Build module dependencies map
        module_deps = {}  # {from_module: {to_module: count}}
        element_to_module = {}  # Cache element paths to module paths
        
        def get_module_path(element: SElement) -> str:
            """Get module path at specified aggregation level."""
            path = element.getPath()
            if path in element_to_module:
                return element_to_module[path]
            
            parts = path.split("/")
            # Keep up to aggregation_level parts (e.g., /Project/module for level=2)
            if len(parts) > aggregation_level:
                module_path = "/".join(parts[:aggregation_level + 1])
            else:
                module_path = path
            
            element_to_module[path] = module_path
            return module_path
        
        # Process all dependencies
        total_dependencies = 0
        for element in all_elements:
            from_module = get_module_path(element)
            
            for assoc in element.outgoing:
                to_element = assoc.toElement
                to_path = to_element.getPath()
                
                # Skip external dependencies if not included
                if not include_external and "/External/" in to_path:
                    continue
                
                to_module = get_module_path(to_element)
                
                # Skip self-dependencies
                if from_module == to_module:
                    continue
                
                # Initialize nested dict if needed
                if from_module not in module_deps:
                    module_deps[from_module] = {}
                
                if to_module not in module_deps[from_module]:
                    module_deps[from_module][to_module] = 0
                
                module_deps[from_module][to_module] += 1
                total_dependencies += 1
        
        # Build results
        result = {
            "scope_path": scope_path or scope_root.getPath(),
            "aggregation_level": aggregation_level,
            "total_modules": 0,
            "total_dependencies": 0,
            "modules": [],
            "dependencies": [],
        }
        
        # Calculate module metrics
        if include_metrics:
            result["metrics"] = {
                "most_depended_upon": [],  # Modules with most incoming dependencies
                "most_dependent": [],       # Modules with most outgoing dependencies  
                "circular_dependencies": [],  # Detected circular dependencies
            }
            
            # Track incoming dependencies per module
            incoming_deps = {}
            
        # Convert module dependencies to list format
        for from_module, targets in module_deps.items():
            for to_module, count in targets.items():
                if count >= min_dependency_count:
                    dep_info = {
                        "from": from_module,
                        "to": to_module,
                        "count": count
                    }
                    result["dependencies"].append(dep_info)
                    
                    # Track incoming dependencies for metrics
                    if include_metrics:
                        if to_module not in incoming_deps:
                            incoming_deps[to_module] = {}
                        incoming_deps[to_module][from_module] = count
        
        # Sort dependencies by count
        result["dependencies"].sort(key=lambda x: x["count"], reverse=True)
        result["total_dependencies"] = len(result["dependencies"])
        
        # Calculate module information
        all_modules = set()
        for dep in result["dependencies"]:
            all_modules.add(dep["from"])
            all_modules.add(dep["to"])
        
        for module_path in all_modules:
            module_info = {
                "path": module_path,
                "outgoing_count": len(module_deps.get(module_path, {})),
                "incoming_count": 0,
            }
            
            if include_metrics and module_path in incoming_deps:
                module_info["incoming_count"] = len(incoming_deps[module_path])
            
            result["modules"].append(module_info)
        
        result["modules"].sort(key=lambda x: x["path"])
        result["total_modules"] = len(result["modules"])
        
        # Calculate metrics
        if include_metrics:
            # Most depended upon (highest incoming)
            result["metrics"]["most_depended_upon"] = sorted(
                [m for m in result["modules"] if m["incoming_count"] > 0],
                key=lambda x: x["incoming_count"],
                reverse=True
            )[:10]
            
            # Most dependent (highest outgoing)
            result["metrics"]["most_dependent"] = sorted(
                [m for m in result["modules"] if m["outgoing_count"] > 0],
                key=lambda x: x["outgoing_count"], 
                reverse=True
            )[:10]
            
            # Detect circular dependencies
            for from_module in module_deps:
                for to_module in module_deps.get(from_module, {}):
                    # Check if there's a reverse dependency
                    if to_module in module_deps and from_module in module_deps[to_module]:
                        # Avoid duplicates by only adding when from < to alphabetically
                        if from_module < to_module:
                            result["metrics"]["circular_dependencies"].append({
                                "module1": from_module,
                                "module2": to_module,
                                "count_1_to_2": module_deps[from_module][to_module],
                                "count_2_to_1": module_deps[to_module][from_module],
                            })
        
        logger.debug(f"High-level dependency analysis complete: {result['total_modules']} modules, "
                    f"{result['total_dependencies']} dependencies")
        
        return result
