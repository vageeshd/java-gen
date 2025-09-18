import os
import json
import re
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows

from fiservai import FiservAI
from fiserv_ai_utils import SimpleConversationManager
from import_openpyxl import get_xpath_fields
from dotenv import load_dotenv

import yaml
from generate_field_assertions_yaml import generate_service_details, save_yaml_file

import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from extract_java_code_blocks import extract_java_code_blocks_with_cross_references

# Load environment variables from .env file
load_dotenv()

@dataclass
class TestCase:
    tc_id: str
    category: str
    type_of_validation: str
    test_objective: str
    request_response_field: str
    test_steps: str
    expected_result: str
    mapping_correlation: str
    manual_automation: str
    status: str = "draft"  # draft, approved, rejected
    timestamp: str = ""

class TestCaseManager:
    def __init__(self):
        self.test_cases: Dict[str, TestCase] = {}
        self.next_id = 1
        
    def parse_and_add_test_cases(self, ai_response: str) -> List[str]:
        """Parse AI response and add test cases, return list of new TC IDs"""
        new_tc_ids = []
        lines = ai_response.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('Category') or line.startswith('---'):
                continue
                
            # Split by tabs
            parts = line.split('\t')
            if len(parts) >= 8:  # Minimum required columns
                # Pad with empty strings if needed
                while len(parts) < 9:
                    parts.append("")
                
                tc_id = f"TC_{self.next_id:03d}"
                test_case = TestCase(
                    tc_id=tc_id,
                    category=parts[0].strip(),
                    type_of_validation=parts[1].strip(),
                    test_objective=parts[2].strip(),
                    request_response_field=parts[3].strip(),
                    test_steps=parts[4].strip(),
                    expected_result=parts[5].strip(),
                    mapping_correlation=parts[6].strip(),
                    manual_automation=parts[7].strip(),
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                
                self.test_cases[tc_id] = test_case
                new_tc_ids.append(tc_id)
                self.next_id += 1
        
        return new_tc_ids
    
    def approve_test_cases(self, tc_ids: List[str]) -> Tuple[List[str], List[str]]:
        """Approve test cases, return (approved, not_found)"""
        approved = []
        not_found = []
        
        for tc_id in tc_ids:
            if tc_id in self.test_cases:
                self.test_cases[tc_id].status = "approved"
                approved.append(tc_id)
            else:
                not_found.append(tc_id)
        
        return approved, not_found
    
    def reject_test_cases(self, tc_ids: List[str]) -> Tuple[List[str], List[str]]:
        """Reject and remove test cases, reassign IDs"""
        rejected = []
        not_found = []
        
        for tc_id in tc_ids:
            if tc_id in self.test_cases:
                del self.test_cases[tc_id]
                rejected.append(tc_id)
            else:
                not_found.append(tc_id)
        
        # Reassign IDs sequentially
        self._reassign_ids()
        return rejected, not_found
    
    def _reassign_ids(self):
        """Reassign TC IDs sequentially after rejections"""
        old_cases = list(self.test_cases.values())
        self.test_cases.clear()
        self.next_id = 1
        
        # Sort by timestamp to maintain order
        old_cases.sort(key=lambda x: x.timestamp)
        
        for case in old_cases:
            new_id = f"TC_{self.next_id:03d}"
            case.tc_id = new_id
            self.test_cases[new_id] = case
            self.next_id += 1
    
    def get_approved_cases(self) -> List[TestCase]:
        """Get all approved test cases"""
        return [tc for tc in self.test_cases.values() if tc.status == "approved"]
    
    def get_all_cases(self) -> List[TestCase]:
        """Get all test cases with their status"""
        return list(self.test_cases.values())
    
    def get_status_summary(self) -> Dict[str, int]:
        """Get summary of test case statuses"""
        summary = {"draft": 0, "approved": 0}
        for tc in self.test_cases.values():
            summary[tc.status] = summary.get(tc.status, 0) + 1
        return summary

class ExcelGenerator:
    @staticmethod
    def generate_excel(approved_cases: List[TestCase], field_name: str, output_dir: str = None) -> str:
        """Generate Excel file from approved test cases"""
        if not approved_cases:
            raise ValueError("No approved test cases to export")
        
        # Create DataFrame
        data = []
        for tc in approved_cases:
            data.append([
                tc.category,
                tc.tc_id,
                tc.type_of_validation,
                tc.test_objective,
                tc.request_response_field,
                tc.test_steps,
                tc.expected_result,
                tc.mapping_correlation,
                tc.manual_automation
            ])
        
        columns = [
            "Category",
            "Test Case ID", 
            "Type of Validation",
            "Test Objective",
            "Request/Response Field",
            "Test Steps",
            "Expected Result",
            "Mapping Correlation",
            "Manual/Automation"
        ]
        
        df = pd.DataFrame(data, columns=columns)
        
        # Generate filename
        if output_dir is None:
            output_dir = os.getcwd()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"TestCases_{field_name}_{timestamp}.xlsx"
        filepath = os.path.join(output_dir, filename)
        
        # Create Excel with formatting
        ExcelGenerator._create_formatted_excel(df, filepath)
        
        return filepath
    
    @staticmethod
    def _create_formatted_excel(df: pd.DataFrame, filepath: str):
        """Create Excel with professional formatting"""
        wb = Workbook()
        ws = wb.active
        ws.title = "Test Cases"
        
        # Define styles
        header_font = Font(name='Arial', size=11, bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
        header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        
        data_font = Font(name='Arial', size=10)
        data_alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
        
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Add headers
        for col, header in enumerate(df.columns, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = border
        
        # Add data
        for row_idx, row in enumerate(df.itertuples(index=False), 2):
            for col_idx, value in enumerate(row, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=str(value))
                cell.font = data_font
                cell.alignment = data_alignment
                cell.border = border
                
                # Color coding for validation types
                if col_idx == 3:  # Type of Validation column
                    if 'positive' in str(value).lower():
                        cell.fill = PatternFill(start_color='E6F3E6', end_color='E6F3E6', fill_type='solid')
                    elif 'negative' in str(value).lower():
                        cell.fill = PatternFill(start_color='FFE6E6', end_color='FFE6E6', fill_type='solid')
        
        # Auto-adjust column widths
        column_widths = [15, 12, 25, 40, 20, 40, 30, 25, 15]
        for col, width in enumerate(column_widths, 1):
            ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width
        
        # Set row height for header
        ws.row_dimensions[1].height = 30
        
        # Freeze header row
        ws.freeze_panes = 'A2'
        
        wb.save(filepath)

class TestObjectiveGenerator:
    def __init__(self, api_key: str, api_secret: str, base_url: str):
        self.client = FiservAI.FiservAI(api_key, api_secret, base_url=base_url, temperature=0.2)
        self.test_manager = TestCaseManager()
        
    def create_comprehensive_prompt(self, field_metadata: Dict[str, Any], java_code_context: str = "") -> str:
        """Create a detailed, comprehensive prompt for test objective generation with exact 9-column format."""
        
        prompt = """You are an expert QA test objectives generator for ESF (Enterprise Service Framework) APIs. 
Your role is to generate comprehensive, realistic, and detailed test objectives based STRICTLY on the provided field metadata and Java code context.

IMPORTANT CONSTRAINTS:
1. Base your test objectives ONLY on the provided metadata and code
2. Do NOT make assumptions about validation rules not explicitly shown in the code
3. If validation logic is unclear from the code, ASK specific questions instead of assuming
4. Focus on what you can definitively determine from the provided information
5. Generate multiple test cases covering different scenarios when the code shows multiple validation paths

OUTPUT FORMAT - EXACTLY 9 COLUMNS (tab-separated):
Category | Test Case ID | Type of Validation | Test Objective | Request/Response Field | Test Steps | Expected Result | Mapping Correlation | Manual/Automation

COLUMN DEFINITIONS:
- Category: Always "Functional"
- Test Case ID: Leave blank (will be auto-assigned)
- Type of Validation: Must be one of: "Business Validation - Positive", "Business Validation - Negative", "Field Validation - Positive", "Field Validation - Negative"
- Test Objective: Clear description of what is being tested
- Request/Response Field: "Request" or "Response"
- Test Steps: Detailed steps to execute the test
- Expected Result: Expected outcome
- Mapping Correlation: Backend xpath from metadata
- Manual/Automation: "Manual" for business validation, "Automation" for field validation

FIELD METADATA PROVIDED:
"""
        
        # Add field metadata in a structured way
        for key, value in field_metadata.items():
            prompt += f"{key}: {value}\n"
        
        if java_code_context:
            prompt += f"""

JAVA CODE CONTEXT PROVIDED:
{java_code_context}

ANALYSIS INSTRUCTIONS:
Based on the Java code above, analyze:
1. What validation rules are explicitly implemented?
2. What data types and constraints are enforced?
3. What error conditions are handled?
4. What are the success scenarios?
5. Are there any business logic rules visible in the code?

Generate test cases for each distinct validation path you can identify in the code.
"""
        else:
            prompt += """

NO JAVA CODE CONTEXT PROVIDED.
Generate basic test objectives based only on the field metadata above.
"""
        
        prompt += """

EXAMPLE OUTPUT (tab-separated, no header row):
Functional		Field Validation - Positive	Verify PostalCode accepts valid 5-digit format	Request	Send request with PostalCode="12345"	Response code 200, PostalCode present in response	PartyRec/PersonPartyInfo/PersonData/Contact/PostAddr/PostalCode	Automation
Functional		Field Validation - Negative	Verify PostalCode rejects invalid format	Request	Send request with PostalCode="INVALID"	Response code 400, validation error message	PartyRec/PersonPartyInfo/PersonData/Contact/PostAddr/PostalCode	Automation
Functional		Business Validation - Positive	Verify PostalCode business rule validation	Request	Send request with valid business scenario	Business rule validation passes	PartyRec/PersonPartyInfo/PersonData/Contact/PostAddr/PostalCode	Manual

CRITICAL: Output ONLY the tab-separated rows. No headers, no explanations, no markdown formatting.
If you need clarification about validation logic, ASK SPECIFIC QUESTIONS instead of generating test cases.
"""
        
        return prompt
    
    def retry_with_stricter_prompt(self, field_metadata: Dict[str, Any], java_code_context: str = "") -> str:
        """Create a stricter prompt when AI doesn't follow format"""
        prompt = self.create_comprehensive_prompt(field_metadata, java_code_context)
        prompt += """

STRICT FORMAT REQUIREMENT:
The previous response was not in the correct format. You MUST respond with ONLY tab-separated lines.
Each line must have exactly 9 columns separated by tabs.
Do NOT include any explanations, headers, or formatting.
Do NOT use markdown or any other formatting.

Example of correct format:
Functional	TC_001	Field Validation - Positive	Test description here	Request	Test steps here	Expected result here	Mapping path here	Automation

Respond with ONLY the test case lines now:
"""
        return prompt
    
    def parse_command(self, user_input: str) -> Tuple[str, List[str]]:
        """Parse user commands for approval/rejection/export"""
        user_input = user_input.lower().strip()
        
        # Export commands
        export_keywords = ['export', 'excel', 'generate excel', 'create spreadsheet', 'save to excel']
        if any(keyword in user_input for keyword in export_keywords):
            return "export", []
        
        # Approval commands
        if user_input.startswith('approve'):
            tc_ids = re.findall(r'tc_\d+', user_input, re.IGNORECASE)
            return "approve", [tc_id.upper() for tc_id in tc_ids]
        
        # Rejection commands  
        if user_input.startswith('reject'):
            tc_ids = re.findall(r'tc_\d+', user_input, re.IGNORECASE)
            return "reject", [tc_id.upper() for tc_id in tc_ids]
        
        # Status command
        if user_input in ['status', 'show status', 'list cases']:
            return "status", []
        
        return "conversation", []

def main():
    # Load FiservAI credentials from environment
    API_KEY = os.getenv("API_KEY")
    API_SECRET = os.getenv("API_SECRET")
    BASE_URL = os.getenv("BASE_URL")
    
    if not all([API_KEY, API_SECRET, BASE_URL]):
        print("Error: Missing required environment variables (API_KEY, API_SECRET, BASE_URL)")
        return
    
    generator = TestObjectiveGenerator(API_KEY, API_SECRET, BASE_URL)
    
    # Get field metadata
    hardcoded_field = "PartyRec/PersonPartyInfo/PersonData/Contact/PostAddr/PostalCode"
    fields_metadata = get_xpath_fields(
        "PartyInq-PRM.xlsm",
        with_metadata=True,
        target_xpath=hardcoded_field
    )
    
    if not fields_metadata:
        print(f"Field '{hardcoded_field}' not found in mapping sheet.")
        return
    
    field = fields_metadata[0]
    field_name = hardcoded_field.split('/')[-1]  # Use for file naming
    print(f"[INFO] Field metadata loaded: {field.get('field_name', 'Unknown')}")
    
    # Get Java source directory
    src_dir = input("Enter path to Java source directory: ").strip()
    if not os.path.isdir(src_dir):
        print(f"Source directory '{src_dir}' does not exist.")
        return
    
    print(f"[INFO] Analyzing Java source directory: {src_dir}")
    
    # Extract relevant Java code
    field_last = hardcoded_field.split('/')[-1]
    field_keywords = [field_last]
    
    backend_xpath = field.get('backend_xpath')
    if backend_xpath and isinstance(backend_xpath, str):
        backend_segments = [seg for seg in backend_xpath.split('/') if seg]
        backend_last = backend_segments[-1] if backend_segments else None
        if backend_last:
            field_keywords.append(backend_last)
    
    print(f"[INFO] Searching for keywords: {field_keywords}")
    
    # Java code extraction with user options
    print("\nJava Code Extraction Options:")
    print("1. Basic (keyword methods only)")
    print("2. Include direct callers/callees (depth 1)")  
    print("3. Include indirect relationships (depth 2)")
    
    choice = input("Select option (1-3, default 2): ").strip() or "2"
    
    if choice == "1":
        java_code_blocks = extract_java_code_blocks_with_cross_references(
            src_dir, field_keywords, max_depth=0
        )
    elif choice == "3":
        java_code_blocks = extract_java_code_blocks_with_cross_references(
            src_dir, field_keywords, max_depth=2, include_callers=True, include_callees=True
        )
    else:  # Default to option 2
        java_code_blocks = extract_java_code_blocks_with_cross_references(
            src_dir, field_keywords, max_depth=1, include_callers=True, include_callees=True
        )
    
    # Combine all code context
    code_context = ""
    total_methods = 0
    
    for file, snippets in java_code_blocks.items():
        total_methods += len(snippets)
        for snip in snippets:
            block = f"\nFile: {file}\n--- Relevant Method ---\n{snip}\n"
            code_context += block
    
    print(f"[INFO] Found {len(java_code_blocks)} files with {total_methods} relevant methods")
    
    # Initialize conversation manager
    convo_mgr = SimpleConversationManager(50)
    
    print("\n" + "="*80)
    print("AGENTIC TEST OBJECTIVE GENERATOR")
    print("Commands: 'approve TC_001 TC_003' - approve test cases")
    print("          'reject TC_002' - reject test cases") 
    print("          'export' - generate Excel file")
    print("          'status' - show test case status")
    print("          'clear' - reset, 'exit' - quit")
    print("="*80)
    
    # Generate initial comprehensive test objectives
    print("\n[INFO] Generating initial test objectives...\n")
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            if attempt == 0:
                initial_prompt = generator.create_comprehensive_prompt(field, code_context)
            else:
                print(f"[INFO] Retrying with stricter prompt (attempt {attempt + 1})")
                initial_prompt = generator.retry_with_stricter_prompt(field, code_context)
            
            response = generator.client.chat_completion(initial_prompt)
            content = response.choices[0].message.content.strip()
            
            # Try to parse test cases
            new_tc_ids = generator.test_manager.parse_and_add_test_cases(content)
            
            if new_tc_ids:
                print("AI GENERATED TEST OBJECTIVES:")
                print("-" * 60)
                
                for tc_id in new_tc_ids:
                    tc = generator.test_manager.test_cases[tc_id]
                    print(f"{tc.tc_id}: {tc.test_objective}")
                
                print(f"\n[INFO] Generated {len(new_tc_ids)} test cases")
                print("-" * 60)
                convo_mgr.add_turn("[initial_generation]", content)
                break
            else:
                if attempt == max_retries - 1:
                    print("[ERROR] Could not parse test cases after retries. Showing raw response:")
                    print(content)
                    
        except Exception as e:
            print(f"[ERROR] Failed to generate test objectives: {e}")
            if attempt == max_retries - 1:
                return
    
    # Interactive session
    while True:
        user_input = input("\nYour input: ").strip()
        
        if user_input.lower() == "exit":
            print("Exiting test objective generator.")
            break
            
        if user_input.lower() == "clear":
            convo_mgr.clear()
            generator.test_manager = TestCaseManager()  # Reset test manager
            print("Chat history and test cases cleared.")
            continue
        
        # Parse commands
        command, tc_ids = generator.parse_command(user_input)
        
        if command == "approve":
            if tc_ids:
                approved, not_found = generator.test_manager.approve_test_cases(tc_ids)
                if approved:
                    print(f"✅ Approved: {', '.join(approved)}")
                if not_found:
                    print(f"❌ Not found: {', '.join(not_found)}")
            else:
                print("No valid test case IDs found. Use format: approve TC_001 TC_003")
                
        elif command == "reject":
            if tc_ids:
                rejected, not_found = generator.test_manager.reject_test_cases(tc_ids)
                if rejected:
                    print(f"🗑️ Rejected and removed: {', '.join(rejected)}")
                    print("📝 Test case IDs have been reassigned sequentially")
                if not_found:
                    print(f"❌ Not found: {', '.join(not_found)}")
            else:
                print("No valid test case IDs found. Use format: reject TC_001 TC_003")
                
        elif command == "status":
            all_cases = generator.test_manager.get_all_cases()
            if all_cases:
                print("\n📊 TEST CASE STATUS:")
                print("-" * 60)
                for tc in all_cases:
                    status_icon = "✅" if tc.status == "approved" else "📝"
                    print(f"{status_icon} {tc.tc_id}: {tc.test_objective[:60]}...")
                
                summary = generator.test_manager.get_status_summary()
                print(f"\n📈 Summary: {summary['approved']} approved, {summary['draft']} draft")
            else:
                print("No test cases generated yet.")
                
        elif command == "export":
            approved_cases = generator.test_manager.get_approved_cases()
            if not approved_cases:
                print("❌ No approved test cases to export. Please approve some test cases first.")
                continue
            
            # Confirmation
            print(f"\n📤 EXPORT CONFIRMATION:")
            print(f"Export {len(approved_cases)} approved test cases to Excel?")
            for tc in approved_cases:
                print(f"  • {tc.tc_id}: {tc.test_objective[:50]}...")
            
            confirm = input("\nProceed with export? (y/n): ").strip().lower()
            if confirm == 'y':
                try:
                    filepath = ExcelGenerator.generate_excel(approved_cases, field_name)
                    print(f"✅ Excel file generated successfully: {filepath}")
                except Exception as e:
                    print(f"❌ Error generating Excel: {e}")
            else:
                print("Export cancelled.")
                
        else:
            # Handle regular conversation
            if not user_input:
                continue
                
            try:
                conversation = convo_mgr.get_conversation()
                
                # Create follow-up prompt with conversation context
                follow_up_prompt = generator.create_comprehensive_prompt(field, code_context)
                follow_up_prompt += f"\n\nPrevious conversation context:\n"
                
                for turn in conversation[-4:]:  # Last 4 turns
                    role = turn.get('role', 'unknown')
                    content = turn.get('content', '')[:200] + "..." if len(turn.get('content', '')) > 200 else turn.get('content', '')
                    follow_up_prompt += f"{role.upper()}: {content}\n"
                
                follow_up_prompt += f"\nUser: {user_input}\n\nRespond with test cases in the exact 9-column tab-separated format, or ask specific questions:"
                
                response = generator.client.chat_completion(follow_up_prompt)
                content = response.choices[0].message.content.strip()
                
                # Try to parse new test cases
                new_tc_ids = generator.test_manager.parse_and_add_test_cases(content)
                
                if new_tc_ids:
                    print(f"\n🆕 GENERATED {len(new_tc_ids)} NEW TEST CASES:")
                    print("-" * 40)
                    for tc_id in new_tc_ids:
                        tc = generator.test_manager.test_cases[tc_id]
                        print(f"{tc.tc_id}: {tc.test_objective}")
                else:
                    print(f"\nAI Response:")
                    print("-" * 40)
                    print(content)
                
                print("-" * 40)
                convo_mgr.add_turn(user_input, content)
                
            except Exception as e:
                print(f"[ERROR] Failed to process input: {e}")

if __name__ == "__main__":
    main()
