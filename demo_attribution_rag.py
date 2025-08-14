#!/usr/bin/env python3
"""
Demo script for the Attribution RAG system.
Shows how to use the robust RAG layer for performance attribution reports.
"""

import asyncio
import pandas as pd
import tempfile
import os
from pathlib import Path

# Import the services
from backend.app.services.performance_attribution_service import PerformanceAttributionService
from backend.app.services.ollama_service import OllamaService
from backend.app.services.qdrant_service import QdrantService


def create_sample_equity_data():
    """Create sample equity attribution data for demo"""
    return pd.DataFrame({
        'GICS Sector': ['Technology', 'Healthcare', 'Financials', 'Energy', 'Consumer Discretionary', 'Industrials'],
        'Portfolio ROR (%)': [15.2, 8.3, -2.1, -8.7, 12.4, 6.8],
        'Benchmark ROR (%)': [12.8, 7.8, -1.5, -6.2, 10.1, 5.9],
        'Allocation (pp)': [0.2, -0.1, 0.3, -0.4, 0.1, 0.2],
        'Selection (pp)': [2.2, 0.4, -0.3, -2.1, 2.1, 0.7],
        'Total Attribution (pp)': [2.4, 0.3, 0.0, -2.5, 2.2, 0.9],
        'Portfolio Weight (%)': [28.0, 18.0, 15.0, 3.0, 20.0, 16.0],
        'Benchmark Weight (%)': [25.0, 19.0, 14.0, 6.0, 19.0, 17.0]
    })


def create_sample_fixed_income_data():
    """Create sample fixed income attribution data for demo"""
    return pd.DataFrame({
        'Country': ['United States', 'Germany', 'Japan', 'United Kingdom', 'France', 'Canada'],
        'Portfolio ROR (%)': [3.2, 2.8, 1.1, 2.9, 2.5, 3.1],
        'Benchmark ROR (%)': [3.0, 2.5, 1.0, 2.7, 2.3, 2.9],
        'Allocation (pp)': [0.1, 0.2, 0.0, 0.1, 0.1, 0.1],
        'Selection (pp)': [0.1, 0.1, 0.1, 0.1, 0.1, 0.1],
        'FX Selection (pp)': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        'Carry (pp)': [0.1, 0.2, 0.0, 0.1, 0.0, 0.1],
        'Roll Down (pp)': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        'Price Return (pp)': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        'Total Attribution (pp)': [0.2, 0.5, 0.1, 0.3, 0.2, 0.3],
        'Portfolio Weight (%)': [35.0, 20.0, 15.0, 12.0, 10.0, 8.0],
        'Benchmark Weight (%)': [33.0, 22.0, 17.0, 10.0, 12.0, 6.0]
    })


async def demo_attribution_rag():
    """Main demo function"""
    print("🚀 Attribution RAG Demo - Robust RAG Layer for Performance Attribution Reports")
    print("=" * 80)
    
    # Initialize services
    print("\n1. Initializing services...")
    try:
        ollama_service = OllamaService()
        qdrant_service = QdrantService()
        attribution_service = PerformanceAttributionService(ollama_service, qdrant_service)
        
        # Health checks
        print("   Checking Ollama connection...")
        await ollama_service.health_check()
        print("   ✅ Ollama is ready")
        
        print("   Checking Qdrant connection...")
        await qdrant_service.health_check()
        print("   ✅ Qdrant is ready")
        
    except Exception as e:
        print(f"   ❌ Service initialization failed: {e}")
        print("   Please ensure Ollama and Qdrant are running:")
        print("   - Ollama: ollama serve")
        print("   - Qdrant: docker run -p 6333:6333 qdrant/qdrant")
        return
    
    # Demo 1: Equity Attribution
    print("\n2. Demo 1: Equity Sector Attribution")
    print("-" * 40)
    
    # Create sample equity data
    equity_data = create_sample_equity_data()
    print(f"   Sample data: {len(equity_data)} sectors")
    
    # Save to temporary Excel file
    with tempfile.NamedTemporaryFile(suffix='_Q2_2025_Equity_Attribution.xlsx', delete=False) as tmp_file:
        equity_data.to_excel(tmp_file.name, sheet_name='Attribution', index=False)
        equity_file_path = tmp_file.name
    
    try:
        session_id_equity = "demo_equity_session"
        
        print(f"   Processing equity attribution file...")
        result = await attribution_service.process_attribution_file(equity_file_path, session_id_equity)
        
        print(f"   ✅ Processed successfully:")
        print(f"      - Session ID: {result['session_id']}")
        print(f"      - Asset Class: {result['asset_class']}")
        print(f"      - Attribution Level: {result['attribution_level']}")
        print(f"      - Chunks Created: {result['chunks_created']}")
        print(f"      - Period: {result['period']}")
        
        # Test Q&A mode
        print(f"\n   Testing Q&A mode...")
        qa_questions = [
            "What were the top 3 contributors by total attribution?",
            "Which sectors had positive selection effect?",
            "What was Technology sector's total attribution?"
        ]
        
        for question in qa_questions:
            print(f"\n   Q: {question}")
            try:
                answer = await attribution_service.answer_question(session_id_equity, question, mode="qa")
                print(f"   A: {answer['response'][:100]}...")
            except Exception as e:
                print(f"   Error: {e}")
        
        # Test Commentary mode
        print(f"\n   Testing Commentary mode...")
        try:
            commentary = await attribution_service.answer_question(
                session_id_equity, 
                "Generate Q2 2025 attribution commentary", 
                mode="commentary"
            )
            print(f"   Commentary Preview:")
            print(f"   {commentary['response'][:200]}...")
        except Exception as e:
            print(f"   Commentary Error: {e}")
        
    finally:
        os.unlink(equity_file_path)
        await attribution_service.clear_session(session_id_equity)
    
    # Demo 2: Fixed Income Attribution
    print("\n3. Demo 2: Fixed Income Country Attribution")
    print("-" * 40)
    
    # Create sample fixed income data
    fi_data = create_sample_fixed_income_data()
    print(f"   Sample data: {len(fi_data)} countries")
    
    # Save to temporary Excel file
    with tempfile.NamedTemporaryFile(suffix='_Q2_2025_FixedIncome_Attribution.xlsx', delete=False) as tmp_file:
        fi_data.to_excel(tmp_file.name, sheet_name='Attribution', index=False)
        fi_file_path = tmp_file.name
    
    try:
        session_id_fi = "demo_fi_session"
        
        print(f"   Processing fixed income attribution file...")
        result = await attribution_service.process_attribution_file(fi_file_path, session_id_fi)
        
        print(f"   ✅ Processed successfully:")
        print(f"      - Session ID: {result['session_id']}")
        print(f"      - Asset Class: {result['asset_class']}")
        print(f"      - Attribution Level: {result['attribution_level']}")
        print(f"      - Chunks Created: {result['chunks_created']}")
        
        # Test Fixed Income specific questions
        print(f"\n   Testing Fixed Income Q&A...")
        fi_questions = [
            "Which countries had positive carry effect?",
            "What was Germany's total attribution?",
            "Show me the rankings by total attribution"
        ]
        
        for question in fi_questions:
            print(f"\n   Q: {question}")
            try:
                answer = await attribution_service.answer_question(session_id_fi, question, mode="qa")
                print(f"   A: {answer['response'][:100]}...")
            except Exception as e:
                print(f"   Error: {e}")
        
        # Session stats
        print(f"\n   Session Statistics:")
        stats = await attribution_service.get_session_stats(session_id_fi)
        if stats['exists']:
            print(f"      - Total Chunks: {stats['total_chunks']}")
            print(f"      - Indexed Chunks: {stats['indexed_chunks']}")
            print(f"      - Status: {stats['status']}")
        
    finally:
        os.unlink(fi_file_path)
        await attribution_service.clear_session(session_id_fi)
    
    # Demo 3: Chunk Types Overview
    print("\n4. Chunk Types Overview")
    print("-" * 40)
    print("   The Attribution RAG system creates 4 types of chunks:")
    print("   📊 ROW CHUNKS: One per sector/country with full attribution details")
    print("   📈 TOTALS CHUNK: Portfolio vs benchmark totals and breakdown")
    print("   🏆 RANKINGS CHUNK: Top contributors and detractors ranked by attribution")
    print("   📚 SCHEMA CHUNK: Glossary explaining attribution effects present")
    
    print("\n5. Key Features Demonstrated")
    print("-" * 40)
    print("   ✅ Automatic asset class detection (Equity vs Fixed Income)")
    print("   ✅ Column name canonicalization (lower_snake_case)")
    print("   ✅ Effect presence detection (FX, Carry, Roll, Price)")
    print("   ✅ Session-scoped Qdrant collections")
    print("   ✅ Row-centric chunking strategy")
    print("   ✅ Hybrid retrieval (semantic + filtering)")
    print("   ✅ Two modes: Q&A (strict) and Commentary (professional)")
    print("   ✅ Proper financial formatting (pp for attribution, % for returns)")
    
    print("\n🎉 Attribution RAG Demo Complete!")
    print("Ready for production use with real Excel attribution files.")


async def demo_api_usage():
    """Demo API usage examples"""
    print("\n6. API Usage Examples")
    print("-" * 40)
    
    api_examples = {
        "upload": {
            "method": "POST",
            "endpoint": "/api/attribution/upload",
            "description": "Upload Excel attribution file",
            "curl": """curl -X POST "http://localhost:8000/api/attribution/upload" \\
  -F "file=@Q2_2025_Equity_Attribution.xlsx" \\
  -F "session_id=my_session_123" """
        },
        "question": {
            "method": "POST", 
            "endpoint": "/api/attribution/question",
            "description": "Ask Q&A questions",
            "curl": """curl -X POST "http://localhost:8000/api/attribution/question" \\
  -F "session_id=my_session_123" \\
  -F "question=Which sectors had negative FX but positive selection?" \\
  -F "mode=qa" """
        },
        "commentary": {
            "method": "POST",
            "endpoint": "/api/attribution/commentary", 
            "description": "Generate professional commentary",
            "curl": """curl -X POST "http://localhost:8000/api/attribution/commentary" \\
  -F "session_id=my_session_123" \\
  -F "period=Q2 2025" """
        }
    }
    
    for name, example in api_examples.items():
        print(f"\n   {example['method']} {example['endpoint']}")
        print(f"   {example['description']}")
        print(f"   {example['curl']}")


if __name__ == "__main__":
    asyncio.run(demo_attribution_rag())
    asyncio.run(demo_api_usage())