"""
Demonstration of the Enhanced Multi-Agent RAG System
"""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.chat_service import ChatService
from app.services.ollama_service import OllamaService
from app.services.qdrant_service import QdrantService
from app.models.chat import ChatRequest

async def demo_enhanced_rag():
    """Demonstrate the enhanced RAG system capabilities"""
    print("Enhanced Multi-Agent RAG System Demo")
    print("="*50)
    
    try:
        # Initialize services
        print("Initializing enhanced RAG system...")
        ollama_service = OllamaService()
        qdrant_service = QdrantService()
        chat_service = ChatService(ollama_service, qdrant_service)
        
        # Create demo session
        session = await chat_service.create_session("Enhanced RAG Demo")
        print(f"Session created: {session.session_id}")
        
        # Demo scenarios
        scenarios = [
            {
                "title": "Personal Information & Memory",
                "query": "Hi, I'm Sarah and I'm a portfolio manager at Goldman Sachs",
                "expected_behavior": "Should store personal info and acknowledge"
            },
            {
                "title": "Personalized Greeting",
                "query": "Hello again!",
                "expected_behavior": "Should remember name and provide personalized greeting"
            },
            {
                "title": "Performance Attribution Query",
                "query": "What are the top 3 detractors to our portfolio performance in Q4?",
                "expected_behavior": "Should be categorized as performance_attribution and search relevant documents"
            },
            {
                "title": "Technical Analysis Query", 
                "query": "Show me the Sharpe ratio and volatility metrics for our funds",
                "expected_behavior": "Should be categorized as technical and search technical documents"
            },
            {
                "title": "AUM Query",
                "query": "What was the total asset growth and capital flows last quarter?",
                "expected_behavior": "Should be categorized as aum and search AUM documents"
            },
            {
                "title": "General Knowledge Query",
                "query": "What does EBITDA stand for?",
                "expected_behavior": "Should be handled as general knowledge without RAG"
            },
            {
                "title": "Conversational Follow-up",
                "query": "Can you explain that in more detail?",
                "expected_behavior": "Should use conversation context and determine if RAG is needed"
            }
        ]
        
        for i, scenario in enumerate(scenarios, 1):
            print(f"\n{i}. {scenario['title']}")
            print("-" * 30)
            print(f"Query: '{scenario['query']}'")
            print(f"Expected: {scenario['expected_behavior']}")
            print()
            
            # Create request
            request = ChatRequest(
                message=scenario['query'],
                session_id=session.session_id,
                use_rag=True,  # Let the router decide
                temperature=0.7,
                max_tokens=400
            )
            
            try:
                # Process the query
                response = await chat_service.chat(request)
                
                # Display results
                print("RESPONSE:")
                print(response.response)
                print()
                
                print("METADATA:")
                print(f"- Confidence Score: {response.confidence_score:.2f}")
                print(f"- Sources Found: {len(response.sources)}")
                print(f"- Processing Time: {response.total_time_ms:.1f}ms")
                print(f"- Context Used: {response.context_used}")
                
                # Show router classification if available
                if hasattr(response, 'metadata') and response.metadata:
                    agent_responses = response.metadata.get('agent_responses', [])
                    if agent_responses:
                        print(f"- Agent Pipeline: {len(agent_responses)} agents used")
                        for agent_resp in agent_responses:
                            agent_name = agent_resp.get('agent', 'unknown')
                            success = agent_resp.get('success', False)
                            print(f"  * {agent_name}: {'✓' if success else '✗'}")
                
                # Check if memory is being used
                if i == 2:  # After personal info storage
                    personal_info = chat_service.router_service.conversation_memory.get_personal_info(session.session_id)
                    print(f"- Stored Personal Info: {personal_info}")
                
                print("STATUS: ✓ SUCCESS")
                
            except Exception as e:
                print(f"STATUS: ✗ FAILED - {str(e)[:100]}...")
            
            print("=" * 50)
        
        # Final summary
        print("\nSUMMARY OF ENHANCED FEATURES:")
        print()
        print("1. INTELLIGENT ROUTING:")
        print("   - Automatic query classification (personal, greeting, knowledge_base, general)")
        print("   - Context-aware routing decisions")
        print("   - Memory-based personalization")
        print()
        print("2. MULTI-AGENT PIPELINE:")
        print("   - Query Categorization Agent (LLM-powered)")
        print("   - Category-Based Context Retriever")
        print("   - Response Generation Agent")
        print()
        print("3. CATEGORY-SPECIFIC COLLECTIONS:")
        print("   - Performance Attribution Documents")
        print("   - Technical Analysis Documents") 
        print("   - Assets Under Management Documents")
        print("   - General Knowledge Fallback")
        print()
        print("4. CONVERSATION MEMORY:")
        print("   - Personal information storage")
        print("   - Context-aware follow-ups")
        print("   - Personalized interactions")
        print()
        print("5. ENHANCED RAG LOGIC:")
        print("   - Smart document relevance checking")
        print("   - Category-specific search optimization")
        print("   - Structured response generation")
        print("   - Confidence scoring and source attribution")
        
        # Show final session state
        final_session = await chat_service.get_session(session.session_id)
        if final_session:
            print(f"\nFINAL SESSION STATE:")
            print(f"- Total Messages: {len(final_session.messages)}")
            print(f"- Session Active: {final_session.is_active}")
            print(f"- Last Activity: {final_session.last_activity}")
        
        print("\n✅ Enhanced Multi-Agent RAG System Demo Complete!")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(demo_enhanced_rag())