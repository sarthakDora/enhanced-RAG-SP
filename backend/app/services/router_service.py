import re
import logging
from typing import Dict, Any, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)

class QueryType(Enum):
    """Types of queries that can be processed"""
    PERSONAL_INFO = "personal_info"  # User sharing personal information (name, preferences, etc.)
    GREETING = "greeting"  # Greetings and casual conversation
    KNOWLEDGE_BASE = "knowledge_base"  # Document-specific questions requiring RAG
    GENERAL_KNOWLEDGE = "general_knowledge"  # General questions not requiring documents
    CONVERSATIONAL = "conversational"  # Follow-up questions, clarifications

class ConversationMemory:
    """Manages conversation memory for personal information"""
    
    def __init__(self):
        self.personal_info: Dict[str, Dict[str, Any]] = {}  # session_id -> info
        self.preferences: Dict[str, Dict[str, Any]] = {}  # session_id -> preferences
        
    def store_personal_info(self, session_id: str, info_type: str, value: Any):
        """Store personal information for a session"""
        if session_id not in self.personal_info:
            self.personal_info[session_id] = {}
        self.personal_info[session_id][info_type] = value
        logger.info(f"Stored {info_type} for session {session_id}")
        
    def get_personal_info(self, session_id: str, info_type: str = None) -> Any:
        """Retrieve personal information for a session"""
        if session_id not in self.personal_info:
            return None if info_type else {}
        
        if info_type:
            return self.personal_info[session_id].get(info_type)
        return self.personal_info[session_id]
        
    def store_preference(self, session_id: str, pref_type: str, value: Any):
        """Store user preferences"""
        if session_id not in self.preferences:
            self.preferences[session_id] = {}
        self.preferences[session_id][pref_type] = value
        
    def get_preferences(self, session_id: str) -> Dict[str, Any]:
        """Get all preferences for a session"""
        return self.preferences.get(session_id, {})

class RouterService:
    """Intelligent query router that determines how to handle different types of questions"""
    
    def __init__(self):
        self.conversation_memory = ConversationMemory()
        
        # Pattern definitions for query classification
        self.patterns = {
            QueryType.PERSONAL_INFO: [
                r"(?:my name is|i am|i'm called|call me|i'm)\s+(\w+)",
                r"(?:i|my)\s+(?:work|live|am based)\s+(?:at|in|for)\s+([\w\s]+)",
                r"(?:i|my)\s+(?:prefer|like|enjoy|hate|dislike)\s+([\w\s]+)",
                r"(?:i|my)\s+(?:age|birthday|born)\s+(?:is|on|in)\s+([\w\s\d]+)",
                r"(?:i|my)\s+(?:email|phone|contact)\s+(?:is|number)\s+([\w\s@\.\-\+]+)"
            ],
            QueryType.GREETING: [
                r"^(?:hi|hello|hey|good morning|good afternoon|good evening)",
                r"^(?:how are you|what's up|how's it going)",
                r"^(?:thanks|thank you|goodbye|bye|see you)"
            ],
            QueryType.KNOWLEDGE_BASE: [
                r"(?:what|who|when|where|how|why).+(?:report|document|data|analysis|performance|attribution)",
                r"(?:show|find|search|look up|get|retrieve).+(?:from|in).+(?:document|report|file)",
                r"(?:top|highest|lowest|best|worst).+(?:performer|contributor|detractor|sector|stock)",
                r"(?:analyze|breakdown|summary|details).+(?:performance|attribution|returns)",
                r"(?:fiscal|quarter|q\d|year|fy|financial).+(?:results|data|report)",
                r"(?:show|find|get|retrieve).+(?:revenue|profit|loss|assets|liability|equity|cash flow|ebitda)",
                r"(?:according to|based on|from).+(?:report|document|analysis)",
                # Performance attribution specific patterns
                r"(?:attribution|performance).+(?:analysis|commentary|drivers|factors)",
                r"(?:contributors?|detractors?|drivers?).+(?:performance|attribution|portfolio)",
                r"(?:sector|security).+(?:selection|attribution|contribution)",
                r"(?:active return|excess return|tracking error|information ratio)",
                r"(?:portfolio|fund).+(?:performance|attribution|analysis|returns)",
                r"(?:benchmark|index).+(?:relative|vs|against|compared)",
                r"(?:pp|basis points?|percentage points?).+(?:contribution|attribution)",
                # Broader financial data queries
                r"(?:show|tell|what).+(?:performance|returns|attribution)",
                r"(?:key|main|primary).+(?:drivers?|contributors?|factors?)",
                # Simple command patterns for performance attribution
                r"(?:summarize|summary).+(?:performance|attribution)",
                r"(?:analyze|analysis).+(?:performance|attribution)",
                r"(?:explain|describe).+(?:performance|attribution)",
                r"(?:performance|attribution).+(?:summary|analysis|report)"
            ],
            QueryType.CONVERSATIONAL: [
                r"^(?:can you|could you|please|also|and|additionally)",
                r"^(?:what about|how about|what if|suppose)",
                r"^(?:yes|no|okay|ok|sure|definitely|absolutely)",
                r"(?:explain|elaborate|clarify|detail|expand).+(?:more|further|better)"
            ]
        }
        
        # Keywords for document-related queries
        self.document_keywords = [
            'report', 'document', 'data', 'analysis', 'performance', 'attribution',
            'revenue', 'profit', 'assets', 'liability', 'equity', 'cash flow',
            'fiscal', 'quarter', 'financial', 'gics', 'sector', 'portfolio',
            'benchmark', 'fund', 'returns', 'metrics', 'breakdown', 'summary',
            # Performance attribution keywords
            'contributors', 'contributor', 'detractors', 'detractor', 'drivers', 'driver',
            'selection', 'allocation', 'active', 'excess', 'relative', 'outperform',
            'underperform', 'tracking', 'alpha', 'beta', 'sharpe', 'volatility',
            # Common query words
            'top', 'best', 'worst', 'highest', 'lowest', 'key', 'main', 'primary'
        ]
        
    def classify_query(self, query: str, session_id: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """Classify a query and determine routing strategy"""
        query_lower = query.lower().strip()
        
        classification = {
            "query_type": QueryType.GENERAL_KNOWLEDGE,
            "confidence": 0.5,
            "requires_rag": False,
            "requires_memory": False,
            "personal_info_extracted": {},
            "routing_decision": "general_knowledge"
        }
        
        # Check for personal information patterns
        personal_info = self._extract_personal_info(query_lower)
        if personal_info:
            classification.update({
                "query_type": QueryType.PERSONAL_INFO,
                "confidence": 0.9,
                "requires_rag": False,
                "requires_memory": True,
                "personal_info_extracted": personal_info,
                "routing_decision": "store_and_respond"
            })
            # Store the personal information
            for info_type, value in personal_info.items():
                self.conversation_memory.store_personal_info(session_id, info_type, value)
            return classification
        
        # Check for greeting patterns
        if self._matches_patterns(query_lower, QueryType.GREETING):
            # Personalize greeting if we know the user's name
            user_name = self.conversation_memory.get_personal_info(session_id, "name")
            classification.update({
                "query_type": QueryType.GREETING,
                "confidence": 0.95,
                "requires_rag": False,
                "requires_memory": True,
                "personal_context": {"name": user_name} if user_name else {},
                "routing_decision": "greeting_with_memory"
            })
            return classification
        
        # Check for conversational follow-ups first (before document check)
        if (conversation_history and len(conversation_history) > 0 and 
            self._matches_patterns(query_lower, QueryType.CONVERSATIONAL)):
            classification.update({
                "query_type": QueryType.CONVERSATIONAL,
                "confidence": 0.7,
                "requires_rag": self._should_use_rag_for_followup(conversation_history),
                "requires_memory": True,
                "routing_decision": "conversational_with_context"
            })
            return classification
        
        # Check for document/knowledge base queries (patterns or performance keywords)
        has_pattern_match = self._matches_patterns(query_lower, QueryType.KNOWLEDGE_BASE)
        has_contextual_keywords = self._contains_document_keywords_contextually(query_lower)
        
        # Special case: if query has performance/attribution keywords, likely needs documents
        performance_keywords = {'performance', 'attribution', 'contributors', 'detractors', 'drivers', 'portfolio', 'returns'}
        query_words = set(query_lower.split())
        has_performance_keywords = bool(query_words.intersection(performance_keywords))
        
        if has_pattern_match or has_contextual_keywords or has_performance_keywords:
            confidence = 0.9 if has_pattern_match else (0.8 if has_contextual_keywords else 0.7)
            classification.update({
                "query_type": QueryType.KNOWLEDGE_BASE,
                "confidence": confidence,
                "requires_rag": True,
                "requires_memory": False,
                "routing_decision": "knowledge_base_search"
            })
            return classification
        
        # Default to general knowledge
        classification.update({
            "routing_decision": "general_knowledge"
        })
        
        logger.info(f"Query '{query}' classified as {classification['query_type'].value} with confidence {classification['confidence']}, routing: {classification['routing_decision']}")
        return classification
    
    def _extract_personal_info(self, query: str) -> Dict[str, str]:
        """Extract personal information from the query"""
        personal_info = {}
        
        # Name extraction
        name_patterns = [
            r"(?:my name is|i am|i'm called|call me|i'm)\s+([a-zA-Z]+)",
            r"(?:i am|i'm)\s+([a-zA-Z]+)(?:\s|$)",
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                name = match.group(1).strip().title()
                if name and len(name) > 1:  # Valid name
                    personal_info["name"] = name
                    break
        
        # Location extraction
        location_patterns = [
            r"(?:i work at|i'm at|i'm from|i live in|i'm based in|i'm located in)\s+([\w\s]+?)(?:\.|$|,)",
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                location = match.group(1).strip().title()
                if location and len(location) > 1:
                    personal_info["location"] = location
                    break
        
        # Preference extraction
        preference_patterns = [
            r"(?:i prefer|i like|i enjoy)\s+([\w\s]+?)(?:\.|$|,)",
        ]
        
        for pattern in preference_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                preference = match.group(1).strip()
                if preference and len(preference) > 1:
                    personal_info["preference"] = preference
                    break
        
        return personal_info
    
    def _matches_patterns(self, query: str, query_type: QueryType) -> bool:
        """Check if query matches patterns for a specific type"""
        if query_type not in self.patterns:
            return False
        
        for pattern in self.patterns[query_type]:
            if re.search(pattern, query, re.IGNORECASE):
                return True
        return False
    
    def _contains_document_keywords(self, query: str) -> bool:
        """Check if query contains keywords that suggest document search"""
        query_words = set(query.split())
        document_words = set(self.document_keywords)
        return bool(query_words.intersection(document_words))
    
    def _contains_document_keywords_contextually(self, query: str) -> bool:
        """Check if query contextually asks for document-specific information"""
        query_words = set(query.split())
        document_words = set(self.document_keywords)
        
        # Check for document keywords
        has_document_keywords = bool(query_words.intersection(document_words))
        
        # Additional context clues that suggest document search
        specific_data_patterns = [
            r"(?:what|show|find|get|retrieve).+(?:from|in).+(?:document|report|file)",
            r"(?:top|highest|lowest|best|worst).+(?:performer|contributor|sector)",
            r"(?:according to|based on|from).+(?:report|document|analysis)",
            r"(?:q\d|quarter|fiscal|year).+(?:data|results|report|performance)",
            r"(?:analyze|breakdown|summary|details).+(?:of|from|in)"
        ]
        
        # Check for general knowledge indicators that should NOT use RAG
        general_knowledge_indicators = [
            r"what is\s+\w+\?",  # "What is EBITDA?"
            r"define\s+\w+",     # "Define revenue"
            r"explain\s+\w+",    # "Explain depreciation"
            r"how does\s+\w+\s+work", # "How does compound interest work"
        ]
        
        # If it's clearly a definition question, treat as general knowledge
        for pattern in general_knowledge_indicators:
            if re.search(pattern, query, re.IGNORECASE):
                return False
        
        # If it has document keywords, check for context patterns or strong performance indicators
        if has_document_keywords:
            for pattern in specific_data_patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    return True
            
            # Additional performance attribution patterns that should trigger document search
            performance_patterns = [
                r"(?:contributors?|detractors?|drivers?)",
                r"(?:attribution|performance).+(?:analysis|commentary)",
                r"(?:top|best|worst|highest|lowest).+(?:sectors?|performers?)",
                r"(?:active|excess|relative).+(?:return|performance)",
                r"(?:sector|security).+(?:selection|allocation)",
                r"(?:pp|basis points?|percentage points?)"
            ]
            
            for pattern in performance_patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    return True
            
            # If query has performance/attribution keywords, likely needs documents
            performance_keywords = {'performance', 'attribution', 'contributors', 'detractors', 'drivers', 'portfolio', 'returns'}
            if query_words.intersection(performance_keywords):
                return True
                
            # Only return False if no strong indicators
            return False
        
        return False
    
    def _should_use_rag_for_followup(self, conversation_history: List[Dict]) -> bool:
        """Determine if a follow-up question should use RAG based on context"""
        if not conversation_history:
            return False
        
        # Check if recent messages mentioned documents or data
        recent_messages = conversation_history[-3:]  # Last 3 messages
        for msg in recent_messages:
            content = msg.get('content', '').lower()
            if (any(keyword in content for keyword in self.document_keywords) or
                'based on' in content or 'according to' in content):
                return True
        
        return False
    
    def generate_response_context(self, classification: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Generate context for response generation based on classification"""
        context = {
            "query_type": classification["query_type"].value,
            "routing_decision": classification["routing_decision"],
            "use_rag": classification["requires_rag"],
            "personal_context": {}
        }
        
        if classification["requires_memory"]:
            # Add relevant personal information to context
            personal_info = self.conversation_memory.get_personal_info(session_id)
            preferences = self.conversation_memory.get_preferences(session_id)
            
            context["personal_context"] = {
                "personal_info": personal_info,
                "preferences": preferences
            }
        
        return context
    
    def get_personalized_greeting(self, session_id: str) -> str:
        """Generate a personalized greeting based on stored information"""
        user_name = self.conversation_memory.get_personal_info(session_id, "name")
        location = self.conversation_memory.get_personal_info(session_id, "location")
        
        if user_name and location:
            return f"Hello {user_name}! Nice to see you again. How are things in {location}?"
        elif user_name:
            return f"Hello {user_name}! Good to see you again."
        else:
            return "Hello! Good to see you again."
    
    def format_personal_info_response(self, personal_info: Dict[str, str]) -> str:
        """Format a response acknowledging stored personal information"""
        responses = []
        
        if "name" in personal_info:
            responses.append(f"Nice to meet you, {personal_info['name']}!")
        
        if "location" in personal_info:
            responses.append(f"Great to know you're in {personal_info['location']}.")
        
        if "preference" in personal_info:
            responses.append(f"I'll remember that you {personal_info['preference']}.")
        
        if responses:
            return " ".join(responses) + " How can I help you today?"
        
        return "Thanks for sharing that information with me. How can I assist you today?"