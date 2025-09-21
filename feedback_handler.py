import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

class FeedbackType(Enum):
    """Types of user feedback"""
    QUESTION = "question"           # User asking a question
    MODIFICATION = "modification"   # Request to modify test cases  
    ADDITION = "addition"          # Request for additional test cases
    CLARIFICATION = "clarification" # Seeking clarification
    APPROVAL = "approval"          # Approving test cases
    REJECTION = "rejection"        # Rejecting test cases
    GENERAL = "general"            # General feedback/comments

@dataclass
class FeedbackAnalysis:
    """Analysis result of user feedback"""
    feedback_type: FeedbackType
    confidence: float
    requires_generation: bool
    requires_response: bool
    extracted_intent: str
    relevant_tc_ids: List[str] = None
    is_question: bool = False
    suggested_response_type: str = "text"  # "text" or "generation"

class EnhancedFeedbackHandler:
    """
    Enhanced feedback handler that processes user feedback and determines appropriate actions
    """
    
    def __init__(self, test_manager):
        self.test_manager = test_manager
        
        # Pattern definitions for feedback classification
        self.question_indicators = [
            r'\?',  # Direct question mark
            r'\b(?:what|how|why|when|where|which|who)\b',
            r'\b(?:can you|could you|would you|should i|do you)\b',
            r'\b(?:explain|tell me|help me understand|clarify|describe)\b',
            r'\b(?:is there|are there|will there)\b'
        ]
        
        self.modification_indicators = [
            r'\b(?:change|modify|update|edit|fix|correct|improve|adjust)\b',
            r'\b(?:instead of|rather than|replace|substitute)\b',
            r'\b(?:different|alternative|better|enhanced)\b',
            r'\b(?:revise|rework|redo)\b'
        ]
        
        self.addition_indicators = [
            r'\b(?:add|include|generate|create|need more|additional|extra)\b',
            r'\b(?:also|plus|furthermore|moreover|and also)\b',
            r'\b(?:missing|lacking|require|want|need)\b',
            r'\b(?:more|another|other)\b'
        ]
        
        self.approval_indicators = [
            r'\b(?:good|great|excellent|perfect|approve|accept|ok|okay|fine|looks good)\b',
            r'\b(?:yes|correct|right|agreed|sounds good)\b',
            r'\b(?:proceed|continue|next|move forward)\b',
            r'\b(?:like it|love it|works for me)\b'
        ]
        
        self.rejection_indicators = [
            r'\b(?:no|not|reject|wrong|incorrect|bad|poor)\b',
            r'\b(?:don\'t|doesn\'t|won\'t|can\'t)\b',
            r'\b(?:remove|delete|discard|eliminate)\b',
            r'\b(?:hate|dislike|terrible)\b'
        ]
    
    def analyze_feedback(self, feedback_text: str, current_field: str = None) -> FeedbackAnalysis:
        """
        Analyze user feedback to determine intent and required actions
        """
        feedback_lower = feedback_text.lower().strip()
        
        if not feedback_lower:
            return self._create_default_analysis()
        
        # Calculate scores for each feedback type
        question_score = self._calculate_pattern_score(feedback_lower, self.question_indicators)
        modification_score = self._calculate_pattern_score(feedback_lower, self.modification_indicators)
        addition_score = self._calculate_pattern_score(feedback_lower, self.addition_indicators)
        approval_score = self._calculate_pattern_score(feedback_lower, self.approval_indicators)
        rejection_score = self._calculate_pattern_score(feedback_lower, self.rejection_indicators)
        
        # Additional heuristics
        has_question_mark = '?' in feedback_text
        is_short = len(feedback_text.split()) <= 3
        
        # Boost question score if question mark present
        if has_question_mark:
            question_score += 0.3
        
        # Handle short approval/rejection phrases
        if is_short:
            if approval_score > 0:
                approval_score += 0.2
            if rejection_score > 0:
                rejection_score += 0.2
        
        # Determine primary feedback type
        scores = {
            FeedbackType.QUESTION: question_score,
            FeedbackType.MODIFICATION: modification_score,
            FeedbackType.ADDITION: addition_score,
            FeedbackType.APPROVAL: approval_score,
            FeedbackType.REJECTION: rejection_score
        }
        
        max_score = max(scores.values())
        
        if max_score == 0:
            primary_type = FeedbackType.GENERAL
            confidence = 0.5
        else:
            primary_type = max(scores, key=scores.get)
            total_score = sum(scores.values())
            confidence = max_score / total_score if total_score > 0 else 0.5
        
        # Special case: clarification requests
        clarification_words = ['clarify', 'explain', 'understand', 'confusion', 'unclear']
        if any(word in feedback_lower for word in clarification_words):
            primary_type = FeedbackType.CLARIFICATION
            confidence = min(confidence * 1.2, 1.0)
        
        # Extract relevant test case IDs
        relevant_tc_ids = self._extract_tc_ids(feedback_text)
        
        # Determine if this is a question vs generation request
        is_question = primary_type in [FeedbackType.QUESTION, FeedbackType.CLARIFICATION] or has_question_mark
        
        # Determine required actions
        requires_generation = primary_type in [FeedbackType.MODIFICATION, FeedbackType.ADDITION, FeedbackType.REJECTION]
        requires_response = True  # Always provide some response
        
        # Determine response type
        suggested_response_type = "text" if is_question else ("generation" if requires_generation else "text")
        
        # Extract clean intent
        extracted_intent = self._clean_intent(feedback_text)
        
        return FeedbackAnalysis(
            feedback_type=primary_type,
            confidence=confidence,
            requires_generation=requires_generation,
            requires_response=requires_response,
            extracted_intent=extracted_intent,
            relevant_tc_ids=relevant_tc_ids,
            is_question=is_question,
            suggested_response_type=suggested_response_type
        )
    
    def _calculate_pattern_score(self, text: str, patterns: List[str]) -> float:
        """Calculate score based on pattern matches in text"""
        score = 0.0
        text_len = len(text.split())
        
        for pattern in patterns:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            if matches > 0:
                # Weight by text length - shorter text gets higher weight for matches
                weight = min(1.0, 10.0 / max(text_len, 1))
                score += matches * weight * 0.2
        
        return min(score, 1.0)
    
    def _extract_tc_ids(self, feedback_text: str) -> List[str]:
        """Extract test case IDs mentioned in feedback"""
        tc_pattern = r'\bTC_\d{3}\b'
        return re.findall(tc_pattern, feedback_text)
    
    def _clean_intent(self, feedback_text: str) -> str:
        """Clean and extract core intent from feedback"""
        intent = feedback_text.strip()
        
        # Remove common filler phrases
        noise_patterns = [
            r'^(?:can you|could you|please|would you|i think|i believe|i want|i need)\s*',
            r'\s*(?:please|thanks|thank you)\.?$'
        ]
        
        for pattern in noise_patterns:
            intent = re.sub(pattern, '', intent, flags=re.IGNORECASE).strip()
        
        # Limit length for context
        if len(intent) > 150:
            intent = intent[:150] + "..."
        
        return intent if intent else feedback_text.strip()
    
    def _create_default_analysis(self) -> FeedbackAnalysis:
        """Create default analysis for unclear feedback"""
        return FeedbackAnalysis(
            feedback_type=FeedbackType.GENERAL,
            confidence=0.5,
            requires_generation=False,
            requires_response=True,
            extracted_intent="General feedback received",
            relevant_tc_ids=[],
            is_question=False,
            suggested_response_type="text"
        )

class FeedbackPromptBuilder:
    """
    Build specialized prompts based on feedback type and context
    """
    
    @staticmethod
    def build_question_response_prompt(feedback_analysis: FeedbackAnalysis, 
                                     field_metadata: Dict, 
                                     existing_cases: List[Dict],
                                     context: str = "") -> str:
        """Build prompt for answering user questions - returns only text response"""
        
        context_part = f"""You are helping a user understand test cases for an API field. Answer their question clearly and helpfully.

FIELD INFORMATION:
"""
        # Add field metadata
        for key, value in field_metadata.items():
            if value:
                context_part += f"- {key}: {value}\n"
        
        # Add existing test cases summary
        if existing_cases:
            context_part += f"""
EXISTING TEST CASES:
"""
            for i, case in enumerate(existing_cases[:5], 1):  # Show up to 5 cases
                tc_id = case.get('Test Case ID', f'TC_{i}')
                val_type = case.get('Type of Validation', 'N/A')
                objective = case.get('Test Objective', 'N/A')
                status = case.get('Status', 'pending')
                context_part += f"- {tc_id} [{status}]: {val_type} - {objective}\n"
        
        # Add conversation context if available
        if context:
            context_part += f"""
RECENT CONVERSATION:
{context}
"""
        
        context_part += f"""
USER'S QUESTION/REQUEST:
{feedback_analysis.extracted_intent}
"""
        
        question_part = """Answer the user's question about the field or test cases. Provide:

1. Clear, helpful information about the topic they're asking about
2. Specific details about test cases if they're asking about them
3. Explanations of testing concepts if needed
4. Practical guidance or suggestions if appropriate

Keep your response conversational and informative. Focus on being helpful rather than formal.

IMPORTANT: Provide ONLY a text response. Do NOT generate test case tables or structured data."""
        
        return f"====CONTEXT {context_part} ====QUESTION {question_part}"
    
    @staticmethod
    def build_generation_prompt(feedback_analysis: FeedbackAnalysis,
                              field_metadata: Dict,
                              existing_cases: List[Dict],
                              context: str = "") -> str:
        """Build prompt for generating test cases based on feedback"""
        
        context_part = f"""Field metadata and feedback for test case generation:

FIELD METADATA:
"""
        for key, value in field_metadata.items():
            if value:
                context_part += f"{key}: {value}\n"
        
        if existing_cases:
            context_part += f"""
EXISTING TEST CASES:
"""
            for i, case in enumerate(existing_cases[:4], 1):
                tc_id = case.get('Test Case ID', f'TC_{i}')
                val_type = case.get('Type of Validation', 'N/A')
                objective = case.get('Test Objective', 'N/A')
                status = case.get('Status', 'pending')
                context_part += f"{tc_id} [{status}]: {val_type} - {objective}\n"
        
        if context:
            context_part += f"""
CONVERSATION CONTEXT:
{context}
"""
        
        context_part += f"""
USER FEEDBACK: {feedback_analysis.extracted_intent}
FEEDBACK TYPE: {feedback_analysis.feedback_type.value}
"""
        
        # Customize generation instruction based on feedback type
        if feedback_analysis.feedback_type == FeedbackType.MODIFICATION:
            instruction = "Modify or improve existing test cases based on the feedback. Generate 1-2 improved test cases."
        elif feedback_analysis.feedback_type == FeedbackType.ADDITION:
            instruction = "Generate 1-3 additional test cases that address the specific requirements mentioned in the feedback."
        elif feedback_analysis.feedback_type == FeedbackType.REJECTION:
            instruction = "Generate alternative test cases that address the concerns mentioned in the feedback."
        else:
            instruction = "Generate 1-2 test cases based on the user's feedback."
        
        question_part = f"""{instruction}

Generate in EXACTLY 9 tab-separated columns:
Category | Test Case ID (blank) | Type of Validation | Test Objective | Request/Response Field | Test Steps | Expected Result | Mapping Correlation | Manual/Automation

REQUIREMENTS:
- Category: Always "Functional"
- Test Case ID: Leave blank (will be auto-assigned)
- Type of Validation: Must be one of: "Field Validation - Positive", "Field Validation - Negative", "Business Validation - Positive", "Business Validation - Negative"
- Request/Response Field: "Request" or "Response"
- Manual/Automation: "Manual" for business validation, "Automation" for field validation
- Focus on the user's specific feedback requirements

Output ONLY the test case rows, no explanations, no headers."""
        
        return f"====CONTEXT {context_part} ====QUESTION {question_part}"