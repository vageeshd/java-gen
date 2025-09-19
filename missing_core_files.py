# core/java_extractor.py

import os
import re
from typing import Dict, List, Set, Tuple, Optional
import javalang
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class MethodInfo:
    file_path: str
    method_name: str
    class_name: str
    package_name: str
    param_types: Tuple[str, ...]
    start_line: int
    end_line: int
    snippet: str
    calls_made: Set[str]  # Method names this method calls
    called_by: Set[str]   # Method signatures that call this method
    contains_keywords: bool
    
    def get_full_signature(self) -> str:
        """Get full method signature including class"""
        return f"{self.class_name}.{self.method_name}({','.join(self.param_types)})"
    
    def get_qualified_name(self) -> str:
        """Get fully qualified method name"""
        package_prefix = f"{self.package_name}." if self.package_name else ""
        return f"{package_prefix}{self.class_name}.{self.method_name}"

def extract_java_code_blocks_with_cross_references(
    src_dir: str, 
    keywords: List[str], 
    max_depth: int = 2,
    include_callers: bool = True,
    include_callees: bool = True
) -> Dict[str, List[str]]:
    """
    Enhanced Java code extractor that traces method calls across files.
    
    Args:
        src_dir: Source directory to scan
        keywords: Keywords to search for
        max_depth: Maximum depth for call tracing (1 = direct calls only, 2 = calls to calls, etc.)
        include_callers: Whether to include methods that call the keyword methods
        include_callees: Whether to include methods called by the keyword methods
    """
    
    print(f"[INFO] Starting cross-file analysis with max_depth={max_depth}")
    
    # Phase 1: Parse all Java files and build method registry
    all_methods = {}  # signature -> MethodInfo
    file_to_methods = defaultdict(list)  # file -> list of method signatures
    method_calls_map = defaultdict(set)  # caller_sig -> set of called_method_names
    
    java_files = []
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith(".java"):
                java_files.append(os.path.join(root, file))
    
    print(f"[INFO] Found {len(java_files)} Java files to analyze")
    
    # Parse all files first
    for file_path in java_files:
        try:
            methods = parse_java_file(file_path, keywords)
            for method in methods:
                sig = method.get_full_signature()
                all_methods[sig] = method
                file_to_methods[file_path].append(sig)
        except Exception as e:
            print(f"[WARN] Failed to parse {file_path}: {e}")
            continue
    
    print(f"[INFO] Parsed {len(all_methods)} total methods")
    
    # Phase 2: Build call relationships
    for method_info in all_methods.values():
        for called_method in method_info.calls_made:
            # Find matching methods by name (simple matching)
            for other_sig, other_method in all_methods.items():
                if other_method.method_name == called_method:
                    method_calls_map[method_info.get_full_signature()].add(other_sig)
                    all_methods[other_sig].called_by.add(method_info.get_full_signature())
    
    # Phase 3: Find seed methods (containing keywords)
    seed_methods = set()
    for method_info in all_methods.values():
        if method_info.contains_keywords:
            seed_methods.add(method_info.get_full_signature())
    
    print(f"[INFO] Found {len(seed_methods)} seed methods containing keywords")
    
    # Phase 4: Trace relationships to specified depth
    relevant_methods = set(seed_methods)
    
    if include_callers or include_callees:
        for depth in range(1, max_depth + 1):
            new_methods = set()
            
            for method_sig in list(relevant_methods):
                method_info = all_methods.get(method_sig)
                if not method_info:
                    continue
                
                # Add callers (methods that call this method)
                if include_callers:
                    for caller_sig in method_info.called_by:
                        if caller_sig not in relevant_methods:
                            new_methods.add(caller_sig)
                
                # Add callees (methods called by this method)
                if include_callees:
                    for called_sig in method_calls_map.get(method_sig, set()):
                        if called_sig not in relevant_methods:
                            new_methods.add(called_sig)
            
            relevant_methods.update(new_methods)
            print(f"[INFO] Depth {depth}: Added {len(new_methods)} related methods")
            
            if not new_methods:  # No new methods found, can stop early
                break
    
    print(f"[INFO] Total relevant methods after tracing: {len(relevant_methods)}")
    
    # Phase 5: Organize results by file
    results = {}
    
    for method_sig in relevant_methods:
        method_info = all_methods.get(method_sig)
        if not method_info:
            continue
        
        file_path = method_info.file_path
        if file_path not in results:
            results[file_path] = []
        
        # Categorize the method
        category = "SEED" if method_sig in seed_methods else "RELATED"
        if method_sig not in seed_methods:
            # Determine if it's a caller or callee
            is_caller = any(seed_sig in method_calls_map.get(method_sig, set()) for seed_sig in seed_methods)
            is_callee = any(method_sig in method_calls_map.get(seed_sig, set()) for seed_sig in seed_methods)
            
            if is_caller and is_callee:
                category = "CALLER_AND_CALLEE"
            elif is_caller:
                category = "CALLER"
            elif is_callee:
                category = "CALLEE"
            else:
                category = "INDIRECTLY_RELATED"
        
        # Create annotated snippet
        header = f"// [{category}] Method: {method_info.get_qualified_name()}"
        if method_info.contains_keywords:
            header += " [CONTAINS KEYWORDS]"
        
        annotated_snippet = f"{header}\n// File: {file_path}\n{method_info.snippet}"
        results[file_path].append(annotated_snippet)
    
    return results

def parse_java_file(file_path: str, keywords: List[str]) -> List[MethodInfo]:
    """Parse a single Java file and extract method information."""
    
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            code = f.read()
    except Exception as e:
        print(f"[WARNING] Could not read {file_path}: {e}")
        return []
    
    try:
        tree = javalang.parse.parse(code)
    except Exception as e:
        print(f"[WARNING] Could not parse {file_path}: {e}")
        return []
    
    code_lines = code.splitlines()
    methods = []
    
    # Extract package name
    package_name = ""
    if tree.package:
        package_name = tree.package.name
    
    # Find class names
    class_names = []
    for path, node in tree.filter(javalang.tree.ClassDeclaration):
        class_names.append(node.name)
    
    # If no classes found, use filename
    if not class_names:
        class_names = [os.path.splitext(os.path.basename(file_path))[0]]
    
    # Extract methods
    for path, node in tree.filter(javalang.tree.MethodDeclaration):
        if not hasattr(node, 'position') or node.position is None:
            continue
        
        # Find the class this method belongs to
        class_name = class_names[0]  # Default to first class
        for path_element in path:
            if isinstance(path_element, javalang.tree.ClassDeclaration):
                class_name = path_element.name
                break
        
        method_name = node.name
        param_types = tuple(
            p.type.name if hasattr(p.type, 'name') else str(p.type) 
            for p in getattr(node, 'parameters', [])
        )
        
        start_line = node.position.line - 1
        end_line = find_method_end(code_lines, start_line)
        
        snippet = "\n".join(code_lines[start_line:end_line + 1])
        
        # Find method calls in this method
        calls_made = extract_method_calls(snippet)
        
        # Check if method contains keywords
        contains_keywords = contains_relevant_keywords(snippet, keywords)
        
        method_info = MethodInfo(
            file_path=file_path,
            method_name=method_name,
            class_name=class_name,
            package_name=package_name,
            param_types=param_types,
            start_line=start_line,
            end_line=end_line,
            snippet=snippet,
            calls_made=calls_made,
            called_by=set(),
            contains_keywords=contains_keywords
        )
        
        methods.append(method_info)
    
    return methods

def find_method_end(code_lines: List[str], start_line: int) -> int:
    """Find the end line of a method by tracking brace balance."""
    brace_count = 0
    in_method_body = False
    
    for i in range(start_line, len(code_lines)):
        line = code_lines[i].strip()
        
        if not line or line.startswith('//') or line.startswith('/*') or line.startswith('*'):
            continue
        
        for char in line:
            if char == '{':
                brace_count += 1
                in_method_body = True
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and in_method_body:
                    return i
    
    return len(code_lines) - 1

def extract_method_calls(snippet: str) -> Set[str]:
    """Extract method calls from a code snippet."""
    calls = set()
    
    # Pattern for method calls: methodName( or object.methodName(
    patterns = [
        r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',  # Direct method calls
        r'\.([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',  # Method calls on objects
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, snippet)
        calls.update(matches)
    
    # Filter out common keywords and constructors
    filtered_calls = set()
    keywords_to_ignore = {'if', 'while', 'for', 'switch', 'catch', 'synchronized', 'return'}
    
    for call in calls:
        if (call not in keywords_to_ignore and 
            not call[0].isupper() and  # Likely not a constructor
            len(call) > 1):
            filtered_calls.add(call)
    
    return filtered_calls

def contains_relevant_keywords(snippet: str, keywords: List[str]) -> bool:
    """Check if snippet contains keywords, excluding comments and annotations."""
    lines = snippet.split('\n')
    
    for line in lines:
        stripped = line.strip()
        
        if (stripped.startswith('@') or 
            stripped.startswith('//') or 
            stripped.startswith('/*') or 
            stripped.startswith('*')):
            continue
        
        if any(kw.lower() in stripped.lower() for kw in keywords):
            return True
    
    return False

def trim_code_context(snippets_by_file: Dict[str, List[str]], max_chars: int = 2500) -> str:
    """Rank and trim snippets by importance until max_chars."""
    
    if not snippets_by_file:
        return ""
    
    ranked_snippets = []
    for file_path, snippets in snippets_by_file.items():
        for snippet in snippets:
            # Priority ranking based on content
            priority = 3  # Default low priority
            
            snippet_lower = snippet.lower()
            if any(keyword in snippet_lower for keyword in ["xpath", "field", "validate", "check"]):
                priority = 1  # High priority - likely validation related
            elif any(keyword in snippet_lower for keyword in ["public", "private", "protected"]):
                priority = 2  # Medium priority - method declarations
            
            # Boost priority for seed methods
            if "[SEED]" in snippet or "CONTAINS KEYWORDS" in snippet:
                priority = 1
            
            ranked_snippets.append((priority, file_path, snippet))
    
    # Sort by priority (1 = highest priority)
    ranked_snippets.sort(key=lambda x: x[0])
    
    # Keep adding until max_chars reached
    final_context = []
    total_len = 0
    original_count = len(ranked_snippets)
    
    for priority, fpath, snippet in ranked_snippets:
        chunk = f"\nFile: {fpath}\n--- Relevant Method ---\n{snippet}\n"
        
        if total_len + len(chunk) > max_chars:
            break
        
        final_context.append(chunk)
        total_len += len(chunk)
    
    included_count = len(final_context)
    
    if included_count < original_count:
        print(f"[INFO] Context trimmed: included {included_count}/{original_count} methods ({total_len} chars)")
    
    return "".join(final_context)

# Wrapper function to maintain compatibility with existing code
def extract_java_code_blocks(src_dir: str, keywords: List[str]) -> Dict[str, List[str]]:
    """
    Original function signature maintained for backward compatibility.
    This version includes cross-file analysis with default settings.
    """
    return extract_java_code_blocks_with_cross_references(
        src_dir=src_dir,
        keywords=keywords,
        max_depth=2,
        include_callers=True,
        include_callees=True
    )


# core/__init__.py

"""
Core module for Agentic Test Case Generator

This module provides the core functionality for generating comprehensive test cases
from field metadata and Java source code analysis.

Components:
- TestObjectiveGeneratorCore: Main generator with AI integration
- TestCaseManager: Test case parsing, storage, and Excel export
- Java code extraction with cross-file analysis and smart context trimming
"""

from .test_objective_core import TestObjectiveGeneratorCore
from .testcase_manager import TestCaseManager
from .java_extractor import (
    extract_java_code_blocks_with_cross_references,
    extract_java_code_blocks,
    trim_code_context
)

__all__ = [
    'TestObjectiveGeneratorCore',
    'TestCaseManager', 
    'extract_java_code_blocks_with_cross_references',
    'extract_java_code_blocks',
    'trim_code_context'
]

__version__ = '1.0.0'
__author__ = 'Agentic Test Generator'
__description__ = 'AI-powered test case generation from field metadata and Java code'


# Additional utility imports that might be needed
try:
    import javalang
except ImportError:
    print("Warning: javalang not installed. Java code analysis will not work.")
    print("Install with: pip install javalang")

try:
    import pandas as pd
    import openpyxl
except ImportError:
    print("Warning: pandas or openpyxl not installed. Excel export will not work.")
    print("Install with: pip install pandas openpyxl")

# Version compatibility checks
import sys
if sys.version_info < (3, 7):
    print("Warning: Python 3.7+ recommended for optimal performance")

print(f"[INFO] Agentic Test Generator v{__version__} loaded successfully")
