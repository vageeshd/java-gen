Perfect ✅ — let’s set up the modular file structure with all the changes we discussed.

You’ll end up with a clean structure that’s easy to extend, maintain, and run.

 

📂 File Structure

project_root/

│

├── complete_agentic_test_generator.py   # main entry (CLI)

├── core/

│   ├── __init__.py

│   ├── test_objective_core.py           # Core GPT logic (chat + bulk)

│   ├── testcase_manager.py              # Parses, stores, exports test cases

│   └── java_extractor.py                # Java code extractor + context trimming

└── mappings/

    └── PartyInq-PRM.xlsm                # Example mapping sheet

 

1️⃣ core/testcase_manager.py

import pandas as pd



class TestCaseManager:

    def __init__(self):

        self.test_cases = []

        self.counter = 1



    def parse_and_add_test_cases(self, raw_text: str, default_mapping: str = ""):

        """Parse raw AI output (tab-separated rows) and add to internal store."""

        for line in raw_text.splitlines():

            if not line.strip():

                continue



            parts = line.split("\t")

            if len(parts) < 9:

                parts = line.split("|")  # fallback if | separator used

            if len(parts) < 9:

                print(f"[WARN] Skipping malformed row: {line}")

                continue



            parts = [p.strip() for p in parts]

            while len(parts) < 9:

                parts.append("")



            category, tc_id, val_type, objective, req_field, steps, expected, mapping, mode = parts



            # Auto-generate ID if missing

            if not tc_id:

                tc_id = f"TC_{self.counter:03d}"

                self.counter += 1



            # Fallback mapping correlation if empty

            if not mapping and default_mapping:

                mapping = default_mapping



            case = {

                "Category": category,

                "Test Case ID": tc_id,

                "Type of Validation": val_type,

                "Test Objective": objective,

                "Request/Response Field": req_field,

                "Test Steps": steps,

                "Expected Result": expected,

                "Mapping Correlation": mapping,

                "Manual/Automation": mode

            }

            self.test_cases.append(case)



    def get_all_cases(self):

        return self.test_cases



    def export_to_excel(self, out_file: str):

        """Export all stored cases to Excel."""

        df = pd.DataFrame(self.test_cases)

        df.to_excel(out_file, index=False)

        print(f"[INFO] Exported {len(self.test_cases)} test cases to {out_file}")

 

2️⃣ core/java_extractor.py

def extract_java_code_blocks_with_cross_references(src_dir, keywords, max_depth=1):

    """

    Your existing extractor implementation.

    Returns {file_path: [list of relevant snippets]}.

    """

    # TODO: paste your original logic here

    return {}



def trim_code_context(snippets_by_file, max_chars=2500):

    """Rank and trim snippets by importance until max_chars."""

    ranked_snippets = []

    for file_path, snippets in snippets_by_file.items():

        for snippet in snippets:

            if "xpath" in snippet or "field" in snippet:

                priority = 1

            elif "public" in snippet or "private" in snippet:

                priority = 2

            else:

                priority = 3

            ranked_snippets.append((priority, file_path, snippet))



    ranked_snippets.sort(key=lambda x: x[0])



    final_context = []

    total_len = 0

    for _, fpath, snip in ranked_snippets:

        chunk = f"\nFile: {fpath}\n{snip}\n"

        if total_len + len(chunk) > max_chars:

            break

        final_context.append(chunk)

        total_len += len(chunk)



    return "".join(final_context)

 

3️⃣ core/test_objective_core.py

import hashlib

from core.java_extractor import extract_java_code_blocks_with_cross_references, trim_code_context



class TestObjectiveGeneratorCore:

    def __init__(self, client, test_manager, src_dir: str):

        self.client = client

        self.test_manager = test_manager

        self.src_dir = src_dir



    def _hash_text(self, text: str) -> str:

        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]



    def _format_prompt(self, fields, code_contexts):

        prompt = (

            "You are an expert QA test objectives generator.\n\n"

            "For each field, generate tab-separated rows with EXACTLY 9 columns:\n"

            "Category | Test Case ID (blank) | Type of Validation | Test Objective | "

            "Request/Response Field | Test Steps | Expected Result | Mapping Correlation | Manual/Automation\n\n"

            "Rules:\n"

            "- Category = 'Functional'\n"

            "- Type of Validation ∈ {Field Validation, Negative Validation, Business Validation, Positive Validation}\n"

            "- Manual/Automation must match Type of Validation\n"

            "Wrap EACH field’s output between ===FIELD_START:<ID>=== and ===FIELD_END:<ID>=== markers.\n"

        )



        for field in fields:

            fid = field.get("backend_xpath") or field.get("field_name", "unknown")

            fid_short = f"{field.get('field_name','F')}_{self._hash_text(fid)}"

            prompt += f"\n===FIELD_START:{fid_short}===\n"

            for k, v in field.items():

                prompt += f"{k}: {v}\n"

            ctx = code_contexts.get(fid_short, "")

            if ctx:

                prompt += f"\nJAVA_CODE_CONTEXT:\n{ctx}\n"

            prompt += f"===FIELD_END:{fid_short}===\n"

        return prompt



    def _call_api(self, prompt: str) -> str:

        response = self.client.chat_completion(prompt)

        return response.choices[0].message.content



    def generate_for_field(self, field: dict):

        """Single-field generation (chatbot mode)."""

        backend_xpath = field.get("backend_xpath") or ""

        last_seg = backend_xpath.split("/")[-1] if backend_xpath else field.get("field_name", "")

        keywords = [last_seg, field.get("field_name", "")]

        snippets = extract_java_code_blocks_with_cross_references(self.src_dir, keywords, max_depth=1)

        context = trim_code_context(snippets, max_chars=2000)



        fid_short = f"{field.get('field_name','F')}_{self._hash_text(backend_xpath or field.get('field_name',''))}"

        prompt = self._format_prompt([field], {fid_short: context})

        output = self._call_api(prompt)



        self._parse_and_store(output, [field])



    from concurrent.futures import ThreadPoolExecutor, as_completed



def bulk_generate(self, fields, batch_size=5, max_workers=6):

    """Sequential bulk generation in batches.

       Code extraction is parallelized, API calls remain sequential."""

    for i in range(0, len(fields), batch_size):

        batch = fields[i:i+batch_size]



        # --- Parallel code extraction ---

        def extract_context(field):

            backend_xpath = field.get("backend_xpath") or ""

            last_seg = backend_xpath.split("/")[-1] if backend_xpath else field.get("field_name", "")

            keywords = [last_seg, field.get("field_name", "")]

            snippets = extract_java_code_blocks_with_cross_references(self.src_dir, keywords, max_depth=1)

            ctx = trim_code_context(snippets, max_chars=2000)

            fid_short = f"{field.get('field_name','F')}_{self._hash_text(backend_xpath or field.get('field_name',''))}"

            return fid_short, ctx



        code_contexts = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:

            future_to_field = {executor.submit(extract_context, field): field for field in batch}

            for future in as_completed(future_to_field):

                fid_short, ctx = future.result()

                code_contexts[fid_short] = ctx



        # --- Sequential API call for this batch ---

        prompt = self._format_prompt(batch, code_contexts)

        output = self._call_api(prompt)



        # --- Parse and store results ---

        self._parse_and_store(output, batch)



    def _parse_and_store(self, output: str, batch_fields):

        """Parse AI output and add cases to TestCaseManager."""

        for field in batch_fields:

            fid = field.get("backend_xpath") or field.get("field_name", "")

            fid_short = f"{field.get('field_name','F')}_{self._hash_text(fid)}"

            start = f"===FIELD_START:{fid_short}==="

            end = f"===FIELD_END:{fid_short}==="

            if start in output and end in output:

                block = output.split(start, 1)[1].split(end, 1)[0].strip()

                self.test_manager.parse_and_add_test_cases(block, default_mapping=fid)

            else:

                self.test_manager.parse_and_add_test_cases(output, default_mapping=fid)

 

4️⃣ complete_agentic_test_generator.py

import argparse

from core.test_objective_core import TestObjectiveGeneratorCore

from core.testcase_manager import TestCaseManager

from some_module import GPTClient, get_xpath_fields  # <-- keep your enterprise versions



def chat_mode(generator, fields):

    print("Entering Chatbot Mode. Type 'exit' to quit.\n")

    while True:

        field_name = input("Enter field name from mapping: ").strip()

        if field_name.lower() == "exit":

            print("[INFO] Exiting Chatbot Mode.")

            break

        field = next((f for f in fields if f.get("field_name") == field_name), None)

        if not field:

            print(f"[WARN] Field '{field_name}' not found in mapping.")

            continue

        generator.generate_for_field(field)

        print(f"[INFO] Added test cases for {field_name}")



def bulk_mode(generator, fields, out_file):

    print("[INFO] Running bulk generation...")

    generator.bulk_generate(fields, batch_size=5)

    generator.test_manager.export_to_excel(out_file)



def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--mode", choices=["chat", "bulk"], help="Run in chatbot or bulk mode")

    parser.add_argument("--mapping", help="Path to mapping sheet")

    parser.add_argument("--src", help="Path to Java source code")

    parser.add_argument("--out", default="test_objectives.xlsx", help="Output Excel file (bulk mode)")

    args = parser.parse_args()



    # Interactive prompts if args missing

    if not args.mode:

        mode_input = input("Select mode: (1) Bulk, (2) Chatbot: ").strip()

        args.mode = "bulk" if mode_input == "1" else "chat"

    if not args.mapping:

        args.mapping = input("Enter path to mapping file: ").strip()

    if not args.src:

        args.src = input("Enter path to Java source directory: ").strip()



    fields = get_xpath_fields(args.mapping, with_metadata=True)

    client = GPTClient()  # enterprise GPT client

    manager = TestCaseManager()

    generator = TestObjectiveGeneratorCore(client, manager, args.src)



    if args.mode == "chat":

        chat_mode(generator, fields)

    else:

        bulk_mode(generator, fields, args.out)



if __name__ == "__main__":

    main()

 

🔹 How to Run

Bulk

python complete_agentic_test_generator.py --mode bulk --mapping mappings/PartyInq-PRM.xlsm --src ./src --out bulk_cases.xlsx

Chatbot

python complete_agentic_test_generator.py --mode chat --mapping mappings/PartyInq-PRM.xlsm --src ./src

Or just run without args:

python complete_agentic_test_generator.py

👉 It will prompt you step by step.

 

✅ With this modular setup, you get:

•	Bulk generation (all fields → Excel).

•	Chatbot mode (one field at a time).

•	Enterprise API integration intact (GPTClient, get_xpath_fields unchanged).

•	Clean structure for future extensions.

 

Do you want me to also add an auto-export step after chatbot mode (so once the user finishes typing fields, it saves everything to Excel automatically)?



