# Enhanced complete_agentic_test_generator.py with conversation memory

import re
from difflib import SequenceMatcher
from fiserv_ai_utils import SimpleConversationManager

class UserIntentParser:
    """Parse user intent with fuzzy matching and conversational understanding"""
    
    def __init__(self):
        self.intent_patterns = {
            # Field selection intents
            'select_field': [
                r'select (.+)', r'choose (.+)', r'pick (.+)', r'use (.+)',
                r'work on (.+)', r'set field (.+)', r'field (.+)'
            ],
            'search_field': [
                r'search (.+)', r'find (.+)', r'look for (.+)', 
                r'show (.+) fields', r'(.+) fields?'
            ],
            'list_fields': [
                r'list', r'show all', r'all fields', r'what fields', 
                r'available', r'options'
            ],
            
            # Generation intents  
            'generate': [
                r'generate', r'create', r'make', r'build', r'start',
                r'generate tests?', r'create tests?', r'make tests?'
            ],
            'regenerate': [
                r'regenerate', r'more', r'again', r'additional', 
                r'generate more', r'create more', r'more tests?'
            ],
            'improve': [
                r'improve (.+)', r'better (.+)', r'enhance (.+)',
                r'add (.+)', r'include (.+)', r'need (.+)'
            ],
            
            # Management intents
            'approve': [
                r'approve (.+)', r'accept (.+)', r'yes (.+)', r'good (.+)',
                r'keep (.+)', r'ok (.+)', r'fine (.+)', r'approve all'
            ],
            'reject': [
                r'reject (.+)', r'no (.+)', r'bad (.+)', r'remove (.+)',
                r'delete (.+)', r'discard (.+)', r'not (.+)'
            ],
            'show_pending': [
                r'show', r'display', r'review', r'see', r'what',
                r'pending', r'current', r'generated'
            ],
            'show_all': [
                r'show all', r'all cases', r'everything', r'status',
                r'summary', r'what do we have'
            ],
            
            # Export/exit intents
            'export': [
                r'export', r'save', r'download', r'file', r'excel',
                r'finish', r'done', r'complete'
            ],
            'help': [
                r'help', r'what can', r'commands', r'how', r'instructions'
            ],
            'exit': [
                r'exit', r'quit', r'bye', r'goodbye', r'stop', r'end'
            ]
        }
        
        self.tc_id_pattern = r'TC_\d{3}'
        
    def parse_intent(self, user_input: str) -> tuple:
        """Parse user intent and extract parameters"""
        user_input = user_input.strip().lower()
        
        if not user_input:
            return 'unknown', {}
        
        # Extract test case IDs first
        tc_ids = re.findall(self.tc_id_pattern, user_input.upper())
        
        # Try exact pattern matches
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, user_input)
                if match:
                    params = {'tc_ids': tc_ids}
                    if match.groups():
                        params['target'] = match.group(1).strip()
                    return intent, params
        
        # Fuzzy matching for common typos/variations
        best_intent = self._fuzzy_match_intent(user_input)
        if best_intent:
            return best_intent, {'tc_ids': tc_ids, 'target': user_input}
        
        return 'unknown', {'raw_input': user_input, 'tc_ids': tc_ids}
    
    def _fuzzy_match_intent(self, user_input: str) -> str:
        """Use fuzzy matching for intent recognition"""
        intent_keywords = {
            'generate': ['generate', 'create', 'make', 'build'],
            'approve': ['approve', 'accept', 'yes', 'good', 'keep'],
            'reject': ['reject', 'no', 'bad', 'remove', 'delete'],
            'export': ['export', 'save', 'download', 'excel'],
            'show_pending': ['show', 'display', 'review', 'see'],
            'help': ['help', 'commands', 'how'],
            'exit': ['exit', 'quit', 'bye', 'stop']
        }
        
        best_match = None
        best_score = 0.6  # Minimum similarity threshold
        
        for intent, keywords in intent_keywords.items():
            for keyword in keywords:
                similarity = SequenceMatcher(None, user_input, keyword).ratio()
                if similarity > best_score:
                    best_score = similarity
                    best_match = intent
        
        return best_match

class ConversationalSession:
    """Manage conversational session with memory and context"""
    
    def __init__(self, conversation_manager: SimpleConversationManager):
        self.convo_mgr = conversation_manager
        self.current_field = None
        self.current_field_metadata = None
        self.session_context = {
            'generated_count': 0,
            'approved_count': 0,
            'rejected_count': 0,
            'last_action': None,
            'help_shown': False
        }
        
    def add_interaction(self, user_input: str, system_response: str, action: str = None):
        """Add interaction to conversation history"""
        self.convo_mgr.add_turn(user_input, system_response)
        if action:
            self.session_context['last_action'] = action
    
    def get_context_for_generation(self) -> str:
        """Get conversation context for AI generation"""
        context = ""
        
        if self.current_field_metadata:
            context += f"Current field: {self.current_field_metadata.get('field_name', 'Unknown')}\n"
            context += f"Field details: {self.current_field_metadata}\n\n"
        
        # Add recent conversation
        conversation = self.convo_mgr.get_conversation()
        if conversation:
            context += "Recent conversation:\n"
            for turn in conversation[-3:]:  # Last 3 turns
                role = turn.get('role', 'unknown')
                content = turn.get('content', '')[:100] + "..." if len(turn.get('content', '')) > 100 else turn.get('content', '')
                context += f"{role.upper()}: {content}\n"
        
        return context
    
    def update_stats(self, action: str, count: int = 1):
        """Update session statistics"""
        if action in self.session_context:
            self.session_context[action] += count

def conversational_interactive_mode(generator: TestObjectiveGeneratorCore, field_loader: FieldMetadataLoader) -> bool:
    """Conversational interactive mode with memory and natural language"""
    
    # Initialize conversation components
    convo_mgr = SimpleConversationManager(50)  # Keep 50 turns of context
    intent_parser = UserIntentParser()
    session = ConversationalSession(convo_mgr)
    
    print("🎯 CONVERSATIONAL TEST CASE GENERATOR")
    print("Talk to me naturally! I'll understand what you want to do.")
    print("=" * 60)
    
    # Load available fields
    try:
        available_fields = field_loader.get_available_fields()
        field_list = sorted(list(available_fields))
        print(f"✅ I have access to {len(field_list)} fields from your mapping file.")
    except Exception as e:
        print(f"❌ Error loading fields: {e}")
        return False
    
    # Show quick start
    print(f"\n💡 Quick Start:")
    print(f"   • Say 'search address' to find address-related fields")
    print(f"   • Say 'select PostalCode' to work on a specific field")
    print(f"   • Say 'help' anytime for more commands")
    print(f"   • Type naturally - I'll understand!")
    
    while True:
        # Show context if available
        if session.current_field:
            field_name = session.current_field.split('/')[-1]
            stats = session.session_context
            status_text = f"📍 Working on: {field_name}"
            if stats['generated_count'] > 0:
                status_text += f" | Generated: {stats['generated_count']} | Approved: {stats['approved_count']}"
            print(f"\n{status_text}")
        
        user_input = input(f"\n💬 You: ").strip()
        
        if not user_input:
            continue
        
        # Parse user intent
        intent, params = intent_parser.parse_intent(user_input)
        
        # Handle intents
        if intent == 'exit':
            response = "👋 Goodbye! Let me check if you want to export your work..."
            print(f"🤖 Assistant: {response}")
            session.add_interaction(user_input, response, 'exit')
            break
            
        elif intent == 'help':
            if not session.session_context['help_shown']:
                response = show_help()
                session.session_context['help_shown'] = True
            else:
                response = show_quick_help()
            print(f"🤖 Assistant: {response}")
            session.add_interaction(user_input, response, 'help')
            
        elif intent == 'list_fields':
            response = handle_list_fields(field_list)
            print(f"🤖 Assistant: {response}")
            session.add_interaction(user_input, response, 'list')
            
        elif intent == 'search_field':
            keyword = params.get('target', '')
            response = handle_search_fields(keyword, field_list)
            print(f"🤖 Assistant: {response}")
            session.add_interaction(user_input, response, 'search')
            
        elif intent == 'select_field':
            target = params.get('target', '')
            selected_field, response = handle_select_field(target, field_list, field_loader)
            print(f"🤖 Assistant: {response}")
            
            if selected_field:
                session.current_field = selected_field
                session.current_field_metadata = field_loader.get_field_metadata(selected_field)
            
            session.add_interaction(user_input, response, 'select')
            
        elif intent == 'generate':
            if not session.current_field_metadata:
                response = "❌ I need you to select a field first. Try: 'search address' or 'select PostalCode'"
                print(f"🤖 Assistant: {response}")
                session.add_interaction(user_input, response, 'generate_failed')
                continue
            
            response, success = handle_generate(generator, session)
            print(f"🤖 Assistant: {response}")
            
            if success:
                session.update_stats('generated_count', 1)
                
            session.add_interaction(user_input, response, 'generate')
            
        elif intent == 'regenerate':
            if not session.current_field_metadata:
                response = "❌ I need a field selected first. What field should I work on?"
                print(f"🤖 Assistant: {response}")
                session.add_interaction(user_input, response, 'regenerate_failed')
                continue
            
            response, success = handle_generate(generator, session, is_regenerate=True)
            print(f"🤖 Assistant: {response}")
            
            if success:
                session.update_stats('generated_count', 1)
                
            session.add_interaction(user_input, response, 'regenerate')
            
        elif intent == 'improve':
            if not session.current_field_metadata:
                response = "❌ I need a field selected first to improve test cases."
                print(f"🤖 Assistant: {response}")
                session.add_interaction(user_input, response, 'improve_failed')
                continue
            
            feedback = params.get('target', user_input)
            response = handle_improve(generator, session, feedback)
            print(f"🤖 Assistant: {response}")
            session.add_interaction(user_input, response, 'improve')
            
        elif intent == 'approve':
            tc_ids = params.get('tc_ids', [])
            target = params.get('target', '')
            
            if 'all' in target or 'all' in user_input.lower():
                response = handle_approve_all(generator, session)
            elif tc_ids:
                response = handle_approve_specific(generator, session, tc_ids)
            else:
                response = "❌ Which test cases should I approve? Say 'approve TC_001 TC_003' or 'approve all'"
            
            print(f"🤖 Assistant: {response}")
            session.add_interaction(user_input, response, 'approve')
            
        elif intent == 'reject':
            tc_ids = params.get('tc_ids', [])
            
            if tc_ids:
                response = handle_reject_specific(generator, session, tc_ids)
            else:
                response = "❌ Which test cases should I reject? Say 'reject TC_002'"
            
            print(f"🤖 Assistant: {response}")
            session.add_interaction(user_input, response, 'reject')
            
        elif intent == 'show_pending':
            response = handle_show_pending(generator)
            print(f"🤖 Assistant: {response}")
            session.add_interaction(user_input, response, 'show')
            
        elif intent == 'show_all':
            response = handle_show_all(generator)
            print(f"🤖 Assistant: {response}")
            session.add_interaction(user_input, response, 'show_all')
            
        elif intent == 'export':
            response = handle_export(generator)
            print(f"🤖 Assistant: {response}")
            session.add_interaction(user_input, response, 'export')
            
        else:
            # Unknown intent - be conversational
            response = handle_unknown_intent(user_input, session)
            print(f"🤖 Assistant: {response}")
            session.add_interaction(user_input, response, 'unknown')
    
    # Exit flow with auto-export
    return handle_exit_flow(generator)

def show_help() -> str:
    """Show comprehensive help"""
    return """📚 I understand natural language! Here's what I can help you with:

🔍 **Finding & Selecting Fields:**
   • "search address" - find fields containing 'address'
   • "show me all fields" - list available fields
   • "select PostalCode" - work on PostalCode field
   • "use the email field" - work on email field

🤖 **Generating Test Cases:**
   • "generate test cases" - create tests for current field
   • "make more tests" - generate additional tests
   • "improve with edge cases" - generate better tests

✅ **Managing Test Cases:**
   • "show me what we have" - see pending test cases
   • "approve TC_001 and TC_003" - approve specific tests
   • "reject TC_002" - reject unwanted tests  
   • "approve all the good ones" - approve all pending

📤 **Finishing Up:**
   • "save to excel" - export approved test cases
   • "we're done" - finish and export

Just talk naturally - I'll understand! 😊"""

def show_quick_help() -> str:
    """Show condensed help"""
    return """💡 Quick reminders:
• Search/select fields: "search address", "select PostalCode"
• Generate: "create tests", "make more tests"  
• Manage: "approve TC_001", "reject TC_002", "show pending"
• Export: "save to excel", "export approved cases"
• Natural language works - just tell me what you want! 😊"""

def handle_list_fields(field_list: list) -> str:
    """Handle listing fields"""
    if not field_list:
        return "❌ No fields available."
    
    response = f"📋 I have {len(field_list)} fields available. Here are some:\n\n"
    
    for i, field in enumerate(field_list[:10]):
        field_name = field.split('/')[-1]
        response += f"   {i+1:2d}. {field_name}\n"
    
    if len(field_list) > 10:
        response += f"\n... and {len(field_list) - 10} more. Try 'search <keyword>' to find specific ones!"
    
    response += f"\n💡 Say 'select <field_name>' to work on one."
    return response

def handle_search_fields(keyword: str, field_list: list) -> str:
    """Handle field search"""
    if not keyword:
        return "🔍 What should I search for? Try: 'search address' or 'search email'"
    
    matches = [f for f in field_list if keyword.lower() in f.lower()]
    
    if not matches:
        return f"🔍 No fields found containing '{keyword}'. Try a different keyword."
    
    response = f"🔍 Found {len(matches)} fields containing '{keyword}':\n\n"
    
    for i, match in enumerate(matches[:10]):
        field_name = match.split('/')[-1]
        response += f"   {i+1}. {field_name}\n"
    
    if len(matches) > 10:
        response += f"\n... and {len(matches) - 10} more."
    
    response += f"\n💡 Say 'select <field_name>' to work on one of these."
    return response

def handle_select_field(target: str, field_list: list, field_loader) -> tuple:
    """Handle field selection"""
    if not target:
        return None, "🤔 Which field should I select? Try 'select PostalCode' or 'search address' to find one."
    
    # Find the field
    selected_field = find_field_fuzzy(target, field_list)
    
    if not selected_field:
        return None, f"❌ Couldn't find a field matching '{target}'. Try 'search {target}' to see similar fields."
    
    try:
        field_metadata = field_loader.get_field_metadata(selected_field)
        if not field_metadata:
            return None, f"❌ Found the field but couldn't load its metadata. Please try another field."
        
        field_name = selected_field.split('/')[-1]
        return selected_field, f"✅ Great! I'm now working on the {field_name} field. Say 'generate' to create test cases for it."
        
    except Exception as e:
        return None, f"❌ Error loading field data: {str(e)}"

def handle_generate(generator: TestObjectiveGeneratorCore, session: ConversationalSession, is_regenerate: bool = False) -> tuple:
    """Handle test case generation with conversation context"""
    
    field_name = session.current_field_metadata.get('field_name', 'Unknown')
    action_word = "additional" if is_regenerate else "new"
    
    try:
        # Get conversation context for AI
        conversation_context = session.get_context_for_generation()
        
        # Generate with enhanced context
        success = generator.generate_for_field_with_context(
            session.current_field_metadata, 
            conversation_context
        )
        
        if success:
            pending_cases = generator.test_manager.get_pending_cases()
            recent_cases = [case for case in pending_cases if case.get('Test Case ID', '').startswith('TC_')][-3:]
            
            response = f"✅ Generated {action_word} test cases for {field_name}!\n\n"
            response += "📋 Here's what I created:\n"
            
            for case in recent_cases:
                tc_id = case.get('Test Case ID', 'N/A')
                objective = case.get('Test Objective', 'N/A')
                val_type = case.get('Type of Validation', 'N/A')
                response += f"   • {tc_id}: {objective[:50]}... ({val_type})\n"
            
            response += f"\n💡 Say 'approve TC_001 TC_002' to keep the good ones, or 'reject TC_003' to remove any."
            return response, True
        else:
            return f"❌ Sorry, I had trouble generating test cases for {field_name}. Want to try again?", False
            
    except Exception as e:
        return f"❌ Oops! Something went wrong: {str(e)}", False

def handle_improve(generator: TestObjectiveGeneratorCore, session: ConversationalSession, feedback: str) -> str:
    """Handle improvement requests"""
    try:
        # This would need enhanced generation method
        field_name = session.current_field_metadata.get('field_name', 'Unknown')
        return f"💡 I'd love to improve the test cases for {field_name} based on '{feedback}', but I need the improvement feature implemented first. For now, try 'regenerate' for more test cases."
    except Exception as e:
        return f"❌ Error with improvement: {str(e)}"

def handle_approve_all(generator: TestObjectiveGeneratorCore, session: ConversationalSession) -> str:
    """Handle approve all"""
    pending_cases = generator.test_manager.get_pending_cases()
    if not pending_cases:
        return "🤷 No pending test cases to approve. Generate some first!"
    
    tc_ids = [case["Test Case ID"] for case in pending_cases]
    result = generator.test_manager.approve_test_cases(tc_ids)
    
    count = len(result["approved"])
    session.update_stats('approved_count', count)
    
    return f"✅ Perfect! I've approved all {count} pending test cases. Say 'export' when you're ready to save them to Excel."

def handle_approve_specific(generator: TestObjectiveGeneratorCore, session: ConversationalSession, tc_ids: list) -> str:
    """Handle specific approvals"""
    result = generator.test_manager.approve_test_cases(tc_ids)
    
    response = ""
    if result["approved"]:
        count = len(result["approved"])
        session.update_stats('approved_count', count)
        response += f"✅ Approved {count} test cases: {', '.join(result['approved'])}\n"
    
    if result["not_found"]:
        response += f"❌ Couldn't find: {', '.join(result['not_found'])}\n"
    
    total_approved = session.session_context['approved_count']
    response += f"\n📊 You now have {total_approved} approved test cases total."
    
    return response.strip()

def handle_reject_specific(generator: TestObjectiveGeneratorCore, session: ConversationalSession, tc_ids: list) -> str:
    """Handle specific rejections"""
    result = generator.test_manager.reject_test_cases(tc_ids)
    
    response = ""
    if result["rejected"]:
        count = len(result["rejected"])
        session.update_stats('rejected_count', count)
        response += f"🗑️ Rejected {count} test cases: {', '.join(result['rejected'])}\n"
    
    if result["not_found"]:
        response += f"❌ Couldn't find: {', '.join(result['not_found'])}\n"
    
    return response.strip()

def handle_show_pending(generator: TestObjectiveGeneratorCore) -> str:
    """Handle showing pending cases"""
    pending_cases = generator.test_manager.get_pending_cases()
    
    if not pending_cases:
        return "📝 No pending test cases to review. Say 'generate' to create some!"
    
    response = f"📝 Here are {len(pending_cases)} pending test cases for your review:\n\n"
    
    for case in pending_cases:
        tc_id = case.get("Test Case ID", "N/A")
        val_type = case.get("Type of Validation", "N/A") 
        objective = case.get("Test Objective", "N/A")
        
        response += f"   📋 {tc_id} - {val_type}\n"
        response += f"       {objective}\n\n"
    
    response += "💡 Say 'approve TC_001 TC_002' to keep good ones, or 'reject TC_003' to remove any."
    
    return response

def handle_show_all(generator: TestObjectiveGeneratorCore) -> str:
    """Handle showing all cases with status"""
    all_cases = generator.test_manager.get_all_cases()
    
    if not all_cases:
        return "📊 No test cases yet. Say 'generate' to create some!"
    
    summary = generator.test_manager.get_status_summary()
    
    response = f"📊 **Test Case Summary:**\n"
    response += f"   📝 Pending: {summary['pending']}\n"
    response += f"   ✅ Approved: {summary['approved']}\n"  
    response += f"   ❌ Rejected: {summary['rejected']}\n"
    response += f"   📊 Total: {sum(summary.values())}\n\n"
    
    if summary['approved'] > 0:
        response += "💡 You have approved test cases ready to export!"
    elif summary['pending'] > 0:
        response += "💡 You have pending test cases to review."
    
    return response

def handle_export(generator: TestObjectiveGeneratorCore) -> str:
    """Handle export request"""
    approved_cases = generator.test_manager.get_approved_cases()
    
    if not approved_cases:
        return "❌ No approved test cases to export. Approve some test cases first by saying 'approve TC_001'."
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"approved_test_cases_{timestamp}.xlsx"
        
        success = generator.test_manager.export_approved_to_excel(filename)
        if success:
            return f"✅ Exported {len(approved_cases)} approved test cases to {filename}! 🎉"
        else:
            return "❌ Export failed. Please try again."
    except Exception as e:
        return f"❌ Export error: {str(e)}"

def handle_unknown_intent(user_input: str, session: ConversationalSession) -> str:
    """Handle unknown user input conversationally"""
    
    # Check if they mentioned test case IDs (might be approval/rejection)
    tc_ids = re.findall(r'TC_\d{3}', user_input.upper())
    if tc_ids:
        if any(word in user_input.lower() for word in ['good', 'yes', 'ok', 'keep', 'like']):
            return f"🤔 It sounds like you want to approve {', '.join(tc_ids)}? Say 'approve {' '.join(tc_ids)}' to confirm."
        elif any(word in user_input.lower() for word in ['bad', 'no', 'remove', 'delete', 'dislike']):
            return f"🤔 It sounds like you want to reject {', '.join(tc_ids)}? Say 'reject {' '.join(tc_ids)}' to confirm."
    
    # Check for field names in input
    if any(char in user_input for char in ['/', 'Code', 'Name', 'Address']):
        return f"🤔 It looks like you mentioned a field name. Try 'select {user_input}' to work on it."
    
    # General help
    responses = [
        "🤔 I'm not sure what you want to do. Try:\n• 'search <field_name>' to find a field\n• 'generate' to create test cases\n• 'help' for more options",
        "💭 Could you rephrase that? I understand commands like 'select field', 'generate tests', 'approve TC_001', etc.",
        "🤷 I didn't quite catch that. Say 'help' to see what I can do, or just tell me what you want to accomplish."
    ]
    
    import random
    return random.choice(responses)

def handle_exit_flow(generator: TestObjectiveGeneratorCore) -> bool:
    """Handle exit with potential export"""
    approved_cases = generator.test_manager.get_approved_cases()
    
    if approved_cases:
        print(f"📤 You have {len(approved_cases)} approved test cases.")
        export_choice = input("🤖 Should I export them to Excel before we finish? (Y/n): ").strip().lower()
        
        if export_choice in ['', 'y', 'yes']:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"final_approved_cases_{timestamp}.xlsx"
                
                success = generator.test_manager.export_approved_to_excel(filename)
                if success:
                    print(f"✅ Exported to {filename}. Great work! 🎉")
                    return True
            except Exception as e:
                print(f"❌ Export failed: {e}")
    
    print("👋 Thanks for using the conversational test case generator!")
    return True

def find_field_fuzzy(target: str, field_list: list) -> str:
    """Find field with fuzzy matching"""
    target = target.lower().strip()
    
    # Exact match
    for field in field_list:
        if target == field.lower():
            return field
    
    # Field name match (last part of xpath)
    for field in field_list:
        field_name = field.split('/')[-1].lower()
        if target == field_name:
            return field
    
    # Partial match in field name
    matches = []
    for field in field_list:
        field_name = field.split('/')[-1].lower()
        if target in field_name or field_name in target:
            matches.append(field)
    
    if len(matches) == 1:
        return matches[0]
    
    # Fuzzy matching
    best_match = None
    best_score = 0.6
    
    for field in field_list:
        field_name = field.split('/')[-1].lower()
        similarity = SequenceMatcher(None, target, field_name).ratio()
        if similarity > best_score:
            best_score = similarity
            best_match = field
    
    return best_match

# Enhanced TestObjectiveGeneratorCore with conversation context

class TestObjectiveGeneratorCore:
    def __init__(self, client, test_manager, src_dir: str):
        self.client = client
        self.test_manager = test_manager
        self.src_dir = src_dir
        self.failed_fields = []

    def generate_for_field_with_context(self, field_metadata: dict, conversation_context: str = "") -> bool:
        """Generate test cases with conversation context for better continuity"""
        
        # Validate field data
        is_valid, error_msg = self._validate_field_data(field_metadata)
        if not is_valid:
            print(f"[ERROR] Invalid field data: {error_msg}")
            return False
        
        try:
            backend_xpath = field_metadata.get("backend_xpath") or ""
            field_name = field_metadata.get("field_name", "")
            
            # Extract keywords safely
            keywords = []
            if backend_xpath:
                last_seg = backend_xpath.split("/")[-1]
                if last_seg:
                    keywords.append(last_seg)
            if field_name:
                keywords.append(field_name)
            
            if not keywords:
                keywords = ["validate", "check"]
            
            # Extract Java code
            try:
                snippets = extract_java_code_blocks_with_cross_references(
                    self.src_dir, keywords, max_depth=1
                )
                code_context = trim_code_context(snippets, max_chars=2000)
            except Exception as e:
                print(f"[WARN] Java extraction failed: {str(e)}, continuing without code context")
                code_context = ""
            
            # Create enhanced prompt with conversation context
            context_part = f"""Field metadata and conversation context for test case generation:

FIELD METADATA:
"""
            for key, value in field_metadata.items():
                if value:
                    context_part += f"{key}: {value}\n"
            
            if code_context:
                context_part += f"""

JAVA CODE CONTEXT:
{code_context}"""
            
            if conversation_context:
                context_part += f"""

CONVERSATION CONTEXT:
{conversation_context}"""
            
            question_part = """Generate test cases in EXACTLY 9 tab-separated columns:
Category | Test Case ID (blank) | Type of Validation | Test Objective | Request/Response Field | Test Steps | Expected Result | Mapping Correlation | Manual/Automation

REQUIREMENTS:
- Category: Always "Functional"
- Type of Validation: "Field Validation - Positive", "Field Validation - Negative", "Business Validation - Positive", "Business Validation - Negative"
- Manual/Automation: "Manual" for business validation, "Automation" for field validation
- Generate 2-4 test cases covering different validation scenarios
- Consider the conversation context for continuity

Output ONLY the test case rows, no explanations."""

            formatted_prompt = f"====CONTEXT {context_part} ====QUESTION {question_part}"
            
            # Call API with retry
            output = self._call_api_with_retry(formatted_prompt)
            
            if output is None:
                print(f"[ERROR] Failed to generate test cases for field: {field_name}")
                self.failed_fields.append(field_name)
                return False
            
            # Parse and store results
            new_tc_ids = self.test_manager.parse_and_add_test_cases(output, 
                default_mapping=field_metadata.get('backend_xpath', ''))
            
            if new_tc_ids:
                print(f"[INFO] Generated {len(new_tc_ids)} new test cases")
                return True
            else:
                print(f"[WARN] No test cases parsed from AI response")
                return False
            
        except Exception as e:
            print(f"[ERROR] Unexpected error processing field {field_metadata.get('field_name', 'unknown')}: {str(e)}")
            self.failed_fields.append(field_metadata.get('field_name', 'unknown'))
            return False
    
    # ... rest of existing methods stay the same ...
    def _validate_field_data(self, field: dict) -> tuple:
        """Validate field has minimum required data"""
        required_fields = ['field_name']
        
        for req_field in required_fields:
            if not field.get(req_field):
                return False, f"Missing required field: {req_field}"
        
        field_name = field.get('field_name', '').strip()
        if len(field_name) < 2:
            return False, f"Field name too short: '{field_name}'"
        
        return True, "Valid"

    def _call_api_with_retry(self, prompt: str, max_retries: int = 3) -> str:
        """Call API with retry logic"""
        for attempt in range(max_retries):
            try:
                response = self.client.chat_completion(prompt)
                content = response.choices[0].message.content.strip()
                
                # Check for "I don't know" responses
                if "sorry" in content.lower() and ("don't know" in content.lower() or "not sure" in content.lower()):
                    if attempt < max_retries - 1:
                        print(f"[WARN] AI responded with 'don't know', retrying...")
                        time.sleep(2)
                        continue
                    else:
                        return None
                
                return content
                
            except Exception as e:
                print(f"[ERROR] API call failed (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return None
        
        return None

# Updated main() function to use conversational mode

def main():
    parser = argparse.ArgumentParser(description="Conversational Test Case Generator")
    parser.add_argument("--mode", choices=["chat", "bulk", "interactive"], help="Run mode")
    parser.add_argument("--mapping", help="Path to mapping sheet")
    parser.add_argument("--src", help="Path to Java source code")
    parser.add_argument("--out", default="test_objectives.xlsx", help="Output Excel file (bulk mode)")
    
    args = parser.parse_args()
    
    # Interactive prompts if args missing
    if not args.mode:
        print("🤖 Select Generation Mode:")
        print("  1. Bulk Mode (process all fields → Excel)")
        print("  2. Interactive Mode (conversational, natural language)")
        print("  3. Basic Chat Mode (simple field selection)")
        mode_input = input("Choose (1/2/3): ").strip()
        if mode_input == "1":
            args.mode = "bulk"
        elif mode_input == "3": 
            args.mode = "chat"
        else:
            args.mode = "interactive"
    
    if not args.mapping:
        args.mapping = input("📊 Enter path to mapping file: ").strip()
    
    if not args.src:
        args.src = input("📁 Enter path to Java source directory: ").strip()
    
    # Validate inputs
    if not validate_mapping_file(args.mapping):
        return
    
    if not os.path.isdir(args.src):
        print(f"❌ Source directory not found: {args.src}")
        return
    
    try:
        # Initialize field loader
        field_loader = FieldMetadataLoader(args.mapping)
        
        # Load FiservAI credentials
        API_KEY = os.getenv("API_KEY")
        API_SECRET = os.getenv("API_SECRET") 
        BASE_URL = os.getenv("BASE_URL")
        
        if not all([API_KEY, API_SECRET, BASE_URL]):
            print("❌ Missing required environment variables (API_KEY, API_SECRET, BASE_URL)")
            return
            
        client = FiservAI.FiservAI(API_KEY, API_SECRET, base_url=BASE_URL, temperature=0.2)
        
        # Initialize components
        manager = TestCaseManager()
        generator = TestObjectiveGeneratorCore(client, manager, args.src)
        
        # Run selected mode
        if args.mode == "bulk":
            success = bulk_mode_with_batch_loading(generator, field_loader, args.out)
        elif args.mode == "chat":
            success = chat_mode_with_field_selection(generator, field_loader)  # Original basic mode
        else:  # interactive mode (new conversational mode)
            success = conversational_interactive_mode(generator, field_loader)
        
        if success:
            print(f"\n🎉 Session completed successfully!")
        else:
            print(f"\n⚠️  Session completed with issues.")
    
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
 