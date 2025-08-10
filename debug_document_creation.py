#!/usr/bin/env python3

import asyncio
import sys
import os
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.append(str(backend_dir))

async def test_document_creation():
    """Test the document creation and storage process directly"""
    try:
        from app.services.document_processor import FinancialDocumentProcessor
        from app.services.ollama_service import OllamaService
        from app.services.qdrant_service import QdrantService
        from app.models.document import DocumentType
        
        print("Testing Document Creation and Storage...")
        print("=" * 50)
        
        # Create a simple test file
        test_file = "debug_test.txt"
        test_content = "Portfolio outperformed benchmark by +0.8 pp in Q3 2024. Technology sector selection (+0.5 pp) was the primary positive driver."
        
        with open(test_file, "w") as f:
            f.write(test_content)
        
        try:
            # Initialize services
            ollama_service = OllamaService()
            processor = FinancialDocumentProcessor(ollama_service)
            qdrant_service = QdrantService()
            
            print("1. Processing document...")
            
            # Process the document (this should create chunks with embeddings)
            document = await processor.process_document(
                test_file, 
                DocumentType.OTHER, 
                {"tags": ["test"]}
            )
            
            print(f"   Document processed: {document.document_id}")
            print(f"   Chunks created: {len(document.chunks)}")
            
            if document.chunks:
                chunk = document.chunks[0]
                print(f"   First chunk ID: {chunk.chunk_id}")
                print(f"   First chunk has embedding: {chunk.embedding is not None}")
                if chunk.embedding:
                    print(f"   Embedding length: {len(chunk.embedding)}")
                print(f"   Chunk content preview: {chunk.content[:100]}...")
            
            print()
            print("2. Storing chunks in Qdrant...")
            
            # Try to store the chunks
            result = await qdrant_service.store_chunks(document.chunks, document.metadata)
            print(f"   Storage result: {result}")
            
            print()
            print("3. Verifying storage...")
            
            # Check if points were actually stored
            stats = await qdrant_service.get_collection_stats()
            print(f"   Points in collection: {stats.get('total_points', 0)}")
            
            if stats.get('total_points', 0) > 0:
                print("   SUCCESS: Document stored successfully!")
            else:
                print("   FAILURE: No points stored in Qdrant")
                
        finally:
            # Clean up test file
            if os.path.exists(test_file):
                os.remove(test_file)
        
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_document_creation())