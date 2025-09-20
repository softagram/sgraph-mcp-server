import asyncio
import re
import logging
import time
import os
from typing import Any, Optional

import nanoid
from sgraph import SElement, SGraph
from sgraph.loader.modelloader import ModelLoader

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SGraphHelper:
    _models: dict[str, SGraph] = {}

    def __init__(self):
        self.ml = ModelLoader()
        # Serialize model loads to avoid concurrent heavy CPU blocking and races
        self._load_lock = asyncio.Lock()

    async def load_sgraph(self, path: str) -> str:
        """Load a sgraph model with comprehensive logging and error handling."""
        logger.info(f"🔍 Starting to load model from: {path}")
        
        # Validate file exists
        if not os.path.exists(path):
            error_msg = f"Model file does not exist: {path}"
            logger.error(f"❌ {error_msg}")
            raise FileNotFoundError(error_msg)
        
        # Check file size for logging
        file_size = os.path.getsize(path)
        logger.info(f"📁 File size: {file_size / (1024*1024):.1f} MB")
        
        start_time = time.perf_counter()

        # Short debug settle sleep to reduce race conditions at request start
        # and make timing more deterministic during investigation.
        await asyncio.sleep(0.1)

        try:
            logger.info("🔒 Waiting for model load lock...")
            async with self._load_lock:
                lock_acquired_time = time.perf_counter()
                logger.info(f"🔓 Model load lock acquired after {lock_acquired_time - start_time:.3f}s")
                logger.info(f"⏳ Loading model using ModelLoader (timeout 60s)...")
                # Use asyncio.to_thread with timeout to prevent hanging
                model = await asyncio.wait_for(
                    asyncio.to_thread(self.ml.load_model, path),
                    timeout=60.0  # 60 second timeout
                )
        except asyncio.TimeoutError:
            error_msg = f"Model loading timed out after 60 seconds: {path}"
            logger.error(f"⏰ {error_msg}")
            raise TimeoutError(error_msg)
        except Exception as e:
            load_time = time.perf_counter() - start_time
            error_msg = (
                f"Failed to load model after {load_time:.2f} seconds: {e} "
                f"(type={type(e).__name__})"
            )
            logger.error(f"💥 {error_msg}")
            raise RuntimeError(error_msg) from e

        load_time = time.perf_counter() - start_time
        logger.info(f"✅ Model loaded successfully in {load_time:.2f} seconds")

        # Generate unique model ID
        model_id = nanoid.generate(size=24)
        logger.info(f"🆔 Generated model ID: {model_id}")

        # Store model in memory cache
        self._models[model_id] = model
        logger.info(f"💾 Model cached in memory (total models: {len(self._models)})")

        # Log basic model info
        if hasattr(model, 'rootNode') and model.rootNode:
            logger.info(f"🌳 Model root: {model.rootNode.name if model.rootNode.name else 'unnamed'}")
            logger.info(f"👶 Root children: {len(model.rootNode.children)}")

        return model_id

    def get_model(self, model_id: str) -> SGraph | None:
        return self._models.get(model_id)

    def element_to_dict(
        self,
        element: SElement,
        additional_fields: list[str] = [],
    ) -> dict[str, Any]:
        return {
            "name": element.name,
            "path": element.getPath(),
            "type": element.getType(),
            "child_paths": [child.getPath() for child in element.children],
            **{
                field: getattr(element, field)
                for field in additional_fields
                if hasattr(element, field)
            },
        }

    def search_elements_by_name(
        self,
        model: SGraph,
        pattern: str,
        element_type: Optional[str] = None,
        scope_path: Optional[str] = None,
    ) -> list[SElement]:
        """Search for elements by name pattern within optional scope and type filters."""
        results = []
        
        # Determine the starting point for search
        start_element = model.rootNode
        if scope_path:
            start_element = model.findElementFromPath(scope_path)
            if start_element is None:
                return results
        
        # Compile regex pattern
        try:
            regex_pattern = re.compile(pattern)
        except re.error:
            # Fallback to simple glob-style matching
            glob_pattern = pattern.replace("*", ".*").replace("?", ".")
            regex_pattern = re.compile(glob_pattern)
        
        """
        def visit_element(element: SElement):
            # Check name pattern match
            if regex_pattern.search(element.name):
                # Check type filter if specified
                if element_type is None or element.getType() == element_type:
                    results.append(element)
        
        # Traverse all elements starting from the scope
        start_element.traverseElements(visit_element)
        """
        
        stack = [start_element]
        while stack:
            element = stack.pop()
            if regex_pattern.search(element.name):
                # Check type filter if specified
                if element_type is None or element.getType() == element_type:
                    results.append(element)
            stack.extend(element.children)
        
        return results

    def get_elements_by_type(
        self,
        model: SGraph,
        element_type: str,
        scope_path: Optional[str] = None,
    ) -> list[SElement]:
        """Get all elements of a specific type within optional scope."""
        results = []
        
        # Determine the starting point for search
        start_element = model.rootNode
        if scope_path:
            start_element = model.findElementFromPath(scope_path)
            if start_element is None:
                return results
        
        # Use iterative stack-based traversal for better performance
        stack = [start_element]
        while stack:
            element = stack.pop()
            if element.getType() == element_type:
                results.append(element)
            stack.extend(element.children)
        
        return results

    def search_elements_by_attributes(
        self,
        model: SGraph,
        attribute_filters: dict[str, Any],
        scope_path: Optional[str] = None,
    ) -> list[SElement]:
        """Search for elements by attribute values within optional scope."""
        results = []
        
        # Determine the starting point for search
        start_element = model.rootNode
        if scope_path:
            start_element = model.findElementFromPath(scope_path)
            if start_element is None:
                return results
        
        # Use iterative stack-based traversal for better performance
        stack = [start_element]
        while stack:
            element = stack.pop()
            
            # Check if element matches all attribute filters
            matches_all = True
            for attr_name, expected_value in attribute_filters.items():
                if not hasattr(element, attr_name):
                    matches_all = False
                    break
                
                actual_value = getattr(element, attr_name)
                
                # Handle different comparison types
                if isinstance(expected_value, str) and isinstance(actual_value, str):
                    # String comparison - support regex patterns
                    try:
                        if not re.search(expected_value, actual_value):
                            matches_all = False
                            break
                    except re.error:
                        # Fallback to exact match
                        if actual_value != expected_value:
                            matches_all = False
                            break
                elif actual_value != expected_value:
                    matches_all = False
                    break
            
            if matches_all:
                results.append(element)
            
            stack.extend(element.children)
        
        return results

    def get_subtree_dependencies(
        self,
        model: SGraph,
        root_path: str,
        include_external: bool = True,
        max_depth: Optional[int] = None,
    ) -> dict[str, Any]:
        """Get all dependencies within a subtree, including both incoming and outgoing."""
        result = {
            "subtree_elements": [],
            "internal_dependencies": [],  # Dependencies within the subtree
            "incoming_dependencies": [],  # Dependencies from outside into subtree
            "outgoing_dependencies": [],  # Dependencies from subtree to outside
        }
        
        # Find the root element
        root_element = model.findElementFromPath(root_path)
        if root_element is None:
            return result
        
        # Collect all elements in the subtree using stack-based traversal
        subtree_elements = set()
        subtree_paths = set()
        
        stack = [(root_element, 0)]  # (element, depth)
        while stack:
            element, depth = stack.pop()
            
            if max_depth is not None and depth > max_depth:
                continue
                
            subtree_elements.add(element)
            subtree_paths.add(element.getPath())
            
            # Add children to stack
            for child in element.children:
                stack.append((child, depth + 1))
        
        # Convert elements to dictionaries for result
        result["subtree_elements"] = [
            self.element_to_dict(element) for element in subtree_elements
        ]
        
        # Analyze dependencies for each element in the subtree
        for element in subtree_elements:
            element_path = element.getPath()
            
            # Check outgoing associations
            for association in element.outgoing:
                target_path = association.toElement.getPath()
                
                # Skip external dependencies if not requested
                if not include_external and "/External/" in target_path:
                    continue
                
                dep_info = {
                    "from": element_path,
                    "to": target_path,
                    "type": getattr(association, 'type', 'unknown'),
                }
                
                if target_path in subtree_paths:
                    # Internal dependency (within subtree)
                    result["internal_dependencies"].append(dep_info)
                else:
                    # Outgoing dependency (subtree -> outside)
                    result["outgoing_dependencies"].append(dep_info)
            
            # Check incoming associations
            for association in element.incoming:
                source_path = association.fromElement.getPath()
                
                # Skip external dependencies if not requested
                if not include_external and "/External/" in source_path:
                    continue
                
                if source_path not in subtree_paths:
                    # Incoming dependency (outside -> subtree)
                    dep_info = {
                        "from": source_path,
                        "to": element_path,
                        "type": getattr(association, 'type', 'unknown'),
                    }
                    result["incoming_dependencies"].append(dep_info)
        
        return result

    def get_dependency_chain(
        self,
        model: SGraph,
        element_path: str,
        direction: str = "outgoing",  # "outgoing", "incoming", or "both"
        max_depth: Optional[int] = None,
    ) -> dict[str, Any]:
        """Get transitive dependency chain from an element."""
        result = {
            "root_element": element_path,
            "direction": direction,
            "max_depth": max_depth,
            "chain": [],
            "all_dependencies": [],
        }
        
        # Find the root element
        root_element = model.findElementFromPath(element_path)
        if root_element is None:
            return result
        
        visited = set()
        chain_elements = []
        
        def traverse_dependencies(element: SElement, depth: int, path: list[str]):
            if max_depth is not None and depth > max_depth:
                return
            
            element_path = element.getPath()
            if element_path in visited:
                return  # Avoid cycles
            
            visited.add(element_path)
            current_path = path + [element_path]
            
            # Get associations based on direction
            associations = []
            if direction in ["outgoing", "both"]:
                associations.extend([(assoc.toElement, "outgoing", getattr(assoc, 'type', 'unknown')) 
                                  for assoc in element.outgoing])
            if direction in ["incoming", "both"]:
                associations.extend([(assoc.fromElement, "incoming", getattr(assoc, 'type', 'unknown')) 
                                  for assoc in element.incoming])
            
            for target_element, dep_direction, dep_type in associations:
                target_path = target_element.getPath()
                
                # Record the dependency
                result["all_dependencies"].append({
                    "from": element_path,
                    "to": target_path,
                    "direction": dep_direction,
                    "type": dep_type,
                    "depth": depth,
                })
                
                # Continue traversal
                traverse_dependencies(target_element, depth + 1, current_path)
            
            # Record the current chain path
            if len(current_path) > 1:
                chain_elements.append({
                    "path": current_path,
                    "depth": depth,
                })
        
        # Start traversal
        traverse_dependencies(root_element, 0, [])
        
        result["chain"] = chain_elements
        return result

    def get_multiple_elements(
        self,
        model: SGraph,
        element_paths: list[str],
        additional_fields: list[str] = [],
    ) -> dict[str, Any]:
        """Get information for multiple elements efficiently."""
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
                element_dict = self.element_to_dict(element, additional_fields)
                result["elements"].append(element_dict)
                result["found_count"] += 1
        
        return result

    def get_model_overview(
        self,
        model: SGraph,
        max_depth: int = 3,
        include_counts: bool = True,
    ) -> dict[str, Any]:
        """Get hierarchical overview of the model structure up to specified depth."""
        result = {
            "root_path": "",
            "max_depth": max_depth,
            "tree_structure": {},
            "summary": {
                "total_elements": 0,
                "depth_counts": {},
                "type_distribution": {},
            }
        }
        
        # Start from root element
        root_element = model.rootNode
        total_elements = 0
        depth_counts = {}
        type_distribution = {}
        
        def build_tree_structure(element: SElement, current_depth: int) -> dict[str, Any]:
            nonlocal total_elements
            total_elements += 1
            
            # Track depth statistics
            if current_depth not in depth_counts:
                depth_counts[current_depth] = 0
            depth_counts[current_depth] += 1
            
            # Track type distribution
            element_type = element.getType() or "unknown"
            if element_type not in type_distribution:
                type_distribution[element_type] = 0
            type_distribution[element_type] += 1
            
            # Build structure for this element
            structure = {
                "name": element.name,
                "path": element.getPath(),
                "type": element_type,
                "depth": current_depth,
            }
            
            if include_counts:
                structure["child_count"] = len(element.children)
                structure["incoming_count"] = len(element.incoming)
                structure["outgoing_count"] = len(element.outgoing)
            
            # Add children if we haven't reached max depth
            if current_depth < max_depth:
                structure["children"] = {}
                for child in element.children:
                    child_name = child.name or f"<unnamed_{child.getType()}>"
                    structure["children"][child_name] = build_tree_structure(child, current_depth + 1)
            elif len(element.children) > 0:
                # Indicate there are more children beyond max depth
                structure["has_more_children"] = len(element.children)
            
            return structure
        
        # Build the complete tree structure
        root_structure = build_tree_structure(root_element, 0)
        result["tree_structure"] = root_structure
        
        # Add summary statistics
        result["summary"]["total_elements"] = total_elements
        result["summary"]["depth_counts"] = depth_counts
        result["summary"]["type_distribution"] = type_distribution
        
        return result
