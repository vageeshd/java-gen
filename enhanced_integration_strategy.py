# Enhanced integration approach - ADD to your existing java_extractor.py

import os
import re
from typing import Dict, List, Set, Tuple, Optional, NamedTuple
import javalang
from dataclasses import dataclass
from collections import defaultdict
from pathlib import Path

# ADD these new classes to your existing file:

class MappingSheetInfo(NamedTuple):
    """Parsed information from mapping sheet filename"""
    operation: str  # add, inq, mod, del
    account_type: Optional[str]  # cda, dda, ddl, sdb, sda, loan, inet
    direction: str  # request, response (inferred from operation)
    raw_filename: str

class ContentRelevanceScore(NamedTuple):
    """Content-based relevance scoring"""
    field_name_matches: int      # Method name contains field name (0-5)
    backend_xpath_matches: int   # Code contains backend xpath segments (0-9)  
    mapping_annotations: int     # MapStruct annotations (0-4)
    keyword_matches: int         # Keywords in method body (0-2)
    total_content_score: int

class PathRelevanceScore(NamedTuple):
    """Path-based relevance scoring"""
    operation_match: int         # 0-2
    account_type_match: int      # 0-2
    direction_match: int         # 0-2  
    structure_match: int         # 0-2
    total_path_score: int

class CombinedRelevanceScore(NamedTuple):
    """Combined relevance scoring"""
    content_score: ContentRelevanceScore
    path_score: PathRelevanceScore
    total_score: int             # Combined weighted score
    category: str                # HIGH/MEDIUM/LOW relevance category

# ADD these functions to your existing file:

def parse_mapping_sheet_info(mapping_file_path: str) -> MappingSheetInfo:
    """Parse operation and account type from mapping sheet filename"""
    
    operations = {'add', 'inq', 'mod', 'del'}
    account_types = {'cda', 'dda', 'ddl', 'sdb', 'sda', 'loan', 'inet'}
    
    filename = os.path.basename(mapping_file_path).lower()
    print(f"[INFO] Parsing mapping sheet: {filename}")
    
    # Extract operation
    operation = "unknown"
    for op in operations:
        if op in filename:
            operation = op
            break
    
    # Extract account type (optional)
    account_type = None
    for acc_type in account_types:
        if acc_type in filename:
            account_type = acc_type
            break
    
    # Infer direction from operation
    direction = 'response' if operation == 'inq' else 'request'
    
    result = MappingSheetInfo(
        operation=operation,
        account_type=account_type, 
        direction=direction,
        raw_filename=filename
    )
    
    print(f"[INFO] Parsed: operation={operation}, account_type={account_type}, direction={direction}")
    return result

def calculate_content_relevance(method_snippet: str, method_name: str, keywords: List[str], 
                              field_metadata: Dict) -> ContentRelevanceScore:
    """Calculate content-based relevance score with field/xpath intelligence"""
    
    field_name = field_metadata.get('field_name', '').lower()
    backend_xpath = field_metadata.get('backend_xpath', '')
    
    # Extract backend xpath segments  
    xpath_segments = []
    if backend_xpath:
        segments = [seg.strip() for seg in backend_xpath.split('/') if seg.strip()]
        xpath_segments = [seg.lower() for seg in segments]
    
    snippet_lower = method_snippet.lower()
    method_name_lower = method_name.lower()
    
    # 1. Field name matches in method name (0-5 points)
    field_name_score = 0
    if field_name and len(field_name) > 2:
        if field_name == method_name_lower:
            field_name_score = 5  # Exact match
        elif field_name in method_name_lower or method_name_lower in field_name:
            field_name_score = 4  # Partial match
        elif any(word in method_name_lower for word in field_name.split('_')):
            field_name_score = 3  # Word match
    
    # 2. Backend xpath segments in code (0-9 points, max 3 per segment)
    xpath_score = 0
    for segment in xpath_segments:
        if len(segment) > 2:  # Skip very short segments
            segment_score = 0
            
            # Check method name
            if segment in method_name_lower:
                segment_score = 3
            # Check method calls/properties
            elif re.search(f'\\b{segment}\\b', snippet_lower):
                segment_score = 2
            # Check as part of string literals  
            elif f'"{segment}"' in snippet_lower or f"'{segment}'" in snippet_lower:
                segment_score = 2
            # Check getter/setter patterns
            elif re.search(f'get{segment}|set{segment}', snippet_lower, re.IGNORECASE):
                segment_score = 3
            
            xpath_score += segment_score
    
    xpath_score = min(xpath_score, 9)  # Cap at 9 points
    
    # 3. MapStruct annotations (0-4 points)
    mapping_score = 0
    mapping_patterns = [
        r'@Mapping\s*\([^)]*target\s*=\s*["\'].*' + re.escape(field_name) + r'.*["\']',
        r'@Mapping\s*\([^)]*source\s*=\s*["\'].*' + re.escape(field_name) + r'.*["\']',
        r'@AfterMapping.*' + re.escape(field_name),
        r'@BeforeMapping.*' + re.escape(field_name)
    ]
    
    for pattern in mapping_patterns:
        if re.search(pattern, method_snippet, re.IGNORECASE):
            mapping_score = 4
            break
    
    # Also check for any MapStruct annotations (lower score)
    if mapping_score == 0 and re.search(r'@(Mapping|AfterMapping|BeforeMapping)', method_snippet):
        mapping_score = 1
    
    # 4. Keywords in method body (0-2 points) - your existing logic
    keyword_score = 0
    for keyword in keywords:
        if keyword.lower() in snippet_lower:
            keyword_score = 2
            break
    
    total_content = field_name_score + xpath_score + mapping_score + keyword_score
    
    return ContentRelevanceScore(
        field_name_matches=field_name_score,
        backend_xpath_matches=xpath_score,
        mapping_annotations=mapping_score, 
        keyword_matches=keyword_score,
        total_content_score=total_content
    )

def calculate_path_relevance(file_path: str, mapping_info: MappingSheetInfo) -> PathRelevanceScore:
    """Calculate path-based relevance score - your existing logic simplified"""
    
    path_lower = file_path.lower()
    
    # Operation matching (0-2 points)
    operation_score = 0
    if mapping_info.operation in path_lower:
        operation_score = 2
    elif mapping_info.direction in path_lower:
        operation_score = 1
    
    # Account type matching (0-2 points)  
    account_type_score = 0
    if mapping_info.account_type:
        if mapping_info.account_type in path_lower:
            account_type_score = 2
        elif any(word in path_lower for word in ['all', 'common', 'generic']):
            account_type_score = 1
    else:
        account_type_score = 2  # N/A - no penalty
    
    # Direction matching (0-2 points)
    direction_score = 0
    if mapping_info.direction in path_lower:
        direction_score = 2
    elif 'request' in path_lower or 'response' in path_lower:
        direction_score = 1  # Some direction indication
    
    # Structure matching (0-2 points)
    structure_score = 0
    if 'mapper' in path_lower or 'mapping' in path_lower:
        structure_score = 2
    elif any(word in path_lower for word in ['processor', 'controller', 'service']):
        structure_score = 1
    
    total_path = operation_score + account_type_score + direction_score + structure_score
    
    return PathRelevanceScore(
        operation_match=operation_score,
        account_type_match=account_type_score,
        direction_match=direction_score,
        structure_match=structure_score,
        total_path_score=total_path
    )

def calculate_combined_relevance(content_score: ContentRelevanceScore, path_score: PathRelevanceScore) -> CombinedRelevanceScore:
    """Combine content and path scores with appropriate weighting"""
    
    # Weight content higher than path (content is more important)
    weighted_total = (content_score.total_content_score * 2) + path_score.total_path_score
    
    # Determine category based on weighted score
    if weighted_total >= 25:  # Very high relevance
        category = "HIGH"
    elif weighted_total >= 15:  # Medium relevance  
        category = "MEDIUM"
    elif weighted_total >= 8:   # Low but still relevant
        category = "LOW"
    else:
        category = "IGNORE"  # Too low relevance
    
    return CombinedRelevanceScore(
        content_score=content_score,
        path_score=path_score,
        total_score=weighted_total,
        category=category
    )

# MODIFY your existing extract_java_code_blocks_with_cross_references function:

def extract_java_code_blocks_with_cross_references(
    src_dir: str, 
    keywords: List[str], 
    max_depth: int = 2,
    include_callers: bool = True,
    include_callees: bool = True,
    mapping_file_path: str = None,        # ADD this parameter
    field_metadata: Dict = None           # ADD this parameter
) -> Dict[str, List[str]]:
    """
    Enhanced extraction with smart relevance scoring when mapping info is available
    """
    
    print(f"[INFO] Starting enhanced Java extraction")
    
    # Parse mapping information if available
    mapping_info = None
    if mapping_file_path and os.path.exists(mapping_file_path):
        mapping_info = parse_mapping_sheet_info(mapping_file_path)
        print(f"[INFO] Using smart extraction with mapping analysis")
    else:
        print(f"[INFO] Using basic extraction (no mapping info)")
    
    # Your existing file discovery logic
    all_methods = {}  # signature -> MethodInfo (keep your existing structure)
    file_to_methods = defaultdict(list)
    method_calls_map = defaultdict(set)
    
    java_files = []
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith(".java"):
                java_files.append(os.path.join(root, file))
    
    print(f"[INFO] Found {len(java_files)} Java files to analyze")
    
    # Parse all files with enhanced scoring
    enhanced_methods = {}  # signature -> enhanced relevance data
    
    for file_path in java_files:
        try:
            # Your existing method parsing logic here...
            methods = parse_java_file(file_path, keywords)  # Your existing function
            
            for method in methods:
                sig = method.get_full_signature()
                all_methods[sig] = method
                file_to_methods[file_path].append(sig)
                
                # ADD enhanced relevance scoring
                if mapping_info and field_metadata:
                    content_score = calculate_content_relevance(
                        method.snippet, method.method_name, keywords, field_metadata
                    )
                    path_score = calculate_path_relevance(file_path, mapping_info)
                    combined_score = calculate_combined_relevance(content_score, path_score)
                    
                    enhanced_methods[sig] = combined_score
                
        except Exception as e:
            print(f"[WARN] Failed to parse {file_path}: {e}")
            continue
    
    print(f"[INFO] Parsed {len(all_methods)} total methods")
    
    # Your existing call relationship building...
    # (keep this unchanged)
    
    # Enhanced seed method selection
    seed_methods = set()
    if enhanced_methods:
        # Use smart scoring to find seed methods
        for sig, combined_score in enhanced_methods.items():
            if combined_score.category in ["HIGH", "MEDIUM"]:
                seed_methods.add(sig)
                if combined_score.category == "HIGH":
                    print(f"[DEBUG] HIGH relevance seed: {all_methods[sig].method_name} (score: {combined_score.total_score})")
    else:
        # Fallback to your existing logic
        for method_info in all_methods.values():
            if method_info.contains_keywords:
                seed_methods.add(method_info.get_full_signature())
    
    print(f"[INFO] Found {len(seed_methods)} seed methods")
    
    # Your existing relationship tracing logic...
    # (keep this unchanged, but filter by relevance if available)
    
    relevant_methods = set(seed_methods)
    # ... your existing tracing code ...
    
    # Enhanced result organization
    results = {}
    
    for method_sig in relevant_methods:
        method_info = all_methods.get(method_sig)
        if not method_info:
            continue
        
        file_path = method_info.file_path
        if file_path not in results:
            results[file_path] = []
        
        # Enhanced annotation with relevance info
        if method_sig in enhanced_methods:
            score = enhanced_methods[method_sig]
            category = f"[{score.category}]"
            score_info = f"[Content:{score.content_score.total_content_score}, Path:{score.path_score.total_path_score}]"
            
            header = f"// {category} Method: {method_info.get_qualified_name()} {score_info}"
            
            if score.content_score.field_name_matches > 0:
                header += " [FIELD_NAME_MATCH]"
            if score.content_score.mapping_annotations > 0:
                header += " [MAPSTRUCT]"
        else:
            # Fallback annotation
            category = "SEED" if method_sig in seed_methods else "RELATED"
            header = f"// [{category}] Method: {method_info.get_qualified_name()}"
        
        annotated_snippet = f"{header}\n// File: {file_path}\n{method_info.snippet}"
        results[file_path].append(annotated_snippet)
    
    return results

# MODIFY your existing trim_code_context function:

def trim_code_context(snippets_by_file: Dict[str, List[str]], max_chars: int = 2500,
                     mapping_file_path: str = None) -> str:
    """Enhanced context trimming with smart relevance-based prioritization"""
    
    if not snippets_by_file:
        return ""
    
    ranked_snippets = []
    
    for file_path, snippets in snippets_by_file.items():
        for snippet in snippets:
            priority = 5  # Default priority
            
            # Enhanced priority based on annotations
            if "[HIGH]" in snippet:
                priority = 1
            elif "[MEDIUM]" in snippet:
                priority = 2  
            elif "[FIELD_NAME_MATCH]" in snippet:
                priority = 2
            elif "[MAPSTRUCT]" in snippet:
                priority = 3
            elif "SEED" in snippet:
                priority = 4
            
            # Further boost for specific content patterns
            if "validate" in snippet.lower() and any(kw in snippet.lower() for kw in ["postal", "address", "code"]):
                priority = min(priority, 2)
            
            ranked_snippets.append((priority, file_path, snippet))
    
    # Sort by priority (1 = highest)
    ranked_snippets.sort(key=lambda x: x[0])
    
    # Build context within limits
    final_context = []
    total_len = 0
    
    for priority, fpath, snippet in ranked_snippets:
        chunk = f"\n{'-'*40}\n{snippet}\n{'-'*40}\n"
        
        if total_len + len(chunk) > max_chars:
            break
        
        final_context.append(chunk)
        total_len += len(chunk)
    
    included_count = len(final_context)
    
    print(f"[INFO] Enhanced context: included {included_count}/{len(ranked_snippets)} methods ({total_len} chars)")
    
    return "".join(final_context)

# Example of how the scoring works:
"""
EXAMPLE SCORING COMPARISON:

Method 1: validatePostalCode() in /random/utils/CommonUtil.java
- Content: field_name(4) + xpath_segments(6) + mapping(0) + keywords(2) = 12
- Path: operation(0) + account_type(0) + direction(0) + structure(0) = 0  
- Weighted Total: (12 * 2) + 0 = 24 points → MEDIUM relevance

Method 2: doSomething() in /request/add/sda/SdaMapper.java  
- Content: field_name(0) + xpath_segments(0) + mapping(0) + keywords(0) = 0
- Path: operation(2) + account_type(2) + direction(2) + structure(2) = 8
- Weighted Total: (0 * 2) + 8 = 8 points → LOW relevance

Method 3: mapPostalCode() in /request/add/sda/SdaAddressMapper.java
- Content: field_name(5) + xpath_segments(6) + mapping(4) + keywords(2) = 17
- Path: operation(2) + account_type(2) + direction(2) + structure(2) = 8  
- Weighted Total: (17 * 2) + 8 = 42 points → HIGH relevance ✅ BEST MATCH

Result: Method 3 wins because content relevance is weighted 2x higher than path relevance!
"""
