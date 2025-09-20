# Enhanced core/java_extractor.py with smart operation and account type matching

import os
import re
from typing import Dict, List, Set, Tuple, Optional, NamedTuple
import javalang
from dataclasses import dataclass
from collections import defaultdict
from pathlib import Path

class MappingSheetInfo(NamedTuple):
    """Parsed information from mapping sheet filename"""
    operation: str  # add, inq, mod, del
    account_type: Optional[str]  # cda, dda, ddl, sdb, sda, loan, inet
    direction: str  # request, response (inferred from operation)
    raw_filename: str

class PathRelevanceScore(NamedTuple):
    """Relevance scoring for file paths"""
    operation_match: int  # 0-3 (exact, partial, inferred, none)
    account_type_match: int  # 0-2 (exact, none, n/a)
    direction_match: int  # 0-2 (exact, inferred, none)
    structure_match: int  # 0-3 (standard, mapper, processor, other)
    total_score: int

@dataclass
class EnhancedMethodInfo:
    """Enhanced method information with relevance scoring"""
    file_path: str
    method_name: str
    class_name: str
    package_name: str
    param_types: Tuple[str, ...]
    start_line: int
    end_line: int
    snippet: str
    calls_made: Set[str]
    called_by: Set[str]
    contains_keywords: bool
    # Enhanced attributes
    relevance_score: PathRelevanceScore
    mapping_annotations: List[str]  # @Mapping annotations found
    field_mappings: List[str]  # mapFieldName methods found
    backend_xpath_matches: List[str]  # backend xpath segments found

class SmartJavaExtractor:
    """Enhanced Java extractor with domain intelligence"""
    
    def __init__(self):
        self.operations = {'add', 'inq', 'mod', 'del'}
        self.account_types = {'cda', 'dda', 'ddl', 'sdb', 'sda', 'loan', 'inet'}
        self.mapping_annotations = ['@Mapping', '@AfterMapping', '@BeforeMapping']
        
    def parse_mapping_sheet_info(self, mapping_file_path: str) -> MappingSheetInfo:
        """Parse operation and account type from mapping sheet filename"""
        
        filename = os.path.basename(mapping_file_path).lower()
        print(f"[INFO] Parsing mapping sheet: {filename}")
        
        # Extract operation (add, inq, mod, del)
        operation = None
        for op in self.operations:
            if op in filename:
                operation = op
                break
        
        if not operation:
            print(f"[WARN] Could not determine operation from filename: {filename}")
            operation = "unknown"
        
        # Extract account type (cda, dda, etc.) - optional
        account_type = None
        for acc_type in self.account_types:
            if acc_type in filename:
                account_type = acc_type
                break
        
        # Infer direction from operation
        if operation == 'inq':
            direction = 'response'  # inquiries typically return response data
        else:
            direction = 'request'   # add/mod/del typically process request data
        
        result = MappingSheetInfo(
            operation=operation,
            account_type=account_type,
            direction=direction,
            raw_filename=filename
        )
        
        print(f"[INFO] Parsed: operation={operation}, account_type={account_type}, direction={direction}")
        return result
    
    def calculate_path_relevance(self, file_path: str, mapping_info: MappingSheetInfo) -> PathRelevanceScore:
        """Calculate relevance score for a file path based on mapping info"""
        
        path_lower = file_path.lower()
        path_parts = Path(path_lower).parts
        
        # Operation matching (0-3 points)
        operation_score = 0
        if mapping_info.operation in path_lower:
            operation_score = 3  # Exact match
        elif any(op in path_lower for op in self.operations if op != mapping_info.operation):
            operation_score = 1  # Different operation present
        elif mapping_info.direction in path_lower:
            operation_score = 2  # Direction match (inferred)
        
        # Account type matching (0-2 points)
        account_type_score = 0
        if mapping_info.account_type:
            if mapping_info.account_type in path_lower:
                account_type_score = 2  # Exact match
            # Check for account type variations or groupings
            elif 'all' in path_lower or 'common' in path_lower:
                account_type_score = 1  # Generic account type folder
        else:
            account_type_score = 2  # N/A - no penalty if no account type specified
        
        # Direction matching (0-2 points)  
        direction_score = 0
        if mapping_info.direction in path_lower:
            direction_score = 2  # Exact match
        elif ('request' in path_lower and mapping_info.direction == 'response') or \
             ('response' in path_lower and mapping_info.direction == 'request'):
            direction_score = 0  # Wrong direction
        else:
            direction_score = 1  # No clear direction indication
        
        # Structure pattern matching (0-3 points)
        structure_score = 0
        if self._matches_standard_structure(path_parts, mapping_info):
            structure_score = 3  # Standard request/response > operation > accttype
        elif self._matches_mapper_structure(path_parts, mapping_info):
            structure_score = 2  # Mapper > request/response > operation
        elif any(pattern in path_lower for pattern in ['processor', 'controller', 'service']):
            structure_score = 1  # Processor/Controller pattern
        
        total = operation_score + account_type_score + direction_score + structure_score
        
        return PathRelevanceScore(
            operation_match=operation_score,
            account_type_match=account_type_score,
            direction_match=direction_score,
            structure_match=structure_score,
            total_score=total
        )
    
    def _matches_standard_structure(self, path_parts: Tuple[str, ...], mapping_info: MappingSheetInfo) -> bool:
        """Check if path matches standard request/response > operation > accttype structure"""
        path_str = '/'.join(path_parts)
        
        # Look for patterns like: .../request/add/cda/... or .../response/inq/sda/...
        patterns = [
            f"{mapping_info.direction}.*{mapping_info.operation}",
            f"{mapping_info.operation}.*{mapping_info.account_type}" if mapping_info.account_type else f"{mapping_info.operation}"
        ]
        
        return any(re.search(pattern, path_str) for pattern in patterns)
    
    def _matches_mapper_structure(self, path_parts: Tuple[str, ...], mapping_info: MappingSheetInfo) -> bool:
        """Check if path matches mapper > request/response > operation structure"""
        path_str = '/'.join(path_parts)
        
        if 'mapper' not in path_str:
            return False
        
        # Look for patterns like: .../mapper/request/add/... or .../mapper/response/inq/...
        patterns = [
            f"mapper.*{mapping_info.direction}.*{mapping_info.operation}",
            f"mapper.*{mapping_info.operation}.*{mapping_info.direction}"
        ]
        
        return any(re.search(pattern, path_str) for pattern in patterns)
    
    def extract_enhanced_method_info(self, file_path: str, keywords: List[str], mapping_info: MappingSheetInfo) -> List[EnhancedMethodInfo]:
        """Extract enhanced method information with relevance scoring"""
        
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
        
        # Calculate path relevance once for the entire file
        path_relevance = self.calculate_path_relevance(file_path, mapping_info)
        
        # Extract package name
        package_name = ""
        if tree.package:
            package_name = tree.package.name
        
        # Find class names
        class_names = []
        for path, node in tree.filter(javalang.tree.ClassDeclaration):
            class_names.append(node.name)
        
        if not class_names:
            class_names = [os.path.splitext(os.path.basename(file_path))[0]]
        
        # Extract methods with enhanced analysis
        for path, node in tree.filter(javalang.tree.MethodDeclaration):
            if not hasattr(node, 'position') or node.position is None:
                continue
            
            # Find the class this method belongs to
            class_name = class_names[0]
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
            end_line = self._find_method_end(code_lines, start_line)
            
            snippet = "\n".join(code_lines[start_line:end_line + 1])
            
            # Enhanced analysis
            contains_keywords = self._contains_relevant_keywords(snippet, keywords)
            calls_made = self._extract_method_calls(snippet)
            mapping_annotations = self._extract_mapping_annotations(snippet)
            field_mappings = self._extract_field_mappings(snippet, keywords)
            backend_xpath_matches = self._extract_backend_xpath_matches(snippet, mapping_info)
            
            method_info = EnhancedMethodInfo(
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
                contains_keywords=contains_keywords,
                relevance_score=path_relevance,
                mapping_annotations=mapping_annotations,
                field_mappings=field_mappings,
                backend_xpath_matches=backend_xpath_matches
            )
            
            methods.append(method_info)
        
        return methods
    
    def _extract_mapping_annotations(self, snippet: str) -> List[str]:
        """Extract MapStruct @Mapping annotations"""
        annotations = []
        
        for line in snippet.split('\n'):
            line = line.strip()
            if line.startswith('@Mapping'):
                annotations.append(line)
            elif line.startswith('@AfterMapping') or line.startswith('@BeforeMapping'):
                annotations.append(line)
        
        return annotations
    
    def _extract_field_mappings(self, snippet: str, keywords: List[str]) -> List[str]:
        """Extract mapFieldName methods that match our keywords"""
        field_mappings = []
        
        for keyword in keywords:
            # Look for method names like mapPostalCode, mapFieldPostalCode, etc.
            patterns = [
                f'map{keyword}',
                f'map.*{keyword}',
                f'{keyword.lower()}.*map'
            ]
            
            for pattern in patterns:
                if re.search(pattern, snippet, re.IGNORECASE):
                    # Extract the actual method name
                    matches = re.findall(r'(map\w*' + keyword + r'\w*)\s*\(', snippet, re.IGNORECASE)
                    field_mappings.extend(matches)
        
        return list(set(field_mappings))  # Remove duplicates
    
    def _extract_backend_xpath_matches(self, snippet: str, mapping_info: MappingSheetInfo) -> List[str]:
        """Extract backend xpath segments found in the code"""
        matches = []
        
        # Look for common backend xpath patterns in the code
        xpath_patterns = [
            r'["\']([A-Za-z0-9_/]+)["\']',  # Quoted strings that might be xpaths
            r'\.([A-Za-z0-9_]+)',  # Property access patterns
            r'get([A-Za-z0-9_]+)\(\)',  # Getter method calls
            r'set([A-Za-z0-9_]+)\('  # Setter method calls
        ]
        
        for pattern in xpath_patterns:
            found_matches = re.findall(pattern, snippet)
            matches.extend(found_matches)
        
        # Filter matches that might be relevant to backend processing
        backend_matches = []
        for match in matches:
            if len(match) > 2 and any(char.isalpha() for char in match):
                backend_matches.append(match)
        
        return list(set(backend_matches))
    
    def smart_extract_java_code_blocks(
        self, 
        src_dir: str, 
        keywords: List[str], 
        mapping_file_path: str,
        max_depth: int = 2,
        include_callers: bool = True,
        include_callees: bool = True
    ) -> Dict[str, List[str]]:
        """
        Smart extraction using mapping sheet information and domain knowledge
        """
        
        print(f"[INFO] Starting smart Java extraction")
        
        # Parse mapping sheet information
        mapping_info = self.parse_mapping_sheet_info(mapping_file_path)
        
        # Find all Java files
        java_files = []
        for root, dirs, files in os.walk(src_dir):
            for file in files:
                if file.endswith(".java"):
                    java_files.append(os.path.join(root, file))
        
        print(f"[INFO] Found {len(java_files)} Java files to analyze")
        
        # Extract enhanced method information from all files
        all_methods = {}  # signature -> EnhancedMethodInfo
        file_to_methods = defaultdict(list)
        
        for file_path in java_files:
            try:
                methods = self.extract_enhanced_method_info(file_path, keywords, mapping_info)
                for method in methods:
                    sig = f"{method.class_name}.{method.method_name}({','.join(method.param_types)})"
                    all_methods[sig] = method
                    file_to_methods[file_path].append(sig)
            except Exception as e:
                print(f"[WARN] Failed to process {file_path}: {e}")
                continue
        
        print(f"[INFO] Extracted {len(all_methods)} methods with enhanced analysis")
        
        # Build call relationships (same as before)
        method_calls_map = defaultdict(set)
        for method_info in all_methods.values():
            for called_method in method_info.calls_made:
                for other_sig, other_method in all_methods.items():
                    if other_method.method_name == called_method:
                        method_calls_map[f"{method_info.class_name}.{method_info.method_name}({','.join(method_info.param_types)})"].add(other_sig)
                        all_methods[other_sig].called_by.add(f"{method_info.class_name}.{method_info.method_name}({','.join(method_info.param_types)})")
        
        # Find seed methods using enhanced criteria
        seed_methods = self._find_smart_seed_methods(all_methods, keywords, mapping_info)
        print(f"[INFO] Found {len(seed_methods)} high-relevance seed methods")
        
        # Trace relationships (same logic as before but with relevance-based selection)
        relevant_methods = set(seed_methods)
        
        if include_callers or include_callees:
            for depth in range(1, max_depth + 1):
                new_methods = set()
                
                for method_sig in list(relevant_methods):
                    method_info = all_methods.get(method_sig)
                    if not method_info:
                        continue
                    
                    # Add callers (with relevance filtering)
                    if include_callers:
                        for caller_sig in method_info.called_by:
                            caller_method = all_methods.get(caller_sig)
                            if (caller_sig not in relevant_methods and 
                                caller_method and 
                                caller_method.relevance_score.total_score >= 3):  # Relevance threshold
                                new_methods.add(caller_sig)
                    
                    # Add callees (with relevance filtering)
                    if include_callees:
                        for called_sig in method_calls_map.get(method_sig, set()):
                            called_method = all_methods.get(called_sig)
                            if (called_sig not in relevant_methods and 
                                called_method and 
                                called_method.relevance_score.total_score >= 3):  # Relevance threshold
                                new_methods.add(called_sig)
                
                relevant_methods.update(new_methods)
                print(f"[INFO] Depth {depth}: Added {len(new_methods)} relevant methods")
                
                if not new_methods:
                    break
        
        # Organize results with enhanced categorization
        results = self._organize_smart_results(all_methods, relevant_methods, seed_methods, mapping_info)
        
        print(f"[INFO] Smart extraction completed: {len(results)} files with relevant methods")
        return results
    
    def _find_smart_seed_methods(self, all_methods: Dict[str, EnhancedMethodInfo], 
                                keywords: List[str], mapping_info: MappingSheetInfo) -> Set[str]:
        """Find seed methods using enhanced relevance criteria"""
        
        seed_methods = set()
        
        for sig, method in all_methods.items():
            score = 0
            
            # Keyword matching (1-3 points)
            if method.contains_keywords:
                score += 3
            
            # Path relevance (use total score from path analysis)
            score += method.relevance_score.total_score
            
            # MapStruct annotations (2 points each)
            score += len(method.mapping_annotations) * 2
            
            # Field mapping methods (3 points each)
            score += len(method.field_mappings) * 3
            
            # Backend xpath matches (1 point each)
            score += len(method.backend_xpath_matches)
            
            # Set threshold for seed methods
            if score >= 6:  # Adjust threshold as needed
                seed_methods.add(sig)
                print(f"[DEBUG] Seed method: {method.method_name} (score: {score})")
        
        return seed_methods
    
    def _organize_smart_results(self, all_methods: Dict[str, EnhancedMethodInfo], 
                               relevant_methods: Set[str], seed_methods: Set[str],
                               mapping_info: MappingSheetInfo) -> Dict[str, List[str]]:
        """Organize results with smart categorization and relevance-based ordering"""
        
        results = {}
        
        # Group methods by file and sort by relevance
        file_methods = defaultdict(list)
        for method_sig in relevant_methods:
            method = all_methods.get(method_sig)
            if method:
                file_methods[method.file_path].append((method_sig, method))
        
        # Process each file
        for file_path, method_list in file_methods.items():
            # Sort by relevance score (highest first)
            method_list.sort(key=lambda x: x[1].relevance_score.total_score, reverse=True)
            
            results[file_path] = []
            
            for method_sig, method in method_list:
                # Determine category with enhanced logic
                category = self._categorize_method(method, method_sig, seed_methods, mapping_info)
                
                # Create enhanced annotation
                header = f"// [{category}] Method: {method.get_qualified_name()}"
                header += f" [Relevance: {method.relevance_score.total_score}]"
                
                if method.contains_keywords:
                    header += " [KEYWORDS]"
                
                if method.mapping_annotations:
                    header += f" [MAPPINGS: {len(method.mapping_annotations)}]"
                
                if method.field_mappings:
                    header += f" [FIELD_MAPS: {', '.join(method.field_mappings)}]"
                
                # Enhanced snippet with metadata
                enhanced_snippet = f"{header}\n"
                enhanced_snippet += f"// File: {file_path}\n"
                enhanced_snippet += f"// Path Relevance: Op={method.relevance_score.operation_match}, "
                enhanced_snippet += f"AccType={method.relevance_score.account_type_match}, "
                enhanced_snippet += f"Dir={method.relevance_score.direction_match}, "
                enhanced_snippet += f"Structure={method.relevance_score.structure_match}\n"
                
                if method.mapping_annotations:
                    enhanced_snippet += f"// Mapping Annotations: {method.mapping_annotations}\n"
                
                enhanced_snippet += method.snippet
                
                results[file_path].append(enhanced_snippet)
        
        return results
    
    def _categorize_method(self, method: EnhancedMethodInfo, method_sig: str, 
                          seed_methods: Set[str], mapping_info: MappingSheetInfo) -> str:
        """Categorize method based on enhanced criteria"""
        
        if method_sig in seed_methods:
            return "HIGH_RELEVANCE_SEED"
        
        if method.mapping_annotations:
            return "MAPSTRUCT_METHOD"
        
        if method.field_mappings:
            return "FIELD_MAPPER"
        
        if method.relevance_score.total_score >= 8:
            return "HIGH_RELEVANCE_RELATED"
        elif method.relevance_score.total_score >= 5:
            return "MEDIUM_RELEVANCE_RELATED"
        else:
            return "LOW_RELEVANCE_RELATED"
    
    # Helper methods (same implementations as before)
    def _find_method_end(self, code_lines: List[str], start_line: int) -> int:
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
    
    def _extract_method_calls(self, snippet: str) -> Set[str]:
        """Extract method calls from a code snippet."""
        calls = set()
        
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
    
    def _contains_relevant_keywords(self, snippet: str, keywords: List[str]) -> bool:
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
    
    def get_qualified_name(self) -> str:
        """Get fully qualified method name"""
        package_prefix = f"{self.package_name}." if self.package_name else ""
        return f"{package_prefix}{self.class_name}.{self.method_name}"

# Add to EnhancedMethodInfo class
EnhancedMethodInfo.get_qualified_name = get_qualified_name

def smart_trim_code_context(snippets_by_file: Dict[str, List[str]], 
                           mapping_info: MappingSheetInfo, max_chars: int = 3000) -> str:
    """Smart context trimming based on relevance scores and mapping information"""
    
    if not snippets_by_file:
        return ""
    
    ranked_snippets = []
    
    for file_path, snippets in snippets_by_file.items():
        for snippet in snippets:
            priority = 5  # Default priority
            
            # Parse relevance score from snippet header
            relevance_match = re.search(r'\[Relevance: (\d+)\]', snippet)
            if relevance_match:
                relevance_score = int(relevance_match.group(1))
                priority = max(1, 6 - (relevance_score // 2))  # Higher relevance = lower priority number
            
            # Boost priority for specific patterns
            snippet_lower = snippet.lower()
            
            if 'HIGH_RELEVANCE_SEED' in snippet:
                priority = 1
            elif 'MAPSTRUCT_METHOD' in snippet or 'FIELD_MAPPER' in snippet:
                priority = 2
            elif any(annotation in snippet for annotation in ['@Mapping', '@AfterMapping']):
                priority = 2
            elif f'[{mapping_info.operation}]' in snippet_lower:
                priority = min(priority, 3)
            elif mapping_info.account_type and mapping_info.account_type in snippet_lower:
                priority = min(priority, 3)
            
            ranked_snippets.append((priority, file_path, snippet))
    
    # Sort by priority (1 = highest priority)
    ranked_snippets.sort(key=lambda x: x[0])
    
    # Build context within limits
    final_context = []
    total_len = 0
    included_count = 0
    
    for priority, file_path, snippet in ranked_snippets:
        chunk = f"\n{'-'*50}\n{snippet}\n{'-'*50}\n"
        
        if total_len + len(chunk) > max_chars:
            break
        
        final_context.append(chunk)
        total_len += len(chunk)
        included_count += 1
    
    context_str = "".join(final_context)
    
    print(f"[INFO] Smart context: included {included_count}/{len(ranked_snippets)} methods ({total_len} chars)")
    print(f"[INFO] Mapping context: {mapping_info.operation}/{mapping_info.account_type or 'generic'}/{mapping_info.direction}")
    
    return context_str

# Wrapper functions for backward compatibility
def extract_java_code_blocks_with_cross_references(
    src_dir: str, 
    keywords: List[str], 
    max_depth: int = 2,
    include_callers: bool = True,
    include_callees: bool = True,
    mapping_file_path: str = None
) -> Dict[str, List[str]]:
    """
    Enhanced wrapper function that uses smart extraction when mapping file is provided
    """
    
    extractor = SmartJavaExtractor()
    
    if mapping_file_path and os.path.exists(mapping_file_path):
        print("[INFO] Using smart extraction with mapping sheet analysis")
        return extractor.smart_extract_java_code_blocks(
            src_dir, keywords, mapping_file_path, max_depth, include_callers, include_callees
        )
    else:
        print("[INFO] Using basic extraction (no mapping sheet provided)")
        # Fall back to basic extraction logic (your original implementation)
        # ... existing implementation
        return {}

def trim_code_context(snippets_by_file: Dict[str, List[str]], max_chars: int = 2500,
                     mapping_file_path: str = None) -> str:
    """
    Enhanced wrapper for context trimming
    """
    
    if mapping_file_path and os.path.exists(mapping_file_path):
        extractor = SmartJavaExtractor()
        mapping_info = extractor.parse_mapping_sheet_info(mapping_file_path)
        return smart_trim_code_context(snippets_by_file, mapping_info, max_chars)
    else:
        # Fall back to basic trimming (your original implementation)
        # ... existing implementation  
        return ""
