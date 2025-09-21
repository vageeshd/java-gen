"""
Complete Test Case Modification Workflow Example

This example shows how the enhanced system handles specific test case modifications
"""

# Initialize the enhanced generator
generator = TestObjectiveGeneratorCore(client, test_manager, src_dir, mapping_file, conversation_manager)

# Example 1: User wants to modify a specific test case
field_metadata = {
    'field_name': 'PostalCode',
    'backend_xpath': '/customer/address/postalCode',
    'description': 'Customer postal code validation'
}

# First, generate some initial test cases
generator.generate_for_field(field_metadata)

# Display current test cases
current_cases = test_manager.get_field_test_cases('PostalCode')
print("=== INITIAL TEST CASES ===")
for case in current_cases:
    print(f"{case['Test Case ID']}: {case['Test Objective']}")

# Example 2: User provides feedback to modify a specific test case
user_feedback_1 = "Change TC_001 to test Canadian postal codes instead of just any postal code"

result = generator.process_user_feedback(user_feedback_1, field_metadata)
print(f"\n=== USER FEEDBACK RESULT ===")
print(f"Response: {result['response']}")
print(f"Action taken: {result['action_taken']}")

if result['action_taken'] == 'created_modifications':
    # Show pending modifications
    pending_mods = generator.get_pending_modifications('PostalCode')
    print(f"\n=== PENDING MODIFICATIONS ===")
    
    for mod in pending_mods:
        temp_tc_id = mod['temp_tc_id']
        original_tc_id = mod['original_tc_id']
        
        # Show detailed comparison
        print(generator.show_modification_comparison(temp_tc_id))
        
        # User can now approve or reject
        # Simulate user approval
        approval_result = generator.approve_modification(temp_tc_id)
        print(f"\nApproval result: {approval_result['message']}")

# Example 3: User wants to modify multiple test cases
user_feedback_2 = "Update all negative test cases to include boundary testing"

result2 = generator.process_user_feedback(user_feedback_2, field_metadata)
print(f"\n=== MULTIPLE MODIFICATION RESULT ===")
print(f"Response: {result2['response']}")

# Example 4: User asks about a specific test case (question, not modification)
user_question = "What does TC_002 validate exactly?"

result3 = generator.process_user_feedback(user_question, field_metadata)
print(f"\n=== QUESTION RESULT ===")
print(f"Is question: {result3['is_question']}")
print(f"Response: {result3['response']}")
print(f"New test cases generated: {len(result3.get('new_test_cases', []))}")

# Example 5: User provides vague modification request
user_feedback_3 = "Make the first test better"

result4 = generator.process_user_feedback(user_feedback_3, field_metadata)
print(f"\n=== VAGUE MODIFICATION RESULT ===")
print(f"Response: {result4['response']}")

# Example 6: Complete workflow with approval/rejection
def complete_modification_workflow():
    """Demonstrate complete modification workflow"""
    
    # User wants to modify test case
    feedback = "Change TC_001 test steps to be more detailed and include data validation"
    result = generator.process_user_feedback(feedback, field_metadata)
    
    if result.get('modifications_created'):
        modification_info = result['modifications_created'][0]
        temp_tc_id = modification_info['temp_tc_id']
        original_tc_id = modification_info['original_tc_id']
        
        print(f"\n=== MODIFICATION WORKFLOW ===")
        print(f"Original: {original_tc_id}")
        print(f"Modified: {temp_tc_id}")
        
        # Show comparison
        comparison = generator.show_modification_comparison(temp_tc_id)
        print(comparison)
        
        # User decides whether to approve
        user_decision = "approve"  # This would come from user input
        
        if user_decision.lower() == "approve":
            approval_result = generator.approve_modification(temp_tc_id)
            print(f"✅ {approval_result['message']}")
            
            # Verify the original test case was updated
            updated_case = test_manager.get_test_case_by_id(original_tc_id)
            print(f"Updated test case: {updated_case['Test Objective']}")
            
        elif user_decision.lower() == "reject":
            rejection_result = generator.reject_modification(temp_tc_id)
            print(f"❌ {rejection_result['message']}")
            
            # Original test case remains unchanged
            original_case = test_manager.get_test_case_by_id(original_tc_id)
            print(f"Original test case unchanged: {original_case['Test Objective']}")

# Run the complete workflow
complete_modification_workflow()

# Example 7: Handle different ways users might reference test cases
test_case_references = [
    "Modify TC_001 to test different scenarios",           # Direct ID
    "Change the first test case to include edge cases",   # Position reference
    "Update test case 2 with better validation",         # Numbered reference
    "Fix the positive validation test",                   # Content reference
    "Improve all the manual tests",                       # Category reference
]

print(f"\n=== TEST CASE REFERENCE HANDLING ===")
for ref in test_case_references:
    result = generator.process_user_feedback(ref, field_metadata)
    print(f"Input: {ref}")
    print(f"Action: {result['action_taken']}")
    print(f"Response: {result['response'][:100]}...")
    print("---")

# Example 8: Batch modification approval
def batch_modification_handling():
    """Handle multiple pending modifications"""
    
    # Generate several modifications
    modifications = [
        "Change TC_001 to test Canadian postal codes",
        "Update TC_002 to include format validation", 
        "Modify TC_003 to test international formats"
    ]
    
    for mod_request in modifications:
        generator.process_user_feedback(mod_request, field_metadata)
    
    # Get all pending modifications
    pending_mods = generator.get_pending_modifications('PostalCode')
    print(f"\n=== BATCH MODIFICATION HANDLING ===")
    print(f"Pending modifications: {len(pending_mods)}")
    
    # User can approve/reject each one
    for mod in pending_mods:
        temp_tc_id = mod['temp_tc_id']
        original_tc_id = mod['original_tc_id']
        reason = mod['reason']
        
        print(f"\nReviewing: {original_tc_id} -> {temp_tc_id}")
        print(f"Reason: {reason}")
        
        # Simulate user decision (in real app, this would be user input)
        decision = "approve"  # or "reject"
        
        if decision == "approve":
            result = generator.approve_modification(temp_tc_id)
            print(f"✅ Approved: {result['message']}")
        else:
            result = generator.reject_modification(temp_tc_id) 
            print(f"❌ Rejected: {result['message']}")

# Run batch handling
batch_modification_handling()

# Example 9: Error handling scenarios
error_scenarios = [
    "Modify TC_999 to test something",        # Non-existent test case
    "Change the test case",                   # No specific reference
    "Update TC_001",                          # No modification details
]

print(f"\n=== ERROR HANDLING ===")
for scenario in error_scenarios:
    result = generator.process_user_feedback(scenario, field_metadata)
    print(f"Input: {scenario}")
    print(f"Response: {result['response']}")
    print("---")

# Example 10: Integration with existing workflow
def integrated_workflow():
    """Show how modification fits into existing workflow"""
    
    # Standard field generation
    generator.generate_for_field(field_metadata)
    
    # User reviews and wants modifications
    user_inputs = [
        "What does TC_001 test?",                    # Question
        "Change TC_001 to be more specific",        # Modification
        "Add more negative test cases",             # Addition  
        "Approve the modified TC_001",              # Approval
        "Complete this field"                       # Field completion
    ]
    
    print(f"\n=== INTEGRATED WORKFLOW ===")
    for user_input in user_inputs:
        result = generator.process_user_feedback(user_input, field_metadata)
        print(f"User: {user_input}")
        print(f"AI: {result['response']}")
        
        # Handle any pending modifications
        if result.get('modifications_created'):
            for mod_info in result['modifications_created']:
                temp_tc_id = mod_info['temp_tc_id']
                # Auto-approve for demo (in real app, wait for user decision)
                generator.approve_modification(temp_tc_id)
                print(f"  ✅ Auto-approved modification")
        
        print("---")
    
    # Complete the field
    if generator.is_field_ready_for_completion():
        completion_result = generator.complete_current_field()
        print(f"Field completed: {completion_result['completed_field']}")

# Run integrated workflow
integrated_workflow()

# Example 11: Session summary with modifications
session_summary = generator.get_session_summary()
print(f"\n=== SESSION SUMMARY ===")
print(f"Fields processed: {session_summary['total_fields_processed']}")
print(f"Questions answered: {session_summary['session_stats']['questions_answered']}")
print(f"Feedback processed: {session_summary['session_stats']['feedback_processed']}")
print(f"Test cases generated: {session_summary['session_stats']['total_test_cases_generated']}")

# Example 12: Export with modifications
if session_summary['completed_fields']:
    export_success = generator.export_all_completed_fields("test_cases_with_modifications.xlsx")
    print(f"\nExport successful: {export_success}")

print("\n=== WORKFLOW COMPLETE ===")
print("The system now handles:")
print("✅ Specific test case modifications")
print("✅ Approval/rejection workflow")
print("✅ Questions vs generation requests")
print("✅ Multiple reference formats") 
print("✅ Batch modification handling")
print("✅ Error scenarios")
print("✅ Integration with existing workflow")