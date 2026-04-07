#!/usr/bin/env python3
"""
Quick Start Guide for AutoSRE AI GenAI Implementation
Execute this script to test all GenAI features locally
"""

import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run a shell command with nice output"""
    print(f"\n{'='*80}")
    print(f"📌 {description}")
    print(f"{'='*80}")
    print(f"$ {cmd}\n")
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0

def main():
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║         AutoSRE AI - GenAI Implementation Quick Start                      ║
║                                                                            ║
║  This script will:                                                         ║
║  1. Verify dependencies                                                   ║
║  2. Test vector embeddings                                                ║
║  3. Test RAG search                                                       ║
║  4. Test MCP tools                                                        ║
║  5. Start the API server                                                  ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Step 1: Check dependencies
    print("\n✓ Checking dependencies...")
    required_packages = [
        "fastapi",
        "uvicorn", 
        "google.cloud",
        "vertexai",
        "faiss",
        "numpy",
        "pydantic"
    ]
    
    for package in required_packages:
        try:
            __import__(package.replace('.', '_'))
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} - Install with: pip install -r requirements.txt")
    
    # Step 2: Verify GCP setup
    print("\n✓ Checking GCP configuration...")
    gcp_checks = [
        ("gcloud", "gcloud --version"),
        ("auth", "gcloud auth list"),
    ]
    
    for name, cmd in gcp_checks:
        result = subprocess.run(cmd, shell=True, capture_output=True)
        if result.returncode == 0:
            print(f"  ✅ {name}")
        else:
            print(f"  ⚠️  {name} - Configure with: gcloud auth application-default login")
    
    # Step 3: Test embeddings module
    print("\n✓ Testing embeddings...")
    try:
        from app.utils.embeddings import embed_text
        embedding = embed_text("test error")
        print(f"  ✅ Got embedding with dimension: {len(embedding)}")
    except Exception as e:
        print(f"  ❌ Embeddings error: {e}")
    
    # Step 4: Test RAG engine
    print("\n✓ Testing RAG engine...")
    try:
        from app.rag.rag_engine import get_rag_engine
        engine = get_rag_engine()
        results = engine.search("database connection", top_k=1)
        print(f"  ✅ RAG search working. Found: {len(results)} results")
        if results:
            print(f"     Confidence: {results[0]['similarity']:.2f}")
    except Exception as e:
        print(f"  ❌ RAG error: {e}")
    
    # Step 5: Test MCP tools
    print("\n✓ Testing MCP tools...")
    try:
        from app.mcp.tools import get_all_tools
        tools = get_all_tools()
        print(f"  ✅ MCP tools loaded: {len(tools)} tools available")
        for tool in tools:
            print(f"     - {tool['name']}")
    except Exception as e:
        print(f"  ❌ MCP error: {e}")
    
    # Step 6: Start server
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                    Starting API Server                                     ║
║                                                                            ║
║  The server will start on http://localhost:8000                           ║
║  API endpoint: POST http://localhost:8000/analyze                         ║
║  Health check: GET http://localhost:8000/health                           ║
║  Docs: http://localhost:8000/docs                                         ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)
    
    print("\nTo stop the server, press Ctrl+C\n")
    
    # Run the server
    run_command(
        "uvicorn app.main:app --reload --port 8000",
        "Starting AutoSRE AI API Server"
    )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✓ Server stopped")
        sys.exit(0)
