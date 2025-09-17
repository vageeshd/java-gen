# java-gen
import os
import re
from typing import Dict, List, Set, Tuple
import javalang

def extract_java_code_blocks(src_dir: str, keywords: List[str]) -> Dict[str, List[str]]:
    """
    Uses javalang to extract methods containing keywords.
    Returns a dict mapping file paths to lists of code snippets.
    """
    file_counts = {}
    file_code = {}
    
    # Find Java files containing all keywords
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith(".java"):
                path = os.path.join(root, file)
                
                try:
                    with open(path, encoding="utf-8", errors="ignore") as f:
                        code = f.read()
                except Exception:
                    continue
                
                # Check if all keywords appear in the file
                if all(kw.lower() in code.lower() for kw in keywords):
                    file_counts[path] = 1
                    file_code[path] = code
    
    # Sort and select top files
    ranked_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
    top_files = [file for file, count in ranked_files[:3]] if ranked_files else []
    
    results = {}
    
    for path in top_files:
        code = file_code[path]
        
        try:
            tree = javalang.parse.parse(code)
        except Exception as e:
            print(f"Failed to parse {path}: {e}")
            continue
        
        code_lines = code.splitlines()
        processed_methods = set()  # Track processed methods to avoid duplicates
        
        # Extract methods containing keywords
        for path_tuple, node in tree.filter(javalang.tree.MethodDeclaration):
            if not hasattr(node, 'position') or node.position is None:
                continue
                
            method_name = node.name
            
            # Create unique method signature
            param_types = tuple(
                p.type.name if hasattr(p.type, 'name') else str(p.type) 
                for p in getattr(node, 'parameters', [])
            )
            method_sig = (method_name, param_types)
            
            # Skip if already processed
            if method_sig in processed_methods:
                continue
            
            start_line = node.position.line - 1  # Convert to 0-based indexing
            
            # Find method end more accurately
            end_line = find_method_end(code_lines, start_line)
            
            if end_line >= len(code_lines):
                end_line = len(code_lines) - 1
            
            # Extract method snippet
            snippet = "\n".join(code_lines[start_line:end_line + 1])
            
            # Check if method contains any keyword (excluding comments and annotations)
            if contains_relevant_keywords(snippet, keywords):
                if path not in results:
                    results[path] = []
                
                # Add method signature as comment for clarity
                method_header = f"// Method: {method_name}({', '.join(param_types)})"
                final_snippet = method_header + "\n" + snippet
                
                results[path].append(final_snippet)
                processed_methods.add(method_sig)
    
    return results

def find_method_end(code_lines: List[str], start_line: int) -> int:
    """
    Find the end line of a method by tracking brace balance.
    """
    brace_count = 0
    in_method_body = False
    
    for i in range(start_line, len(code_lines)):
        line = code_lines[i].strip()
        
        # Skip empty lines and comments
        if not line or line.startswith('//') or line.startswith('/*') or line.startswith('*'):
            continue
        
        # Count braces
        for char in line:
            if char == '{':
                brace_count += 1
                in_method_body = True
            elif char == '}':
                brace_count -= 1
                
                # If we've closed all braces and we were in the method body
                if brace_count == 0 and in_method_body:
                    return i
    
    # Fallback: return last line if braces don't balance
    return len(code_lines) - 1

def contains_relevant_keywords(snippet: str, keywords: List[str]) -> bool:
    """
    Check if snippet contains keywords, excluding comments and annotations.
    """
    lines = snippet.split('\n')
    
    for line in lines:
        stripped = line.strip()
        
        # Skip comments and annotations
        if (stripped.startswith('@') or 
            stripped.startswith('//') or 
            stripped.startswith('/*') or 
            stripped.startswith('*')):
            continue
        
        # Check for keywords in actual code
        if any(kw.lower() in stripped.lower() for kw in keywords):
            return True
    
    return False

# Example usage
if __name__ == "__main__":
    # Test the function
    keywords = ["your", "keywords", "here"]
    src_directory = "/path/to/your/java/source"
    
    results = extract_java_code_blocks(src_directory, keywords)
    
    for file_path, methods in results.items():
        print(f"\n=== File: {file_path} ===")
        for i, method in enumerate(methods, 1):
            print(f"\n--- Method {i} ---")
            print(method)
