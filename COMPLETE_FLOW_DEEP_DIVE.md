# AutoSRE AI - Deep Dive: Complete Flow Explanation

## **TL;DR - The Simplest Possible Explanation**

Your app breaks → AutoSRE catches it → AutoSRE reads what's wrong → AutoSRE looks up fixes in memory → AutoSRE either fixes it or alerts you → AutoSRE learns from every fix it makes → Next time it fixes faster

---

## **The Complete Journey: Error to Resolution**

### **PHASE 0: System Startup (One-Time Setup)**

**When the app starts:**

1. **Initialize the Knowledge Base**
   - Load `knowledge_base.json` (a file containing all solutions we've seen before)
   - Convert each solution to vector numbers (embeddings)
   - Build FAISS index (super-fast search engine)
   - This is like creating an index in a library

2. **Start Scheduled Learning**
   - Start background job that checks GitHub every 6 hours
   - Looks for merged PRs with "auto-detected-fix" label
   - These mean someone fixed something, so learn it
   - Store any new solutions we find

3. **Log Initial Status**
   ```
   ✅ KB sync job initialized for 3 repos
   📚 Knowledge Base: 45 solutions (12 auto-learned)
   ```

---

### **PHASE 1: Error Comes In**

**Scenario:** Your billing service crashes with a database timeout

**What happens:**

```
┌─ Monitoring System (Datadog, etc.) ─┐
│ Detects: Database isn't responding   │
│ Generates: Error log entry           │
├─────────────────────────────────────┤
│ Timestamp: 2026-04-08 10:45:23      │
│ Service: billing-service             │
│ Error: Connection timeout            │
│ Severity: Critical                   │
│ Message: "Unable to acquire DB       │
│          connection after 30s"       │
└─ Calls AutoSRE API endpoint ─────────┘
   │
   ▼
POST /analyze
{
  "log": "2026-04-08 10:45:23 ERROR ... connection timeout..."
}
   │
   ▼
orchestrator.py → handle_incident() starts
```

**Key Point:** From error detection to analysis starts, all happening in milliseconds.

---

### **PHASE 2: Analyze the Error (Log Agent)**

**Question:** "What just happened here?"

**The Log Agent does this:**

1. **Take the messy error log** (could be 100+ lines of text)
2. **Ask the LLM (Claude/GPT-4) to analyze it:**
   - "What type of error is this?"
   - "How serious is it?"
   - "Why did it happen?"
   - "Which services are affected?"

3. **LLM responds with structured data:**
   ```python
   {
     "type": "DB_CONNECTION_TIMEOUT",
     "severity": "HIGH",  # Not CRITICAL because not total failure
     "root_cause": "Connection pool exhausted - too many concurrent connections",
     "services_affected": ["billing-service", "payment-processor"],
     "error_message": "Unable to acquire connection after 30s"
   }
   ```

**Why structured data?**
- Machine can understand it
- Can make decisions based on it
- Can compare it to other errors
- Can search the knowledge base

**Code:**
```python
from app.agents.log_agent import analyze_log

result = analyze_log(raw_error_log)
# Takes ~2-3 seconds (calls LLM)
# Returns structured information above
```

**Timeline: T+2 seconds**

---

### **PHASE 3: Search Knowledge Base (RAG Agent)**

**Question:** "Have we fixed this before?"

**The RAG Agent does this:**

#### **Step 3a: Convert to Vector**

Instead of searching text, we search with numbers:

```
Error: "DB_CONNECTION_TIMEOUT"
Context: "Connection pool exhausted"

Converted to vector (simplified):
[0.23, 0.15, 0.89, 0.45, 0.92, ... 0.34]  ← 384 numbers total
```

Each solution in knowledge base is also vectors:
```
Solution 1: "Increase pool size" → [0.22, 0.16, 0.88, 0.46, 0.93, ...]
Solution 2: "Reduce max connections" → [0.11, 0.23, 0.45, 0.67, 0.22, ...]
Solution 3: "Add database replica" → [0.78, 0.34, 0.12, 0.56, 0.45, ...]
```

#### **Step 3b: Find Similar Solutions (FAISS Search)**

FAISS calculates: "Which solution has numbers closest to our error?"

```
Similarity Comparison:
Our error vector vs Solution 1: 0.94 match! ✓ (94% similar)
Our error vector vs Solution 2: 0.52 match  (52% similar)
Our error vector vs Solution 3: 0.18 match  (18% similar)

Filter by confidence (>60%):
- Solution 1: 0.94 ✓ INCLUDED
- Solution 2: 0.52 ✗ EXCLUDED
- Solution 3: 0.18 ✗ EXCLUDED
```

#### **Step 3c: Return Results**

```python
{
  "found": True,
  "solutions": [
    {
      "error_type": "DB_CONNECTION_TIMEOUT",
      "fix_type": "INCREASE_POOL_SIZE",
      "steps": [
        "Update config: max_pool_size = 100 (from 50)",
        "Restart database connection pool",
        "Verify new connections are available"
      ],
      "severity": "HIGH",
      "confidence": 0.94,   # HOW SURE WE ARE
      "last_used": "2 days ago",
      "success_rate": "98%"  # 49/50 times it worked
    }
  ],
  "total_results": 1,
  "overall_confidence": 0.94
}
```

**Key Insight:** 0.94 confidence means we're 94% sure this is the right fix!

**Code:**
```python
from app.agents.rag_agent import search_rag

results = search_rag(
  error_type="DB_CONNECTION_TIMEOUT",
  log_context=raw_error_log
)
# Takes ~0.5 seconds
# FAISS is very fast!
```

**Timeline: T+2.5 seconds**

---

### **PHASE 4: Enrich Analysis (Optional)**

**Question:** "Can we do better?"

**The Enrichment does this:**

1. **Take error analysis + RAG results**
2. **Ask LLM to synthesize both:**
   ```
   "We found a database connection timeout error.
    We found a similar incident that was fixed by increasing pool size.
    
    Given all this, what's the best recommendation?"
   ```

3. **LLM returns enhanced analysis:**
   ```python
   {
     "error_type": "DB_CONNECTION_TIMEOUT",
     "severity": "HIGH",
     "root_cause": "Connection pool exhausted",
     "recommended_solutions": [
       "Increase connection pool size to 100",
       "Monitor active connections",
       "Consider database read replicas"
     ],
     "confidence_in_diagnosis": 0.95
   }
   ```

**Timeline: T+2.7 seconds**

---

### **PHASE 5: Make Decision (Decision Agent)**

**Question:** "What should we DO about this?"

**Decision Options:**

```
┌─────────────────────────────────────────────────┐
│ DECISION TREE                                   │
├─────────────────────────────────────────────────┤
│                                                 │
│ Is it CRITICAL severity?                        │
│ │                                               │
│ ├─YES → ESCALATE (humans only)                 │
│ │       (e.g., "All servers down")             │
│ │                                               │
│ └─NO → Continue...                              │
│                                                 │
│     Does KB have high-confidence solution?      │
│     (> 0.80 match)                              │
│     │                                           │
│     ├─YES → AUTO_FIX ✅                         │
│     │       (We're very sure)                  │
│     │                                           │
│     └─NO → Continue...                          │
│                                                 │
│         Is it a new error (very low KB match)?  │
│         (< 0.60 match)                          │
│         │                                       │
│         ├─YES → AUTO_FIX_FROM_CONTEXT 🔧       │
│         │       (Analyze code to fix it)       │
│         │                                       │
│         └─NO → ALERT 📢                         │
│               (Medium confidence, notify team)  │
│                                                 │
└─────────────────────────────────────────────────┘
```

**For Our Scenario:**

```
Error: DB_CONNECTION_TIMEOUT
Severity: HIGH (not CRITICAL)
KB Match: 0.94 (very high!)

Decision Logic:
- Severity HIGH? Not CRITICAL → Continue
- KB confidence 0.94 > 0.80? YES!
  
DECISION: AUTO_FIX ✅
   
Reasoning: "High-confidence KB solution exists (94% match)
           Error is not critical, safe to auto-fix.
           Previous success rate: 98%"
```

**Code:**
```python
from app.agents.decision_agent import decide_action

decision = decide_action(
  parsed=error_analysis,
  rag_results=kb_search_results
)

# Returns:
# {
#   "action": "AUTO_FIX",
#   "confidence": 0.94,
#   "reasoning": "High-confidence KB solution",
#   "recommended_tools": ["update_db_config", "restart_pool"]
# }
```

**Timeline: T+3 seconds**

---

### **PHASE 6: Execute Decision (Execution Engine)**

**Question:** "Let's actually FIX this!"

#### **For AUTO_FIX Decision:**

The system now EXECUTES the fix steps:

```
EXECUTION PLAN:
├─ Step 1: Update configuration
│  └─ Config file: /etc/db/config.yaml
│  └─ Change: max_pool_size: 50 → 100
│  └─ Validate syntax: ✓ OK
│  └─ Apply change: ✓ Applied
│
├─ Step 2: Restart connection pool
│  └─ Shutdown old pool: ✓ Graceful drain 2 seconds
│  └─ Initialize new pool: ✓ 100 connections created
│  └─ Test connections: ✓ All healthy
│
├─ Step 3: Verify fix worked
│  └─ Query database: ✓ Response time 45ms
│  └─ Check query queue: ✓ Now 0 (was 50+)
│  └─ Monitor for 10 seconds: ✓ No new errors
│
└─ Result: ✅ FIXED!

Time taken: 45 seconds
```

**Other tools that might be called:**

| Tool | Purpose | Example |
|------|---------|---------|
| `store_incident` | Save to database | Log incident for audit trail |
| `publish_alert` | Send notification | Slack: "DB timeout fixed" |
| `exec_cloud_function` | Run code in cloud | Query GitHub for context |
| `update_kb_confidence` | Learn from fix | Mark solution as successful |

**Code:**
```python
from app.agents.decision_agent import execute_decision

result = execute_decision(
  decision=decision,
  parsed=error_analysis,
  rag_results=kb_results
)

# Returns:
# {
#   "success": True,
#   "action_taken": "AUTO_FIX",
#   "tools_executed": ["update_db_config", "restart_pool"],
#   "time_to_fix": 45,
#   "incident_id": "INC-12345"
# }
```

**Timeline: T+48 seconds (45s to execute + previous phases)**

---

### **PHASE 7: Learn & Improve (Feedback Loop)**

**Question:** "How can we be smarter next time?"

#### **Scenario A: Fix Succeeded (Most Common)**

1. **Record Success**
   ```
   Solution: "Increase pool size to 100"
   Result: WORKED
   Time: 45 seconds
   ```

2. **Update Confidence Score**
   ```
   Old confidence: 0.94
   New confidence: 0.94 + 0.05 = 0.99 (capped at 0.95)
   Updated: 0.95
   
   Success count: 49 → 50
   Success rate: 98% → 100%
   ```

3. **Store Success in Git (for team visibility)**
   ```
   Create GitHub PR:
   - Title: "[AUTO-FIX] DB_CONNECTION_TIMEOUT - Increased pool size"
   - Body: Solution details, steps taken, results
   - Label: "auto-detected-fix" ← IMPORTANT!
   - Merge: Approved and merged
   ```

4. **GitHub Webhook Fires**
   ```
   GitHub sees label "auto-detected-fix"
   Sends webhook to: POST /api/webhooks/github
   Payload contains: PR title, body, merge info
   ```

5. **Auto-Learn Handler Processes**
   ```python
   from app.api.webhook_handler import handle_pr_event
   
   - Extract solution from PR body (regex parsing)
   - Validate quality (checks format, steps, etc.)
   - Add to Knowledge Base
   - Rebuild FAISS index
   - Now: Searchable immediately!
   ```

6. **Final Result**
   ```
   Knowledge Base Entry:
   {
     "DB_CONNECTION_TIMEOUT": {
       "error_type": "DB_CONNECTION_TIMEOUT",
       "fix": "Increase pool size to 100",
       "steps": [...],
       "confidence": 0.95,
       "is_auto_learned": true,
       "learned_from": "github_pr_#1234",
       "success_count": 50,
       "last_used": "2026-04-08T10:45:23Z"
     }
   }
   
   ✅ Ready for next occurrence!
   ```

#### **Scenario B: Fix Failed (Rare)**

```
If fix didn't work:

1. Record failure
   Solution confidence: 0.95 - 0.15 = 0.80
   (dropped from 0.95 to 0.80)

2. Next time we find this error:
   - Still might auto-fix (0.80 > 0.8 threshold)
   - OR escalate to humans if multiple failures
   - OR try different solution

3. Humans investigate why it failed
   - Store findings in PR
   - Update KB with new information
```

**Timeline: T+50 seconds to T+6 minutes**
(For GitHub processing and FAISS rebuild)

---

## **Complete Timeline from Start to Finish**

```
T+0s   ├─ Error detected in production
       │
T+1s   ├─ Log received at /analyze endpoint
       │
T+2s   ├─ Phase 1: Log Agent analyzes
       │  └─ "This is DB_CONNECTION_TIMEOUT, HIGH severity"
       │
T+2.5s ├─ Phase 2: RAG searches knowledge base
       │  └─ "Found solution with 0.94 confidence"
       │
T+2.7s ├─ Phase 3: Enrichment synthesizes
       │  └─ "Recommended: increase pool size"
       │
T+3s   ├─ Phase 4: Decision Agent chooses
       │  └─ "Decision: AUTO_FIX (confidence 0.94)"
       │
T+3.1s ├─ Phase 5: Execution starts
       │
T+48s  ├─ ✅ FIX APPLIED
       │  └─ Database pool size increased
       │  └─ Services responding normally
       │
T+50s  ├─ Phase 6: Learn from fix
       │  └─ Create GitHub PR with solution
       │  └─ Send webhook notification
       │
T+55s  ├─ GitHub webhook processed
       │  └─ Solution added to KB
       │  └─ FAISS index rebuilt
       │
T+60s  └─ ✅ ALL DONE - Next similar error will be found even faster!
```

---

## **What Makes This Intelligent?**

### **1. Understanding Context (Vector Search)**

Instead of exact text match, system understands meaning:

```
DB_CONNECTION_TIMEOUT
DB conn timeout
Cannot connect to db 30s
Database connection rejected

All understood as: "Database connection problem"
Because vectors are similar!
```

### **2. Confidence Scoring**

System knows how sure it is:

```
Confidence 0.95: "Do it immediately"
Confidence 0.75: "Send alert, verify with team"
Confidence 0.45: "Escalate to humans"
```

### **3. Self-Improving**

Every fix makes it smarter:

```
Fix 1: confidence 0.80
Fix 2: confidence 0.85 (worked again!)
Fix 3: confidence 0.90 (worked again!)
Fix 4: confidence 0.95 (very confident now!)
```

### **4. Multiple Strategies**

Doesn't put all eggs in one basket:

- **AUTO_FIX**: Use KB solution (fastest)
- **AUTO_FIX_FROM_CONTEXT**: Generate fix from code (for new issues)
- **ALERT**: Notify team (for medium confidence)
- **ESCALATE**: Human takes over (for critical)

### **5. Learning Without Human**

Automatically learns from successful merges:

```
GitHub PR merged with "auto-detected-fix" label
    └─ Webhook fires
        └─ Solution extracted
            └─ KB updated
                └─ Next similar error: Found faster!
```

---

## **Real Examples of Decisions**

### **Example 1: Common Problem**
```
Error: DB_CONNECTION_TIMEOUT (we've fixed 50 times before)
Confidence: 0.95
Decision: AUTO_FIX
Result: Fixed in 45 seconds ✅
```

### **Example 2: New Problem**
```
Error: WEIRD_MEMORY_LEAK (we've never seen this before)
Confidence: 0.15
Decision: AUTO_FIX_FROM_CONTEXT
Result: System analyzes code, finds issue, fixes it
        Stores solution for future! 🚀
```

### **Example 3: Unsure Problem**
```
Error: INTERMITTENT_TIMEOUT (maybe one thing, maybe another)
Confidence: 0.65
Decision: ALERT
Result: Slack notification sent to team
        Shows best guess: "Probably retry logic"
        Team verifies: "Yes, retry logic!" ✅
```

### **Example 4: Critical Problem**
```
Error: DATABASE_DOWN (all 4 servers unreachable)
Severity: CRITICAL
Confidence: 0.90
Decision: ESCALATE (even though high confidence!)
Result: PagerDuty alert → on-call engineer paged
        System provides best guess for them
        Humans make final call (because critical)
```

---

## **System Components Simplified**

```
┌────────────────────────────────────────────┐
│         AUTOSRE AI SYSTEM                  │
├────────────────────────────────────────────┤
│                                            │
│  LOG AGENT (Understands errors)           │
│  ├─ Takes: Raw messy log                  │
│  └─ Returns: Structured info              │
│                                            │
│  RAG ENGINE (Remembers solutions)         │
│  ├─ Stores: Knowledge base                │
│  ├─ Searches: Using vectors               │
│  └─ Index: FAISS for speed                │
│                                            │
│  DECISION AGENT (Makes choices)           │
│  ├─ Rules: Based on severity              │
│  ├─ Logic: Based on confidence            │
│  └─ Output: Action to take                │
│                                            │
│  EXECUTION ENGINE (Does the work)         │
│  ├─ Calls: MCP tools                      │
│  ├─ Executes: Fix steps                   │
│  └─ Verifies: Fix actually worked         │
│                                            │
│  FEEDBACK LOOP (Learns from fixes)        │
│  ├─ Watches: GitHub PRs                   │
│  ├─ Extracts: Solutions                   │
│  └─ Updates: Knowledge base               │
│                                            │
└────────────────────────────────────────────┘
```

---

## **Data Flow at a Glance**

```
ERROR LOG
    ↓
LOG AGENT → Structured Analysis
    ↓
RAG AGENT → Similar Solutions + Confidence
    ↓
ENRICHMENT → Best Recommendation
    ↓
DECISION AGENT → Action (AUTO_FIX/ALERT/ESCALATE)
    ↓
EXECUTION ENGINE → Apply Fix
    ↓
FEEDBACK LOOP → Learn & Improve
    ↓
✅ Smarter for Next Time!
```

---

## **Key Metrics to Understand**

| Metric | Meaning | Example |
|--------|---------|---------|
| **Confidence** | How sure we are about solution (0-1) | 0.94 = 94% sure |
| **Similarity** | How close error matches KB entry (0-1) | 0.87 = 87% match |
| **Success Rate** | % of times this solution worked | 49/50 = 98% |
| **Time to Fix** | How long from error to resolution | 45 seconds |
| **Validation Count** | How many times solution was used | Used 50 times |

---

## **When to Use Each Decision Type**

| Situation | Decision | Why |
|-----------|----------|-----|
| Database timeout (seen 100+ times) | AUTO_FIX | Very confident (0.95+) |
| Brand new error (never seen before) | AUTO_FIX_FROM_CONTEXT | No KB entry, but not critical |
| API error (seen sometimes) | ALERT | Medium confidence (0.65) |
| All servers down | ESCALATE | CRITICAL (humans must decide) |

---

## **The Beautiful Cycle**

```
┌─────────────────────────────────────────────┐
│                                             │
│  Error happens in production                │
│          ↓                                  │
│  AutoSRE analyzes and fixes                │
│          ↓                                  │
│  Fix merged to GitHub (auto-detected tag)  │
│          ↓                                  │
│  Webhook fires → KB updated                │
│          ↓                                  │
│  FAISS index rebuilt                       │
│          ↓                                  │
│  Same error happens again (inevitable)     │
│          ↓                                  │
│  AutoSRE finds it FASTER and STRONGER      │
│          ↓                                  │
│  System gets progressively smarter ✨      │
│                                             │
└─────────────────────────────────────────────┘
```

---

## **TL;DR Summary**

| Step | What | How | Time |
|------|------|-----|------|
| 1 | Error Arrives | API call | T+0s |
| 2 | Analyze | LLM reads log | T+2s |
| 3 | Search | FAISS finds similar | T+2.5s |
| 4 | Enrich | LLM synthesizes | T+2.7s |
| 5 | Decide | Choose action | T+3s |
| 6 | Execute | Run fix tools | T+3-48s |
| 7 | Learn | Update KB via GitHub | T+50s+ |

**Total: ~1 minute from error to resolution + learning**

---

**AutoSRE AI: The system that fixes itself while learning!** 🚀
