def find_field_fuzzy(target: str, field_list: list) -> str:
    """Fixed field matching for paths like customer/address/postalCode"""
    
    if not target or not field_list:
        return None
    
    target_original = target.strip()
    target = target.lower().strip()
    
    print(f"[DEBUG] Finding field for target: '{target_original}'")
    print(f"[DEBUG] Normalized target: '{target}'")
    print(f"[DEBUG] Available fields: {field_list}")
    
    # Step 1: EXACT full path match (no leading slash normalization)
    for field in field_list:
        field_normalized = field.lower().strip()
        target_normalized = target.strip()
        
        print(f"[DEBUG] Comparing '{target_normalized}' == '{field_normalized}'")
        
        if target_normalized == field_normalized:
            print(f"[DEBUG] ✅ EXACT PATH MATCH found: {field}")
            return field
    
    # Step 2: Path components match (handle variations in spacing/case)
    if '/' in target:
        print(f"[DEBUG] Target contains '/', treating as path")
        
        for field in field_list:
            # Split and compare path components
            field_parts = [part.strip().lower() for part in field.split('/') if part.strip()]
            target_parts = [part.strip().lower() for part in target.split('/') if part.strip()]
            
            print(f"[DEBUG] Comparing path parts:")
            print(f"[DEBUG]   Target: {target_parts}")
            print(f"[DEBUG]   Field:  {field_parts}")
            
            if len(field_parts) == len(target_parts) and field_parts == target_parts:
                print(f"[DEBUG] ✅ PATH COMPONENTS MATCH found: {field}")
                return field
        
        # Target looks like a path but no exact match found
        print(f"[DEBUG] ❌ Target looks like path but no exact match found")
        
        # Try partial path matching for user convenience
        target_parts = [part.strip().lower() for part in target.split('/') if part.strip()]
        partial_matches = []
        
        for field in field_list:
            field_parts = [part.strip().lower() for part in field.split('/') if part.strip()]
            
            # Check if target path is a suffix of field path
            if len(target_parts) <= len(field_parts):
                if field_parts[-len(target_parts):] == target_parts:
                    partial_matches.append(field)
                    print(f"[DEBUG] Partial path match: {field}")
        
        if len(partial_matches) == 1:
            print(f"[DEBUG] ✅ Single partial path match: {partial_matches[0]}")
            return partial_matches[0]
        elif len(partial_matches) > 1:
            print(f"[DEBUG] Multiple partial path matches found:")
            for field in partial_matches:
                print(f"   → {field}")
            return None
        
        # No matches for path-like input
        return None
    
    # Step 3: Field name matching (only if target is NOT a path)
    print(f"[DEBUG] Target is field name, looking for exact name matches...")
    
    exact_name_matches = []
    for field in field_list:
        field_name = field.split('/')[-1].lower()
        print(f"[DEBUG] Comparing field name '{field_name}' with target '{target}'")
        
        if target == field_name:
            exact_name_matches.append(field)
            print(f"[DEBUG] Found name match: {field}")
    
    print(f"[DEBUG] Found {len(exact_name_matches)} exact name matches")
    
    # Handle exact name matches
    if len(exact_name_matches) == 1:
        print(f"[DEBUG] ✅ Single name match: {exact_name_matches[0]}")
        return exact_name_matches[0]
    elif len(exact_name_matches) > 1:
        # Multiple name matches - require disambiguation
        print(f"[DEBUG] ❌ Multiple name matches found, requiring disambiguation")
        print(f"\n⚠️  Multiple fields named '{target}' found:")
        for i, field in enumerate(exact_name_matches, 1):
            print(f"   {i}. {field}")
        
        print(f"\n💡 To select a specific one, use the full path:")
        for field in exact_name_matches:
            print(f"   Try: 'select {field}'")
        
        return None
    
    # Step 4: Fuzzy field name matching (last resort)
    print(f"[DEBUG] No exact matches, trying fuzzy matching...")
    
    best_match = None
    best_score = 0.7
    
    for field in field_list:
        field_name = field.split('/')[-1].lower()
        from difflib import SequenceMatcher
        similarity = SequenceMatcher(None, target, field_name).ratio()
        
        if similarity > best_score:
            best_score = similarity
            best_match = field
            print(f"[DEBUG] New best fuzzy match: {field} (score: {similarity:.2f})")
    
    if best_match:
        print(f"[DEBUG] ✅ Fuzzy match found: {best_match}")
    else:
        print(f"[DEBUG] ❌ No matches found")
    
    return best_match


You're absolutely right! The issue is that the **field selection intent** (`select_field` or `switch_field`) is not being recognized properly, and then it's trying to find a field literally named "switch to ranking" instead of understanding that "switch to" is the **intent** and "ranking" is the **target field**.

## **The Problem**

1. **Intent Parser Issue**: "can you switch to ranking" should be parsed as:
   - Intent: `select_field` 
   - Target: `ranking`

2. **But instead it's being parsed as**:
   - Intent: `unknown` 
   - Trying to find field: "switch to ranking" (literal)

## **Root Cause Analysis**

Looking at the enhanced intent parser patterns, the issue is likely:

### **1. Cleanup Not Applied to Field Selection**
The `clean_user_input()` should remove "can you" and "switch to" should map to `select_field` intent.

### **2. Pattern Matching Failure**
The spaCy patterns for field selection might not be comprehensive enough.

### **3. Missing Keyword Fallbacks**
The keyword fallback doesn't include "switch" as a field selection trigger.

## **Immediate Fixes**

### **1. Add "switch" to Field Selection Patterns**

**In your `_setup_patterns()` method, UPDATE the select_patterns:**

```python
# Field selection patterns - ADD switch patterns
select_patterns = [
    [{"LOWER": {"IN": ["select", "choose", "pick", "use", "switch"]}}, {"LOWER": "to", "OP": "?"}, {"TEXT": {"REGEX": ".*"}, "OP": "+"}],
    [{"LOWER": "work"}, {"LOWER": {"IN": ["on", "with"]}}, {"TEXT": {"REGEX": ".*"}, "OP": "+"}],
    [{"LOWER": {"IN": ["let's", "lets"]}}, {"LOWER": {"IN": ["work", "start"]}}, {"LOWER": "on", "OP": "?"}, {"TEXT": {"REGEX": ".*"}, "OP": "+"}],
    [{"LOWER": "i"}, {"LOWER": {"IN": ["want", "need"]}}, {"LOWER": "to", "OP": "?"}, {"LOWER": {"IN": ["work", "use", "switch"]}}, {"TEXT": {"REGEX": ".*"}, "OP": "+"}],
    [{"LOWER": {"IN": ["switch", "go", "move"]}}, {"LOWER": "to"}, {"TEXT": {"REGEX": ".*"}, "OP": "+"}],
    [{"LOWER": "field"}, {"TEXT": {"REGEX": ".*"}, "OP": "+"}]
]
```

### **2. Add "switch" to Command Variations**

**In your `_setup_cleanup_patterns()` method, UPDATE command_variations:**

```python
self.command_variations = {
    'generate': [
        'generate', 'create', 'make', 'build', 'produce', 'develop', 'construct',
        'give me', 'show me', 'provide', 'come up with', 'put together'
    ],
    # ... other commands ...
    'select_field': [  # ADD THIS
        'select', 'choose', 'pick', 'use', 'switch', 'go to', 'move to',
        'work on', 'work with', 'change to', 'switch to'
    ]
}
```

### **3. Enhanced Keyword Fallback**

**UPDATE your `_extract_intent_keywords()` method to handle "switch":**

```python
def _extract_intent_keywords(self, cleaned_input: str) -> dict:
    """Extract intent keywords with confidence scores"""
    
    intent_scores = {}
    words = cleaned_input.split()
    
    # Special handling for field selection keywords
    field_selection_triggers = ['select', 'choose', 'pick', 'use', 'switch', 'work on', 'go to']
    
    for trigger in field_selection_triggers:
        trigger_words = trigger.split()
        
        # Check for exact phrase or individual words
        if trigger in cleaned_input:
            intent_scores['select_field'] = 1.0
            break
        elif all(word in words for word in trigger_words):
            intent_scores['select_field'] = 0.8
            break
    
    # Continue with existing command variations logic...
    for intent, variations in self.command_variations.items():
        if intent == 'select_field':
            continue  # Already handled above
            
        score = 0.0
        for variation in variations:
            # ... existing logic
```

### **4. Debug the Specific Case**

**Add debug to see what's happening with "can you switch to ranking":**

```python
# Test this specific input
user_input = "can you switch to ranking"
cleaned = intent_parser.clean_user_input(user_input)
print(f"Original: '{user_input}'")
print(f"Cleaned: '{cleaned}'")

intent, params = intent_parser.parse_intent(user_input)
print(f"Intent: {intent}")
print(f"Params: {params}")
```

## **Quick Test Fix**

**Add this temporary debug in your main conversation loop:**

```python
# In your main conversation loop, BEFORE processing with orchestrator:
if 'switch' in user_input.lower() or 'change to' in user_input.lower():
    print(f"[DEBUG] Detected potential field switch: '{user_input}'")
    
    # Extract the target field manually for now
    if 'switch to' in user_input.lower():
        target_field = user_input.lower().split('switch to')[-1].strip()
        print(f"[DEBUG] Extracted target field: '{target_field}'")
        
        # Try to handle as field selection
        result = handle_select_field(target_field, available_fields, field_loader)
        if result[0]:  # Success
            session.current_field = result[0]
            session.current_field_metadata = field_loader.get_field_metadata(result[0])
            print(f"🤖 Assistant: {result[1]}")
            continue
```

## **Root Cause - Intent Parser Chain**

The issue is likely in this chain:
1. **spaCy patterns** don't match "can you switch to ranking"
2. **Keyword extraction** doesn't recognize "switch" as field selection
3. **Fuzzy matching** fails
4. **Falls through to unknown** → tries literal field search

## **Long-term Solution**

**Add a specialized field-switching detector:**

```python
def detect_field_switching_intent(self, user_input: str) -> tuple:
    """Specialized detector for field switching requests"""
    
    switch_patterns = [
        r'(?:can you |could you |please )?(?:switch|change|go|move) to (.+)',
        r'(?:work on|use) (.+) (?:field|now)',
        r'(?:let\'?s|lets) (?:work on|use) (.+)',
        r'(?:i want to|i need to) (?:work on|use|switch to) (.+)'
    ]
    
    user_lower = user_input.lower().strip()
    
    for pattern in switch_patterns:
        match = re.search(pattern, user_lower)
        if match:
            target_field = match.group(1).strip()
            # Remove common filler words from target
            target_field = re.sub(r'\b(the|a|an|field|now)\b', '', target_field).strip()
            
            return 'select_field', {'target': target_field, 'tc_ids': []}
    
    return None, {}
```

**Then call this in your `parse_intent()` method BEFORE spaCy processing:**

```python
def parse_intent(self, user_input: str) -> tuple:
    # ... existing code ...
    
    # Step 0: Check for field switching first (before cleanup)
    switch_intent, switch_params = self.detect_field_switching_intent(user_input)
    if switch_intent:
        print(f"[DEBUG] Detected field switching: {switch_intent}, {switch_params}")
        return switch_intent, switch_params
    
    # Step 1: Clean the input
    cleaned_input = self.clean_user_input(user_input)
    
    # ... rest of existing logic
```

This should fix the "can you switch to ranking" issue by properly detecting field switching intent before the general parsing logic takes over.
