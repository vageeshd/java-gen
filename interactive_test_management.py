# Enhanced core/testcase_manager.py - Add approval functionality

import pandas as pd
import os
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

class TestCaseManager:
    def __init__(self):
        self.test_cases: List[Dict[str, Any]] = []
        self.counter = 1
        self.parse_errors = []
        # Add approval tracking
        self.approved_cases: Set[str] = set()  # Set of approved TC IDs
        self.rejected_cases: Set[str] = set()  # Set of rejected TC IDs
        
    def parse_and_add_test_cases(self, raw_text: str, default_mapping: str = "") -> List[str]:
        """Parse raw AI output and return list of new TC IDs for user review"""
        
        if not raw_text or not raw_text.strip():
            print("[WARN] Empty input provided for parsing")
            return []
        
        initial_count = len(self.test_cases)
        new_tc_ids = []
        lines = raw_text.strip().splitlines()
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # Skip empty lines, headers, and obvious non-data lines
            if (not line or 
                line.startswith('Category') or 
                line.startswith('---') or 
                line.startswith('===') or
                'Test Case ID' in line or
                line.startswith('Sorry') or
                line.startswith('I don\'t') or
                len(line) < 10):
                continue
            
            try:
                # Try tab separation first
                parts = line.split('\t')
                
                # Fallback to pipe separation if not enough parts
                if len(parts) < 6:
                    parts = line.split('|')
                
                if len(parts) < 6:
                    continue
                
                # Clean and pad parts
                parts = [p.strip() for p in parts]
                while len(parts) < 9:
                    parts.append("")
                
                # Validate required fields
                objective = parts[3]
                steps = parts[5]
                
                if not objective or len(objective.strip()) < 5:
                    continue
                if not steps or len(steps.strip()) < 5:
                    continue
                
                # Auto-generate ID
                tc_id = f"TC_{self.counter:03d}"
                self.counter += 1
                
                # Extract and validate components
                category = parts[0] or "Functional"
                val_type = self._normalize_validation_type(parts[2])
                req_field = parts[4] or "Request"
                expected = parts[6] or "Expected result"
                mapping = parts[7] or default_mapping
                mode = self._determine_automation_mode(val_type, parts[8])
                
                case = {
                    "Category": category,
                    "Test Case ID": tc_id,
                    "Type of Validation": val_type,
                    "Test Objective": objective,
                    "Request/Response Field": req_field,
                    "Test Steps": steps,
                    "Expected Result": expected,
                    "Mapping Correlation": mapping,
                    "Manual/Automation": mode,
                    "Status": "pending"  # Add status tracking
                }
                
                self.test_cases.append(case)
                new_tc_ids.append(tc_id)
                
            except Exception as e:
                error_msg = f"Line {line_num}: Parse error - {str(e)}"
                self.parse_errors.append(error_msg)
                continue
        
        added_count = len(new_tc_ids)
        if added_count > 0:
            print(f"[INFO] Successfully parsed {added_count} test cases")
        
        return new_tc_ids
    
    def _normalize_validation_type(self, val_type: str) -> str:
        """Normalize validation type to standard values"""
        if not val_type:
            return "Field Validation - Positive"
        
        val_type_lower = val_type.lower()
        if "positive" in val_type_lower and "field" in val_type_lower:
            return "Field Validation - Positive"
        elif "negative" in val_type_lower and "field" in val_type_lower:
            return "Field Validation - Negative"
        elif "positive" in val_type_lower and "business" in val_type_lower:
            return "Business Validation - Positive"
        elif "negative" in val_type_lower and "business" in val_type_lower:
            return "Business Validation - Negative"
        else:
            return "Field Validation - Positive"
    
    def _determine_automation_mode(self, val_type: str, provided_mode: str) -> str:
        """Determine automation mode based on validation type"""
        if provided_mode and provided_mode.strip():
            return provided_mode.strip()
        
        if "Business" in val_type:
            return "Manual"
        else:
            return "Automation"
    
    def approve_test_cases(self, tc_ids: List[str]) -> Dict[str, List[str]]:
        """Approve specific test cases"""
        approved = []
        not_found = []
        
        for tc_id in tc_ids:
            # Find the test case
            case = self.get_test_case_by_id(tc_id)
            if case:
                case["Status"] = "approved"
                self.approved_cases.add(tc_id)
                self.rejected_cases.discard(tc_id)  # Remove from rejected if present
                approved.append(tc_id)
            else:
                not_found.append(tc_id)
        
        return {"approved": approved, "not_found": not_found}
    
    def reject_test_cases(self, tc_ids: List[str]) -> Dict[str, List[str]]:
        """Reject specific test cases"""
        rejected = []
        not_found = []
        
        for tc_id in tc_ids:
            case = self.get_test_case_by_id(tc_id)
            if case:
                case["Status"] = "rejected"
                self.rejected_cases.add(tc_id)
                self.approved_cases.discard(tc_id)  # Remove from approved if present
                rejected.append(tc_id)
            else:
                not_found.append(tc_id)
        
        return {"rejected": rejected, "not_found": not_found}
    
    def get_test_case_by_id(self, tc_id: str) -> Optional[Dict[str, Any]]:
        """Get test case by ID"""
        for case in self.test_cases:
            if case.get("Test Case ID") == tc_id:
                return case
        return None
    
    def get_cases_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get test cases by status (pending, approved, rejected)"""
        return [case for case in self.test_cases if case.get("Status") == status]
    
    def get_all_cases(self) -> List[Dict[str, Any]]:
        """Get all stored test cases"""
        return self.test_cases.copy()
    
    def get_approved_cases(self) -> List[Dict[str, Any]]:
        """Get only approved test cases"""
        return self.get_cases_by_status("approved")
    
    def get_pending_cases(self) -> List[Dict[str, Any]]:
        """Get only pending test cases"""
        return self.get_cases_by_status("pending")
    
    def get_status_summary(self) -> Dict[str, int]:
        """Get summary of test case statuses"""
        summary = {"pending": 0, "approved": 0, "rejected": 0}
        for case in self.test_cases:
            status = case.get("Status", "pending")
            summary[status] = summary.get(status, 0) + 1
        return summary
    
    def display_test_cases(self, cases: List[Dict[str, Any]], show_details: bool = True):
        """Display test cases in a readable format"""
        if not cases:
            print("No test cases to display.")
            return
        
        for case in cases:
            tc_id = case.get("Test Case ID", "N/A")
            status = case.get("Status", "pending")
            val_type = case.get("Type of Validation", "N/A")
            objective = case.get("Test Objective", "N/A")
            
            # Status icon
            if status == "approved":
                icon = "✅"
            elif status == "rejected":
                icon = "❌"
            else:
                icon = "📝"
            
            print(f"\n{icon} {tc_id} - {val_type}")
            print(f"    📋 Objective: {objective}")
            
            if show_details:
                steps = case.get("Test Steps", "N/A")
                expected = case.get("Expected Result", "N/A")
                mode = case.get("Manual/Automation", "N/A")
                
                print(f"    🔧 Steps: {steps}")
                print(f"    ✅ Expected: {expected}")
                print(f"    🤖 Mode: {mode}")
    
    def export_approved_to_excel(self, out_file: str) -> bool:
        """Export only approved test cases to Excel"""
        approved_cases = self.get_approved_cases()
        
        if not approved_cases:
            print("[ERROR] No approved test cases to export")
            return False
        
        try:
            # Create DataFrame from approved cases only
            df = pd.DataFrame(approved_cases)
            
            # Remove the Status column for export
            if "Status" in df.columns:
                df = df.drop("Status", axis=1)
            
            # Ensure all required columns are present
            required_columns = [
                "Category", "Test Case ID", "Type of Validation", 
                "Test Objective", "Request/Response Field", "Test Steps", 
                "Expected Result", "Mapping Correlation", "Manual/Automation"
            ]
            
            for col in required_columns:
                if col not in df.columns:
                    df[col] = ""
            
            # Reorder columns
            df = df[required_columns]
            
            # Create Excel with formatting
            self._create_formatted_excel(df, out_file)
            
            print(f"[INFO] Exported {len(approved_cases)} approved test cases to {out_file}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Export failed: {str(e)}")
            return False
    
    # ... rest of existing methods stay the same ...
    
    def _create_formatted_excel(self, df: pd.DataFrame, filepath: str):
        """Create Excel with professional formatting (same as before)"""
        # ... existing implementation ...
        pass


# Enhanced complete_agentic_test_generator.py - Interactive mode

def interactive_test_case_mode(generator: TestObjectiveGeneratorCore, field_loader: FieldMetadataLoader) -> bool:
    """Interactive mode with test case approval/rejection workflow"""
    
    print("🎯 INTERACTIVE TEST CASE GENERATOR")
    print("Generate → Review → Approve/Reject → Refine → Export")
    print("=" * 60)
    
    # Load available fields
    try:
        available_fields = field_loader.get_available_fields()
        field_list = sorted(list(available_fields))
        print(f"✅ Loaded {len(field_list)} available fields")
    except Exception as e:
        print(f"❌ Error loading fields: {e}")
        return False
    
    current_field = None
    current_field_metadata = None
    
    while True:
        print(f"\n🎯 INTERACTIVE COMMANDS:")
        print("  📝 Field Selection:")
        print("     • 'select <field_name>' - select field to work on")
        print("     • 'search <keyword>' - search for fields")
        print("     • 'list' - show all fields")
        print("")
        print("  🤖 Test Case Generation:")
        print("     • 'generate' - generate test cases for current field")
        print("     • 'regenerate' - generate more test cases")
        print("     • 'improve <feedback>' - generate improved test cases")
        print("")
        print("  ✅ Test Case Management:")
        print("     • 'show' - show pending test cases")
        print("     • 'show all' - show all test cases with status")
        print("     • 'approve TC_001 TC_003' - approve specific test cases")  
        print("     • 'reject TC_002' - reject specific test cases")
        print("     • 'approve all' - approve all pending cases")
        print("")
        print("  📤 Export & Exit:")
        print("     • 'status' - show approval status summary")
        print("     • 'export' - export approved test cases")
        print("     • 'exit' - quit")
        
        if current_field:
            field_name = current_field.split('/')[-1]
            print(f"\n📍 Current field: {field_name}")
        
        user_input = input(f"\n➤ Enter command: ").strip()
        
        if not user_input:
            continue
            
        # Parse command
        command_parts = user_input.lower().split()
        main_command = command_parts[0] if command_parts else ""
        
        # Exit
        if main_command == "exit":
            break
            
        # Field selection commands
        elif main_command == "select":
            if len(command_parts) < 2:
                print("❌ Usage: select <field_name_or_number>")
                continue
                
            field_identifier = " ".join(command_parts[1:])
            selected_field = find_field(field_identifier, field_list)
            
            if selected_field:
                current_field = selected_field
                print(f"✅ Selected field: {selected_field.split('/')[-1]}")
                
                # Load metadata
                try:
                    current_field_metadata = field_loader.get_field_metadata(selected_field)
                    if current_field_metadata:
                        print("✅ Field metadata loaded")
                    else:
                        print("❌ Could not load field metadata")
                        current_field = None
                except Exception as e:
                    print(f"❌ Error loading field metadata: {e}")
                    current_field = None
            else:
                print(f"❌ Field not found: {field_identifier}")
                
        elif main_command == "search":
            if len(command_parts) < 2:
                print("❌ Usage: search <keyword>")
                continue
                
            keyword = " ".join(command_parts[1:]).lower()
            matches = [f for f in field_list if keyword in f.lower()]
            
            if matches:
                print(f"\n🔍 Found {len(matches)} matches:")
                for i, match in enumerate(matches[:10]):
                    field_name = match.split('/')[-1]
                    print(f"  {i+1:2d}. {field_name}")
                    print(f"       └─ {match}")
                if len(matches) > 10:
                    print(f"  ... and {len(matches) - 10} more")
            else:
                print(f"🔍 No matches found for '{keyword}'")
                
        elif main_command == "list":
            print(f"\n📋 Available fields:")
            for i, field in enumerate(field_list[:20]):
                field_name = field.split('/')[-1]
                print(f"  {i+1:3d}. {field_name}")
            if len(field_list) > 20:
                print(f"  ... and {len(field_list) - 20} more")
                
        # Generation commands
        elif main_command == "generate":
            if not current_field or not current_field_metadata:
                print("❌ No field selected. Use 'select <field_name>' first.")
                continue
                
            print(f"🔄 Generating test cases for {current_field.split('/')[-1]}...")
            success = generator.generate_for_field(current_field_metadata)
            
            if success:
                # Get newly generated cases
                all_cases = generator.test_manager.get_all_cases()
                pending_cases = generator.test_manager.get_pending_cases()
                
                print(f"✅ Generated {len(pending_cases)} new test cases")
                print(f"\n📋 NEW TEST CASES FOR REVIEW:")
                generator.test_manager.display_test_cases(pending_cases[-5:])  # Show last 5
                
                print(f"\n💡 Next steps:")
                print(f"   • Review cases above")
                print(f"   • Use 'approve TC_001 TC_002' to approve")
                print(f"   • Use 'reject TC_003' to reject")
                print(f"   • Use 'improve <feedback>' for better cases")
            else:
                print("❌ Failed to generate test cases")
                
        elif main_command == "regenerate":
            if not current_field or not current_field_metadata:
                print("❌ No field selected. Use 'select <field_name>' first.")
                continue
                
            print(f"🔄 Generating additional test cases for {current_field.split('/')[-1]}...")
            success = generator.generate_for_field(current_field_metadata)
            
            if success:
                pending_cases = generator.test_manager.get_pending_cases()
                print(f"✅ Generated additional test cases")
                print(f"\n📋 ALL PENDING CASES:")
                generator.test_manager.display_test_cases(pending_cases)
            else:
                print("❌ Failed to generate additional test cases")
                
        elif main_command == "improve":
            if not current_field or not current_field_metadata:
                print("❌ No field selected. Use 'select <field_name>' first.")
                continue
                
            if len(command_parts) < 2:
                print("❌ Usage: improve <your feedback>")
                print("Example: improve 'add more negative test cases for invalid formats'")
                continue
            
            feedback = " ".join(command_parts[1:])
            print(f"🔄 Generating improved test cases based on feedback...")
            
            # Create improvement context
            try:
                # This would need to be implemented in TestObjectiveGeneratorCore
                success = generator.generate_with_feedback(current_field_metadata, feedback)
                if success:
                    pending_cases = generator.test_manager.get_pending_cases()
                    print(f"✅ Generated improved test cases")
                    print(f"\n📋 NEW IMPROVED CASES:")
                    generator.test_manager.display_test_cases(pending_cases[-3:])
                else:
                    print("❌ Failed to generate improved test cases")
            except AttributeError:
                print("❌ Improvement feature not yet implemented")
                
        # Approval/rejection commands
        elif main_command == "approve":
            if len(command_parts) < 2:
                print("❌ Usage: approve TC_001 TC_002 OR approve all")
                continue
                
            if command_parts[1] == "all":
                pending_cases = generator.test_manager.get_pending_cases()
                if not pending_cases:
                    print("❌ No pending test cases to approve")
                    continue
                    
                tc_ids = [case["Test Case ID"] for case in pending_cases]
                result = generator.test_manager.approve_test_cases(tc_ids)
                print(f"✅ Approved {len(result['approved'])} test cases")
            else:
                tc_ids = [tc.upper() for tc in command_parts[1:] if tc.upper().startswith('TC_')]
                if not tc_ids:
                    print("❌ No valid test case IDs found")
                    continue
                    
                result = generator.test_manager.approve_test_cases(tc_ids)
                if result["approved"]:
                    print(f"✅ Approved: {', '.join(result['approved'])}")
                if result["not_found"]:
                    print(f"❌ Not found: {', '.join(result['not_found'])}")
                    
        elif main_command == "reject":
            if len(command_parts) < 2:
                print("❌ Usage: reject TC_001 TC_002")
                continue
                
            tc_ids = [tc.upper() for tc in command_parts[1:] if tc.upper().startswith('TC_')]
            if not tc_ids:
                print("❌ No valid test case IDs found")
                continue
                
            result = generator.test_manager.reject_test_cases(tc_ids)
            if result["rejected"]:
                print(f"🗑️ Rejected: {', '.join(result['rejected'])}")
            if result["not_found"]:
                print(f"❌ Not found: {', '.join(result['not_found'])}")
                
        # Display commands
        elif user_input.lower() == "show":
            pending_cases = generator.test_manager.get_pending_cases()
            if pending_cases:
                print(f"\n📝 PENDING TEST CASES ({len(pending_cases)}):")
                generator.test_manager.display_test_cases(pending_cases)
            else:
                print("📝 No pending test cases")
                
        elif user_input.lower() == "show all":
            all_cases = generator.test_manager.get_all_cases()
            if all_cases:
                print(f"\n📊 ALL TEST CASES ({len(all_cases)}):")
                generator.test_manager.display_test_cases(all_cases)
            else:
                print("📊 No test cases generated yet")
                
        elif main_command == "status":
            summary = generator.test_manager.get_status_summary()
            total = sum(summary.values())
            
            if total == 0:
                print("📊 No test cases generated yet")
            else:
                print(f"\n📊 TEST CASE STATUS SUMMARY:")
                print(f"   📝 Pending: {summary['pending']}")
                print(f"   ✅ Approved: {summary['approved']}")
                print(f"   ❌ Rejected: {summary['rejected']}")
                print(f"   📊 Total: {total}")
                
                if summary['approved'] > 0:
                    print(f"\n💡 Ready to export {summary['approved']} approved test cases!")
                    
        elif main_command == "export":
            approved_cases = generator.test_manager.get_approved_cases()
            if not approved_cases:
                print("❌ No approved test cases to export")
                continue
                
            print(f"\n📤 EXPORT CONFIRMATION:")
            print(f"Export {len(approved_cases)} approved test cases?")
            
            for case in approved_cases:
                tc_id = case.get("Test Case ID", "N/A")
                objective = case.get("Test Objective", "N/A")
                print(f"  ✅ {tc_id}: {objective[:50]}...")
            
            confirm = input("\nProceed with export? (Y/n): ").strip().lower()
            if confirm in ['', 'y', 'yes']:
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"approved_test_cases_{timestamp}.xlsx"
                    
                    success = generator.test_manager.export_approved_to_excel(filename)
                    if success:
                        print(f"✅ Exported to: {filename}")
                    else:
                        print("❌ Export failed")
                except Exception as e:
                    print(f"❌ Export error: {e}")
            else:
                print("❌ Export cancelled")
                
        else:
            print(f"❌ Unknown command: {user_input}")
            print("💡 Type a command from the list above")
    
    # Exit logic
    approved_cases = generator.test_manager.get_approved_cases()
    if approved_cases:
        export_choice = input(f"\n📤 Export {len(approved_cases)} approved test cases before exit? (Y/n): ").strip().lower()
        if export_choice in ['', 'y', 'yes']:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"final_approved_cases_{timestamp}.xlsx"
            
            success = generator.test_manager.export_approved_to_excel(filename)
            if success:
                print(f"✅ Final export completed: {filename}")
                return True
    
    return True

def find_field(identifier: str, field_list: List[str]) -> Optional[str]:
    """Find field by name, number, or partial match"""
    
    # Try exact match first
    if identifier in field_list:
        return identifier
    
    # Try number
    if identifier.isdigit():
        index = int(identifier) - 1
        if 0 <= index < len(field_list):
            return field_list[index]
    
    # Try partial match on field name (case insensitive)
    matches = [f for f in field_list if identifier.lower() in f.split('/')[-1].lower()]
    
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        print(f"🔍 Multiple matches found:")
        for i, match in enumerate(matches[:5]):
            field_name = match.split('/')[-1]
            print(f"  {i+1}. {field_name} ({match})")
        print("Please be more specific.")
        return None
    
    return None

# Update main() to use interactive mode
def main():
    # ... existing argument parsing ...
    
    # Change mode selection
    if not args.mode:
        print("🤖 Select Generation Mode:")
        print("  1. Bulk Mode (process all fields → Excel)")
        print("  2. Interactive Mode (select, generate, approve, export)")
        mode_input = input("Choose (1/2): ").strip()
        args.mode = "bulk" if mode_input == "1" else "interactive"
    
    # ... existing validation and setup ...
    
    # Run selected mode
    if args.mode == "bulk":
        success = bulk_mode_with_batch_loading(generator, field_loader, args.out)
    else:  # interactive mode
        success = interactive_test_case_mode(generator, field_loader)
