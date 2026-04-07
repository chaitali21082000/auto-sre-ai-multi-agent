# Knowledge Base Feedback Loop - Complete Integration Guide

## ✅ Implementation Complete

The **knowledge base feedback loop** has been fully implemented. The system now learns from every incident it fixes, progressively building its knowledge base.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                   FEEDBACK LOOP SYSTEM                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  GitHub PR Merge        Webhook Receiver          KB Manager   │
│  ┌─────────────────┐    ┌──────────────────┐     ┌────────┐   │
│  │ auto-detected   │───▶│ Verify Signature │────▶│ Add    │   │
│  │ fix label       │    │ Extract Solution │     │ to KB  │   │
│  └─────────────────┘    │ Validate Quality │     └────────┘   │
│                        └──────────────────┘           │        │
│                                                       ▼        │
│  Scheduled Sync (6h)    GitHub API Query      FAISS Rebuild   │
│  ┌────────────────────┐   ┌──────────────┐    ┌──────────┐   │
│  │ Query merged PRs   │──▶│ auto-detected│───▶│ Search   │   │
│  │ Check for labels   │   │ fix label    │    │ Index    │   │
│  │ Deduplicate        │   └──────────────┘    └──────────┘   │
│  └────────────────────┘                                       │
│                                                                 │
│  Manual API Endpoints          Dashboard                       │
│  ┌────────────────────┐       ┌─────────────┐                │
│  │ POST /kb/solutions │       │ /kb/stats   │                │
│  │ POST /kb/confidence│───────│ /kb/health  │                │
│  │ DELETE /kb/solution│       │ Confidence  │                │
│  └────────────────────┘       │ Distribution│                │
│                               └─────────────┘                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Files Created

### 1. **app/rag/knowledge_manager.py** (350 lines)
**Purpose**: Core knowledge base operations with feedback loop support

**Key Methods**:
- `add_solution(solution_data)` - Add/update solutions in KB
- `validate_solution_quality(data)` - Pre-automation validation
- `update_confidence(error_type, event)` - Dynamic confidence scoring
  - `SUCCESS` +0.05 (caps at 0.95)
  - `FAILURE` -0.15 (floors at 0.40)
  - `MANUAL_REVIEW` +0.10 (caps at 0.98)
  - `PARTIAL_SUCCESS` +0.02 (caps at 0.95)
- `get_solution(error_type)` - Retrieve specific solution
- `list_all_solutions()` - Return all solutions
- `list_learned_solutions()` - Auto-learned only
- `get_kb_statistics()` - Dashboard metrics
- `delete_solution(error_type)` - Rollback mechanism

**Validation Rules**:
- Error type: UPPER_CASE format
- Steps: Minimum 2 required
- Confidence: 0.0 - 1.0 range
- Severity: HIGH, MEDIUM, or LOW

---

### 2. **app/api/webhook_handler.py** (400 lines)
**Purpose**: GitHub webhook receiver that auto-learns from PR merges

**Endpoint**: `POST /api/webhooks/github`

**Flow**:
1. Receive GitHub webhook event
2. Verify HMAC SHA256 signature
3. Check for "auto-detected-fix" label
4. Extract solution using regex patterns
5. Validate solution quality
6. Add to KB
7. Rebuild FAISS index
8. Return status

**Solution Extraction** (7 regex patterns):
- **Error Type**: `[AUTO-FIX] ERROR_TYPE` or `\b([A-Z_]{3,})\b`
- **Description**: Looks for "Error:" or "**Description**" sections
- **Root Cause**: Multiple patterns checked sequentially
- **Fix Type**: Extracts categorized fix approach
- **Steps**: Parses markdown lists or numbered steps
- **Severity**: HIGH, MEDIUM, or LOW (default HIGH)
- **Confidence**: Float 0.0-1.0 (default 0.85 for auto-learned)

**Key Functions**:
- `verify_github_signature(body, signature, secret)` - HMAC validation
- `extract_solution_from_pr(pr_data)` - Parse PR body to solution
- `handle_pr_event(payload)` - Process PR merged events
- `handle_issue_event(payload)` - Process issue closed events

---

### 3. **app/jobs/sync_kb_from_github.py** (350 lines)
**Purpose**: Background scheduler that syncs KB from GitHub (fallback mechanism)

**Process** (Runs every 6 hours by default):
1. Authenticate with GitHub API
2. Query each configured repo for merged PRs
3. Filter by "auto-detected-fix" label
4. Filter by last 6 hours (configurable)
5. Skip if error_type already in KB (deduplication)
6. Extract and validate solutions
7. Batch add to KB
8. Rebuild FAISS once after all additions

**Key Classes**:
- `KnowledgeBaseSyncJob` - Main scheduler class
- Methods: `sync_kb_from_github()`, `start_scheduler()`, `stop_scheduler()`, `add_repo()`, `set_repos()`, `get_status()`

**Configuration**:
- `SYNC_REPOS` - Comma-separated list of repos to monitor
- `KB_SYNC_INTERVAL_HOURS` - Sync frequency (default 6)
- `GITHUB_TOKEN` - Personal access token for API

**Reliability Features**:
- Per-repo exception handling (doesn't fail entire batch)
- Daemon thread with graceful shutdown
- Duplicate detection and skipping
- Rate limit awareness (50 PRs max per repo)

---

### 4. **app/api/kb_api.py** (300 lines)
**Purpose**: REST API for knowledge base management and operations

**Endpoints** (All at `/api/kb/`):

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/solutions` | List all solutions |
| GET | `/solutions/<error_type>` | Get specific solution |
| GET | `/solutions/auto-learned` | Filter auto-learned only |
| POST | `/solutions` | Add new solution (manual) |
| POST | `/solutions/<error_type>/confidence` | Update confidence score |
| DELETE | `/solutions/<error_type>` | Remove solution (with confirmation) |
| GET | `/stats` | KB statistics dashboard |
| GET | `/health` | Health check with integrity validation |

**Example: Add Solution via API**
```bash
curl -X POST http://localhost:8000/api/kb/solutions \
  -H "Content-Type: application/json" \
  -d '{
    "error_type": "DATABASE_CONNECTION_TIMEOUT",
    "description": "Connection pool exhausted",
    "fix_type": "CONFIG_ADJUSTMENT",
    "steps": [
      "Increase max_pool_size to 50",
      "Restart service"
    ],
    "severity": "HIGH",
    "confidence": 0.85,
    "is_auto_learned": true
  }'
```

**Example: Update Confidence**
```bash
curl -X POST http://localhost:8000/api/kb/solutions/DATABASE_CONNECTION_TIMEOUT/confidence \
  -H "Content-Type: application/json" \
  -d '{
    "event": "SUCCESS"
  }'
```

---

## Environment Configuration

Add to your `.env` file:

```bash
# GitHub Integration
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxx          # Personal access token
GITHUB_WEBHOOK_SECRET=your_webhook_secret       # For signature verification
GITHUB_ORG=your-organization                     # Organization name

# Knowledge Base Sync
SYNC_REPOS=org/service1,org/service2,org/service3  # Repos to sync from
KB_SYNC_INTERVAL_HOURS=6                        # How often to run (default 6)
KB_AUTO_LEARN_ENABLED=true                      # Enable/disable auto-learning
```

---

## GitHub Webhook Setup

For each repository that will feed solutions to the KB:

1. Go to: `https://github.com/YOUR_ORG/YOUR_REPO/settings/hooks`
2. Click "Add webhook"
3. Configure:
   - **Payload URL**: `https://your-autosre-domain.com/api/webhooks/github`
   - **Content type**: `application/json`
   - **Secret**: (Paste your `GITHUB_WEBHOOK_SECRET` value)
   - **Events**: Select "Pull requests" and "Issues"
4. Click "Add webhook"
5. Test by clicking "Redeliver" on a recent delivery

---

## Testing the Feedback Loop

### 1. Check KB Status
```bash
curl http://localhost:8000/api/kb/stats | jq .
```

Response:
```json
{
  "status": "success",
  "statistics": {
    "total_solutions": 15,
    "auto_learned_solutions": 8,
    "manual_solutions": 7,
    "avg_confidence": 0.82,
    "total_file_size_kb": 42.5
  }
}
```

### 2. Add Solution Manually
```bash
curl -X POST http://localhost:8000/api/kb/solutions \
  -H "Content-Type: application/json" \
  -d '{
    "error_type": "TEST_ERROR",
    "description": "Test solution",
    "fix_type": "TEST_FIX",
    "steps": ["Step 1", "Step 2"],
    "severity": "HIGH",
    "confidence": 0.85
  }'
```

### 3. Simulate GitHub Webhook (for testing locally)
```bash
# Create payload
PAYLOAD='{"action": "closed", "pull_request": {"merged": true, "title": "[AUTO-FIX] DATABASE_TIMEOUT", "body": "...solution details..."}}'

# Calculate signature
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "your_secret" | sed 's/^.* //')

# Send webhook
curl -X POST http://localhost:8000/api/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -H "X-Hub-Signature-256: sha256=$SIGNATURE" \
  -d "$PAYLOAD"
```

### 4. Monitor Scheduled Sync
Check logs for:
```
INFO - KB sync job initialized for 3 repos
INFO - Syncing KB from GitHub...
INFO - Added 5 new solutions from GitHub
```

---

## Confidence Scoring

The system maintains confidence scores for each solution (0.0 to 1.0):

- **Auto-learned solutions**: Start at 0.85
- **Manual solutions**: Default to 0.90
- **Dynamic adjustments**:
  - SUCCESS execution: +0.05 (capped at 0.95)
  - FAILURE execution: -0.15 (floored at 0.40)
  - Manual review: +0.10 (capped at 0.98)
  - Partial success: +0.02 (capped at 0.95)

Solutions with low confidence (<0.60) after >5 applications trigger health warnings.

---

## Safety Mechanisms

### 1. Solution Quality Validation
Before adding to KB, solutions must:
- Have error type in UPPER_CASE
- Include at least 2 fix steps
- Have confidence between 0 and 1
- Specify valid severity (HIGH/MEDIUM/LOW)

### 2. Signature Verification
GitHub webhooks are verified using HMAC SHA256:
- Webhook payload is signed by GitHub using your secret
- Signature verified before processing
- Invalid signatures rejected with 401

### 3. Deduplication
Scheduled sync and manual additions:
- Check if error_type already exists
- Skip duplicate entries
- Prevent corrupted KB state

### 4. Rollback Capability
All solutions can be deleted with confirmation:
```bash
curl -X DELETE "http://localhost:8000/api/kb/solutions/ERROR_TYPE?confirm=true"
```

---

## Monitoring & Analytics

### KB Health Check
```bash
curl http://localhost:8000/api/kb/health | jq .
```

Returns:
- Overall health status (healthy/warning)
- Statistics (total solutions, avg confidence)
- Issues detected (low-confidence solutions)

### Solutions by Source
```bash
# Auto-learned only
curl http://localhost:8000/api/kb/solutions/auto-learned

# Manual only
curl http://localhost:8000/api/kb/solutions
```

---

## Next Steps

1. **Install Dependencies**: `pip install -r requirements.txt`
2. **Configure GitHub**: Set `GITHUB_TOKEN` and `GITHUB_WEBHOOK_SECRET` in `.env`
3. **Add Webhooks**: Configure webhook in your service repositories
4. **Set Repos to Sync**: Configure `SYNC_REPOS` in `.env`
5. **Start App**: `python -m uvicorn app.main:app --reload`
6. **Test**: Merge a PR with "auto-detected-fix" label and verify KB update

---

## Data Storage

Knowledge base stored at: `app/rag/knowledge_base.json`

Format:
```json
{
  "DATABASE_TIMEOUT": {
    "error_type": "DATABASE_TIMEOUT",
    "description": "Connection pool exhausted",
    "fix_type": "CONFIG_ADJUSTMENT",
    "steps": [
      "Increase max_pool_size to 50",
      "Restart service"
    ],
    "severity": "HIGH",
    "confidence": 0.82,
    "is_auto_learned": true,
    "learned_from": "github_pr_#1234",
    "last_used": "2024-01-15T10:30:00Z",
    "validation_count": 3,
    "source": "webhook"
  }
}
```

---

## Support & Debugging

### Check if endpoints are registered
```bash
curl http://localhost:8000/api/kb/stats
```

### View startup logs
```bash
# Should see:
# ✅ KB sync job initialized for N repos
# 📚 Knowledge Base: X solutions (Y auto-learned)
```

### Verify webhook signature verification
Set `GITHUB_WEBHOOK_SECRET` in `.env` to enable signature validation.

### Monitor FAISS index rebuilds
Manually rebuild if needed:
```python
from app.rag.knowledge_manager import rebuild_faiss_index
rebuild_faiss_index()
```

---

**Implementation Complete** ✅

The knowledge base now learns continuously from your incident fixes!
