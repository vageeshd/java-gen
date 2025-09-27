import spacy
import re
from spacy.matcher import Matcher
from spacy.util import filter_spans
from difflib import SequenceMatcher

class AdvancedUserIntentParser:
    """
    Complete enhanced intent parser with spaCy NLP, natural language cleanup,
    and comprehensive modification support - Drop-in replacement
    """
    
    def __init__(self):
        # Load spaCy model with fallback
        try:
            self.nlp = spacy.load("en_core_web_sm")
            print("[INFO] spaCy model loaded successfully")
        except OSError:
            print("❌ spaCy model not found. Install with: python -m spacy download en_core_web_sm")
            print("Falling back to basic tokenizer...")
            self.nlp = spacy.blank("en")
        
        self.matcher = Matcher(self.nlp.vocab)
        self._setup_patterns()
        
        # Test case ID patterns
        self.tc_id_pattern = r'TC_\d{3}'
        self.mod_id_pattern = r'TC_\d{3}_MODIFIED_\d+'
        
        # Natural language cleanup components
        self._setup_cleanup_patterns()
    
    def _setup_cleanup_patterns(self):
        """Setup patterns for natural language cleanup"""
        
        # Define comprehensive stop words and filler phrases
        self.stop_words = {
            'polite_words': ['please', 'kindly', 'could', 'would', 'can', 'will', 'may', 'might'],
            'filler_words': ['you', 'i', 'me', 'my', 'we', 'us', 'our', 'the', 'a', 'an', 'just', 'simply'],
            'request_starters': ['can you', 'could you', 'would you', 'will you', 'may i', 'might you'],
            'confirmation_words': ['go ahead', 'proceed', 'continue', 'do it', 'yes please', 'sure'],
            'question_starters': ['how do i', 'how can i', 'what should i', 'where do i', 'when should i'],
            'intensifiers': ['really', 'very', 'quite', 'rather', 'pretty', 'somewhat', 'definitely', 'absolutely']
        }
        
        # Request phrases to remove (ordered by length - longer first)
        self.request_phrases = [
            'can you please', 'could you please', 'would you please', 'will you please',
            'can you kindly', 'could you kindly', 'would you kindly', 'will you kindly',
            'i would like you to', 'i need you to', 'i want you to', 'i would love you to',
            'please can you', 'please could you', 'please would you', 'please will you',
            'i would like', 'i would love', 'i want', 'i need', 'i wish',
            'can you', 'could you', 'would you', 'will you', 'may you',
            'please', 'kindly'
        ]
        
        # Politeness endings to remove
        self.politeness_endings = [
            'please', 'thanks', 'thank you', 'if possible', 'for me', 'if you can',
            'if you could', 'if you would', 'when possible', 'at your convenience'
        ]
        
        # Command variations for flexible matching
        self.command_variations = {
            'generate': [
                'generate', 'create', 'make', 'build', 'produce', 'develop', 'construct',
                'give me', 'show me', 'provide', 'come up with', 'put together'
            ],
            'more': [
                'more', 'additional', 'extra', 'another', 'some more', 'a few more',
                'couple more', 'several more', 'add more', 'need more', 'want more'
            ],
            'modify': [
                'modify', 'change', 'update', 'edit', 'alter', 'adjust', 'fix',
                'improve', 'enhance', 'revise', 'correct', 'tweak', 'amend'
            ],
            'show': [
                'show', 'display', 'list', 'see', 'view', 'look at', 'check',
                'review', 'examine', 'inspect', 'present', 'reveal'
            ],
            'approve': [
                'approve', 'accept', 'keep', 'good', 'yes', 'ok', 'fine',
                'great', 'perfect', 'excellent', 'like', 'love'
            ],
            'reject': [
                'reject', 'remove', 'delete', 'discard', 'no', 'bad',
                'terrible', 'awful', 'hate', 'dislike', 'get rid of'
            ],
            'export': [
                'export', 'save', 'download', 'file', 'excel', 'done',
                'finish', 'complete', 'output', 'generate file'
            ]
        }
    
    def _setup_patterns(self):
        """Setup comprehensive spaCy matcher patterns for all intents"""
        
        # Field selection patterns
        select_patterns = [
            [{"LOWER": {"IN": ["select", "choose", "pick", "use"]}}, {"TEXT": {"REGEX": ".*"}, "OP": "+"}],
            [{"LOWER": "work"}, {"LOWER": {"IN": ["on", "with"]}}, {"TEXT": {"REGEX": ".*"}, "OP": "+"}],
            [{"LOWER": {"IN": ["let's", "lets"]}}, {"LOWER": {"IN": ["work", "start"]}}, {"LOWER": "on", "OP": "?"}, {"TEXT": {"REGEX": ".*"}, "OP": "+"}],
            [{"LOWER": "i"}, {"LOWER": {"IN": ["want", "need"]}}, {"LOWER": "to", "OP": "?"}, {"LOWER": {"IN": ["work", "use"]}}, {"TEXT": {"REGEX": ".*"}, "OP": "+"}],
            [{"LOWER": {"IN": ["switch", "go"]}}, {"LOWER": "to"}, {"TEXT": {"REGEX": ".*"}, "OP": "+"}],
            [{"LOWER": "field"}, {"TEXT": {"REGEX": ".*"}, "OP": "+"}]
        ]
        
        # Search patterns
        search_patterns = [
            [{"LOWER": {"IN": ["search", "find", "look"]}}, {"LOWER": "for", "OP": "?"}, {"TEXT": {"REGEX": ".*"}, "OP": "+"}],
            [{"LOWER": "show"}, {"LOWER": "me", "OP": "?"}, {"TEXT": {"REGEX": ".*"}}, {"LOWER": "fields"}],
            [{"LOWER": {"IN": ["do", "are"]}}, {"LOWER": "you"}, {"LOWER": "have"}, {"TEXT": {"REGEX": ".*"}, "OP": "+"}],
            [{"LOWER": "any"}, {"TEXT": {"REGEX": ".*"}}, {"LOWER": "fields", "OP": "?"}]
        ]
        
        # List patterns
        list_patterns = [
            [{"LOWER": {"IN": ["list", "show"]}}, {"LOWER": {"IN": ["all", "everything", "options", "available"]}}],
            [{"LOWER": "what"}, {"LOWER": {"IN": ["fields", "options"]}}, {"LOWER": {"IN": ["are", "do"]}, "OP": "?"}, {"LOWER": {"IN": ["available", "you", "we"]}, "OP": "?"}],
            [{"LOWER": {"IN": ["show", "list"]}}, {"LOWER": {"IN": ["available", "all"]}, "OP": "?"}, {"LOWER": "fields", "OP": "?"}],
            [{"LOWER": {"IN": ["what's", "whats"]}}, {"LOWER": "available"}]
        ]
        
        # Generation patterns
        generate_patterns = [
            [{"LOWER": {"IN": ["generate", "create", "make", "build", "produce"]}}],
            [{"LOWER": {"IN": ["generate", "create", "make", "build"]}}, {"LOWER": {"IN": ["test", "tests"]}, "OP": "?"}, {"LOWER": {"IN": ["cases", "case"]}, "OP": "?"}],
            [{"LOWER": {"IN": ["let's", "lets"]}}, {"LOWER": {"IN": ["start", "begin", "go"]}}],
            [{"LOWER": {"IN": ["go", "do"]}}, {"LOWER": {"IN": ["ahead", "it"]}}],
            [{"LOWER": "start"}, {"LOWER": {"IN": ["generating", "creating"]}, "OP": "?"}],
            [{"LOWER": {"IN": ["give", "show", "provide"]}}, {"LOWER": "me"}, {"LOWER": {"IN": ["some", "test", "tests"]}, "OP": "?"}]
        ]
        
        # More generation patterns
        more_patterns = [
            [{"LOWER": {"IN": ["more", "additional", "extra", "another"]}}],
            [{"LOWER": {"IN": ["generate", "create", "make"]}}, {"LOWER": "more"}],
            [{"LOWER": {"IN": ["need", "want"]}}, {"LOWER": "more"}],
            [{"LOWER": "give"}, {"LOWER": "me"}, {"LOWER": "more"}],
            [{"LOWER": {"IN": ["again", "regenerate"]}}],
            [{"LOWER": {"IN": ["few", "couple", "several"]}}, {"LOWER": "more"}]
        ]
        
        # Improvement/modification patterns (general)
        improve_patterns = [
            [{"LOWER": {"IN": ["improve", "enhance", "better", "fix"]}}, {"TEXT": {"REGEX": ".*"}, "OP": "*"}],
            [{"LOWER": {"IN": ["change", "modify", "update", "adjust"]}}, {"TEXT": {"REGEX": ".*"}, "OP": "*"}],
            [{"LOWER": "make"}, {"TEXT": {"REGEX": ".*"}, "OP": "*"}, {"LOWER": {"IN": ["better", "different"]}}],
            [{"LOWER": {"IN": ["can", "could"]}}, {"LOWER": "you"}, {"TEXT": {"REGEX": ".*"}, "OP": "+"}],
            [{"LOWER": "i"}, {"LOWER": {"IN": ["want", "need"]}}, {"TEXT": {"REGEX": ".*"}, "OP": "+"}],
            [{"LOWER": {"IN": ["add", "include"]}}, {"TEXT": {"REGEX": ".*"}, "OP": "+"}]
        ]
        
        # Specific test case modification patterns
        modify_tc_patterns = [
            # Direct TC ID modification
            [{"TEXT": {"REGEX": r"TC_\d{3}"}}, {"LOWER": {"IN": ["to", "should", "needs", "must"]}}, {"TEXT": {"REGEX": ".*"}, "OP": "+"}],
            [{"LOWER": {"IN": ["modify", "change", "update", "fix"]}}, {"TEXT": {"REGEX": r"TC_\d{3}"}}, {"TEXT": {"REGEX": ".*"}, "OP": "*"}],
            [{"LOWER": {"IN": ["change", "modify", "update"]}}, {"LOWER": {"IN": ["the", "that"]}, "OP": "?"}, {"LOWER": {"IN": ["first", "second", "third", "last"]}}, {"LOWER": {"IN": ["test", "case"]}}],
            # Ordinal references
            [{"LOWER": {"IN": ["modify", "change", "update"]}}, {"LOWER": {"IN": ["test", "case"]}}, {"TEXT": {"REGEX": r"\d+"}}],
            [{"LOWER": {"IN": ["the", "that"]}, "OP": "?"}, {"LOWER": {"IN": ["first", "second", "third", "last"]}}, {"LOWER": {"IN": ["test", "case"]}}, {"TEXT": {"REGEX": ".*"}, "OP": "*"}]
        ]
        
        # Approve modification patterns
        approve_mod_patterns = [
            [{"TEXT": {"REGEX": r"TC_\d{3}_MODIFIED_\d+"}}, {"LOWER": {"IN": ["approved", "accepted", "good", "ok"]}, "OP": "?"}],
            [{"LOWER": {"IN": ["approve", "accept", "yes", "keep"]}}, {"TEXT": {"REGEX": r"TC_\d{3}_MODIFIED_\d+"}}],
            [{"LOWER": {"IN": ["approve", "accept"]}}, {"LOWER": {"IN": ["the", "this"]}, "OP": "?"}, {"LOWER": {"IN": ["modification", "change", "update"]}}],
            [{"LOWER": "yes"}, {"LOWER": "to"}, {"TEXT": {"REGEX": r"TC_\d{3}_MODIFIED_\d+"}}],
            [{"LOWER": {"IN": ["looks", "look"]}}, {"LOWER": "good"}, {"TEXT": {"REGEX": r"TC_\d{3}_MODIFIED_\d+"}, "OP": "?"}],
            [{"LOWER": {"IN": ["that's", "thats"]}}, {"LOWER": {"IN": ["good", "better", "perfect"]}}]
        ]
        
        # Reject modification patterns  
        reject_mod_patterns = [
            [{"LOWER": {"IN": ["reject", "no", "discard"]}}, {"TEXT": {"REGEX": r"TC_\d{3}_MODIFIED_\d+"}}],
            [{"TEXT": {"REGEX": r"TC_\d{3}_MODIFIED_\d+"}}, {"LOWER": {"IN": ["rejected", "bad", "wrong", "no"]}}],
            [{"LOWER": "no"}, {"LOWER": "to"}, {"TEXT": {"REGEX": r"TC_\d{3}_MODIFIED_\d+"}}],
            [{"LOWER": {"IN": ["don't", "dont"]}}, {"LOWER": {"IN": ["want", "like"]}}, {"TEXT": {"REGEX": r"TC_\d{3}_MODIFIED_\d+"}}],
            [{"LOWER": {"IN": ["reject", "discard"]}}, {"LOWER": {"IN": ["the", "this"]}, "OP": "?"}, {"LOWER": {"IN": ["modification", "change"]}}],
            [{"LOWER": {"IN": ["that's", "thats"]}}, {"LOWER": {"IN": ["wrong", "bad", "terrible"]}}]
        ]
        
        # Show modifications patterns
        show_mod_patterns = [
            [{"LOWER": "show"}, {"LOWER": {"IN": ["modifications", "changes", "pending"]}}],
            [{"LOWER": {"IN": ["what", "which"]}}, {"LOWER": {"IN": ["modifications", "changes"]}}, {"LOWER": {"IN": ["are", "do"]}, "OP": "?"}, {"LOWER": "pending", "OP": "?"}],
            [{"LOWER": {"IN": ["review", "see"]}}, {"LOWER": {"IN": ["modifications", "changes"]}}],
            [{"LOWER": "pending"}, {"LOWER": {"IN": ["modifications", "changes"]}}],
            [{"LOWER": {"IN": ["show", "display"]}}, {"LOWER": "me"}, {"LOWER": {"IN": ["modifications", "changes"]}}],
            [{"LOWER": {"IN": ["what", "which"]}}, {"LOWER": {"IN": ["changes", "modifications"]}}, {"LOWER": {"IN": ["need", "require"]}, "OP": "?"}, {"LOWER": {"IN": ["approval", "review"]}}]
        ]
        
        # Approval patterns (regular test cases)
        approve_patterns = [
            [{"LOWER": {"IN": ["approve", "accept", "keep"]}}],
            [{"LOWER": {"IN": ["yes", "good", "great", "perfect", "excellent"]}}],
            [{"LOWER": {"IN": ["looks", "look"]}}, {"LOWER": "good"}],
            [{"LOWER": "that's"}, {"LOWER": {"IN": ["good", "great", "perfect"]}}],
            [{"LOWER": {"IN": ["approve", "accept", "keep"]}}, {"LOWER": "all"}],
            [{"LOWER": "i"}, {"LOWER": "like"}, {"TEXT": {"REGEX": ".*"}, "OP": "*"}],
            [{"LOWER": {"IN": ["all", "everything"]}}, {"LOWER": {"IN": ["looks", "look"]}}, {"LOWER": "good"}]
        ]
        
        # Rejection patterns (regular test cases)
        reject_patterns = [
            [{"LOWER": {"IN": ["reject", "remove", "delete", "discard"]}}],
            [{"LOWER": {"IN": ["no", "bad", "terrible", "awful", "wrong"]}}],
            [{"LOWER": {"IN": ["don't", "dont"]}}, {"LOWER": {"IN": ["want", "like"]}}],
            [{"LOWER": "get"}, {"LOWER": "rid"}, {"LOWER": "of"}],
            [{"LOWER": {"IN": ["i", "that's"]}}, {"LOWER": {"IN": ["hate", "dislike"]}}]
        ]
        
        # Show/review patterns
        show_patterns = [
            [{"LOWER": {"IN": ["show", "display", "see", "review"]}}],
            [{"LOWER": "what"}, {"LOWER": {"IN": ["do", "did"]}, "OP": "?"}, {"LOWER": {"IN": ["we", "you"]}, "OP": "?"}, {"LOWER": "have"}],
            [{"LOWER": "let"}, {"LOWER": "me"}, {"LOWER": "see"}],
            [{"LOWER": {"IN": ["what's", "whats"]}}, {"LOWER": {"IN": ["there", "pending", "generated"]}}],
            [{"LOWER": {"IN": ["review", "check"]}}, {"LOWER": {"IN": ["tests", "cases"]}, "OP": "?"}]
        ]
        
        # Show all patterns
        show_all_patterns = [
            [{"LOWER": "show"}, {"LOWER": "all"}],
            [{"LOWER": "all"}, {"LOWER": {"IN": ["cases", "tests"]}}],
            [{"LOWER": {"IN": ["everything", "status", "summary"]}}],
            [{"LOWER": {"IN": ["full", "complete"]}}, {"LOWER": {"IN": ["status", "summary"]}}]
        ]
        
        # Export patterns
        export_patterns = [
            [{"LOWER": {"IN": ["export", "save", "download"]}}],
            [{"LOWER": {"IN": ["we're", "were", "i'm", "im"]}}, {"LOWER": {"IN": ["done", "finished"]}}],
            [{"LOWER": {"IN": ["create", "make"]}}, {"LOWER": {"IN": ["file", "excel"]}}],
            [{"LOWER": {"IN": ["finish", "complete", "done"]}}]
        ]
        
        # Complete field patterns
        complete_patterns = [
            [{"LOWER": {"IN": ["complete", "finish"]}}, {"LOWER": {"IN": ["field", "this"]}, "OP": "?"}],
            [{"LOWER": {"IN": ["done", "finished"]}}, {"LOWER": "with"}, {"TEXT": {"REGEX": ".*"}, "OP": "*"}],
            [{"LOWER": {"IN": ["field", "this"]}}, {"LOWER": {"IN": ["complete", "done", "finished"]}}]
        ]
        
        # Help patterns
        help_patterns = [
            [{"LOWER": "help"}],
            [{"LOWER": {"IN": ["what", "how"]}}, {"LOWER": {"IN": ["can", "do", "should"]}}, {"LOWER": "i"}],
            [{"LOWER": {"IN": ["i'm", "im"]}}, {"LOWER": {"IN": ["lost", "confused"]}}],
            [{"LOWER": "guide"}, {"LOWER": "me"}],
            [{"LOWER": {"IN": ["what", "which"]}}, {"LOWER": {"IN": ["commands", "options"]}}]
        ]
        
        # Add all patterns to matcher
        self.matcher.add("SELECT_FIELD", select_patterns)
        self.matcher.add("SEARCH_FIELD", search_patterns)
        self.matcher.add("LIST_FIELDS", list_patterns)
        self.matcher.add("GENERATE", generate_patterns)
        self.matcher.add("MORE", more_patterns)
        self.matcher.add("IMPROVE", improve_patterns)
        self.matcher.add("MODIFY_TESTCASE", modify_tc_patterns)
        self.matcher.add("APPROVE_MODIFICATION", approve_mod_patterns)
        self.matcher.add("REJECT_MODIFICATION", reject_mod_patterns)
        self.matcher.add("SHOW_MODIFICATIONS", show_mod_patterns)
        self.matcher.add("APPROVE", approve_patterns)
        self.matcher.add("REJECT", reject_patterns)
        self.matcher.add("SHOW", show_patterns)
        self.matcher.add("SHOW_ALL", show_all_patterns)
        self.matcher.add("EXPORT", export_patterns)
        self.matcher.add("COMPLETE_FIELD", complete_patterns)
        self.matcher.add("HELP", help_patterns)
    
    def clean_user_input(self, user_input: str) -> str:
        """Clean user input by removing stop words and filler phrases"""
        
        cleaned = user_input.lower().strip()
        
        # Remove common request phrases (order matters - longer phrases first)
        for phrase in self.request_phrases:
            if cleaned.startswith(phrase + ' '):
                cleaned = cleaned[len(phrase):].strip()
                break
        
        # Remove trailing politeness
        for ending in self.politeness_endings:
            if cleaned.endswith(' ' + ending):
                cleaned = cleaned[:-len(ending)].strip()
            elif cleaned.endswith(ending + '.'):
                cleaned = cleaned[:-len(ending)-1].strip()
        
        # Clean up extra whitespace and common filler words at start/end
        words = cleaned.split()
        
        # Remove leading filler words
        while words and words[0] in ['just', 'simply', 'maybe', 'perhaps', 'possibly', 'really']:
            words.pop(0)
        
        # Remove trailing filler words  
        while words and words[-1] in ['now', 'today', 'here', 'there', 'then']:
            words.pop()
        
        result = ' '.join(words).strip()
        
        # If we cleaned too much, return original
        if len(result) < 2:
            return user_input.strip()
        
        return result
    
    def parse_intent(self, user_input: str) -> tuple:
        """Enhanced intent parsing with natural language cleanup and comprehensive support"""
        
        if not user_input.strip():
            return 'unknown', {}
        
        original_input = user_input.strip()
        
        # Step 1: Clean the input
        cleaned_input = self.clean_user_input(user_input)
        
        # Step 2: Extract test case IDs from original input (preserve case and full context)
        tc_ids = re.findall(self.tc_id_pattern, original_input.upper())
        mod_ids = re.findall(self.mod_id_pattern, original_input.upper())
        all_ids = tc_ids + mod_ids
        
        # Step 3: Try spaCy parsing on cleaned input
        try:
            doc = self.nlp(cleaned_input.lower())
            matches = self.matcher(doc)
            
            if matches:
                # Sort matches by priority (modification patterns first)
                priority_labels = [
                    "APPROVE_MODIFICATION", "REJECT_MODIFICATION", "SHOW_MODIFICATIONS",
                    "MODIFY_TESTCASE", "APPROVE", "REJECT", "GENERATE", "MORE",
                    "SELECT_FIELD", "SEARCH_FIELD", "LIST_FIELDS"
                ]
                
                # Find the highest priority match
                best_match = None
                best_priority = float('inf')
                
                for match in matches:
                    match_id, start, end = match
                    label = self.nlp.vocab.strings[match_id]
                    
                    if label in priority_labels:
                        priority = priority_labels.index(label)
                        if priority < best_priority:
                            best_priority = priority
                            best_match = match
                    
                    if best_match is None:
                        best_match = match
                
                match_id, start, end = best_match
                label = self.nlp.vocab.strings[match_id]
                
                # Convert spaCy label to intent
                intent = self._map_spacy_label_to_intent(label)
                
                # Build parameters
                params = self._build_intent_parameters(
                    label, doc, start, end, all_ids, original_input, cleaned_input
                )
                
                return intent, params
        
        except Exception as e:
            print(f"[DEBUG] spaCy parsing failed: {e}, falling back to keyword matching")
        
        # Step 4: Enhanced keyword fallback with cleaned input
        intent_scores = self._extract_intent_keywords(cleaned_input)
        
        if intent_scores:
            best_intent, confidence = max(intent_scores.items(), key=lambda x: x[1])
            
            if confidence > 0.5:  # Confidence threshold
                return self._map_keyword_to_intent(best_intent), {
                    'tc_ids': all_ids,
                    'target': cleaned_input,
                    'original_input': original_input,
                    'confidence': confidence,
                    'fallback': 'keyword_enhanced'
                }
        
        # Step 5: Final fuzzy matching
        fuzzy_intent = self._fuzzy_match_intent(cleaned_input)
        if fuzzy_intent:
            return fuzzy_intent, {
                'tc_ids': all_ids, 
                'target': cleaned_input, 
                'original_input': original_input,
                'fallback': 'fuzzy'
            }
        
        return 'unknown', {
            'raw_input': original_input, 
            'cleaned_input': cleaned_input,
            'tc_ids': all_ids
        }
    
    def _map_spacy_label_to_intent(self, label: str) -> str:
        """Map spaCy labels to intent names"""
        
        intent_map = {
            "SELECT_FIELD": "select_field",
            "SEARCH_FIELD": "search_field", 
            "LIST_FIELDS": "list_fields",
            "GENERATE": "generate",
            "MORE": "regenerate",
            "IMPROVE": "improve",
            "MODIFY_TESTCASE": "improve",  # Routes to improve but with specific TC context
            "APPROVE": "approve",
            "REJECT": "reject",
            "SHOW": "show_pending",
            "SHOW_ALL": "show_all",
            "EXPORT": "export",
            "COMPLETE_FIELD": "complete_field",
            "HELP": "help",
            
            # MODIFICATION INTENTS
            "APPROVE_MODIFICATION": "approve_modification",
            "REJECT_MODIFICATION": "reject_modification",
            "SHOW_MODIFICATIONS": "show_modifications"
        }
        
        return intent_map.get(label, "unknown")
    
    def _build_intent_parameters(self, label: str, doc, start: int, end: int, 
                               all_ids: list, original_input: str, cleaned_input: str) -> dict:
        """Build parameters based on intent type and extracted information"""
        
        params = {'tc_ids': all_ids}
        
        # Special handling for modification IDs
        mod_ids = [tc_id for tc_id in all_ids if 'MODIFIED' in tc_id]
        if mod_ids:
            params['modification_ids'] = mod_ids
            params['is_modification_action'] = True
        
        # Extract target/context based on intent type
        if label == "MODIFY_TESTCASE":
            # For test case modifications, preserve the full request
            params['target'] = original_input
            params['specific_tc_modification'] = True
        elif label in ["APPROVE_MODIFICATION", "REJECT_MODIFICATION", "SHOW_MODIFICATIONS"]:
            # For modification actions, use original input
            params['target'] = original_input
            params['is_modification_action'] = True
        else:
            # Standard target extraction from remaining tokens
            remaining_tokens = [token.text for i, token in enumerate(doc) if i < start or i >= end]
            if remaining_tokens:
                params['target'] = ' '.join(remaining_tokens).strip()
            elif end < len(doc):
                params['target'] = ' '.join([token.text for token in doc[end:]]).strip()
            else:
                params['target'] = cleaned_input
        
        # Clean up target by removing excessive stop words
        if 'target' in params and params['target']:
            params['target'] = self._clean_target_text(params['target'])
        
        return params
    
    def _clean_target_text(self, target: str) -> str:
        """Clean target text while preserving important context"""
        
        if not target:
            return target
        
        # Remove common stop words but preserve important context
        stop_words = {'the', 'a', 'an', 'to', 'for', 'with', 'on', 'at', 'by', 'in'}
        words = target.split()
        
        # Only remove stop words if we have enough context left
        if len(words) > 3:
            filtered_words = [word for word in words if word.lower() not in stop_words]
            if len(filtered_words) >= 2:  # Ensure we keep meaningful content
                return ' '.join(filtered_words)
        
        return target
    
    def _extract_intent_keywords(self, cleaned_input: str) -> dict:
        """Extract intent keywords with confidence scores"""
        
        intent_scores = {}
        words = cleaned_input.split()
        
        # Check for each command variation
        for intent, variations in self.command_variations.items():
            score = 0.0
            
            for variation in variations:
                variation_words = variation.split()
                
                # Exact phrase match (highest score)
                if variation in cleaned_input:
                    score = max(score, 1.0)
                
                # Partial word match with position weighting
                elif any(word in words for word in variation_words):
                    matching_words = sum(1 for word in variation_words if word in words)
                    word_score = matching_words / len(variation_words)
                    
                    # Boost score if match is at beginning of sentence
                    if words and words[0] in variation_words:
                        word_score *= 1.2
                    
                    score = max(score, word_score * 0.8)
            
            if score > 0:
                intent_scores[intent] = min(score, 1.0)  # Cap at 1.0
        
        return intent_scores
    
    def _map_keyword_to_intent(self, keyword_intent: str) -> str:
        """Map keyword intentions to actual intents"""
        
        keyword_to_intent = {
            'generate': 'generate',
            'more': 'regenerate', 
            'modify': 'improve',
            'show': 'show_pending',
            'approve': 'approve',
            'reject': 'reject',
            'export': 'export'
        }
        
        return keyword_to_intent.get(keyword_intent, 'unknown')
    
    def _fuzzy_match_intent(self, user_input: str) -> str:
        """Use fuzzy matching for intent recognition as final fallback"""
        
        intent_keywords = {
            'generate': ['generate', 'create', 'make', 'build'],
            'approve': ['approve', 'accept', 'yes', 'good', 'keep'],
            'reject': ['reject', 'no', 'bad', 'remove', 'delete'],
            'export': ['export', 'save', 'download', 'excel'],
            'show_pending': ['show', 'display', 'review', 'see'],
            'help': ['help', 'commands', 'how'],
            'improve': ['improve', 'change', 'modify', 'better'],
            'select_field': ['select', 'choose', 'field'],
            'regenerate': ['more', 'additional', 'again']
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
    
    def handle_natural_language_variations(self, user_input: str) -> str:
        """Handle common natural language variations and convert to standard form"""
        
        # Common variations mapping
        variations = {
            'give me some tests': 'generate test cases',
            'make some more': 'generate more test cases',
            'let me see what we have': 'show pending test cases',
            'are we done': 'show status',
            'what do you think': 'show pending test cases',
            'looks good to me': 'approve all',
            'not quite right': 'need modifications',
            'make it better': 'improve test cases',
            'save everything': 'export test cases',
            'show me everything': 'show all test cases',
            'what have we got': 'show pending test cases',
            'that will do': 'approve all',
            'wrap it up': 'export test cases',
            'we are good': 'approve all',
            'start over': 'clear and restart'
        }
        
        user_lower = user_input.lower().strip()
        
        # Check for direct matches
        if user_lower in variations:
            return variations[user_lower]
        
        # Check for partial matches
        for variation, standard_form in variations.items():
            if variation in user_lower or user_lower in variation:
                return standard_form
        
        return user_input
    
    def get_intent_suggestions(self, failed_input: str) -> list:
        """Get suggested intents when parsing fails"""
        
        suggestions = [
            "Try: 'generate test cases' to create tests",
            "Try: 'show pending' to review existing cases", 
            "Try: 'approve TC_001' to approve specific tests",
            "Try: 'export results' to save your work",
            "Try: 'help' to see all available commands"
        ]
        
        # Add context-specific suggestions based on failed input
        failed_lower = failed_input.lower()
        
        if any(word in failed_lower for word in ['test', 'case', 'TC_']):
            suggestions.insert(0, "Try: 'modify TC_001 to [your changes]' to change specific tests")
        
        if any(word in failed_lower for word in ['field', 'select', 'choose']):
            suggestions.insert(0, "Try: 'select [field_name]' to work on a specific field")
        
        if any(word in failed_lower for word in ['save', 'download', 'file']):
            suggestions.insert(0, "Try: 'export to excel' to save your test cases")
        
        return suggestions[:4]  # Return top 4 suggestions
    
    def analyze_input_complexity(self, user_input: str) -> dict:
        """Analyze input complexity and provide debugging info"""
        
        cleaned = self.clean_user_input(user_input)
        tc_ids = re.findall(self.tc_id_pattern, user_input.upper())
        mod_ids = re.findall(self.mod_id_pattern, user_input.upper())
        
        analysis = {
            'original_length': len(user_input),
            'cleaned_length': len(cleaned),
            'word_count': len(user_input.split()),
            'cleaned_word_count': len(cleaned.split()),
            'has_test_case_ids': len(tc_ids) > 0,
            'has_modification_ids': len(mod_ids) > 0,
            'polite_phrases_detected': any(phrase in user_input.lower() for phrase in self.request_phrases[:5]),
            'question_indicators': '?' in user_input or any(q in user_input.lower() for q in ['what', 'how', 'why', 'when', 'where']),
            'complexity_score': len(user_input.split()) + (2 if '?' in user_input else 0) + len(tc_ids)
        }
        
        return analysis
    
    # BACKWARD COMPATIBILITY METHODS
    # These ensure the enhanced parser works as drop-in replacement
    
    def _fuzzy_match_intent_legacy(self, user_input: str) -> str:
        """Legacy fuzzy matching method for backward compatibility"""
        return self._fuzzy_match_intent(user_input)
    
    def get_intent_confidence(self, user_input: str) -> float:
        """Get confidence score for intent recognition"""
        
        try:
            intent, params = self.parse_intent(user_input)
            
            if intent == 'unknown':
                return 0.0
            elif params.get('fallback') == 'fuzzy':
                return 0.4
            elif params.get('fallback') == 'keyword_enhanced':
                return params.get('confidence', 0.6)
            else:
                return 0.9  # spaCy match
                
        except Exception:
            return 0.0
    
    def debug_parse_intent(self, user_input: str) -> dict:
        """Debug version of parse_intent that returns detailed information"""
        
        debug_info = {
            'original_input': user_input,
            'cleaned_input': self.clean_user_input(user_input),
            'analysis': self.analyze_input_complexity(user_input)
        }
        
        try:
            intent, params = self.parse_intent(user_input)
            debug_info.update({
                'parsed_intent': intent,
                'parameters': params,
                'confidence': self.get_intent_confidence(user_input),
                'success': True
            })
        except Exception as e:
            debug_info.update({
                'parsed_intent': 'unknown',
                'error': str(e),
                'success': False,
                'suggestions': self.get_intent_suggestions(user_input)
            })
        
        return debug_info
    
    def validate_test_case_references(self, tc_ids: list, existing_cases: list) -> dict:
        """Validate that referenced test case IDs exist"""
        
        existing_tc_ids = [case.get('Test Case ID', '') for case in existing_cases]
        
        valid_ids = [tc_id for tc_id in tc_ids if tc_id in existing_tc_ids]
        invalid_ids = [tc_id for tc_id in tc_ids if tc_id not in existing_tc_ids]
        
        return {
            'valid_ids': valid_ids,
            'invalid_ids': invalid_ids,
            'all_valid': len(invalid_ids) == 0
        }
    
    def suggest_test_case_corrections(self, invalid_tc_id: str, existing_cases: list) -> list:
        """Suggest corrections for invalid test case IDs"""
        
        existing_tc_ids = [case.get('Test Case ID', '') for case in existing_cases]
        suggestions = []
        
        # Try fuzzy matching
        for existing_id in existing_tc_ids:
            similarity = SequenceMatcher(None, invalid_tc_id.lower(), existing_id.lower()).ratio()
            if similarity > 0.6:
                suggestions.append(existing_id)
        
        # If no fuzzy matches, suggest first few test cases
        if not suggestions and existing_tc_ids:
            suggestions = existing_tc_ids[:3]
        
        return suggestions
    
    def extract_ordinal_references(self, user_input: str, existing_cases: list) -> dict:
        """Extract ordinal references like 'first test', 'second case', etc."""
        
        ordinals = {
            'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
            'last': len(existing_cases) if existing_cases else 1,
            '1st': 1, '2nd': 2, '3rd': 3, '4th': 4, '5th': 5
        }
        
        input_lower = user_input.lower()
        found_ordinals = {}
        
        for ordinal, position in ordinals.items():
            if ordinal in input_lower and position <= len(existing_cases):
                tc_id = existing_cases[position - 1].get('Test Case ID', '') if existing_cases else ''
                if tc_id:
                    found_ordinals[ordinal] = tc_id
        
        return found_ordinals
    
    def preprocess_common_typos(self, user_input: str) -> str:
        """Preprocess and fix common typos in user input"""
        
        typo_corrections = {
            'generat': 'generate',
            'creat': 'create',
            'approv': 'approve',
            'rejct': 'reject',
            'modif': 'modify',
            'chang': 'change',
            'updat': 'update',
            'delet': 'delete',
            'remov': 'remove',
            'exprt': 'export',
            'sav': 'save',
            'tes case': 'test case',
            'test cas': 'test case',
            'TC ': 'TC_',
            'tc ': 'TC_'
        }
        
        corrected = user_input
        for typo, correction in typo_corrections.items():
            corrected = re.sub(r'\b' + typo + r'\b', correction, corrected, flags=re.IGNORECASE)
        
        return corrected
    
    