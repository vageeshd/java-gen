import os
import re
from typing import Dict, List, Set, Tuple, Optional, NamedTuple
import javalang
from dataclasses import dataclass
from collections import defaultdict
from pathlib import Path

# Existing NamedTuple classes (keep these from previous implementation)
class EnhancedMappingInfo(NamedTuple):
    service_name: str           
    operation: str              
    account_type: Optional[str] 
    direction: str              
    raw_filename: str

class ContentRelevanceScore(NamedTuple):
    field_name_matches: int      
    backend_xpath_matches: int   
    mapping_annotations: int     
    keyword_matches: int         
    total_content_score: int

class PathRelevanceScore(NamedTuple):
    operation_match: int         
    account_type_match: int      
    direction_match: int         
    structure_match: int         
    total_path_score: int

class CombinedRelevanceScore(NamedTuple):
    content_score: ContentRelevanceScore
    path_score: PathRelevanceScore
    total_score: int
    category: str

# Helper functions for method signature (keep these)
def get_method_signature(method_info) -> str:
    """Get full method signature for any method info object"""
    return f"{method_info.class_name}.{method_info.method_name}({','.join(method_info.param_types)})"

def get_qualified_method_name(method_info) -> str:
    """Get qualified method name for any method info object"""
    package_prefix = f"{method_info.package_name}." if method_info.package_name else ""
    return f"{package_prefix}{method_info.class_name}.{method_info.method_name}"

# Enhanced mapping sheet parsing (from previous implementation)
def parse_enhanced_mapping_info(mapping_file_path: str) -> EnhancedMappingInfo:
    """Parse operation and account type from mapping sheet filename"""
    
    filename = os.path.basename(mapping_file_path)
    filename_lower = filename.lower()
    
    print(f"[INFO] Enhanced parsing: {filename}")
    
    # Remove common suffixes to get clean name
    clean_name = re.sub(r'_prm\d+\.\d+.*$|_v\d+\.\d+.*$|_\d{4}.*$', '', filename_lower, re.IGNORECASE)
    clean_name = clean_name.replace('.xlsm', '').replace('.xlsx', '')
    
    # Extract operation first (add, inq, mod, del)
    operations = ['add', 'inq', 'mod', 'del']
    operation = "unknown"
    operation_pattern = None
    
    for op in operations:
        if clean_name.endswith(op):
            operation = op
            operation_pattern = op
            break
        elif op in clean_name:
            # Check if it's part of service name (like "addr" contains "add")
            if op == "add" and "addr" in clean_name and not clean_name.endswith("add"):
                continue  # Skip false positive
            operation = op
            operation_pattern = op
            break
    
    # Extract service name and account type
    service_name = "unknown"
    account_type = None
    
    if operation_pattern:
        # Remove operation from end to get service part
        service_part = clean_name.replace(operation_pattern, '').rstrip('_')
        
        # Check if it's an account service (contains "acct")
        if "acct" in service_part:
            service_name = "acct"
            
            # Extract account type if present
            account_types = ['sda', 'dda', 'cda', 'ddl', 'sdb', 'loan', 'inet']
            
            # Look for account type in original filename (case sensitive)
            for acc_type in account_types:
                if acc_type.upper() in filename.upper():
                    account_type = acc_type.lower()
                    break
        else:
            # Non-account service - extract service name
            service_candidates = service_part.split('_')
            
            if service_candidates:
                service_name = service_candidates[0] if service_candidates[0] else "unknown"
    
    # Infer direction from operation
    direction = 'response' if operation == 'inq' else 'request'
    
    result = EnhancedMappingInfo(
        service_name=service_name,
        operation=operation,
        account_type=account_type,
        direction=direction,
        raw_filename=filename
    )
    
    print(f"[INFO] Enhanced parsed: service={service_name}, operation={operation}, "
          f"account_type={account_type}, direction={direction}")
    
    return result

def should_skip_directory(dir_path: str) -> bool:
    """Skip obviously irrelevant directories"""
    skip_patterns = [
        'test', 'tests', 'spec',  # Test directories
        'doc', 'docs', 'documentation',  # Documentation  
        'config', 'configuration',  # Configuration
        'resource', 'resources',  # Resource files
        'target', 'build', 'out',  # Build outputs
        'node_modules', '.git'  # Dependencies/version control
    ]
    
    dir_path_lower = dir_path.lower()
    return any(pattern in dir_path_lower for pattern in skip_patterns)

def extract_keywords_from_field(field_metadata: Dict) -> Tuple[List[str], List[str]]:
    """Extract primary and secondary keywords from field metadata"""
    
    primary_keywords = []
    secondary_keywords = []
    
    field_name = field_metadata.get('field_name', '').strip()
    backend_xpath = field_metadata.get('backend_xpath', '').strip()
    
    # Primary keywords - field name and backend xpath segments
    if field_name:
        primary_keywords.append(field_name)
        # Add camelCase breakdown: PostalCode -> postal, code
        camel_parts = re.findall(r'[A-Z][a-z]*|[a-z]+', field_name)
        primary_keywords.extend(camel_parts)
    
    if backend_xpath:
        # Extract meaningful segments from backend xpath
        xpath_segments = [seg.strip() for seg in backend_xpath.split('/') if len(seg.strip()) > 2]
        primary_keywords.extend(xpath_segments)
    
    # Secondary keywords - related field context
    description = field_metadata.get('description', '').strip()
    if description:
        # Extract meaningful words from description (simple approach)
        desc_words = [word.strip() for word in re.findall(r'\w+', description) if len(word) > 3]
        secondary_keywords.extend(desc_words[:3])  # Limit to avoid noise
    
    # Remove duplicates and empty strings
    primary_keywords = list(set([kw for kw in primary_keywords if kw and len(kw) > 1]))
    secondary_keywords = list(set([kw for kw in secondary_keywords if kw and len(kw) > 1]))
    
    print(f"[DEBUG] Primary keywords: {primary_keywords}")
    print(f"[DEBUG] Secondary keywords: {secondary_keywords}")
    
    return primary_keywords, secondary_keywords

def fast_keyword_filter(src_dir: str, primary_keywords: List[str]) -> List[str]:
    """Quickly filter files that contain ANY primary keywords (case insensitive)"""
    
    relevant_files = []
    primary_keywords_lower = [kw.lower() for kw in primary_keywords]
    
    print(f"[INFO] Fast filtering for keywords: {primary_keywords}")
    
    for root, dirs, files in os.walk(src_dir):
        # Skip irrelevant directories early
        dirs[:] = [d for d in dirs if not should_skip_directory(os.path.join(root, d))]
        
        for file in files:
            if file.endswith(".java"):
                file_path = os.path.join(root, file)
                
                try:
                    # Fast file content check (no parsing)
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                    
                    # Check if ANY primary keyword exists in file (case insensitive)
                    if any(keyword in content for keyword in primary_keywords_lower):
                        relevant_files.append(file_path)
                        
                except Exception as e:
                    # Skip files that give errors when reading
                    print(f"[WARN] Skipping file due to read error: {file_path} - {e}")
                    continue
    
    print(f"[INFO] Fast filtering found {len(relevant_files)} files containing keywords")
    return relevant_files

def calculate_method_relevance_score(method, primary_keywords: List[str], secondary_keywords: List[str], 
                                   mapping_info: EnhancedMappingInfo) -> int:
    """Calculate relevance score for a method based on keyword placement"""
    
    score = 0
    method_name_lower = method.method_name.lower()
    method_code_lower = method.snippet.lower()
    
    # Convert keywords to lowercase for case-insensitive matching
    primary_lower = [kw.lower() for kw in primary_keywords]
    secondary_lower = [kw.lower() for kw in secondary_keywords]
    
    # Primary keyword scoring (highest weight) - case insensitive
    for keyword in primary_lower:
        if keyword in method_name_lower:
            score += 50  # Method name match is most important
        elif keyword in method_code_lower:
            score += 20  # Code content match
    
    # Secondary keyword scoring (medium weight) - case insensitive
    for keyword in secondary_lower:
        if keyword in method_name_lower:
            score += 25
        elif keyword in method_code_lower:
            score += 10
    
    # Path relevance scoring
    file_path_lower = method.file_path.lower()
    
    # Service name matching
    if mapping_info.service_name != "unknown" and mapping_info.service_name in file_path_lower:
        score += 15
    
    # Operation matching  
    if mapping_info.operation != "unknown" and mapping_info.operation in file_path_lower:
        score += 15
    
    # Direction matching
    if mapping_info.direction in file_path_lower:
        score += 10
    
    # Account type matching (if applicable)
    if mapping_info.account_type and mapping_info.account_type in file_path_lower:
        score += 15
    
    # File type bonuses
    file_name_lower = os.path.basename(method.file_path).lower()
    if any(pattern in file_name_lower for pattern in ['mapper', 'mapping']):
        score += 20  # Mapper files are highly relevant
    elif any(pattern in file_name_lower for pattern in ['validator', 'validation']):
        score += 15  # Validation files are relevant
    elif any(pattern in file_name_lower for pattern in ['service', 'processor']):
        score += 10  # Service files are somewhat relevant
    
    # Method type bonuses (case insensitive)
    if any(pattern in method_name_lower for pattern in ['map', 'transform', 'convert']):
        score += 10  # Mapping methods
    if any(pattern in method_name_lower for pattern in ['validate', 'check', 'verify']):
        score += 8   # Validation methods
    
    return score

def find_relevant_callers_callees(high_scoring_methods: Dict, all_methods: Dict, 
                                threshold: int = 30) -> Dict:
    """Find callers and callees only for high-scoring methods"""
    
    relationship_methods = {}
    
    print(f"[INFO] Finding relationships for {len(high_scoring_methods)} high-scoring methods")
    
    for method_sig, method_info in high_scoring_methods.items():
        if method_info.relevance_score >= threshold:
            
            # Find callers (methods that call this high-scoring method)
            for other_sig, other_method in all_methods.items():
                if method_info.method_name in other_method.calls_made:
                    if other_sig not in high_scoring_methods:  # Don't duplicate
                        # Give relationship methods a base score
                        other_method.relevance_score = getattr(other_method, 'relevance_score', 0) + 5
                        relationship_methods[other_sig] = other_method
            
            # Find callees (methods called by this high-scoring method)
            for called_method_name in method_info.calls_made:
                for other_sig, other_method in all_methods.items():
                    if other_method.method_name == called_method_name:
                        if other_sig not in high_scoring_methods:  # Don't duplicate
                            # Give relationship methods a base score  
                            other_method.relevance_score = getattr(other_method, 'relevance_score', 0) + 5
                            relationship_methods[other_sig] = other_method
    
    print(f"[INFO] Found {len(relationship_methods)} related methods through caller/callee analysis")
    return relationship_methods

def organize_results_by_relevance(all_relevant_methods: Dict) -> Dict[str, List[str]]:
    """Organize methods by file and create annotated snippets"""
    
    results = {}
    
    # Group methods by file
    methods_by_file = defaultdict(list)
    for method_sig, method_info in all_relevant_methods.items():
        methods_by_file[method_info.file_path].append((method_sig, method_info))
    
    # Sort methods within each file by relevance score
    for file_path, method_list in methods_by_file.items():
        method_list.sort(key=lambda x: getattr(x[1], 'relevance_score', 0), reverse=True)
        
        results[file_path] = []
        
        for method_sig, method_info in method_list:
            relevance_score = getattr(method_info, 'relevance_score', 0)
            
            # Categorize by relevance score
            if relevance_score >= 50:
                category = "HIGH"
            elif relevance_score >= 30:
                category = "MEDIUM" 
            elif relevance_score >= 15:
                category = "LOW"
            else:
                category = "RELATED"
            
            # Create annotated header
            header = f"// [{category}] Method: {get_qualified_method_name(method_info)}"
            header += f" [Score: {relevance_score}]"
            
            # Add specific match information
            if relevance_score >= 50:
                header += " [PRIMARY_KEYWORD_IN_METHOD_NAME]"
            elif relevance_score >= 30:
                header += " [KEYWORD_MATCH]"
            
            # Create full annotated snippet
            annotated_snippet = f"{header}\n// File: {file_path}\n{method_info.snippet}"
            
            results[file_path].append(annotated_snippet)
    
    return results

def extract_java_code_blocks_with_cross_references(
    src_dir: str, 
    keywords: List[str], 
    max_depth: int = 2,
    include_callers: bool = True,
    include_callees: bool = True,
    mapping_file_path: str = None,        
    field_metadata: Dict = None           
) -> Dict[str, List[str]]:
    """
    Optimized extraction with hierarchical keyword filtering and smart relevance scoring
    """
    
    print(f"[INFO] Starting optimized Java extraction")
    
    # Parse mapping information if available
    mapping_info = None
    if mapping_file_path and os.path.exists(mapping_file_path):
        try:
            mapping_info = parse_enhanced_mapping_info(mapping_file_path)
            print(f"[INFO] Using smart extraction with mapping analysis")
        except Exception as e:
            print(f"[WARN] Mapping parsing failed, using basic mode: {e}")
            mapping_info = EnhancedMappingInfo("unknown", "unknown", None, "request", "")
    else:
        print(f"[INFO] No mapping info provided, using keywords only")
        mapping_info = EnhancedMappingInfo("unknown", "unknown", None, "request", "")
    
    # Extract keywords from field metadata
    if field_metadata:
        primary_keywords, secondary_keywords = extract_keywords_from_field(field_metadata)
    else:
        # Fallback to provided keywords as primary
        primary_keywords = keywords if keywords else []
        secondary_keywords = []
    
    if not primary_keywords:
        print("[ERROR] No keywords available for extraction")
        return {}
    
    # Stage 1: Fast file filtering using primary keywords
    relevant_files = fast_keyword_filter(src_dir, primary_keywords)
    
    if not relevant_files:
        print("[WARN] No files contain the specified keywords")
        return {}
    
    # Stage 2: Parse relevant files and score methods
    print(f"[INFO] Parsing {len(relevant_files)} relevant files")
    
    all_parsed_methods = {}
    high_scoring_methods = {}
    
    for file_path in relevant_files:
        try:
            # Parse Java file (this can fail, so we skip on error)
            methods = parse_java_file(file_path, primary_keywords)
            
            for method in methods:
                method_sig = get_method_signature(method)
                
                # Calculate relevance score
                relevance_score = calculate_method_relevance_score(
                    method, primary_keywords, secondary_keywords, mapping_info
                )
                method.relevance_score = relevance_score
                
                all_parsed_methods[method_sig] = method
                
                # Keep methods with decent relevance scores
                if relevance_score >= 15:  # Minimum threshold for relevance
                    high_scoring_methods[method_sig] = method
                    
        except Exception as e:
            # Skip files that give parsing errors
            print(f"[WARN] Skipping file due to parsing error: {file_path} - {e}")
            continue
    
    print(f"[INFO] Found {len(high_scoring_methods)} high-scoring methods from {len(all_parsed_methods)} total methods")
    
    # Stage 3: Find callers and callees only for high-scoring methods (if enabled)
    relationship_methods = {}
    if (include_callers or include_callees) and len(high_scoring_methods) > 0:
        relationship_methods = find_relevant_callers_callees(
            high_scoring_methods, all_parsed_methods, threshold=20
        )
    
    # Stage 4: Combine and organize results
    all_relevant_methods = {**high_scoring_methods, **relationship_methods}
    
    # Limit total methods to avoid overwhelming context
    max_methods = 50
    if len(all_relevant_methods) > max_methods:
        # Keep only the highest scoring methods
        sorted_methods = sorted(all_relevant_methods.items(), 
                              key=lambda x: getattr(x[1], 'relevance_score', 0), 
                              reverse=True)
        all_relevant_methods = dict(sorted_methods[:max_methods])
        print(f"[INFO] Limited to top {max_methods} methods by relevance score")
    
    # Organize final results
    results = organize_results_by_relevance(all_relevant_methods)
    
    total_methods = sum(len(methods) for methods in results.values())
    print(f"[INFO] Optimized extraction completed: {len(results)} files with {total_methods} relevant methods")
    
    return results

# Updated trim function to work with new approach
def trim_code_context(snippets_by_file: Dict[str, List[str]], max_chars: int = 2500,
                     mapping_file_path: str = None) -> str:
    """Trim context prioritizing by relevance scores in annotations"""
    
    if not snippets_by_file:
        return ""
    
    ranked_snippets = []
    
    for file_path, snippets in snippets_by_file.items():
        for snippet in snippets:
            priority = 5  # Default priority
            
            # Extract relevance category and score from annotation
            if "[HIGH]" in snippet:
                priority = 1
            elif "[MEDIUM]" in snippet:
                priority = 2  
            elif "[LOW]" in snippet:
                priority = 3
            elif "[RELATED]" in snippet:
                priority = 4
            
            # Further prioritize by specific indicators
            if "PRIMARY_KEYWORD_IN_METHOD_NAME" in snippet:
                priority = min(priority, 1)  # Highest priority
            elif "KEYWORD_MATCH" in snippet:
                priority = min(priority, 2)
            
            ranked_snippets.append((priority, file_path, snippet))
    
    # Sort by priority (1 = highest)
    ranked_snippets.sort(key=lambda x: x[0])
    
    # Build context within limits
    final_context = []
    total_len = 0
    
    for priority, fpath, snippet in ranked_snippets:
        chunk = f"\n{'-'*50}\n{snippet}\n{'-'*50}\n"
        
        if total_len + len(chunk) > max_chars:
            break
        
        final_context.append(chunk)
        total_len += len(chunk)
    
    included_count = len(final_context)
    
    print(f"[INFO] Context trimming: included {included_count}/{len(ranked_snippets)} methods ({total_len} chars)")
    
    return "".join(final_context)