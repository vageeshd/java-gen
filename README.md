# core/test_objective_core.py
import hashlib
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple

from core.java_extractor import extract_java_code_blocks_with_cross_references, trim_code_context

class TestObjectiveGeneratorCore:
    def __init__(self, client, test_manager, src_dir: str):
        self.client = client
        self.test_manager = test_manager
        self.src_dir = src_dir
        self.failed_fields = []  # Track failed fields for reporting

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]

    def _validate_field_data(self, field: dict) -> Tuple[bool, str]:
        """Validate field has minimum required data"""
        required_fields = ['field_name']
        
        for req_field in required_fields:
            if not field.get(req_field):
                return False, f"Missing required field: {req_field}"
        
        # Check for reasonable field name
        field_name = field.get('field_name', '').strip()
        if len(field_name) < 2:
            return False, f"Field name too short: '{field_name}'"
        
        # Validate backend_xpath if present
        backend_xpath = field.get('backend_xpath', '')
        if backend_xpath and not backend_xpath.replace('/', '').replace('_', '').replace('-', '').isalnum():
            return False, f"Invalid backend_xpath format: '{backend_xpath}'"
        
        return True, "Valid"

    def _format_fiservai_prompt(self, fields: List[dict], code_contexts: Dict[str, str]) -> str:
        """Format prompt for FiservAI's CONTEXT/QUESTION format"""
        
        # Build CONTEXT section
        context = """You are an expert QA test objectives generator for ESF APIs.

FIELD INFORMATION AND CODE CONTEXT:
"""
        
        for field in fields:
            fid = field.get("backend_xpath") or field.get("field_name", "unknown")
            fid_short = f"{field.get('field_name','F')}_{self._hash_text(fid)}"
            
            context += f"\n--- FIELD: {field.get('field_name', 'Unknown')} ---\n"
            for k, v in field.items():
                if v:  # Only include non-empty values
                    context += f"{k}: {v}\n"
            
            ctx = code_contexts.get(fid_short, "")
            if ctx:
                context += f"\nJAVA CODE CONTEXT:\n{ctx}\n"
            else:
                context += "\nNO JAVA CODE FOUND FOR THIS FIELD\n"
        
        # Build QUESTION section
        question = """Generate test cases in EXACTLY this format - 9 tab-separated columns:

Category | Test Case ID (leave blank) | Type of Validation | Test Objective | Request/Response Field | Test Steps | Expected Result | Mapping Correlation | Manual/Automation

REQUIREMENTS:
- Category: Always "Functional"
- Type of Validation: Must be one of: "Field Validation - Positive", "Field Validation - Negative", "Business Validation - Positive", "Business Validation - Negative"
- Manual/Automation: "Manual" for business validation, "Automation" for field validation
- Mapping Correlation: Use backend_xpath from field metadata

For each field, wrap output between markers:
===FIELD_START:<FIELD_ID>=== 
[test case rows here]
===FIELD_END:<FIELD_ID>===

Generate 2-4 test cases per field covering positive and negative scenarios based on the code context."""

        return f"====CONTEXT {context} ====QUESTION {question}"

    def _call_api_with_retry(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """Call API with retry logic and error handling"""
        
        for attempt in range(max_retries):
            try:
                print(f"[DEBUG] API call attempt {attempt + 1}/{max_retries}")
                response = self.client.chat_completion(prompt)
                content = response.choices[0].message.content.strip()
                
                # Check for FiservAI's "I don't know" responses
                if "sorry" in content.lower() and ("don't know" in content.lower() or "not sure" in content.lower()):
                    if attempt < max_retries - 1:
                        print(f"[WARN] AI responded with 'don't know', retrying with simpler prompt...")
                        # Create simpler fallback prompt
                        prompt = self._create_fallback_prompt(prompt)
                        time.sleep(2)  # Brief delay before retry
                        continue
                    else:
                        print(f"[ERROR] AI couldn't generate test cases after {max_retries} attempts")
                        return None
                
                return content
                
            except Exception as e:
                print(f"[ERROR] API call failed (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"[INFO] Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    print(f"[ERROR] All API retry attempts failed")
                    return None
        
        return None

    def _create_fallback_prompt(self, original_prompt: str) -> str:
        """Create simpler prompt when AI says 'I don't know'"""
        
        # Extract field info from original prompt
        if "FIELD INFORMATION" in original_prompt:
            context_part = original_prompt.split("====QUESTION")[0].replace("====CONTEXT ", "")
        else:
            context_part = "Generate basic test cases for API field validation."
        
        # Simpler question
        question = """Generate basic test cases in this simple format:

Functional	 	Field Validation - Positive	Test valid input	Request	Send valid data	Success expected	field/path	Automation
Functional	 	Field Validation - Negative	Test invalid input	Request	Send invalid data	Error expected	field/path	Automation

Just create 2 simple test cases following this exact pattern."""
        
        return f"====CONTEXT {context_part} ====QUESTION {question}"

    def generate_for_field(self, field: dict) -> bool:
        """Single-field generation (chatbot mode) with error handling"""
        
        # Validate field data
        is_valid, error_msg = self._validate_field_data(field)
        if not is_valid:
            print(f"[ERROR] Invalid field data: {error_msg}")
            return False
        
        try:
            backend_xpath = field.get("backend_xpath") or ""
            field_name = field.get("field_name", "")
            
            # Extract keywords safely
            keywords = []
            if backend_xpath:
                last_seg = backend_xpath.split("/")[-1]
                if last_seg:
                    keywords.append(last_seg)
            if field_name:
                keywords.append(field_name)
            
            if not keywords:
                print(f"[WARN] No valid keywords found for field, using generic search")
                keywords = ["validate", "check"]  # Fallback keywords
            
            print(f"[INFO] Extracting Java code for keywords: {keywords}")
            
            # Extract Java code with error handling
            try:
                snippets = extract_java_code_blocks_with_cross_references(
                    self.src_dir, keywords, max_depth=1
                )
                context = trim_code_context(snippets, max_chars=2000)
            except Exception as e:
                print(f"[WARN] Java extraction failed: {str(e)}, continuing without code context")
                context = ""
            
            fid_short = f"{field_name}_{self._hash_text(backend_xpath or field_name)}"
            
            # Generate prompt and call API
            prompt = self._format_fiservai_prompt([field], {fid_short: context})
            output = self._call_api_with_retry(prompt)
            
            if output is None:
                print(f"[ERROR] Failed to generate test cases for field: {field_name}")
                self.failed_fields.append(field_name)
                return False
            
            # Parse and store results
            success = self._parse_and_store(output, [field])
            if not success:
                print(f"[ERROR] Failed to parse test cases for field: {field_name}")
                self.failed_fields.append(field_name)
                return False
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Unexpected error processing field {field.get('field_name', 'unknown')}: {str(e)}")
            self.failed_fields.append(field.get('field_name', 'unknown'))
            return False

    def bulk_generate(self, fields: List[dict], batch_size: int = 5, max_workers: int = 6) -> Dict[str, Any]:
        """Bulk generation with comprehensive error handling"""
        
        print(f"[INFO] Starting bulk generation for {len(fields)} fields")
        
        # Validate all fields first
        valid_fields = []
        invalid_fields = []
        
        for field in fields:
            is_valid, error_msg = self._validate_field_data(field)
            if is_valid:
                valid_fields.append(field)
            else:
                invalid_fields.append({
                    'field': field.get('field_name', 'unknown'),
                    'error': error_msg
                })
                print(f"[WARN] Skipping invalid field: {error_msg}")
        
        if not valid_fields:
            print("[ERROR] No valid fields to process")
            return {
                'success': False,
                'processed': 0,
                'failed': len(fields),
                'invalid_fields': invalid_fields,
                'error': 'No valid fields found'
            }
        
        print(f"[INFO] Processing {len(valid_fields)} valid fields in batches of {batch_size}")
        
        total_processed = 0
        total_failed = 0
        batch_failures = []
        
        # Process in batches
        for i in range(0, len(valid_fields), batch_size):
            batch_num = i // batch_size + 1
            total_batches = (len(valid_fields) + batch_size - 1) // batch_size
            batch = valid_fields[i:i + batch_size]
            
            print(f"[INFO] Processing batch {batch_num}/{total_batches} ({len(batch)} fields)")
            
            try:
                # Parallel code extraction with error handling
                code_contexts = {}
                extraction_errors = []
                
                def extract_context_safe(field):
                    try:
                        backend_xpath = field.get("backend_xpath") or ""
                        field_name = field.get("field_name", "")
                        
                        keywords = []
                        if backend_xpath:
                            last_seg = backend_xpath.split("/")[-1]
                            if last_seg:
                                keywords.append(last_seg)
                        if field_name:
                            keywords.append(field_name)
                        
                        if not keywords:
                            keywords = ["validate", "check"]
                        
                        snippets = extract_java_code_blocks_with_cross_references(
                            self.src_dir, keywords, max_depth=1
                        )
                        ctx = trim_code_context(snippets, max_chars=2000)
                        fid_short = f"{field_name}_{self._hash_text(backend_xpath or field_name)}"
                        return fid_short, ctx, None
                        
                    except Exception as e:
                        return None, "", str(e)
                
                # Execute code extraction in parallel
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_field = {executor.submit(extract_context_safe, field): field for field in batch}
                    
                    for future in as_completed(future_to_field):
                        field = future_to_field[future]
                        field_name = field.get('field_name', 'unknown')
                        
                        try:
                            fid_short, ctx, error = future.result()
                            if error:
                                extraction_errors.append(f"{field_name}: {error}")
                                # Continue with empty context
                                fid_short = f"{field_name}_{self._hash_text(field.get('backend_xpath', field_name))}"
                                ctx = ""
                            code_contexts[fid_short] = ctx
                        except Exception as e:
                            extraction_errors.append(f"{field_name}: {str(e)}")
                            fid_short = f"{field_name}_{self._hash_text(field.get('backend_xpath', field_name))}"
                            code_contexts[fid_short] = ""
                
                if extraction_errors:
                    print(f"[WARN] Code extraction errors in batch {batch_num}: {len(extraction_errors)} fields")
                
                # Sequential API call for the batch
                print(f"[INFO] Generating test cases for batch {batch_num}...")
                prompt = self._format_fiservai_prompt(batch, code_contexts)
                output = self._call_api_with_retry(prompt, max_retries=3)
                
                if output is None:
                    print(f"[ERROR] API call failed for batch {batch_num}")
                    batch_failures.append({
                        'batch': batch_num,
                        'fields': [f.get('field_name', 'unknown') for f in batch],
                        'error': 'API call failed'
                    })
                    total_failed += len(batch)
                    continue
                
                # Parse and store results
                success = self._parse_and_store(output, batch)
                if success:
                    total_processed += len(batch)
                    print(f"[INFO] Successfully processed batch {batch_num}")
                else:
                    print(f"[ERROR] Failed to parse results for batch {batch_num}")
                    batch_failures.append({
                        'batch': batch_num,
                        'fields': [f.get('field_name', 'unknown') for f in batch],
                        'error': 'Parsing failed'
                    })
                    total_failed += len(batch)
                
            except Exception as e:
                print(f"[ERROR] Batch {batch_num} failed with exception: {str(e)}")
                batch_failures.append({
                    'batch': batch_num,
                    'fields': [f.get('field_name', 'unknown') for f in batch],
                    'error': str(e)
                })
                total_failed += len(batch)
            
            # Brief pause between batches
            if i + batch_size < len(valid_fields):
                time.sleep(1)
        
        # Generate summary
        success_rate = (total_processed / len(valid_fields)) * 100 if valid_fields else 0
        
        summary = {
            'success': total_processed > 0,
            'processed': total_processed,
            'failed': total_failed,
            'success_rate': round(success_rate, 2),
            'invalid_fields': invalid_fields,
            'batch_failures': batch_failures,
            'total_test_cases': len(self.test_manager.get_all_cases())
        }
        
        print(f"\n[INFO] Bulk generation completed:")
        print(f"  - Processed: {total_processed}/{len(valid_fields)} fields ({success_rate:.1f}%)")
        print(f"  - Generated: {summary['total_test_cases']} test cases")
        print(f"  - Failed batches: {len(batch_failures)}")
        
        return summary

    def _parse_and_store(self, output: str, batch_fields: List[dict]) -> bool:
        """Parse AI output and add cases to TestCaseManager with error handling"""
        
        try:
            initial_count = len(self.test_manager.get_all_cases())
            
            for field in batch_fields:
                field_name = field.get('field_name', 'unknown')
                fid = field.get("backend_xpath") or field_name
                fid_short = f"{field_name}_{self._hash_text(fid)}"
                
                start_marker = f"===FIELD_START:{fid_short}==="
                end_marker = f"===FIELD_END:{fid_short}==="
                
                if start_marker in output and end_marker in output:
                    try:
                        block = output.split(start_marker, 1)[1].split(end_marker, 1)[0].strip()
                        self.test_manager.parse_and_add_test_cases(block, default_mapping=fid)
                        print(f"[DEBUG] Parsed test cases for field: {field_name}")
                    except Exception as e:
                        print(f"[WARN] Failed to parse marked section for {field_name}: {str(e)}")
                        # Try parsing the entire output as fallback
                        self.test_manager.parse_and_add_test_cases(output, default_mapping=fid)
                else:
                    print(f"[WARN] No field markers found for {field_name}, using entire output")
                    self.test_manager.parse_and_add_test_cases(output, default_mapping=fid)
            
            final_count = len(self.test_manager.get_all_cases())
            new_cases = final_count - initial_count
            
            if new_cases > 0:
                print(f"[INFO] Successfully added {new_cases} new test cases")
                return True
            else:
                print("[WARN] No new test cases were added")
                return False
                
        except Exception as e:
            print(f"[ERROR] Failed to parse and store test cases: {str(e)}")
            return False

    def get_generation_summary(self) -> Dict[str, Any]:
        """Get summary of generation results"""
        all_cases = self.test_manager.get_all_cases()
        
        return {
            'total_test_cases': len(all_cases),
            'failed_fields': self.failed_fields.copy(),
            'success_rate': 0 if not all_cases else 100 - (len(self.failed_fields) / (len(all_cases) + len(self.failed_fields)) * 100)
        }


# complete_agentic_test_generator.py (updated main functions)

import argparse
import os
from datetime import datetime
from typing import List, Dict, Any

from core.test_objective_core import TestObjectiveGeneratorCore
from core.testcase_manager import TestCaseManager
# from some_module import GPTClient, get_xpath_fields  # <-- keep your enterprise versions

def chat_mode_with_auto_export(generator: TestObjectiveGeneratorCore, fields: List[dict]) -> bool:
    """Chat mode with automatic export on exit"""
    
    print("ðŸ¤– CHAT MODE - Interactive Test Case Generation")
    print("Commands: 'list' - show available fields, 'exit' - quit and export")
    print("=" * 60)
    
    # Show available fields
    print(f"\nAvailable fields ({len(fields)}):")
    for i, field in enumerate(fields[:10]):  # Show first 10
        print(f"  {i+1}. {field.get('field_name', 'Unknown')}")
    if len(fields) > 10:
        print(f"  ... and {len(fields) - 10} more (type 'list' to see all)")
    
    generated_any = False
    
    while True:
        field_input = input(f"\nðŸ“ Enter field name (or 'list'/'exit'): ").strip()
        
        if field_input.lower() == "exit":
            break
            
        elif field_input.lower() == "list":
            print(f"\nAll available f
