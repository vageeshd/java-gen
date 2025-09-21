import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass
from .feedback_handler import FeedbackType, FeedbackAnalysis

@dataclass
class TestCaseModification:
    """Represents a modification to a specific test case"""
    original_tc_id: str
    modified_tc_data: Dict[str, Any]
    modification_reason: str
    timestamp: datetime
    status: str = "pending_approval"  # pending_approval, approved, rejected
    temp_tc_id: str = ""  # Temporary ID for the modified version

class TestCaseModifier:
    """
    Handles modification of existing test cases based on user feedback
    """
    
    def __init__(self, test_manager, client):
        self.test_manager = test_manager
        self.client = client
        self.pending_modifications = {}  # tc_id -> TestCaseModification
    
    def identify_target_test_cases(self, feedback_text: str, existing_cases: List[Dict]) -> List[str]:
        """
        Identify which specific test cases the user is referring to
        """
        referenced_tc_ids = []
        
        # Direct TC ID references (TC_001, TC_002, etc.)
        direct_matches = re.findall(r'\bTC_\d{3}\b', feedback_text)
        referenced_tc_ids.extend(direct_matches)
        
        # Handle variations like "test case 1", "TC1", "the first test"
        variations = [
            (r'\btest case (\d+)\b', lambda m: f"TC_{int(m.group(1)):03d}"),
            (r'\bTC(\d+)\b', lambda m: f"TC_{int(m.group(1)):03d}"),
            (r'\b(\d+)(?:st|nd|rd|th) test\b', lambda m: f"TC_{int(m.group(1)):03d}"),
            (r'\bfirst test\b', lambda m: "TC_001"),
            (r'\bsecond test\b', lambda m: "TC_002"),
            (r'\bthird test\b', lambda m: "TC_003"),
            (r'\blast test\b', lambda m: f"TC_{len(existing_cases):03d}" if existing_cases else "TC_001"),
            (r'\ball tests?\b', lambda m: "ALL")
        ]
        
        for pattern, converter in variations:
            matches = re.finditer(pattern, feedback_text, re.IGNORECASE)
            for match in matches:
                tc_id = converter(match)
                if tc_id == "ALL":
                    # User wants to modify all test cases
                    return [case.get('Test Case ID') for case in existing_cases if case.get('Test Case ID')]
                elif tc_id not in referenced_tc_ids:
                    referenced_tc_ids.append(tc_id)
        
        # If no specific test case mentioned, try to infer from context
        if not referenced_tc_ids:
            referenced_tc_ids = self._infer_target_from_context(feedback_text, existing_cases)
        
        # Validate that referenced test cases actually exist
        valid_tc_ids = []
        existing_tc_ids = [case.get('Test Case ID') for case in existing_cases if case.get('Test Case ID')]
        
        for tc_id in referenced_tc_ids:
            if tc_id in existing_tc_ids:
                valid_tc_ids.append(tc_id)
        
        return valid_tc_ids
    
    def _infer_target_from_context(self, feedback_text: str, existing_cases: List[Dict]) -> List[str]:
        """
        Try to infer which test case user is referring to based on content
        """
        feedback_lower = feedback_text.lower()
        
        # Look for validation type mentions
        validation_keywords = {
            'positive': 'Field Validation - Positive',
            'negative': 'Field Validation - Negative',
            'business': 'Business Validation',
            'manual': 'Manual',
            'automation': 'Automation'
        }
        
        inferred_tc_ids = []
        
        for keyword, full_term in validation_keywords.items():
            if keyword in feedback_lower:
                # Find test cases matching this validation type
                matching_cases = [
                    case for case in existing_cases
                    if (full_term in case.get('Type of Validation', '') or 
                        keyword in case.get('Manual/Automation', '').lower())
                ]
                for case in matching_cases:
                    tc_id = case.get('Test Case ID')
                    if tc_id and tc_id not in inferred_tc_ids:
                        inferred_tc_ids.append(tc_id)
        
        # If still no matches, look for objective keywords
        if not inferred_tc_ids:
            objective_keywords = re.findall(r'\b\w{4,}\b', feedback_lower)
            for keyword in objective_keywords[:3]:  # Limit to avoid noise
                matching_cases = [
                    case for case in existing_cases
                    if keyword in case.get('Test Objective', '').lower()
                ]
                for case in matching_cases:
                    tc_id = case.get('Test Case ID')
                    if tc_id and tc_id not in inferred_tc_ids:
                        inferred_tc_ids.append(tc_id)
        
        return inferred_tc_ids[:2]  # Limit to 2 inferred cases to avoid overwhelming
    
    def modify_test_case(self, tc_id: str, feedback: str, field_metadata: Dict, 
                        original_case: Dict) -> Optional[TestCaseModification]:
        """
        Generate a modified version of a specific test case based on user feedback
        """
        try:
            print(f"[INFO] Modifying test case {tc_id} based on feedback")
            
            # Build modification prompt
            prompt = self._build_modification_prompt(tc_id, feedback, field_metadata, original_case)
            
            # Call API to generate modified version
            response = self.client.chat_completion(prompt)
            modified_content = response.choices[0].message.content.strip()
            
            # Parse the modified test case
            modified_tc_data = self._parse_modified_test_case(modified_content, original_case)
            
            if not modified_tc_data:
                print(f"[ERROR] Failed to parse modified test case for {tc_id}")
                return None
            
            # Create temporary test case with modified data
            temp_tc_id = f"{tc_id}_MODIFIED_{datetime.now().strftime('%H%M%S')}"
            modified_tc_data['Test Case ID'] = temp_tc_id
            modified_tc_data['Status'] = 'pending_modification_approval'
            modified_tc_data['Original_TC_ID'] = tc_id
            modified_tc_data['Modification_Reason'] = feedback[:200]
            
            # Create modification record
            modification = TestCaseModification(
                original_tc_id=tc_id,
                modified_tc_data=modified_tc_data,
                modification_reason=feedback,
                timestamp=datetime.now(),
                temp_tc_id=temp_tc_id
            )
            
            # Store pending modification
            self.pending_modifications[temp_tc_id] = modification
            
            print(f"[INFO] Created modified version {temp_tc_id} for original {tc_id}")
            return modification
            
        except Exception as e:
            print(f"[ERROR] Failed to modify test case {tc_id}: {str(e)}")
            return None
    
    def _build_modification_prompt(self, tc_id: str, feedback: str, field_metadata: Dict, 
                                 original_case: Dict) -> str:
        """Build prompt for modifying a specific test case"""
        
        context_part = f"""You are modifying an existing test case based on user feedback.

ORIGINAL TEST CASE ({tc_id}):
Category: {original_case.get('Category', '')}
Type of Validation: {original_case.get('Type of Validation', '')}
Test Objective: {original_case.get('Test Objective', '')}
Request/Response Field: {original_case.get('Request/Response Field', '')}
Test Steps: {original_case.get('Test Steps', '')}
Expected Result: {original_case.get('Expected Result', '')}
Mapping Correlation: {original_case.get('Mapping Correlation', '')}
Manual/Automation: {original_case.get('Manual/Automation', '')}

FIELD METADATA:
"""
        for key, value in field_metadata.items():
            if value:
                context_part += f"{key}: {value}\n"
        
        context_part += f"""
USER FEEDBACK FOR MODIFICATION:
{feedback}
"""
        
        question_part = """Based on the user feedback, modify the original test case to address their concerns. Keep the same structure but update the relevant fields.

Generate the MODIFIED test case in EXACTLY 9 tab-separated columns:
Category | Test Case ID (leave blank) | Type of Validation | Test Objective | Request/Response Field | Test Steps | Expected Result | Mapping Correlation | Manual/Automation

REQUIREMENTS:
- Address the specific feedback provided
- Maintain consistency with the original test case structure
- Keep fields that don't need changes unchanged
- Make only the changes requested in the feedback
- Output ONLY the modified test case row, no explanations"""
        
        return f"====CONTEXT {context_part} ====QUESTION {question_part}"
    
    def _parse_modified_test_case(self, api_response: str, original_case: Dict) -> Optional[Dict[str, Any]]:
        """Parse the API response containing modified test case"""
        
        lines = api_response.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('Category') or line.startswith('---'):
                continue
            
            # Try tab separation first, then pipe
            parts = line.split('\t')
            if len(parts) < 6:
                parts = line.split('|')
            
            if len(parts) >= 6:
                # Clean and pad parts
                parts = [p.strip() for p in parts]
                while len(parts) < 9:
                    parts.append("")
                
                # Create modified test case data
                modified_case = {
                    "Category": parts[0] or original_case.get('Category', 'Functional'),
                    "Test Case ID": "",  # Will be set later
                    "Type of Validation": parts[2] or original_case.get('Type of Validation', ''),
                    "Test Objective": parts[3] or original_case.get('Test Objective', ''),
                    "Request/Response Field": parts[4] or original_case.get('Request/Response Field', ''),
                    "Test Steps": parts[5] or original_case.get('Test Steps', ''),
                    "Expected Result": parts[6] or original_case.get('Expected Result', ''),
                    "Mapping Correlation": parts[7] or original_case.get('Mapping Correlation', ''),
                    "Manual/Automation": parts[8] or original_case.get('Manual/Automation', ''),
                    "Field Name": original_case.get('Field Name', ''),
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                return modified_case
        
        return None
    
    def approve_modification(self, temp_tc_id: str) -> bool:
        """
        Approve a pending modification - replace original with modified version
        """
        if temp_tc_id not in self.pending_modifications:
            print(f"[ERROR] No pending modification found for {temp_tc_id}")
            return False
        
        modification = self.pending_modifications[temp_tc_id]
        original_tc_id = modification.original_tc_id
        
        try:
            # Get the original test case
            original_case = self.test_manager.get_test_case_by_id(original_tc_id)
            if not original_case:
                print(f"[ERROR] Original test case {original_tc_id} not found")
                return False
            
            # Update the original test case with modified data
            field_name = original_case.get('Field Name')
            if field_name and field_name in self.test_manager.field_sessions:
                field_session = self.test_manager.field_sessions[field_name]
                
                if original_tc_id in field_session.test_cases:
                    # Update the original test case object
                    original_test_case = field_session.test_cases[original_tc_id]
                    
                    # Update fields with modified data (keep original TC ID)
                    modified_data = modification.modified_tc_data.copy()
                    modified_data['Test Case ID'] = original_tc_id  # Keep original ID
                    modified_data['Status'] = 'approved'  # Mark as approved
                    
                    # Update the test case object
                    original_test_case.category = modified_data.get('Category', original_test_case.category)
                    original_test_case.type_of_validation = modified_data.get('Type of Validation', original_test_case.type_of_validation)
                    original_test_case.test_objective = modified_data.get('Test Objective', original_test_case.test_objective)
                    original_test_case.request_response_field = modified_data.get('Request/Response Field', original_test_case.request_response_field)
                    original_test_case.test_steps = modified_data.get('Test Steps', original_test_case.test_steps)
                    original_test_case.expected_result = modified_data.get('Expected Result', original_test_case.expected_result)
                    original_test_case.mapping_correlation = modified_data.get('Mapping Correlation', original_test_case.mapping_correlation)
                    original_test_case.manual_automation = modified_data.get('Manual/Automation', original_test_case.manual_automation)
                    original_test_case.status = 'approved'
                    original_test_case.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Mark modification as approved
                    modification.status = 'approved'
                    
                    # Clean up pending modification
                    del self.pending_modifications[temp_tc_id]
                    
                    print(f"[INFO] Successfully approved modification for {original_tc_id}")
                    return True
            
            print(f"[ERROR] Could not find field session for test case {original_tc_id}")
            return False
            
        except Exception as e:
            print(f"[ERROR] Failed to approve modification for {original_tc_id}: {str(e)}")
            return False
    
    def reject_modification(self, temp_tc_id: str) -> bool:
        """
        Reject a pending modification - keep original test case unchanged
        """
        if temp_tc_id not in self.pending_modifications:
            print(f"[ERROR] No pending modification found for {temp_tc_id}")
            return False
        
        modification = self.pending_modifications[temp_tc_id]
        modification.status = 'rejected'
        
        # Clean up pending modification
        del self.pending_modifications[temp_tc_id]
        
        print(f"[INFO] Rejected modification {temp_tc_id} for original {modification.original_tc_id}")
        return True
    
    def get_pending_modifications(self, field_name: str = None) -> List[Dict[str, Any]]:
        """Get all pending modifications, optionally filtered by field"""
        
        pending_mods = []
        
        for temp_tc_id, modification in self.pending_modifications.items():
            if modification.status == 'pending_approval':
                mod_dict = {
                    'temp_tc_id': temp_tc_id,
                    'original_tc_id': modification.original_tc_id,
                    'modified_data': modification.modified_tc_data,
                    'reason': modification.modification_reason,
                    'timestamp': modification.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Filter by field if specified
                if field_name:
                    if modification.modified_tc_data.get('Field Name') == field_name:
                        pending_mods.append(mod_dict)
                else:
                    pending_mods.append(mod_dict)
        
        return pending_mods
    
    def display_modification_comparison(self, temp_tc_id: str) -> str:
        """Display original vs modified test case for user review"""
        
        if temp_tc_id not in self.pending_modifications:
            return f"No pending modification found for {temp_tc_id}"
        
        modification = self.pending_modifications[temp_tc_id]
        original_tc_id = modification.original_tc_id
        
        # Get original test case
        original_case = self.test_manager.get_test_case_by_id(original_tc_id)
        if not original_case:
            return f"Original test case {original_tc_id} not found"
        
        modified_data = modification.modified_tc_data
        
        comparison = f"""
MODIFICATION COMPARISON FOR {original_tc_id}

REASON: {modification.modification_reason}

ORIGINAL:
  Test Objective: {original_case.get('Test Objective', '')}
  Type of Validation: {original_case.get('Type of Validation', '')}
  Test Steps: {original_case.get('Test Steps', '')}
  Expected Result: {original_case.get('Expected Result', '')}
  Manual/Automation: {original_case.get('Manual/Automation', '')}

MODIFIED:
  Test Objective: {modified_data.get('Test Objective', '')}
  Type of Validation: {modified_data.get('Type of Validation', '')}
  Test Steps: {modified_data.get('Test Steps', '')}
  Expected Result: {modified_data.get('Expected Result', '')}
  Manual/Automation: {modified_data.get('Manual/Automation', '')}

Actions: approve_modification("{temp_tc_id}") or reject_modification("{temp_tc_id}")
"""
        return comparison