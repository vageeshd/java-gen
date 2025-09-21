import hashlib
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple

# Import the optimized java extractor functions
from .java_extractor import extract_java_code_blocks_with_cross_references, trim_code_context

class TestObjectiveGeneratorCore:
    """
    Enhanced test objective generator with multi-field support and conversation context integration
    """
    
    def __init__(self, client, test_manager, src_dir: str, mapping_file_path: str = None, 
                 conversation_manager = None):
        self.client = client
        self.test_manager = test_manager
        self.src_dir = src_dir
        self.mapping_file_path = mapping_file_path
        self.conversation_manager = conversation_manager
        
        # Multi-field state management
        self.current_field_name = None
        self.field_contexts = {}  # Store contexts per field
        self.failed_fields = []
        
        # Session statistics
        self.session_stats = {
            'fields_processed': 0,
            'total_test_cases_generated': 0,
            'total_approved_cases': 0,
            'session_start_time': datetime.now()
        }
    
    def _hash_text(self, text: str) -> str:
        """Generate hash for field identification"""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    
    def _validate_field_data(self, field: dict) -> Tuple[bool, str]:
        """Validate field has minimum required data"""
        required_fields = ['field_name']
        
        for req_field in required_fields:
            if not field.get(req_field):
                return False, f"Missing required field: {req_field}"
        
        field_name = field.get('field_name', '').strip()
        if len(field_name) < 2:
            return False, f"Field name too short: '{field_name}'"
        
        # Validate backend_xpath if present
        backend_xpath = field.get('backend_xpath', '')
        if backend_xpath and not backend_xpath.replace('/', '').replace('_', '').replace('-', '').isalnum():
            return False, f"Invalid backend_xpath format: '{backend_xpath}'"
        
        return True, "Valid"
    
    def _extract_conversation_context(self) -> str:
        """Extract relevant conversation history for current field generation"""
        
        if not self.conversation_manager:
            return ""
        
        try:
            recent_turns = self.conversation_manager.get_conversation()[-5:]  # Last 5 turns
            
            context_summary = ""
            for turn in recent_turns:
                role = turn.get('role', '')
                content = turn.get('content', '')
                
                # Truncate very long content
                if len(content) > 200:
                    content = content[:200] + "..."
                
                context_summary += f"{role.upper()}: {content}\n"
            
            return context_summary
            
        except Exception as e:
            print(f"[WARN] Could not extract conversation context: {e}")
            return ""
    
    def _build_ai_prompt(self, field_metadata: dict, java_context: str = "", conversation_context: str = "") -> str:
        """Build the complete AI prompt in FiservAI format"""
        
        # Build CONTEXT section
        context_part = f"""Field metadata and context for test case generation:

FIELD METADATA:
"""
        for key, value in field_metadata.items():
            if value:
                context_part += f"{key}: {value}\n"
        
        if java_context:
            context_part += f"""

JAVA CODE CONTEXT:
{java_context}"""
        
        if conversation_context:
            context_part += f"""

CONVERSATION CONTEXT:
{conversation_context}"""
        
        # Build QUESTION section
        question_part = """Generate test cases in EXACTLY 9 tab-separated columns:
Category | Test Case ID (blank) | Type of Validation | Test Objective | Request/Response Field | Test Steps | Expected Result | Mapping Correlation | Manual/Automation

REQUIREMENTS:
- Category: Always "Functional"
- Test Case ID: Leave blank (will be auto-assigned)
- Type of Validation: Must be one of: "Field Validation - Positive", "Field Validation - Negative", "Business Validation - Positive", "Business Validation - Negative"
- Request/Response Field: "Request" or "Response" 
- Manual/Automation: "Manual" for business validation, "Automation" for field validation
- Mapping Correlation: Use backend_xpath from field metadata
- Generate 2-4 test cases covering different validation scenarios
- Consider the conversation context for continuity

Output ONLY the test case rows, no explanations, no headers, no markdown formatting."""

        return f"====CONTEXT {context_part} ====QUESTION {question_part}"
    
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
                        time.sleep(2)
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
        if "FIELD METADATA" in original_prompt:
            context_part = original_prompt.split("====QUESTION")[0].replace("====CONTEXT ", "")
        else:
            context_part = "Generate basic test cases for API field validation."
        
        # Simpler question
        question = """Generate basic test cases in this simple format (tab-separated):

Functional	 	Field Validation - Positive	Test valid input	Request	Send valid data	Success expected	field/path	Automation
Functional	 	Field Validation - Negative	Test invalid input	Request	Send invalid data	Error expected	field/path	Automation

Create 2 simple test cases following this exact pattern."""
        
        return f"====CONTEXT {context_part} ====QUESTION {question}"
    
    def generate_for_field(self, field_metadata: dict) -> bool:
        """Generate test cases for a specific field with automatic context extraction"""
        
        # Validate field data
        is_valid, error_msg = self._validate_field_data(field_metadata)
        if not is_valid:
            print(f"[ERROR] Invalid field data: {error_msg}")
            return False
        
        field_name = field_metadata.get('field_name', 'Unknown')
        self.current_field_name = field_name
        
        # Store field context for session tracking
        self.field_contexts[field_name] = {
            'metadata': field_metadata,
            'generation_timestamp': datetime.now(),
            'attempts': self.field_contexts.get(field_name, {}).get('attempts', 0) + 1
        }
        
        print(f"[INFO] Generating test cases for field: {field_name}")
        
        try:
            backend_xpath = field_metadata.get("backend_xpath") or ""
            
            # Extract keywords for Java code search
            keywords = []
            if field_name:
                keywords.append(field_name)
                # Add camelCase breakdown: PostalCode -> postal, code  
                camel_parts = re.findall(r'[A-Z][a-z]*|[a-z]+', field_name)
                keywords.extend(camel_parts)
            
            if backend_xpath:
                xpath_segments = [seg.strip() for seg in backend_xpath.split('/') if len(seg.strip()) > 2]
                keywords.extend(xpath_segments)
            
            if not keywords:
                print(f"[WARN] No valid keywords found for field, using generic search")
                keywords = ["validate", "check"]
            
            print(f"[INFO] Extracting Java code for keywords: {keywords}")
            
            # Extract Java code with optimized approach
            java_context = ""
            try:
                snippets = extract_java_code_blocks_with_cross_references(
                    self.src_dir, 
                    keywords, 
                    max_depth=1,
                    mapping_file_path=self.mapping_file_path,
                    field_metadata=field_metadata
                )
                java_context = trim_code_context(
                    snippets, 
                    max_chars=2500,
                    mapping_file_path=self.mapping_file_path
                )
                
                if java_context:
                    print(f"[INFO] Extracted {len(java_context)} chars of relevant Java context")
                else:
                    print(f"[WARN] No relevant Java code found for keywords: {keywords}")
                    
            except Exception as e:
                print(f"[WARN] Java extraction failed: {str(e)}, continuing without code context")
                java_context = ""
            
            # Extract conversation context automatically
            conversation_context = self._extract_conversation_context()
            
            # Build AI prompt
            prompt = self._build_ai_prompt(field_metadata, java_context, conversation_context)
            
            # Call API with retry logic
            output = self._call_api_with_retry(prompt)
            
            if output is None:
                print(f"[ERROR] Failed to generate test cases for field: {field_name}")
                self.failed_fields.append(field_name)
                return False
            
            # Parse and store results using TestCaseManager
            new_tc_ids = self.test_manager.parse_and_add_test_cases(
                output, 
                default_mapping=backend_xpath,
                field_name=field_name  # Pass field name for multi-field support
            )
            
            if new_tc_ids:
                self.session_stats['total_test_cases_generated'] += len(new_tc_ids)
                print(f"[INFO] Generated {len(new_tc_ids)} new test cases for {field_name}")
                return True
            else:
                print(f"[WARN] No test cases parsed from AI response for {field_name}")
                return False
            
        except Exception as e:
            print(f"[ERROR] Unexpected error processing field {field_name}: {str(e)}")
            self.failed_fields.append(field_name)
            return False
    
    def generate_with_feedback(self, field_metadata: dict, feedback: str) -> bool:
        """Generate improved test cases based on user feedback"""
        
        field_name = field_metadata.get('field_name', 'Unknown')
        print(f"[INFO] Generating feedback-based test cases for {field_name}: '{feedback}'")
        
        try:
            # Get existing test cases for context
            existing_cases = self.test_manager.get_field_test_cases(field_name)
            
            # Build context with existing cases
            context_part = f"""Field metadata and feedback for test case improvement:

FIELD METADATA:
"""
            for key, value in field_metadata.items():
                if value:
                    context_part += f"{key}: {value}\n"
            
            if existing_cases:
                context_part += f"""

EXISTING TEST CASES:
"""
                for i, case in enumerate(existing_cases[:3]):  # Show up to 3 existing cases
                    context_part += f"TC_{i+1}: {case.get('Test Objective', 'N/A')}\n"
            
            # Add conversation context
            conversation_context = self._extract_conversation_context()
            if conversation_context:
                context_part += f"""

CONVERSATION CONTEXT:
{conversation_context}"""
            
            context_part += f"""

USER FEEDBACK:
{feedback}"""
            
            # Build question for feedback-driven generation
            question_part = """Based on the user feedback, generate 1-2 additional test cases that address the specific requirements mentioned.

Generate in EXACTLY 9 tab-separated columns:
Category | Test Case ID (blank) | Type of Validation | Test Objective | Request/Response Field | Test Steps | Expected Result | Mapping Correlation | Manual/Automation

Focus on the user's specific feedback and avoid duplicating existing test scenarios.
Output ONLY the test case rows, no explanations."""

            formatted_prompt = f"====CONTEXT {context_part} ====QUESTION {question_part}"
            
            # Call API with retry
            output = self._call_api_with_retry(formatted_prompt)
            
            if output is None:
                print(f"[ERROR] Failed to generate feedback-based test cases for field: {field_name}")
                return False
            
            # Parse and store results
            new_tc_ids = self.test_manager.parse_and_add_test_cases(
                output, 
                default_mapping=field_metadata.get('backend_xpath', ''),
                field_name=field_name
            )
            
            if new_tc_ids:
                self.session_stats['total_test_cases_generated'] += len(new_tc_ids)
                print(f"[INFO] Generated {len(new_tc_ids)} feedback-based test cases for {field_name}")
                return True
            else:
                print(f"[WARN] No feedback-based test cases parsed from AI response")
                return False
                
        except Exception as e:
            print(f"[ERROR] Error generating feedback-based test cases: {str(e)}")
            return False
    
    def is_field_ready_for_completion(self, field_name: str = None) -> bool:
        """Check if current field has sufficient approved test cases"""
        
        target_field = field_name or self.current_field_name
        if not target_field:
            return False
        
        # Get field-specific approved cases from TestCaseManager
        approved_cases = self.test_manager.get_field_approved_cases(target_field)
        
        # Field is ready for completion if user has approved at least one case
        return len(approved_cases) >= 1
    
    def complete_current_field(self) -> dict:
        """Mark current field as completed and return summary"""
        
        if not self.current_field_name:
            return {'error': 'No current field to complete'}
        
        field_name = self.current_field_name
        
        # Get completion summary from TestCaseManager
        completion_data = self.test_manager.complete_field(field_name)
        
        # Update session stats
        self.session_stats['fields_processed'] += 1
        self.session_stats['total_approved_cases'] += completion_data.get('approved_count', 0)
        
        # Mark field as completed in context
        if field_name in self.field_contexts:
            self.field_contexts[field_name]['completion_time'] = datetime.now()
            self.field_contexts[field_name]['status'] = 'completed'
        
        # Reset current field
        self.current_field_name = None
        
        print(f"[INFO] Completed field: {field_name} with {completion_data.get('approved_count', 0)} approved cases")
        
        return {
            'completed_field': field_name,
            'approved_count': completion_data.get('approved_count', 0),
            'total_generated': completion_data.get('total_generated', 0),
            'completion_time': datetime.now(),
            'status': 'success'
        }
    
    def switch_to_field(self, field_name: str) -> bool:
        """Switch context to a different field"""
        
        if field_name == self.current_field_name:
            print(f"[INFO] Already working on field: {field_name}")
            return True
        
        # If there's a current field, check if it should be completed first
        if self.current_field_name:
            if self.is_field_ready_for_completion():
                print(f"[WARN] Current field {self.current_field_name} has approved cases but is not completed")
                print(f"[INFO] Consider completing it before switching to {field_name}")
        
        self.current_field_name = field_name
        print(f"[INFO] Switched to field: {field_name}")
        
        return True
    
    def get_session_summary(self) -> dict:
        """Get comprehensive summary of current session"""
        
        session_duration = datetime.now() - self.session_stats['session_start_time']
        
        # Get multi-field stats from TestCaseManager
        multi_field_stats = self.test_manager.get_multi_field_stats()
        
        completed_fields = [name for name, context in self.field_contexts.items() 
                          if context.get('status') == 'completed']
        
        return {
            'session_duration': str(session_duration),
            'current_field': self.current_field_name,
            'fields_worked_on': list(self.field_contexts.keys()),
            'completed_fields': completed_fields,
            'fields_in_progress': [name for name in self.field_contexts.keys() 
                                 if name not in completed_fields and name != self.current_field_name],
            'total_fields_processed': len(self.field_contexts),
            'failed_fields': self.failed_fields.copy(),
            'session_stats': {
                'total_test_cases_generated': self.session_stats['total_test_cases_generated'],
                'total_approved_cases': multi_field_stats.get('total_approved', 0),
                'success_rate': len(completed_fields) / len(self.field_contexts) if self.field_contexts else 0
            },
            'multi_field_breakdown': multi_field_stats
        }
    
    def export_all_completed_fields(self, output_file: str) -> bool:
        """Export all completed fields to single Excel file with sequential TC IDs"""
        
        try:
            success = self.test_manager.export_multi_field_session(output_file)
            
            if success:
                completed_fields = [name for name, context in self.field_contexts.items() 
                                  if context.get('status') == 'completed']
                print(f"[INFO] Successfully exported {len(completed_fields)} completed fields to {output_file}")
            
            return success
            
        except Exception as e:
            print(f"[ERROR] Failed to export multi-field session: {str(e)}")
            return False
    
    def get_generation_summary(self) -> Dict[str, Any]:
        """Get summary of generation results (backward compatibility)"""
        
        session_summary = self.get_session_summary()
        
        return {
            'total_test_cases': session_summary['session_stats']['total_test_cases_generated'],
            'failed_fields': self.failed_fields.copy(),
            'success_rate': session_summary['session_stats']['success_rate'] * 100,
            'fields_processed': session_summary['total_fields_processed']
        }
    
    # Bulk generation method (keep existing implementation for compatibility)
    def bulk_generate(self, fields: List[dict], batch_size: int = 5, max_workers: int = 6) -> Dict[str, Any]:
        """Bulk generation with comprehensive error handling (existing implementation)"""
        
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
        
        # Process each field individually using the single field method
        for field in valid_fields:
            field_name = field.get('field_name', 'unknown')
            
            try:
                success = self.generate_for_field(field)
                if success:
                    # Auto-approve all generated cases in bulk mode
                    field_cases = self.test_manager.get_field_test_cases(field_name)
                    pending_cases = [case for case in field_cases if case.get('status') == 'pending']
                    
                    if pending_cases:
                        tc_ids = [case.get('Test Case ID') for case in pending_cases if case.get('Test Case ID')]
                        self.test_manager.approve_test_cases(tc_ids)
                    
                    # Complete field automatically in bulk mode
                    self.complete_current_field()
                    total_processed += 1
                else:
                    total_failed += 1
                    
            except Exception as e:
                print(f"[ERROR] Bulk processing failed for field {field_name}: {str(e)}")
                total_failed += 1
        
        # Generate summary
        success_rate = (total_processed / len(valid_fields)) * 100 if valid_fields else 0
        
        summary = {
            'success': total_processed > 0,
            'processed': total_processed,
            'failed': total_failed,
            'success_rate': round(success_rate, 2),
            'invalid_fields': invalid_fields,
            'total_test_cases': self.session_stats['total_test_cases_generated']
        }
        
        print(f"\n[INFO] Bulk generation completed:")
        print(f"  - Processed: {total_processed}/{len(valid_fields)} fields ({success_rate:.1f}%)")
        print(f"  - Generated: {summary['total_test_cases']} test cases")
        
        return summary