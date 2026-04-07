# AutoSRE AI - Quick Deployment Reference

## 🎯 What's Left

**Documentation (5 files only):**
1. ✅ **README.md** - Project overview
2. ✅ **QUICKSTART.md** - Quick start guide
3. ✅ **COMPLETE_FLOW_DEEP_DIVE.md** - How the system works
4. ✅ **FEEDBACK_LOOP_INTEGRATION.md** - Learning feature
5. ✅ **DEPLOYMENT_AND_TESTING_GCP.md** - **👈 USE THIS TO DEPLOY**

---

## 🚀 One-Command Deployment (Start Here!)

```bash
# 1. Set variables
export PROJECT_ID="your-gcp-project"
export REGION="us-central1"

# 2. Clone repo and navigate
cd auto-sre-ai-multi-agent

# 3. Run the comprehensive deployment guide
# Follow: DEPLOYMENT_AND_TESTING_GCP.md (full instructions)
```

---

## ⚡ Quick 5-Step Deployment Summary

### **1️⃣ GCP Setup (30 min)**
```bash
# Enable services + create service account + databases
# See: DEPLOYMENT_AND_TESTING_GCP.md → Part 1
```

### **2️⃣ Update Code (15 min)**
```bash
# Add persistence to Cloud Storage + Secret Manager
# See: DEPLOYMENT_AND_TESTING_GCP.md → Part 2
```

### **3️⃣ Deploy (30 min)**
```bash
# Build Docker image → Deploy to Cloud Run + Cloud Function
# See: DEPLOYMENT_AND_TESTING_GCP.md → Part 3
```

### **4️⃣ Test End-to-End (40 min)**
```bash
# Health check → Error analysis → KB storage → Webhooks
# See: DEPLOYMENT_AND_TESTING_GCP.md → Part 4
```

### **5️⃣ Load Test (20 min, optional)**
```bash
# Verify production readiness
# See: DEPLOYMENT_AND_TESTING_GCP.md → Part 5
```

---

## 🔑 Critical Code Changes Required

Before deployment, update these 4 files:

### **1. app/rag/knowledge_manager.py**
- Replace `load_kb()` to read from Cloud Storage
- Replace `save_kb()` to write to Cloud Storage
- Add GCS imports
- ✅ See detailed code in: DEPLOYMENT_AND_TESTING_GCP.md → Step 2.1

### **2. app/rag/rag_engine.py**
- Replace `_rebuild_index()` to save to Cloud Storage
- Add `_load_index_from_gcs()` method
- Add `_save_index_to_gcs()` method
- ✅ See detailed code in: DEPLOYMENT_AND_TESTING_GCP.md → Step 2.2

### **3. app/github/client.py**
- Replace token initialization to use Secret Manager
- Add `get_secret()` helper function
- ✅ See detailed code in: DEPLOYMENT_AND_TESTING_GCP.md → Step 2.3

### **4. app/api/webhook_handler.py**
- Improve `verify_github_signature()` function
- Add Secret Manager fetch
- ✅ See detailed code in: DEPLOYMENT_AND_TESTING_GCP.md → Step 2.4

---

## 📋 Pre-Deployment Checklist

- [ ] All 4 code files updated (see above)
- [ ] GCP project created with billing enabled
- [ ] `gcloud` CLI installed
- [ ] Docker installed
- [ ] GitHub personal access token available
- [ ] Read entire: DEPLOYMENT_AND_TESTING_GCP.md

---

## 🧪 Testing After Deployment

```bash
# 1. Health check
curl $CLOUD_RUN_URL/health

# 2. Analyze error
curl -X POST $CLOUD_RUN_URL/analyze \
  -H "Content-Type: application/json" \
  -d '{"log": "ERROR: Database timeout"}'

# 3. Check KB stats
curl $CLOUD_RUN_URL/api/kb/stats

# 4. Simulate webhook
# See: DEPLOYMENT_AND_TESTING_GCP.md → Step 4.5
```

---

## ⚠️ Most Important: Data Persistence

**The #1 Issue in GCP:**

```
❌ PROBLEM: Default code stores KB as local file
   - Cloud Run restarts = KB LOST
   - Every restart = Start from scratch
   - Learning stops working

✅ SOLUTION: Store in Cloud Storage
   - Survive restarts
   - Permanent persistence
   - Learning continues
```

**This is why Step 2.1 & 2.2 are critical!**

---

## 📞 Support

If deployment fails:
1. Check Cloud Run logs: `gcloud run logs read autosre-ai`
2. Verify IAM permissions: `gcloud projects get-iam-policy $PROJECT_ID`
3. Confirm Firestore is running: `gcloud firestore databases list`
4. See troubleshooting in: DEPLOYMENT_AND_TESTING_GCP.md → Part 6

---

## 📊 Architecture After Deployment

```
┌─────────────────────────────┐
│   Your Monitoring System     │
│ (Datadog, Prometheus, etc)   │
└──────────────┬──────────────┘
               │ logs
               ▼
        ┌─────────────┐
        │  Cloud Run  │◄─── Service Account
        │ AutoSRE AI  │
        └─┬───────┬───┘
          │       │
    ┌─────▼─────┐ │
    │ Firestore │ │ stores incidents
    │incidents  │ │
    └───────────┘ │
          │       │
    ┌─────▼─────────────┐
    │ Cloud Storage     │
    │ - knowledge_base  │  auto-learning
    │ - faiss_index     │
    │ - embeddings      │
    └───────────────────┘
          │
    ┌─────▼─────────────┐
    │  Pub/Sub Topics   │
    │  (alerts)         │  notifications
    └───────────────────┘
          │
    ┌─────▼─────┐
    │   Slack   │
    │  PagerDuty│  ◄─── Your team
    │   Email   │
    └───────────┘
```

---

## 🎓 Learning Resources in This Repo

| File | Purpose |
|------|---------|
| **README.md** | Overview and features |
| **QUICKSTART.md** | Local development setup |
| **COMPLETE_FLOW_DEEP_DIVE.md** | How system works step-by-step |
| **FEEDBACK_LOOP_INTEGRATION.md** | How auto-learning works |
| **DEPLOYMENT_AND_TESTING_GCP.md** | 👈 **MAIN deployment guide** |

---

## 🎯 Success Criteria

After following DEPLOYMENT_AND_TESTING_GCP.md, you should have:

✅ Cloud Run service running and accessible
✅ Firestore storing incidents
✅ Cloud Storage persisting KB data
✅ GitHub webhooks auto-learning solutions
✅ Error analysis working end-to-end
✅ All tests passing

---

**Total time: ~2 hours 15 minutes**

👉 **Start with: DEPLOYMENT_AND_TESTING_GCP.md**
