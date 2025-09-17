import os

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

# Helper to create a prompt for each field
def create_test_objective_prompt(field_metadata):
    prompt = (
        "You are an expert QA test objectives generator for ESF (Enterprise Service Framework) APIs. "
        "Given the following field metadata, generate a realistic, detailed, and relevant test objective for this field. "
        "Output ONLY a single tab-separated line (no header) matching the columns below.\n\n"
        "Columns (tab-separated, one line, no header):\n"
        "Test Case Id\tType of Validation\tObjective(Short Description)\tTest Steps\tPrerequisite\tTest Data\tExpected Results\tActual Results\tReview Comments\tManual/Automation\tAutomation pattern\tMapping corelation\tComments\n\n"
        "Example:\n"
        "TC_001\tField Validation\tVerify PostalCode is accepted when valid\tSend request with valid PostalCode\tAPI is up\tPostalCode=12345\tResponse code 200, PostalCode present in response\tResponse as expected\tNone\tAutomation\tPositive\tPartyRec/PersonPartyInfo/PersonData/Contact/PostAddr/PostalCode\tNone\n\n"
        "Field metadata for this test objective:\n"
    )
    for key, value in field_metadata.items():
        prompt += f"{key}: {value}\n"
    prompt += (
        "\nGenerate a realistic test objective for this field, following the example and columns above. "
        "Respond ONLY with a single tab-separated line. Do NOT include any explanation, markdown, or formatting."
    )
    return prompt

# Load FiservAI credentials from environment
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
BASE_URL = os.getenv("BASE_URL")

client = FiservAI.FiservAI(API_KEY, API_SECRET, base_url=BASE_URL, temperature=0.0)

class DummyTools:
    @classmethod
    def get_tools_metadata(cls):
        return []

def main():

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

    src_dir = input("Enter path to Java source directory: ").strip()
    if not os.path.isdir(src_dir):
        print(f"Source directory '{src_dir}' does not exist.")
        return

    print(f"[DEBUG] Using Java source directory: {src_dir}")
    # Only use the last segment of the field path
    field_last = hardcoded_field.split('/')[-1]
    field_keywords = [field_last]
    print(f"[DEBUG] Field last segment keyword: {field_keywords}")
    backend_xpath = field.get('backend_xpath')
    backend_last = None
    if backend_xpath and isinstance(backend_xpath, str):
        backend_segments = [seg for seg in backend_xpath.split('/') if seg]
        backend_last = backend_segments[-1] if backend_segments else None
        print(f"[DEBUG] Backend xpath last segment: {backend_last}")
        if backend_last:
            field_keywords.append(backend_last)
    print(f"[DEBUG] Final field keywords for Java code search: {field_keywords}")

    # Call extract_java_code_blocks, which now handles ranking and selection internally
    java_code_blocks = extract_java_code_blocks(src_dir, field_keywords)
    print(f"[DEBUG] Java code blocks found: {len(java_code_blocks)} files")
    code_context = ""
    code_blocks_txt = ""
    for file, snippets in java_code_blocks.items():
        print(f"[DEBUG] File: {file}, Snippets found: {len(snippets)}")
        for snip in snippets:
            block = f"\nFile: {file}\n--- Relevant Block ---\n{snip}\n"
            code_context += block
            code_blocks_txt += block

    output_txt_path = os.path.join(os.getcwd(), "java_code_blocks_found.txt")
    try:
        with open(output_txt_path, "w", encoding="utf-8") as f:
            f.write(code_blocks_txt)
        print(f"[DEBUG] Java code blocks written to: {output_txt_path}")
    except Exception as e:
        print(f"[ERROR] Could not write code blocks to file: {e}")

    convo_mgr = SimpleConversationManager(40)
    print("Conversational Test Objective Generator. Type 'clear' to reset chat, 'exit' to quit.\n")
    # First, send the metadata prompt + code context to the AI and print the response
    prompt = create_test_objective_prompt(field)
    if code_context:
        prompt += f"\nRelevant code context from Java source:\n{code_context}"
    try:
        response = client.chat_completion(prompt)
        content = response.choices[0].message.content.strip()
        print(f"AI: {content}\n{'-'*60}")
        # Optionally, store the initial AI response in conversation history with a dummy user input
        convo_mgr.add_turn("[metadata prompt]", content)
    except Exception as e:
        print(f"Error: {e}")
        return

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "exit":
            print("Exiting.")
            break
        if user_input.lower() == "clear":
            convo_mgr.clear()
            print("Chat history cleared.")
            # Re-send the metadata prompt + code context after clearing
            prompt = create_test_objective_prompt(field)
            if code_context:
                prompt += f"\nRelevant code context from Java source:\n{code_context}"
            try:
                response = client.chat_completion(prompt)
                content = response.choices[0].message.content.strip()
                print(f"AI: {content}\n{'-'*60}")
                convo_mgr.add_turn("[metadata prompt]", content)
            except Exception as e:
                print(f"Error: {e}")
            continue
        # Compose prompt with conversation history and user input
        conversation = convo_mgr.get_conversation()
        prompt = create_test_objective_prompt(field)
        if code_context:
            prompt += f"\nRelevant code context from Java source:\n{code_context}"
        for turn in conversation:
            if turn['role'] == 'user':
                prompt += f"\nUser: {turn['content']}"
            elif turn['role'] == 'assistant':
                prompt += f"\nAI: {turn['content']}"
        prompt += f"\nUser: {user_input}"
        try:
            response = client.chat_completion(prompt)
            content = response.choices[0].message.content.strip()
            print(f"AI: {content}\n{'-'*60}")
            convo_mgr.add_turn(user_input, content)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
