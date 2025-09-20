def extract_java_code_blocks_with_cross_references(
    src_dir: str, 
    keywords: List[str], 
    max_depth: int = 2,
    include_callers: bool = True,
    include_callees: bool = True,
    mapping_file_path: str = None,        # NEW parameter
    field_metadata: Dict = None           # NEW parameter
) -> Dict[str, List[str]]:
    """
    Enhanced extraction with smart relevance scoring when mapping info is available.
    Falls back to basic extraction when mapping file is not provided.
    """
    
    print(f"[INFO] Starting enhanced Java extraction with max_depth={max_depth}")
    
    # Initialize smart extraction components
    mapping_info = None
    enhanced_methods = {}
    
    if mapping_file_path and os.path.exists(mapping_file_path) and field_metadata:
        try:
            mapping_info = parse_enhanced_mapping_info(mapping_file_path)
            print(f"[INFO] Using smart extraction with mapping analysis")
        except Exception as e:
            print(f"[WARN] Smart extraction failed, using basic mode: {e}")
            mapping_info = None
    else:
        print(f"[INFO] Using basic extraction (no mapping info provided)")
    
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
    
    # Parse all files with enhanced scoring
    for file_path in java_files:
        try:
            methods = parse_java_file(file_path, keywords)
            for method in methods:
                sig = method.get_full_signature()
                all_methods[sig] = method
                file_to_methods[file_path].append(sig)
                
                # Add enhanced relevance scoring if smart extraction is enabled
                if mapping_info and field_metadata:
                    try:
                        content_score = calculate_content_relevance(
                            method.snippet, method.method_name, keywords, field_metadata
                        )
                        path_score, match_flags = calculate_enhanced_path_score(file_path, mapping_info)
                        combined_score = calculate_tiebreaking_score(
                            content_score.total_content_score, path_score, match_flags, 
                            mapping_info, method.method_name
                        )
                        enhanced_methods[sig] = combined_score
                    except Exception as e:
                        print(f"[WARN] Scoring failed for {method.method_name}: {e}")
                        
        except Exception as e:
            print(f"[WARN] Failed to parse {file_path}: {e}")
            continue
    
    print(f"[INFO] Parsed {len(all_methods)} total methods")
    if enhanced_methods:
        print(f"[INFO] Applied smart scoring to {len(enhanced_methods)} methods")
    
    # Phase 2: Build call relationships
    for method_info in all_methods.values():
        for called_method in method_info.calls_made:
            # Find matching methods by name (simple matching)
            for other_sig, other_method in all_methods.items():
                if other_method.method_name == called_method:
                    method_calls_map[method_info.get_full_signature()].add(other_sig)
                    all_methods[other_sig].called_by.add(method_info.get_full_signature())
    
    # Phase 3: Find seed methods using enhanced criteria or fallback to basic
    seed_methods = set()
    
    if enhanced_methods:
        # Use smart scoring to find seed methods
        high_relevance = []
        medium_relevance = []
        
        for sig, combined_score in enhanced_methods.items():
            if combined_score.category == "HIGH":
                high_relevance.append((sig, combined_score))
            elif combined_score.category == "MEDIUM":
                medium_relevance.append((sig, combined_score))
        
        # Resolve conflicts if multiple high-relevance methods exist
        if len(high_relevance) > 10:  # Too many high-relevance methods
            resolved_high = resolve_content_conflicts(high_relevance)
            seed_methods.update([sig for sig, score in resolved_high])
        else:
            seed_methods.update([sig for sig, score in high_relevance])
        
        # Add some medium relevance methods if we don't have enough seeds
        if len(seed_methods) < 5 and medium_relevance:
            medium_relevance.sort(key=lambda x: x[1].total_score, reverse=True)
            additional_seeds = [sig for sig, score in medium_relevance[:5]]
            seed_methods.update(additional_seeds)
        
        print(f"[INFO] Smart seed selection: {len(seed_methods)} high-relevance methods")
        for sig in list(seed_methods)[:5]:  # Show first 5
            if sig in enhanced_methods:
                score = enhanced_methods[sig]
                method_name = all_methods[sig].method_name
                print(f"[DEBUG] {score.category} seed: {method_name} (score: {score.total_score})")
    else:
        # Fallback to basic keyword-based seed selection
        for method_info in all_methods.values():
            if method_info.contains_keywords:
                seed_methods.add(method_info.get_full_signature())
        
        print(f"[INFO] Basic seed selection: {len(seed_methods)} keyword-containing methods")
    
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
                            # Apply relevance filtering if smart extraction is enabled
                            if enhanced_methods and caller_sig in enhanced_methods:
                                caller_score = enhanced_methods[caller_sig]
                                if caller_score.category != "IGNORE":  # Only include relevant callers
                                    new_methods.add(caller_sig)
                            else:
                                new_methods.add(caller_sig)  # Basic mode - include all
                
                # Add callees (methods called by this method)
                if include_callees:
                    for called_sig in method_calls_map.get(method_sig, set()):
                        if called_sig not in relevant_methods:
                            # Apply relevance filtering if smart extraction is enabled
                            if enhanced_methods and called_sig in enhanced_methods:
                                called_score = enhanced_methods[called_sig]
                                if called_score.category != "IGNORE":  # Only include relevant callees
                                    new_methods.add(called_sig)
                            else:
                                new_methods.add(called_sig)  # Basic mode - include all
            
            relevant_methods.update(new_methods)
            print(f"[INFO] Depth {depth}: Added {len(new_methods)} related methods")
            
            if not new_methods:  # No new methods found, can stop early
                break
    
    print(f"[INFO] Total relevant methods after tracing: {len(relevant_methods)}")
    
    # Phase 5: Organize results by file with enhanced annotations
    results = {}
    method_categories = {
        'HIGH': [],
        'MEDIUM': [],
        'LOW': [],
        'BASIC_SEED': [],
        'BASIC_RELATED': []
    }
    
    for method_sig in relevant_methods:
        method_info = all_methods.get(method_sig)
        if not method_info:
            continue
        
        file_path = method_info.file_path
        if file_path not in results:
            results[file_path] = []
        
        # Determine category and create enhanced annotation
        if method_sig in enhanced_methods:
            # Smart extraction mode - use relevance scoring
            score = enhanced_methods[method_sig]
            category = score.category
            
            header = f"// [{category}] Method: {method_info.get_qualified_name()}"
            header += f" [Score: {score.total_score}]"
            
            # Add specific match information
            if score.content_score.field_name_matches > 0:
                header += " [FIELD_NAME_MATCH]"
            if score.content_score.mapping_annotations > 0:
                header += " [MAPSTRUCT]"
            if score.content_score.backend_xpath_matches > 0:
                header += " [XPATH_MATCH]"
            
            # Add path relevance details
            if mapping_info:
                path_details = f"[Path: {score.path_score.operation_match + score.path_score.account_type_match + score.path_score.direction_match + score.path_score.structure_match}/8]"
                header += f" {path_details}"
            
            method_categories[category].append(method_sig)
        else:
            # Basic extraction mode - use simple categorization
            if method_sig in seed_methods:
                category = "BASIC_SEED"
                header = f"// [SEED] Method: {method_info.get_qualified_name()}"
                if method_info.contains_keywords:
                    header += " [CONTAINS KEYWORDS]"
            else:
                category = "BASIC_RELATED"
                # Determine relationship type
                is_caller = any(seed_sig in method_info.calls_made for seed_sig in seed_methods if seed_sig in all_methods)
                is_callee = any(method_sig in method_calls_map.get(seed_sig, set()) for seed_sig in seed_methods)
                
                if is_caller and is_callee:
                    relationship = "CALLER_AND_CALLEE"
                elif is_caller:
                    relationship = "CALLS_SEED_METHOD"
                elif is_callee:
                    relationship = "CALLED_BY_SEED"
                else:
                    relationship = "INDIRECTLY_RELATED"
                
                header = f"// [{relationship}] Method: {method_info.get_qualified_name()}"
            
            method_categories[category].append(method_sig)
        
        # Create enhanced snippet with metadata
        enhanced_snippet = f"{header}\n"
        enhanced_snippet += f"// File: {file_path}\n"
        
        if enhanced_methods and method_sig in enhanced_methods:
            score = enhanced_methods[method_sig]
            enhanced_snippet += f"// Content Score: {score.content_score.total_content_score} "
            enhanced_snippet += f"(Field:{score.content_score.field_name_matches}, "
            enhanced_snippet += f"XPath:{score.content_score.backend_xpath_matches}, "
            enhanced_snippet += f"Mapping:{score.content_score.mapping_annotations})\n"
        
        enhanced_snippet += method_info.snippet
        
        results[file_path].append(enhanced_snippet)
    
    # Print summary of categorization
    total_methods = sum(len(methods) for methods in method_categories.values())
    print(f"\n[INFO] Method categorization summary:")
    for category, methods in method_categories.items():
        if methods:
            print(f"  {category}: {len(methods)} methods")
    
    print(f"[INFO] Enhanced extraction completed: {len(results)} files with {total_methods} relevant methods")
    
    return results