# Quick Start - AutoSRE AI GenAI Implementation

## 🚀 5-Minute Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set GCP Credentials
```bash
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT=auto-sre-ai-multi-agent
```

### 3. Run Quick Start Script
```bash
python quickstart.py
```

### 4. Test the API
In another terminal:
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "log": "ERROR: Connection pool exhausted. Unable to acquire DB connection after 30s timeout."
  }'
```

---

## 📊 API Response Example

```json
{
  "success": true,
  "analysis": {
    "error_type": "DB_CONNECTION_ERROR",
    "severity": "HIGH",
    "root_cause": "Connection pool exhausted",
    "services_affected": ["database"]
  },
  "rag": {
    "found": true,
    "confidence": 0.92,
    "solutions_count": 3
  },
  "decision": {
    "action": "AUTO_FIX",
    "reasoning": "Known issue with proven solution available",
    "confidence": 0.92
  },
  "execution": {
    "success": true,
    "tools_executed": [
      {"tool": "store_incident", "result": {"success": true}},
      {"tool": "publish_alert", "result": {"success": true}},
      {"tool": "trigger_auto_fix", "result": {"success": true}}
    ]
  }
}
```

---

## 🔍 What Each Component Does

### Phase 1: Log Analysis
- Parses raw error logs
- Uses LLM with SRE expertise
- Returns structured error classification
- Example output: type, severity, root cause

### Phase 2: RAG Search
- Searches knowledge base with semantic similarity
- Uses vector embeddings (Vertex AI)
- Returns relevant solutions with confidence scores
- Compares only meaningful solutions

### Phase 3: Decision Making
- Analyzes error severity vs solution confidence
- Decides on action (AUTO_FIX, ALERT, ESCALATE)
- Uses MCP tool definitions
- Returns decision with reasoning

### Phase 4: Execution
- Executes MCP tools based on decision
- Stores incident in Firestore
- Publishes alerts to Pub/Sub
- Triggers auto-fix if needed

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `app/utils/llm.py` | Advanced LLM integration with function calling |
| `app/utils/embeddings.py` | Vertex AI embeddings service |
| `app/rag/rag_engine.py` | Vector-based RAG engine with FAISS |
| `app/mcp/tools.py` | MCP tool definitions and schemas |
| `app/mcp/executor.py` | Executes tools called by LLM |
| `app/agents/log_agent.py` | Analyzes error logs |
| `app/agents/rag_agent.py` | Searches knowledge base |
| `app/agents/decision_agent.py` | Makes incident decisions |
| `app/orchestrator.py` | Coordinates multi-agent workflow |

---

## 🔧 Configuration

### Environment Variables
```bash
GOOGLE_CLOUD_PROJECT=auto-sre-ai-multi-agent
PORT=8000
LOG_LEVEL=INFO
```

### Knowledge Base
Edit `app/rag/knowledge_base.json` to add more error scenarios:
```json
{
  "NEW_ERROR": {
    "error_type": "description",
    "fix_type": "automation_type",
    "parameters": {...},
    "steps": [...],
    "severity": "HIGH"
  }
}
```

### MCP Tools
Add new tools in `app/mcp/tools.py` and implement in `app/mcp/executor.py`

---

## 📊 Testing

### Test RAG Search
```bash
python -c "
from app.rag.rag_engine import get_rag_engine
engine = get_rag_engine()
results = engine.search('database connection error', top_k=3)
for r in results:
    print(f\"Similarity: {r['similarity']:.2f}, Type: {r['document'].get('error_type')}\")
"
```

### Test MCP Tools
```bash
python -c "
from app.mcp.tools import get_all_tools
for tool in get_all_tools():
    print(f\"Tool: {tool['name']} - {tool['description']}\")
"
```

---

## 🚢 Deploy to Cloud Run

```bash
# Build image
gcloud builds submit --tag gcr.io/auto-sre-ai-multi-agent/autosre-ai:latest

# Deploy
gcloud run deploy autosre-ai \
  --image gcr.io/auto-sre-ai-multi-agent/autosre-ai:latest \
  --platform managed \
  --region us-central1 \
  --memory 2Gi

# Get URL
gcloud run services describe autosre-ai --region us-central1
```

---

## 📖 Documentation

- [GENAI_ANALYSIS.md](GENAI_ANALYSIS.md) - Complete analysis and improvements
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Detailed deployment guide  
- [README.md](README.md) - Architecture and usage

---

## 🎯 Demo Script

### Try This Error Log
```
ERROR 2024-04-07 15:42:10 [db-pool] Connection pool exhausted. 
Unable to acquire connection after 30s. 
Service: billing-service. 
Connections: 50/50 active. 
Queue wait time: 45s
```

Expected behavior:
1. ✅ Identified as DB_CONNECTION_ERROR with HIGH severity
2. ✅ Found matching solution in knowledge base (0.92 confidence)
3. ✅ Decision: AUTO_FIX (restart DB service)
4. ✅ Executed: store_incident, publish_alert, trigger_auto_fix

---

## ❓ Troubleshooting

**Issue: GCP authentication fails**
```bash
gcloud auth application-default login
```

**Issue: Embedding service not responding**
- Check GCP project configuration
- Verify Vertex AI API is enabled

**Issue: FAISS index not found**
- First RAG search will rebuild index
- Index is cached for faster subsequent searches

**Issue: Tools not executing**
- Verify Firestore collection exists
- Verify Pub/Sub topic exists  
- Check IAM permissions

---

Happy hacking! 🚀
