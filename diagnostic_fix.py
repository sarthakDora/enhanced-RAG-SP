#!/usr/bin/env python3

import asyncio
import sys
import os
import logging
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.append(str(backend_dir))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Comprehensive diagnostic and fix script"""
    print("🔧 Enhanced RAG System Diagnostic & Fix Tool")
    print("=" * 50)
    
    try:
        # Import modules
        from app.core.config import settings
        from app.services.qdrant_service import QdrantService
        from app.services.ollama_service import OllamaService
        
        print(f"✅ Configuration loaded:")
        print(f"   - Qdrant URL: {settings.QDRANT_URL}")
        print(f"   - Collection: {settings.COLLECTION_NAME}")
        print(f"   - Ollama URL: {settings.OLLAMA_BASE_URL}")
        print(f"   - LLM Model: {settings.LLM_MODEL}")
        print()
        
        # Test Qdrant connection
        print("🔍 Testing Qdrant Connection...")
        qdrant_service = QdrantService()
        
        try:
            await qdrant_service.health_check()
            print("✅ Qdrant connection successful")
        except Exception as e:
            print(f"❌ Qdrant connection failed: {e}")
            print("🔧 Fix: Ensure Qdrant is running on", settings.QDRANT_URL)
            return
        
        # Check collection
        print("\n🔍 Checking Qdrant Collection...")
        collection_exists = await qdrant_service.collection_exists()
        
        if not collection_exists:
            print(f"❌ Collection '{settings.COLLECTION_NAME}' does not exist")
            print("🔧 Creating collection...")
            try:
                await qdrant_service.create_collection()
                print("✅ Collection created successfully")
            except Exception as e:
                print(f"❌ Failed to create collection: {e}")
                return
        else:
            print(f"✅ Collection '{settings.COLLECTION_NAME}' exists")
        
        # Check documents in collection
        print("\n🔍 Checking Documents in Qdrant...")
        all_points = await qdrant_service.get_all_points()
        
        if not all_points:
            print("❌ No documents found in Qdrant collection")
            print("🔧 This is likely why the system says 'no documents uploaded'")
            print("   Solution: Upload documents via /documents/upload endpoint")
        else:
            # Analyze document structure
            doc_ids = set()
            for point in all_points:
                payload = point.get("payload", {})
                doc_id = payload.get("document_id")
                if doc_id:
                    doc_ids.add(doc_id)
            
            print(f"✅ Found {len(all_points)} points representing {len(doc_ids)} unique documents")
            
            # Show sample document
            if doc_ids:
                sample_doc_id = list(doc_ids)[0]
                sample_chunks = [p for p in all_points if p.get("payload", {}).get("document_id") == sample_doc_id]
                if sample_chunks:
                    sample_payload = sample_chunks[0]["payload"]
                    print(f"📄 Sample document: {sample_payload.get('filename', 'unknown')}")
                    print(f"   - Type: {sample_payload.get('document_type', 'unknown')}")
                    print(f"   - Chunks: {len(sample_chunks)}")
        
        # Test Ollama connection
        print("\n🔍 Testing Ollama Connection...")
        ollama_service = OllamaService()
        
        try:
            await ollama_service.health_check()
            print("✅ Ollama connection successful")
        except Exception as e:
            print(f"❌ Ollama connection failed: {e}")
            print("🔧 Fix: Ensure Ollama is running and models are available")
            return
        
        # Test embedding generation
        print("\n🔍 Testing Embedding Generation...")
        try:
            test_embedding = await ollama_service.generate_embedding("test query")
            if test_embedding and len(test_embedding) > 0:
                print(f"✅ Embedding generation working (dimension: {len(test_embedding)})")
            else:
                print("❌ Embedding generation failed - empty result")
        except Exception as e:
            print(f"❌ Embedding generation failed: {e}")
        
        # Test LLM response
        print("\n🔍 Testing LLM Response...")
        try:
            response = await ollama_service.generate_response(
                prompt="What is 2+2?",
                context="",
                temperature=0.1,
                max_tokens=50
            )
            if response and response.get("response"):
                print(f"✅ LLM response working: {response['response'][:50]}...")
            else:
                print("❌ LLM response failed - empty result")
        except Exception as e:
            print(f"❌ LLM response failed: {e}")
        
        print("\n" + "=" * 50)
        print("🎯 SUMMARY & NEXT STEPS:")
        
        if all_points:
            print("✅ Documents found in Qdrant - system should work for queries")
            print("🔧 If still getting 'no documents' error:")
            print("   1. Try: POST /chat/debug/force-sync")
            print("   2. Check: GET /chat/debug/metadata")
            print("   3. Test query: 'Summarize Performance attribution'")
        else:
            print("❌ No documents in Qdrant - need to upload documents first")
            print("🔧 Upload documents using:")
            print("   POST /documents/upload with your PDF/Excel files")
        
        print("\n🔧 Debug endpoints available:")
        print("   - GET /documents/debug/qdrant-status")
        print("   - GET /documents/list")
        print("   - GET /chat/debug/metadata")
        print("   - POST /chat/debug/force-sync")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("🔧 Run from project root: python diagnostic_fix.py")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())