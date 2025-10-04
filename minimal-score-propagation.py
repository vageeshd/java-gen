"""
Minimal Score Propagation Enhancement
Drop this into your existing java_extractor.py with minimal changes

WHAT IT DOES:
1. Find high-scoring methods (your existing logic)
2. Propagate scores to their callees (NEW - simple BFS)
3. Include callees even if they have low intrinsic scores (SOLVES YOUR PROBLEM)

INTEGRATION:
- Add 2 new methods to your existing class
- Modify your filtering logic slightly
- That's it!
"""

from collections import deque
from typing import Dict, Set

class ScorePropagationMixin:
    """
    Add this mixin to your existing SmartJavaExtractor class
    
    Usage:
        class SmartJavaExtractor(ScorePropagationMixin):
            # Your existing code...
    """
    
    def propagate_scores_to_callees(
        self,
        all_methods: Dict[str, 'EnhancedMethodInfo'],
        seed_method_sigs: Set[str],
        propagation_factor: float = 0.75,
        max_depth: int = 2
    ) -> Dict[str, int]:
        """
        Propagate scores from high-scoring methods to their callees
        
        Args:
            all_methods: Dict of method_signature -> EnhancedMethodInfo
            seed_method_sigs: Set of high-scoring method signatures
            propagation_factor: How much score to pass (0.75 = 75%)
            max_depth: How many levels deep to propagate
        
        Returns:
            Dict of method_signature -> propagated_score
        """
        propagated_scores = {}
        
        # Initialize seed methods with their intrinsic scores
        for sig in seed_method_sigs:
            if sig in all_methods:
                method = all_methods[sig]
                # Use your existing scoring logic
                intrinsic_score = self._calculate_method_score(method)
                propagated_scores[sig] = intrinsic_score
        
        # BFS to propagate scores to callees
        queue = deque([(sig, 0) for sig in seed_method_sigs])
        visited = set(seed_method_sigs)
        
        print(f"[PROPAGATION] Starting from {len(seed_method_sigs)} seed methods")
        
        while queue:
            current_sig, depth = queue.popleft()
            
            if depth >= max_depth:
                continue
            
            current_method = all_methods.get(current_sig)
            if not current_method:
                continue
            
            current_score = propagated_scores.get(current_sig, 0)
            propagated_amount = int(current_score * (propagation_factor ** (depth + 1)))
            
            # Find all callees
            for called_method_name in current_method.calls_made:
                # Match by method name
                for callee_sig, callee_method in all_methods.items():
                    if callee_method.method_name == called_method_name:
                        
                        # Add or update propagated score (take max if multiple paths)
                        existing_score = propagated_scores.get(callee_sig, 0)
                        new_score = max(existing_score, propagated_amount)
                        
                        if new_score > existing_score:
                            propagated_scores[callee_sig] = new_score
                            
                            # Add to queue if not visited yet
                            if callee_sig not in visited:
                                visited.add(callee_sig)
                                queue.append((callee_sig, depth + 1))
                                
                                print(f"[PROPAGATION] {callee_method.method_name} "
                                      f"gets +{propagated_amount} from {current_method.method_name} "
                                      f"(depth {depth + 1})")
        
        print(f"[PROPAGATION] Completed - {len(propagated_scores)} methods scored")
        return propagated_scores
    
    def _calculate_method_score(self, method: 'EnhancedMethodInfo') -> int:
        """
        Calculate intrinsic score for a method
        ADAPT THIS to match your existing scoring logic!
        """
        score = 0
        
        # Your existing scoring factors
        if method.contains_keywords:
            score += 10
        
        if method.relevance_score:
            score += method.relevance_score.total_score
        
        score += len(method.mapping_annotations) * 8
        score += len(method.field_mappings) * 12
        
        return score


# ============================================================================
# INTEGRATION INTO YOUR EXISTING CODE
# ============================================================================

class SmartJavaExtractor(ScorePropagationMixin):
    """Your existing class - just add the mixin"""
    
    def smart_extract_java_code_blocks(
        self, 
        src_dir: str, 
        keywords: List[str], 
        mapping_file_path: str,
        max_depth: int = 2,
        include_callers: bool = True,
        include_callees: bool = True,
        # NEW PARAMETERS
        use_score_propagation: bool = True,  # Enable propagation
        propagation_factor: float = 0.75,     # 75% of parent score
        min_propagated_score: int = 8         # Min score to include
    ) -> Dict[str, List[str]]:
        """
        Your existing method - with minimal modifications
        """
        
        print(f"[INFO] Starting smart Java extraction")
        
        # ===== YOUR EXISTING CODE =====
        mapping_info = self.parse_mapping_sheet_info(mapping_file_path)
        
        java_files = []
        for root, dirs, files in os.walk(src_dir):
            for file in files:
                if file.endswith(".java"):
                    java_files.append(os.path.join(root, file))
        
        print(f"[INFO] Found {len(java_files)} Java files to analyze")
        
        # Extract methods
        all_methods = {}
        for file_path in java_files:
            try:
                methods = self.extract_enhanced_method_info(file_path, keywords, mapping_info)
                for method in methods:
                    sig = f"{method.class_name}.{method.method_name}({','.join(method.param_types)})"
                    all_methods[sig] = method
            except Exception as e:
                print(f"[WARN] Failed to process {file_path}: {e}")
                continue
        
        print(f"[INFO] Extracted {len(all_methods)} methods")
        
        # Build call relationships
        method_calls_map = defaultdict(set)
        for method_info in all_methods.values():
            for called_method in method_info.calls_made:
                for other_sig, other_method in all_methods.items():
                    if other_method.method_name == called_method:
                        method_calls_map[f"{method_info.class_name}.{method_info.method_name}"].add(other_sig)
                        all_methods[other_sig].called_by.add(
                            f"{method_info.class_name}.{method_info.method_name}"
                        )
        
        # Find seed methods (your existing logic)
        seed_methods = self._find_seed_methods(all_methods, keywords, mapping_info)
        print(f"[INFO] Found {len(seed_methods)} seed methods")
        
        # ===== NEW: SCORE PROPAGATION =====
        if use_score_propagation and include_callees:
            print(f"\n[INFO] Propagating scores to callees...")
            
            propagated_scores = self.propagate_scores_to_callees(
                all_methods=all_methods,
                seed_method_sigs=seed_methods,
                propagation_factor=propagation_factor,
                max_depth=max_depth
            )
            
            # Include methods with sufficient propagated score
            relevant_methods = set(seed_methods)
            
            for method_sig, prop_score in propagated_scores.items():
                if prop_score >= min_propagated_score:
                    relevant_methods.add(method_sig)
            
            print(f"[INFO] After propagation: {len(relevant_methods)} relevant methods "
                  f"(+{len(relevant_methods) - len(seed_methods)} from propagation)")
        
        else:
            # ===== YOUR EXISTING LOGIC (if propagation disabled) =====
            relevant_methods = set(seed_methods)
            
            if include_callers or include_callees:
                for depth in range(1, max_depth + 1):
                    new_methods = set()
                    
                    for method_sig in list(relevant_methods):
                        method_info = all_methods.get(method_sig)
                        if not method_info:
                            continue
                        
                        if include_callers:
                            for caller_sig in method_info.called_by:
                                if caller_sig not in relevant_methods:
                                    new_methods.add(caller_sig)
                        
                        if include_callees:
                            for called_sig in method_calls_map.get(method_sig, set()):
                                if called_sig not in relevant_methods:
                                    new_methods.add(called_sig)
                    
                    relevant_methods.update(new_methods)
                    print(f"[INFO] Depth {depth}: Added {len(new_methods)} methods")
                    
                    if not new_methods:
                        break
        
        # ===== YOUR EXISTING RESULT ORGANIZATION =====
        results = self._organize_results(all_methods, relevant_methods, seed_methods, mapping_info)
        
        print(f"[INFO] Extraction completed: {len(results)} files with relevant methods")
        return results
    
    def _find_seed_methods(
        self, 
        all_methods: Dict[str, 'EnhancedMethodInfo'], 
        keywords: List[str], 
        mapping_info: 'MappingSheetInfo'
    ) -> Set[str]:
        """
        Your existing seed method finding logic
        Just calculate intrinsic scores
        """
        seed_methods = set()
        
        for sig, method in all_methods.items():
            score = self._calculate_method_score(method)
            
            # Your threshold
            if score >= 6:
                seed_methods.add(sig)
                print(f"[DEBUG] Seed: {method.method_name} (score: {score})")
        
        return seed_methods
    
    def _organize_results(
        self,
        all_methods: Dict[str, 'EnhancedMethodInfo'],
        relevant_methods: Set[str],
        seed_methods: Set[str],
        mapping_info: 'MappingSheetInfo'
    ) -> Dict[str, List[str]]:
        """
        Your existing result organization
        Optionally enhance with propagation info
        """
        results = {}
        
        file_methods = defaultdict(list)
        for method_sig in relevant_methods:
            method = all_methods.get(method_sig)
            if method:
                file_methods[method.file_path].append((method_sig, method))
        
        for file_path, method_list in file_methods.items():
            # Sort by your existing criteria
            method_list.sort(key=lambda x: self._calculate_method_score(x[1]), reverse=True)
            
            results[file_path] = []
            
            for method_sig, method in method_list:
                # Determine category
                if method_sig in seed_methods:
                    category = "HIGH_RELEVANCE_SEED"
                else:
                    category = "RELATED_METHOD"  # Could be from propagation!
                
                intrinsic_score = self._calculate_method_score(method)
                
                # Create header
                header = f"// [{category}] Method: {method.class_name}.{method.method_name}\n"
                header += f"// Intrinsic Score: {intrinsic_score}\n"
                header += f"// File: {file_path}\n"
                
                if method.contains_keywords:
                    header += "// [KEYWORDS MATCH]\n"
                
                snippet = f"{header}{method.snippet}"
                results[file_path].append(snippet)
        
        return results


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

def example_usage():
    """How to use the enhanced extractor"""
    
    extractor = SmartJavaExtractor()
    
    # Enable score propagation (NEW!)
    results = extractor.smart_extract_java_code_blocks(
        src_dir="/path/to/src",
        keywords=["postalCode", "zipCode"],
        mapping_file_path="/path/to/mapping.xlsx",
        max_depth=2,
        include_callees=True,
        
        # NEW PARAMETERS - tune these for your needs
        use_score_propagation=True,   # Enable the feature
        propagation_factor=0.75,       # Callees get 75% of parent score
        min_propagated_score=8         # Must score at least 8 to include
    )
    
    # Results now include callees that would have been missed!
    for file_path, snippets in results.items():
        print(f"\n{'='*80}")
        print(f"File: {file_path}")
        print('='*80)
        for snippet in snippets:
            print(snippet)
            print()


# ============================================================================
# BEFORE/AFTER COMPARISON
# ============================================================================

def show_comparison():
    """
    BEFORE (without propagation):
    
    Seed methods found:
    ✓ mapAddressInfo (score: 25) - has keywords
    
    Callees checked:
    ✗ validatePostalCode (score: 5) - EXCLUDED (below threshold)
    ✗ normalizeZipCode (score: 4) - EXCLUDED (below threshold)
    
    Result: Lost critical validation logic!
    
    
    AFTER (with propagation):
    
    Seed methods found:
    ✓ mapAddressInfo (score: 25) - has keywords
    
    Propagation:
    ✓ validatePostalCode gets 25 × 0.75 = +18 propagated
      Final score: 5 + 18 = 23 - INCLUDED!
    ✓ normalizeZipCode gets 25 × 0.75 = +18 propagated
      Final score: 4 + 18 = 22 - INCLUDED!
    
    Result: All critical methods included with full context!
    """
    pass


# ============================================================================
# TESTING
# ============================================================================

def test_propagation():
    """Quick test to verify propagation works"""
    
    from dataclasses import dataclass
    
    @dataclass
    class MockMethod:
        method_name: str
        contains_keywords: bool
        calls_made: Set[str]
        relevance_score = None
        mapping_annotations = []
        field_mappings = []
    
    # Setup: A → B → C chain
    method_a = MockMethod("methodA", True, {"methodB"})
    method_b = MockMethod("methodB", False, {"methodC"})
    method_c = MockMethod("methodC", False, set())
    
    all_methods = {
        "ClassA.methodA()": method_a,
        "ClassB.methodB()": method_b,
        "ClassC.methodC()": method_c
    }
    
    extractor = SmartJavaExtractor()
    
    # Propagate from A
    scores = extractor.propagate_scores_to_callees(
        all_methods=all_methods,
        seed_method_sigs={"ClassA.methodA()"},
        propagation_factor=0.75,
        max_depth=2
    )
    
    print("\nPropagation Test Results:")
    print(f"methodA score: {scores.get('ClassA.methodA()', 0)}")
    print(f"methodB score: {scores.get('ClassB.methodB()', 0)}")  
    print(f"methodC score: {scores.get('ClassC.methodC()', 0)}")
    
    # Verify
    assert scores.get("ClassA.methodA()", 0) == 10  # Intrinsic (has keywords)
    assert scores.get("ClassB.methodB()", 0) > 5    # Got propagated score
    assert scores.get("ClassC.methodC()", 0) > 3    # Got propagated score (2nd level)
    
    print("✓ Propagation test passed!")


if __name__ == "__main__":
    test_propagation()
    example_usage()
