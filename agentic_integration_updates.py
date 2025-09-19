# Updates to complete_agentic_test_generator.py

import argparse
import os
from datetime import datetime
from typing import List, Dict, Any

# Your existing enterprise imports:
from fiservai import FiservAI
from fiserv_ai_utils import SimpleConversationManager
from dotenv import load_dotenv

# Updated import:
from import_openpyxl import FieldMetadataLoader, validate_mapping_file

# Core module imports:
from core import TestObjectiveGeneratorCore, TestCaseManager

# Load environment variables
load_dotenv()

def chat_mode_with_field_selection(generator: TestObjectiveGeneratorCore, field_loader: FieldMetadataLoader) -> bool:
    """Enhanced chat mode with field selection from mapping"""
    
    print("🤖 CHAT MODE - Interactive Test Case Generation")
    print("=" * 60)
    
    # Load available fields (lightweight operation)
    print("[INFO] Loading available fields...")
    try:
        available_fields = field_loader.get_available_fields()
        if not available_fields:
            print("❌ No fields found in mapping file")
            return False
            
        field_list = sorted(list(available_fields))
        print(f"✅ Loaded {len(field_list)} available fields")
        
    except Exception as e:
        print(f"❌ Error loading fields: {e}")
        return False
    
    # Show available fields (first 10)
    print(f"\n📋 Available fields (showing first 10 of {len(field_list)}):")
    for i, field in enumerate(field_list[:10]):
        # Show just the last part of the xpath for readability
        field_name = field.split('/')[-1] if '/' in field else field
        print(f"  {i+1:2d}. {field_name} ({field})")
    
    if len(field_list) > 10:
        print(f"  ... and {len(field_list) - 10} more (type 'list' to see all)")
    
    generated_any = False
    
    while True:
        print(f"\n📝 Commands:")
        print("  • Type field name or number")
        print("  • 'list' - show all fields")  
        print("  • 'search <keyword>' - search fields")
        print("  • 'status' - show generated test cases")
        print("  • 'exit' - quit and export")
        
        user_input = input(f"\nEnter command: ").strip()
        
        if user_input.lower() == "exit":
            break
            
        elif user_input.lower() == "list":
            print(f"\n📋 All available fields ({len(field_list)}):")
            for i, field in enumerate(field_list):
                field_name = field.split('/')[-1] if '/' in field else field
                print(f"  {i+1:3d}. {field_name}")
                print(f"       └─ {field}")
            continue
            
        elif user_input.lower().startswith("search "):
            keyword = user_input[7:].strip().lower()
            matches = [f for f in field_list if keyword in f.lower()]
            
            if matches:
                print(f"\n🔍 Found {len(matches)} matches for '{keyword}':")
                for i, match in enumerate(matches[:10]):
                    field_name = match.split('/')[-1] if '/' in match else match
                    print(f"  {i+1:2d}. {field_name} ({match})")
                if len(matches) > 10:
                    print(f"  ... and {len(matches) - 10} more")
            else:
                print(f"🔍 No matches found for '{keyword}'")
            continue
            
        elif user_input.lower() == "status":
            cases = generator.test_manager.get_all_cases()
            if cases:
                print(f"\n📊 Generated {len(cases)} test cases so far:")
                for case in cases[-5:]:  # Show last 5
                    print(f"  • {case.get('Test Case ID', 'N/A')}: {case.get('Test Objective', 'N/A')[:50]}...")
            else:
                print("\n📊 No test cases generated yet")
            continue
        
        # Try to find the field
        selected_field = None
        
        # Check if input is a number
        if user_input.isdigit():
            field_index = int(user_input) - 1
            if 0 <= field_index < len(field_list):
                selected_field = field_list[field_index]
        else:
            # Try exact match first
            if user_input in field_list:
                selected_field = user_input
            else:
                # Try partial match on field name (last part of xpath)
                matches = [f for f in field_list if user_input.lower() in f.split('/')[-1].lower()]
                
                if len(matches) == 1:
                    selected_field = matches[0]
                    field_name = selected_field.split('/')[-1]
                    print(f"🔍 Found match: {field_name}")
                elif len(matches) > 1:
                    print(f"🔍 Multiple matches found:")
                    for i, match in enumerate(matches[:5]):
                        field_name = match.split('/')[-1]
                        print(f"  {i+1}. {field_name} ({match})")
                    continue
        
        if not selected_field:
            print(f"❌ Field not found. Try 'list' or 'search <keyword>' to find fields.")
            continue
        
        # Load field metadata (on-demand)
        print(f"\n🔄 Loading metadata for: {selected_field.split('/')[-1]}")
        try:
            field_metadata = field_loader.get_field_metadata(selected_field)
            if not field_metadata:
                print(f"❌ Could not load metadata for field: {selected_field}")
                continue
                
        except Exception as e:
            print(f"❌ Error loading field metadata: {e}")
            continue
        
        # Generate test cases for the field
        print(f"🔄 Generating test cases...")
        print("-" * 40)
        
        success = generator.generate_for_field(field_metadata)
        
        if success:
            field_name = selected_field.split('/')[-1]
            print(f"✅ Successfully generated test cases for {field_name}")
            generated_any = True
            
            # Show what was generated
            all_cases = generator.test_manager.get_all_cases()
            if all_cases:
                recent_cases = all_cases[-3:]  # Show last 3 cases
                print(f"\n📋 Recent test cases:")
                for case in recent_cases:
                    print(f"  • {case.get('Test Case ID', 'N/A')}: {case.get('Test Objective', 'N/A')}")
        else:
            print(f"❌ Failed to generate test cases")
    
    # Auto-export logic (same as before)
    all_cases = generator.test_manager.get_all_cases()
    
    if not all_cases:
        print("\n🤷 No test cases were generated during this session.")
        return False
    
    print(f"\n📤 CHAT SESSION COMPLETE")
    print(f"Generated {len(all_cases)} test cases total")
    
    # Auto-export prompt
    export_choice = input("Save all test cases to Excel? (Y/n): ").strip().lower()
    
    if export_choice in ['', 'y', 'yes']:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"chat_mode_test_cases_{timestamp}.xlsx"
            filepath = os.path.join(os.getcwd(), filename)
            
            generator.test_manager.export_to_excel(filepath)
            print(f"✅ Test cases exported to: {filename}")
            return True
            
        except Exception as e:
            print(f"❌ Export failed: {str(e)}")
            return False
    else:
        print("❌ Export cancelled. Test cases remain in memory only.")
        return False

def bulk_mode_with_batch_loading(generator: TestObjectiveGeneratorCore, field_loader: FieldMetadataLoader, out_file: str) -> bool:
    """Enhanced bulk mode with optimized field loading"""
    
    print("🚀 BULK MODE - Processing All Fields")
    print("=" * 50)
    
    # Load all field metadata at once (optimized for bulk)
    print("[INFO] Loading all field metadata...")
    try:
        all_fields = field_loader.get_all_field_metadata()
        
        if not all_fields:
            print("❌ No fields found in mapping file")
            return False
            
        print(f"✅ Loaded metadata for {len(all_fields)} fields")
        
    except Exception as e:
        print(f"❌ Error loading field metadata: {e}")
        return False
    
    # Show what will be processed
    print(f"📊 Will process {len(all_fields)} fields")
    print(f"💾 Output file: {out_file}")
    
    # Show sample fields
    print(f"\n📋 Sample fields to be processed:")
    for field in all_fields[:5]:
        field_name = field.get('field_name', 'Unknown')
        xpath = field.get('xpath', 'Unknown')
        print(f"  • {field_name} ({xpath})")
    
    if len(all_fields) > 5:
        print(f"  ... and {len(all_fields) - 5} more")
    
    # Confirm before starting
    proceed = input(f"\n🚦 Proceed with bulk generation? (Y/n): ").strip().lower()
    if proceed not in ['', 'y', 'yes']:
        print("❌ Bulk generation cancelled")
        return False
    
    # Start bulk generation (same as before)
    print(f"\n🔄 Starting bulk generation...")
    start_time = datetime.now()
    
    summary = generator.bulk_generate(all_fields, batch_size=5)
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    # Show detailed results (same as before)
    print(f"\n📈 BULK GENERATION RESULTS")
    print("=" * 50)
    print(f"⏱️  Duration: {duration}")
    print(f"✅ Successful: {summary['processed']} fields")
    print(f"❌ Failed: {summary['failed']} fields")
    print(f"📊 Success Rate: {summary['success_rate']}%")
    print(f"📋 Total Test Cases: {summary['total_test_cases']}")
    
    # Export results (same as before)
    if summary['total_test_cases'] > 0:
        try:
            print(f"\n💾 Exporting {summary['total_test_cases']} test cases to Excel...")
            generator.test_manager.export_to_excel(out_file)
            print(f"✅ Export successful: {out_file}")
            return True
            
        except Exception as e:
            print(f"❌ Export failed: {str(e)}")
            return False
    else:
        print("❌ No test cases generated - nothing to export")
        return False

def main():
    parser = argparse.ArgumentParser(description="Agentic Test Case Generator")
    parser.add_argument("--mode", choices=["chat", "bulk"], help="Run in chatbot or bulk mode")
    parser.add_argument("--mapping", help="Path to mapping sheet")
    parser.add_argument("--src", help="Path to Java source code")
    parser.add_argument("--out", default="test_objectives.xlsx", help="Output Excel file (bulk mode)")
    
    args = parser.parse_args()
    
    # Interactive prompts if args missing
    if not args.mode:
        print("🤖 Select Generation Mode:")
        print("  1. Bulk Mode (process all fields → Excel)")
        print("  2. Chat Mode (interactive field selection)")
        mode_input = input("Choose (1/2): ").strip()
        args.mode = "bulk" if mode_input == "1" else "chat"
    
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
        if args.mode == "chat":
            success = chat_mode_with_field_selection(generator, field_loader)
        else:
            success = bulk_mode_with_batch_loading(generator, field_loader, args.out)
        
        if success:
            print(f"\n🎉 Generation completed successfully!")
        else:
            print(f"\n⚠️  Generation completed with issues. Check the logs above.")
    
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
