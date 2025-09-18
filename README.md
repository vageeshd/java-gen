import os
import json
from typing import Dict, List, Any, Optional
from fiservai import FiservAI
from fiserv_ai_utils import SimpleConversationManager
from import_openpyxl import get_xpath_fields
from dotenv import load_dotenv

import yaml
from generate_field_assertions_yaml import generate_service_details, save_yaml_file

import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from extract_java_code_blocks import extract_java_code_blocks

# Load environment variables from .env file
load_dotenv()

class TestObjectiveGenerator:
    def __init__(self, api_key: str, api_secret: str, base_url: str):
        self.client = FiservAI.FiservAI(api_key, api_secret, base_url=base_url, temperature=0.2)
        
    def create_comprehensive_prompt(self, field_metadata: Dict[str, Any], java_code_context: str = "") -> str:
        """Create a detailed, comprehensive prompt for test objective generation."""
        
        prompt = """You are an expert QA test objectives generator for ESF (Enterprise Service Framework) APIs. 
Your role is to generate comprehensive, realistic, and detailed test objectives based STRICTLY on the provided field metadata and Java code context.

IMPORTANT CONSTRAINTS:
1. Base your test objectives ONLY on the provided metadata and code
2. Do NOT make assumptions about validation rules not explicitly shown in the code
3. If validation logic is unclear from the code, ASK specific questions instead of assuming
4. Focus on what you can definitively determine from the provided information
5. Generate multiple test cases covering different scenarios when the code shows multiple validation paths

OUTPUT FORMAT:
Generate test objectives as tab-separated lines with these columns:
Test Case Id | Type of Validation | Objective(Short Description) | Test Steps | Prerequisite | Test Data | Expected Results | Actual Results | Review Comments | Manual/Automation | Automation pattern | Mapping correlation | Comments

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

EXAMPLE OUTPUT FORMAT:
TC_001	Field Validation	Verify PostalCode accepts valid 5-digit format	Send request with PostalCode="12345"	API is up	PostalCode=12345	Response code 200, PostalCode present in response	Response as expected	None	Automation	Positive	PartyRec/PersonPartyInfo/PersonData/Contact/PostAddr/PostalCode	Based on field metadata
TC_002	Field Validation	Verify PostalCode rejects invalid format	Send request with PostalCode="INVALID"	API is up	PostalCode=INVALID	Response code 400, validation error message	Error as expected	None	Automation	Negative	PartyRec/PersonPartyInfo/PersonData/Contact/PostAddr/PostalCode	Based on field metadata

GENERATE TEST OBJECTIVES NOW:
If you need clarification about any aspect of the validation logic or business rules that are not clear from the provided information, please ASK SPECIFIC QUESTIONS rather than making assumptions.
"""
        
        return prompt
    
    def create_follow_up_prompt(self, original_field_metadata: Dict[str, Any], java_code_context: str, 
                               conversation_history: List[Dict], user_question: str) -> str:
        """Create a follow-up prompt that maintains context while addressing user questions."""
        
        prompt = """You are continuing to help generate comprehensive test objectives for an ESF API field.

ORIGINAL FIELD METADATA:
"""
        for key, value in original_field_metadata.items():
            prompt += f"{key}: {value}\n"
        
        if java_code_context:
            prompt += f"""

ORIGINAL JAVA CODE CONTEXT:
{java_code_context}
"""
        
        prompt += """

CONVERSATION HISTORY:
"""
        for turn in conversation_history[-6:]:  # Keep last 6 turns for context
            role = turn.get('role', 'unknown')
            content = turn.get('content', '')
            prompt += f"{role.upper()}: {content}\n"
        
        prompt += f"""

USER'S CURRENT QUESTION/REQUEST:
{user_question}

INSTRUCTIONS:
1. Address the user's specific question/request
2. Continue to base responses ONLY on provided metadata and code
3. If generating new test objectives, use the same tab-separated format
4. If you still need clarification, ask specific questions
5. Do not make assumptions about validation rules not shown in the code

RESPONSE:
"""
        
        return prompt
    
    def analyze_code_for_validation_patterns(self, java_code_context: str) -> Dict[str, List[str]]:
        """Analyze Java code to identify common validation patterns."""
        
        analysis_prompt = f"""Analyze the following Java code and identify validation patterns. 
Return your analysis in JSON format with these categories:

{{
    "data_type_validations": ["list of data type checks found"],
    "length_validations": ["list of length/size validations found"],
    "format_validations": ["list of format/pattern validations found"],
    "null_empty_checks": ["list of null/empty checks found"],
    "business_rules": ["list of business logic rules found"],
    "error_conditions": ["list of error conditions handled"],
    "success_conditions": ["list of success scenarios identified"]
}}

Java Code:
{java_code_context}

Provide ONLY the JSON response with actual validation patterns found in the code. 
If a category has no patterns found, use an empty list.
"""
        
        try:
            response = self.client.chat_completion(analysis_prompt)
            content = response.choices[0].message.content.strip()
            
            # Try to extract JSON from the response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                return json.loads(json_str)
        except Exception as e:
            print(f"[DEBUG] Could not analyze code patterns: {e}")
        
        return {
            "data_type_validations": [],
            "length_validations": [],
            "format_validations": [],
            "null_empty_checks": [],
            "business_rules": [],
            "error_conditions": [],
            "success_conditions": []
        }
    
    def generate_test_categories_prompt(self, field_metadata: Dict[str, Any], 
                                      validation_patterns: Dict[str, List[str]]) -> str:
        """Generate a prompt to create test categories based on validation patterns."""
        
        prompt = f"""Based on the field metadata and validation patterns identified in the Java code, 
suggest comprehensive test categories that should be covered.

FIELD METADATA:
"""
        for key, value in field_metadata.items():
            prompt += f"{key}: {value}\n"
        
        prompt += f"""

VALIDATION PATTERNS IDENTIFIED:
{json.dumps(validation_patterns, indent=2)}

Generate a list of test categories that should be covered for this field, such as:
- Positive validation tests
- Negative validation tests  
- Boundary condition tests
- Data type tests
- Business rule tests
- Error handling tests

For each category, briefly explain what should be tested based on the patterns found.
Respond in a structured format that can guide comprehensive test case generation.
"""
        
        return prompt

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
    
    java_code_blocks = extract_java_code_blocks(src_dir, field_keywords)
    
    # Combine all code context
    code_context = ""
    code_blocks_txt = ""
    total_methods = 0
    
    for file, snippets in java_code_blocks.items():
        total_methods += len(snippets)
        for snip in snippets:
            block = f"\nFile: {file}\n--- Relevant Method ---\n{snip}\n"
            code_context += block
            code_blocks_txt += block
    
    print(f"[INFO] Found {len(java_code_blocks)} files with {total_methods} relevant methods")
    
    # Save code blocks to file
    output_txt_path = os.path.join(os.getcwd(), "java_code_blocks_found.txt")
    try:
        with open(output_txt_path, "w", encoding="utf-8") as f:
            f.write(code_blocks_txt)
        print(f"[INFO] Java code blocks saved to: {output_txt_path}")
    except Exception as e:
        print(f"[ERROR] Could not write code blocks to file: {e}")
    
    # Analyze validation patterns in the code
    print("[INFO] Analyzing validation patterns in Java code...")
    validation_patterns = generator.analyze_code_for_validation_patterns(code_context)
    
    print("\n[INFO] Validation patterns identified:")
    for category, patterns in validation_patterns.items():
        if patterns:
            print(f"  {category}: {len(patterns)} patterns found")
    
    # Initialize conversation manager
    convo_mgr = SimpleConversationManager(50)
    
    print("\n" + "="*80)
    print("COMPREHENSIVE TEST OBJECTIVE GENERATOR")
    print("Commands: 'analyze' - analyze code patterns, 'generate' - create test objectives,")
    print("         'categories' - suggest test categories, 'clear' - reset, 'exit' - quit")
    print("="*80)
    
    # Generate initial comprehensive test objectives
    print("\n[INFO] Generating initial comprehensive test objectives...\n")
    
    try:
        initial_prompt = generator.create_comprehensive_prompt(field, code_context)
        response = generator.client.chat_completion(initial_prompt)
        content = response.choices[0].message.content.strip()
        
        print("AI GENERATED TEST OBJECTIVES:")
        print("-" * 60)
        print(content)
        print("-" * 60)
        
        convo_mgr.add_turn("[initial_generation]", content)
        
    except Exception as e:
        print(f"[ERROR] Failed to generate initial test objectives: {e}")
        return
    
    # Interactive session
    while True:
        user_input = input("\nYour input/question: ").strip()
        
        if user_input.lower() == "exit":
            print("Exiting test objective generator.")
            break
            
        if user_input.lower() == "clear":
            convo_mgr.clear()
            print("Chat history cleared.")
            continue
            
        if user_input.lower() == "analyze":
            print("\nVALIDATION PATTERNS ANALYSIS:")
            print(json.dumps(validation_patterns, indent=2))
            continue
            
        if user_input.lower() == "generate":
            # Regenerate comprehensive test objectives
            try:
                prompt = generator.create_comprehensive_prompt(field, code_context)
                response = generator.client.chat_completion(prompt)
                content = response.choices[0].message.content.strip()
                
                print("\nREGENERATED TEST OBJECTIVES:")
                print("-" * 60)
                print(content)
                print("-" * 60)
                
                convo_mgr.add_turn("generate", content)
                
            except Exception as e:
                print(f"[ERROR] Failed to regenerate test objectives: {e}")
            continue
            
        if user_input.lower() == "categories":
            try:
                categories_prompt = generator.generate_test_categories_prompt(field, validation_patterns)
                response = generator.client.chat_completion(categories_prompt)
                content = response.choices[0].message.content.strip()
                
                print("\nSUGGESTED TEST CATEGORIES:")
                print("-" * 60)
                print(content)
                print("-" * 60)
                
                convo_mgr.add_turn("categories", content)
                
            except Exception as e:
                print(f"[ERROR] Failed to generate test categories: {e}")
            continue
        
        if not user_input:
            continue
            
        # Handle regular conversation
        try:
            conversation = convo_mgr.get_conversation()
            follow_up_prompt = generator.create_follow_up_prompt(
                field, code_context, conversation, user_input
            )
            
            response = generator.client.chat_completion(follow_up_prompt)
            content = response.choices[0].message.content.strip()
            
            print(f"\nAI Response:")
            print("-" * 40)
            print(content)
            print("-" * 40)
            
            convo_mgr.add_turn(user_input, content)
            
        except Exception as e:
            print(f"[ERROR] Failed to process input: {e}")
    
    # Save final conversation to file
    try:
        conversation_file = os.path.join(os.getcwd(), "test_objectives_conversation.json")
        final_conversation = convo_mgr.get_conversation()
        
        with open(conversation_file, "w", encoding="utf-8") as f:
            json.dump({
                "field_metadata": field,
                "validation_patterns": validation_patterns,
                "conversation": final_conversation
            }, f, indent=2)
        
        print(f"\n[INFO] Full conversation saved to: {conversation_file}")
        
    except Exception as e:
        print(f"[ERROR] Could not save conversation: {e}")

if __name__ == "__main__":
    main()
