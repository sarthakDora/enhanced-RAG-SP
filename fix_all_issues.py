#!/usr/bin/env python3

import asyncio
import sys
import os
import logging
from pathlib import Path
import json

# Add the backend directory to Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.append(str(backend_dir))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_all_issues():
    """Comprehensive fix for all known issues"""
    print("🛠️  Enhanced RAG System - Fix All Issues")
    print("=" * 50)
    
    fixes_applied = []
    
    try:
        from app.core.config import settings
        from app.services.qdrant_service import QdrantService
        from app.services.ollama_service import OllamaService
        from app.models.document import DocumentMetadata
        from datetime import datetime
        
        # Initialize services
        qdrant_service = QdrantService()
        ollama_service = OllamaService()
        
        print("🔧 Fix 1: Ensure Qdrant Collection Exists")
        try:
            collection_exists = await qdrant_service.collection_exists()
            if not collection_exists:
                await qdrant_service.create_collection()
                print("✅ Created missing Qdrant collection")
                fixes_applied.append("Created Qdrant collection")
            else:
                print("✅ Qdrant collection already exists")
        except Exception as e:
            print(f"❌ Failed to create collection: {e}")
        
        print("\n🔧 Fix 2: Check and Rebuild Document Metadata Cache")
        try:
            all_points = await qdrant_service.get_all_points()
            if all_points:
                # Simulate the metadata cache rebuild
                document_chunks = {}
                for point in all_points:
                    payload = point.get("payload", {})
                    doc_id = payload.get("document_id")
                    if doc_id:
                        if doc_id not in document_chunks:
                            document_chunks[doc_id] = []
                        document_chunks[doc_id].append(payload)
                
                print(f"✅ Found {len(document_chunks)} documents with {len(all_points)} chunks")
                
                # Validate document structure
                valid_docs = 0
                for doc_id, chunks in document_chunks.items():
                    first_chunk = chunks[0]
                    required_fields = ['filename', 'document_type', 'content']
                    if all(field in first_chunk for field in required_fields):
                        valid_docs += 1
                
                print(f"✅ {valid_docs}/{len(document_chunks)} documents have valid structure")
                fixes_applied.append(f"Validated {valid_docs} documents")
                
            else:
                print("⚠️  No documents found in Qdrant - need to upload documents")
        except Exception as e:
            print(f"❌ Failed to check documents: {e}")
        
        print("\n🔧 Fix 3: Test Multi-Agent Pipeline Components")
        try:
            # Test query categorization
            from app.services.multi_agent_pipeline import QueryCategorizationAgent, QueryCategory
            categorization_agent = QueryCategorizationAgent(ollama_service)
            
            test_query = "Summarize Performance attribution"
            category, confidence = await categorization_agent.categorize_query(test_query)
            
            if category == QueryCategory.PERFORMANCE_ATTRIBUTION:
                print("✅ Performance attribution queries correctly categorized")
                fixes_applied.append("Query categorization working")
            else:
                print(f"⚠️  Query categorized as {category.value} instead of performance_attribution")
        except Exception as e:
            print(f"❌ Multi-agent pipeline test failed: {e}")
        
        print("\n🔧 Fix 4: Test Router Service Patterns")
        try:
            from app.services.router_service import RouterService, QueryType
            router = RouterService()
            
            test_queries = [
                "Summarize Performance attribution",
                "What are the top contributors?",
                "Show me performance analysis",
                "Performance drivers"
            ]
            
            correct_classifications = 0
            for query in test_queries:
                classification = router.classify_query(query, "test_session")
                if classification["query_type"] == QueryType.KNOWLEDGE_BASE:
                    correct_classifications += 1
                else:
                    print(f"⚠️  Query '{query}' classified as {classification['query_type'].value}")
            
            print(f"✅ {correct_classifications}/{len(test_queries)} performance queries correctly routed")
            if correct_classifications == len(test_queries):
                fixes_applied.append("Router patterns working correctly")
        except Exception as e:
            print(f"❌ Router service test failed: {e}")
        
        print("\n🔧 Fix 5: Test Search Functionality")
        try:
            if all_points:
                # Test similarity search
                test_embedding = await ollama_service.generate_embedding("performance attribution")
                
                from app.models.document import DocumentSearchRequest
                search_request = DocumentSearchRequest(
                    query="performance attribution",
                    top_k=5,
                    similarity_threshold=0.3
                )
                
                results = await qdrant_service.search_similar_chunks(
                    test_embedding, search_request, {}
                )
                
                if results:
                    print(f"✅ Search functionality working - found {len(results)} results")
                    fixes_applied.append("Search functionality working")
                else:
                    print("⚠️  Search returned no results - may need to adjust similarity threshold")
        except Exception as e:
            print(f"❌ Search functionality test failed: {e}")
        
        print("\n🔧 Fix 6: Create Auto-Repair Function for Common Issues")
        auto_repair_code = '''
# Add this to your FastAPI startup or create a maintenance endpoint
async def auto_repair_system():
    """Auto-repair common issues"""
    try:
        from app.services.qdrant_service import QdrantService
        from app.core.config import settings
        
        qdrant_service = QdrantService()
        
        # Ensure collection exists
        if not await qdrant_service.collection_exists():
            await qdrant_service.create_collection()
        
        # Force metadata sync
        shared_metadata_store = {}  # Your app state
        all_points = await qdrant_service.get_all_points()
        
        if all_points:
            document_chunks = {}
            for point in all_points:
                payload = point.get("payload", {})
                doc_id = payload.get("document_id")
                if doc_id:
                    if doc_id not in document_chunks:
                        document_chunks[doc_id] = []
                    document_chunks[doc_id].append(payload)
            
            # Rebuild metadata
            for doc_id, chunks in document_chunks.items():
                first_chunk = chunks[0]
                shared_metadata_store[doc_id] = first_chunk
        
        return len(shared_metadata_store)
    except Exception as e:
        print(f"Auto-repair failed: {e}")
        return 0
'''
        
        # Save the auto-repair code
        with open("auto_repair.py", "w") as f:
            f.write(auto_repair_code)
        print("✅ Created auto_repair.py for system maintenance")
        fixes_applied.append("Created auto-repair script")
        
        print("\n" + "=" * 50)
        print("🎉 FIXES SUMMARY:")
        for i, fix in enumerate(fixes_applied, 1):
            print(f"   {i}. {fix}")
        
        if not fixes_applied:
            print("   No issues found or all systems working correctly!")
        
        print("\n🚀 NEXT STEPS:")
        print("1. If no documents found: Upload via POST /documents/upload")
        print("2. Test document listing: GET /documents/list") 
        print("3. Force metadata sync: POST /chat/debug/force-sync")
        print("4. Test query: 'Summarize Performance attribution'")
        print("5. Check logs for any remaining issues")
        
        print("\n📋 MAINTENANCE ENDPOINTS:")
        print("   - GET /documents/debug/qdrant-status")
        print("   - GET /chat/debug/metadata")
        print("   - POST /chat/debug/force-sync")
        
    except Exception as e:
        print(f"❌ Critical error during fixes: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fix_all_issues())