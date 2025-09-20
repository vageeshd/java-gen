# Corrected smart extraction logic

import os
import re
from typing import Dict, List, Set, Tuple, Optional, NamedTuple
from dataclasses import dataclass

class EnhancedMappingInfo(NamedTuple):
    """Enhanced parsing with proper service extraction"""
    service_name: str           # beneficiary, addr, acct, party, etc.
    operation: str              # add, inq, mod, del
    account_type: Optional[str] # sda, cda, etc. (only if service="acct")
    direction: str              # request, response
    raw_filename: str

class TieBreakingScore(NamedTuple):
    """Enhanced scoring with proper tiebreaking"""
    content_score: int          # Content relevance (0-20)
    path_score: int            # Path relevance (0-12) 
    service_match: bool        # Critical: does service match?
    operation_match: bool      # Critical: does operation match?
    account_type_match: bool   # Critical if applicable
    final_score: int           # Weighted with tiebreaking
    category: str              # HIGH/MEDIUM/LOW
    tiebreak_reason: str       # Why this scored higher in conflicts

def parse_enhanced_mapping_info(mapping_file_path: str) -> EnhancedMappingInfo:
    """Enhanced parsing with proper service/account type extraction"""
    
    filename = os.path.basename(mapping_file_path)
    filename_lower = filename.lower()
    
    print(f"[INFO] Enhanced parsing: {filename}")
    
    # Remove common suffixes to get clean name
    clean_name = re.sub(r'_prm\d+\.\d+.*$|_v\d+\.\d+.*$|_\d{4}.*$', '', filename_lower, re.IGNORECASE)
    clean_name = clean_name.replace('.xlsm', '').replace('.xlsx', '')
    
    print(f"[DEBUG] Clean name: {clean_name}")
    
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
        
        print(f"[DEBUG] Service part after removing operation: {service_part}")
        
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
            
            print(f"[DEBUG] Account service detected, account_type: {account_type}")
            
        else:
            # Non-account service - extract service name
            # Common services: beneficiary, addr, party, customer, etc.
            service_candidates = service_part.split('_')
            
            if service_candidates:
                # Take the first meaningful part as service name
                service_name = service_candidates[0] if service_candidates[0] else "unknown"
                
                # Handle compound services like "addr_party" 
                if len(service_candidates) > 1 and len(service_candidates[1]) > 2:
                    service_name = service_candidates[0]  # Use first part
    
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

def calculate_enhanced_path_score(file_path: str, mapping_info: EnhancedMappingInfo) -> Tuple[int, Dict[str, bool]]:
    """Calculate path score with proper service/operation matching"""
    
    path_lower = file_path.lower()
    path_parts = file_path.lower().split('/')
    
    print(f"[DEBUG] Analyzing path: {file_path}")
    print(f"[DEBUG] Looking for: service={mapping_info.service_name}, op={mapping_info.operation}, "
          f"dir={mapping_info.direction}, acct_type={mapping_info.account_type}")
    
    # Critical matching flags
    service_match = False
    operation_match = False  
    account_type_match = True  # Default true if not applicable
    direction_match = False
    
    score = 0
    
    # 1. Direction matching (0-2 points) - CRITICAL
    if mapping_info.direction in path_lower:
        direction_match = True
        score += 2
        print(f"[DEBUG] Direction match: {mapping_info.direction}")
    
    # 2. Service name matching (0-4 points) - MOST CRITICAL
    if mapping_info.service_name != "unknown":
        if mapping_info.service_name in path_lower:
            service_match = True
            score += 4
            print(f"[DEBUG] Service match: {mapping_info.service_name}")
        
        # Check for service name variations
        service_variations = {
            'addr': ['address', 'addr'],
            'acct': ['account', 'acct'], 
            'party': ['party', 'customer'],
            'beneficiary': ['beneficiary', 'benef']
        }
        
        variations = service_variations.get(mapping_info.service_name, [mapping_info.service_name])
        for variation in variations:
            if variation in path_lower:
                service_match = True
                score += 3  # Slightly less for variations
                print(f"[DEBUG] Service variation match: {variation}")
                break
    
    # 3. Operation matching (0-3 points) - CRITICAL  
    if mapping_info.operation in path_lower:
        operation_match = True
        score += 3
        print(f"[DEBUG] Operation match: {mapping_info.operation}")
    
    # 4. Account type matching (0-3 points) - CRITICAL if applicable
    if mapping_info.account_type:
        if mapping_info.account_type in path_lower:
            account_type_match = True
            score += 3
            print(f"[DEBUG] Account type match: {mapping_info.account_type}")
        else:
            account_type_match = False
            print(f"[DEBUG] Account type MISMATCH: expected {mapping_info.account_type}")
    
    match_flags = {
        'service_match': service_match,
        'operation_match': operation_match,
        'account_type_match': account_type_match,
        'direction_match': direction_match
    }
    
    print(f"[DEBUG] Path score: {score}, matches: {match_flags}")
    
    return score, match_flags

def calculate_tiebreaking_score(content_score: int, path_score: int, match_flags: Dict[str, bool],
                               mapping_info: EnhancedMappingInfo, method_name: str) -> TieBreakingScore:
    """Calculate final score with proper tiebreaking logic"""
    
    service_match = match_flags['service_match']
    operation_match = match_flags['operation_match'] 
    account_type_match = match_flags['account_type_match']
    direction_match = match_flags['direction_match']
    
    # CRITICAL PATH REQUIREMENTS - must match these for HIGH relevance
    critical_path_score = 0
    if direction_match:
        critical_path_score += 1
    if service_match:
        critical_path_score += 2  # Most important
    if operation_match:
        critical_path_score += 1
    if account_type_match:  # Only matters if account_type exists
        critical_path_score += 1
    
    # Base weighted score
    base_score = (content_score * 2) + path_score
    
    # Tiebreaking and category logic
    category = "IGNORE"
    tiebreak_reason = ""
    final_score = base_score
    
    if content_score >= 12 and critical_path_score >= 3:
        # High content + good path match = HIGH
        category = "HIGH"
        final_score = base_score + 10  # Bonus for perfect match
        tiebreak_reason = "High content + critical path match"
        
    elif content_score >= 12 and critical_path_score >= 2:
        # High content + partial path match = MEDIUM-HIGH
        category = "MEDIUM"  
        final_score = base_score + 5
        tiebreak_reason = "High content + partial path match"
        
    elif content_score >= 8 and critical_path_score >= 3:
        # Medium content + good path = MEDIUM
        category = "MEDIUM"
        final_score = base_score + 3
        tiebreak_reason = "Medium content + critical path match"
        
    elif content_score >= 12:
        # High content but poor path = MEDIUM (content wins but penalized)
        category = "MEDIUM"
        tiebreak_reason = "High content but path mismatch - content wins"
        
    elif content_score >= 6 and critical_path_score >= 2:
        # Low content but good path = LOW
        category = "LOW" 
        tiebreak_reason = "Low content + decent path match"
        
    else:
        # Everything else ignored
        category = "IGNORE"
        tiebreak_reason = "Insufficient content and path relevance"
    
    print(f"[DEBUG] Method: {method_name}")
    print(f"[DEBUG] Content: {content_score}, Path: {path_score}, Critical Path: {critical_path_score}")
    print(f"[DEBUG] Final: {final_score}, Category: {category}, Reason: {tiebreak_reason}")
    
    return TieBreakingScore(
        content_score=content_score,
        path_score=path_score,
        service_match=service_match,
        operation_match=operation_match,
        account_type_match=account_type_match,
        final_score=final_score,
        category=category,
        tiebreak_reason=tiebreak_reason
    )

def resolve_content_conflicts(candidates: List[Tuple[str, TieBreakingScore]]) -> List[Tuple[str, TieBreakingScore]]:
    """Resolve conflicts when multiple methods have similar content scores"""
    
    if len(candidates) <= 1:
        return candidates
    
    print(f"[INFO] Resolving conflicts between {len(candidates)} similar methods")
    
    # Group by content score ranges
    high_content = [(sig, score) for sig, score in candidates if score.content_score >= 12]
    medium_content = [(sig, score) for sig, score in candidates if 8 <= score.content_score < 12]
    
    resolved = []
    
    # For high content methods, use path as primary tiebreaker
    if high_content:
        print(f"[INFO] {len(high_content)} methods with high content scores - using path as tiebreaker")
        
        # Sort by critical path matches first, then by path score
        high_content.sort(key=lambda x: (
            x[1].service_match + x[1].operation_match + x[1].account_type_match,  # Critical matches
            x[1].path_score,  # Path score
            x[1].content_score  # Content as final tiebreaker
        ), reverse=True)
        
        # Take top candidates from each path score tier
        best_path_score = high_content[0][1].path_score
        for sig, score in high_content:
            if score.path_score >= best_path_score - 2:  # Within 2 points of best
                resolved.append((sig, score))
        
    # For medium content methods, be more selective with path requirements
    if medium_content and len(resolved) < 5:  # Don't overcrowd
        medium_content.sort(key=lambda x: x[1].final_score, reverse=True)
        
        for sig, score in medium_content[:3]:  # Top 3 medium content
            if score.service_match and score.operation_match:  # Must have service+operation match
                resolved.append((sig, score))
    
    print(f"[INFO] Resolved to {len(resolved)} methods after conflict resolution")
    
    return resolved

# Example of the tiebreaking in action:
"""
CONFLICT RESOLUTION EXAMPLE:

Method A: validatePostalCode() in /request/party/add/PartyValidator.java
- Content: 15 points (field name + xpath matches)
- Path: 9 points (service=party✅, operation=add✅, direction=request✅)
- Critical path score: 4/4 
- Final: (15×2) + 9 + 10 = 49 → HIGH (perfect match bonus)

Method B: validatePostalCode() in /request/beneficiary/add/BeneficiaryValidator.java  
- Content: 15 points (same field name + xpath matches)
- Path: 5 points (service=beneficiary❌, operation=add✅, direction=request✅)
- Critical path score: 2/4 (missing service match)
- Final: (15×2) + 5 + 5 = 40 → MEDIUM (partial path match)

Method C: validatePostalCode() in /util/CommonValidator.java
- Content: 15 points (same field name + xpath matches)  
- Path: 0 points (no service/operation/direction matches)
- Critical path score: 0/4
- Final: (15×2) + 0 + 0 = 30 → MEDIUM (high content but path mismatch)

RESULT: Method A wins because path relevance acts as the tiebreaker when content is similar!
The path score becomes CRITICAL when multiple methods have similar content relevance.
"""

def enhanced_extract_with_conflict_resolution(
    src_dir: str,
    keywords: List[str], 
    mapping_file_path: str,
    field_metadata: Dict,
    max_depth: int = 2
) -> Dict[str, List[str]]:
    """Main extraction function with enhanced conflict resolution"""
    
    # Parse enhanced mapping info
    mapping_info = parse_enhanced_mapping_info(mapping_file_path)
    
    # ... existing file discovery and method parsing logic ...
    
    # Calculate enhanced scores for all methods
    scored_methods = {}
    
    for method_sig, method_info in all_methods.items():
        # Calculate content score (your existing logic)
        content_score = calculate_content_relevance(
            method_info.snippet, method_info.method_name, keywords, field_metadata
        )
        
        # Calculate enhanced path score
        path_score, match_flags = calculate_enhanced_path_score(
            method_info.file_path, mapping_info
        )
        
        # Calculate final tiebreaking score
        final_score = calculate_tiebreaking_score(
            content_score.total_content_score, path_score, match_flags, 
            mapping_info, method_info.method_name
        )
        
        scored_methods[method_sig] = final_score
    
    # Find candidates and resolve conflicts
    high_relevance = [(sig, score) for sig, score in scored_methods.items() if score.category == "HIGH"]
    medium_relevance = [(sig, score) for sig, score in scored_methods.items() if score.category == "MEDIUM"]
    
    # Resolve conflicts within each tier
    resolved_high = resolve_content_conflicts(high_relevance)
    resolved_medium = resolve_content_conflicts(medium_relevance)
    
    seed_methods = set([sig for sig, score in resolved_high + resolved_medium])
    
    print(f"[INFO] Final seed methods: {len(resolved_high)} HIGH + {len(resolved_medium)} MEDIUM")
    
    # Continue with your existing relationship tracing and result organization...
    
    return results
