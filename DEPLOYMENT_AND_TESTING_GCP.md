# AutoSRE AI - Deployment & Testing on GCP (Complete Guide)

## **Overview**

This guide walks you through deploying AutoSRE AI to Google Cloud Platform and testing it end-to-end.

**Prerequisites:**
- Google Cloud Project with billing enabled
- `gcloud` CLI installed locally
- Docker installed (for local testing)
- GitHub organization with at least one repository
- Python 3.11+

---

## **Part 1: GCP Setup (30 minutes)**

### **Step 1.1: Create GCP Project & Enable APIs**

```bash
# Set your project ID
export PROJECT_ID="your-project-id"
export REGION="us-central1"

# Set default project
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
  aiplatform.googleapis.com \
  firestore.googleapis.com \
  pubsub.googleapis.com \
  cloudfunctions.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  compute.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com

echo "✅ APIs enabled"
```

---

### **Step 1.2: Create Service Account**

```bash
# Create service account
gcloud iam service-accounts create autosre-sa \
  --display-name="AutoSRE AI Service Account" \
  --description="Service account for AutoSRE AI application"

# Store service account email
export SA_EMAIL="autosre-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant Vertex AI permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/aiplatform.user"

# Grant Firestore permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/datastore.user"

# Grant Pub/Sub permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/pubsub.editor"

# Grant Secret Manager permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"

# Grant Cloud Functions permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/cloudfunctions.developer"

# Grant Cloud Run permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.developer"

# Grant Storage permissions (for FAISS index)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin"

echo "✅ Service account created with permissions"
```

---

### **Step 1.3: Create Firestore Database**

```bash
# Create Firestore database (native mode)
gcloud firestore databases create \
  --location=$REGION \
  --type=firestore-native

echo "✅ Firestore database created"
```

---

### **Step 1.4: Create Pub/Sub Topic for Alerts**

```bash
# Create topic
gcloud pubsub topics create alerts

# Create subscription (for manual testing)
gcloud pubsub subscriptions create alerts-sub \
  --topic=alerts \
  --ack-deadline=60

echo "✅ Pub/Sub topic created"
```

---

### **Step 1.5: Create Cloud Storage Bucket**

```bash
# Create unique bucket name
export BUCKET_NAME="autosre-kb-${PROJECT_ID}"

gsutil mb -l $REGION gs://${BUCKET_NAME}

echo "✅ Cloud Storage bucket created: $BUCKET_NAME"
```

---

### **Step 1.6: Store Secrets**

```bash
# GitHub Token (get from https://github.com/settings/tokens)
read -p "Enter GitHub Personal Access Token: " GITHUB_TOKEN
echo -n "$GITHUB_TOKEN" | gcloud secrets create github-token --data-file=-

# GitHub Webhook Secret (generate random)
WEBHOOK_SECRET=$(openssl rand -hex 32)
echo -n "$WEBHOOK_SECRET" | gcloud secrets create github-webhook-secret --data-file=-

# Grant service account access to secrets
gcloud secrets add-iam-policy-binding github-token \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding github-webhook-secret \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"

echo "✅ Secrets created"
echo "GitHub Token: [created]"
echo "Webhook Secret: $WEBHOOK_SECRET"
```

---

## **Part 2: Code Updates for GCP Persistence**

### **Step 2.1: Update Knowledge Manager for Firestore**

Update `app/rag/knowledge_manager.py` to use Cloud Storage instead of local files:

```python
# Add at top of file:
from google.cloud import storage
from google.cloud import firestore
import os

# Replace load_kb and save_kb methods:
def load_kb(self):
    """Load KB from Cloud Storage"""
    try:
        storage_client = storage.Client()
        bucket_name = os.getenv("KB_BUCKET_NAME", "autosre-kb-default")
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob("knowledge_base.json")
        
        if blob.exists():
            content = blob.download_as_string()
            return json.loads(content)
        return {}
    except Exception as e:
        logger.warning(f"Could not load KB from GCS: {e}")
        # Fallback to local file if available
        if os.path.exists("app/rag/knowledge_base.json"):
            with open("app/rag/knowledge_base.json") as f:
                return json.load(f)
        return {}

def save_kb(self):
    """Save KB to Cloud Storage"""
    try:
        storage_client = storage.Client()
        bucket_name = os.getenv("KB_BUCKET_NAME", "autosre-kb-default")
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob("knowledge_base.json")
        
        blob.upload_from_string(
            json.dumps(self.knowledge_base, indent=2),
            content_type="application/json"
        )
        logger.info("KB saved to GCS")
    except Exception as e:
        logger.error(f"Error saving KB to GCS: {e}")
        # Try fallback to local storage
        os.makedirs("app/rag", exist_ok=True)
        with open("app/rag/knowledge_base.json", "w") as f:
            json.dump(self.knowledge_base, f, indent=2)
```

---

### **Step 2.2: Update RAG Engine for GCS Persistence**

Update `app/rag/rag_engine.py` to persist FAISS index:

```python
# Add at imports:
from google.cloud import storage
import os

# Update _initialize_index and _rebuild_index:
def _initialize_index(self):
    """Initialize FAISS index from GCS or create new one"""
    if self._gcs_index_exists():
        self._load_index_from_gcs()
    else:
        self._rebuild_index()

def _rebuild_index(self):
    """Rebuild FAISS index and save to GCS"""
    if not self.documents:
        self.index = faiss.IndexFlatL2(384)
        self.embeddings = np.array([])
        self._save_index_to_gcs()
        return
    
    # Get embeddings for all documents
    doc_texts = [json.dumps(doc) if isinstance(doc, dict) else str(doc) 
                 for doc in self.documents]
    embeddings = get_embeddings(doc_texts)
    
    # Create FAISS index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings.astype(np.float32))
    
    self.index = index
    self.embeddings = embeddings
    
    # Save to GCS
    self._save_index_to_gcs()

def _gcs_index_exists(self):
    """Check if FAISS index exists in GCS"""
    try:
        storage_client = storage.Client()
        bucket_name = os.getenv("KB_BUCKET_NAME", "autosre-kb-default")
        bucket = storage_client.bucket(bucket_name)
        return bucket.blob("faiss_index.bin").exists()
    except:
        return False

def _load_index_from_gcs(self):
    """Load FAISS index from GCS"""
    try:
        storage_client = storage.Client()
        bucket_name = os.getenv("KB_BUCKET_NAME", "autosre-kb-default")
        bucket = storage_client.bucket(bucket_name)
        
        # Download index
        bucket.blob("faiss_index.bin").download_to_filename("/tmp/index.bin")
        self.index = faiss.read_index("/tmp/index.bin")
        
        # Download embeddings
        bucket.blob("kb_embeddings.npy").download_to_filename("/tmp/embeddings.npy")
        self.embeddings = np.load("/tmp/embeddings.npy")
        
        logger.info("FAISS index loaded from GCS")
    except Exception as e:
        logger.error(f"Could not load FAISS from GCS: {e}")
        self._rebuild_index()

def _save_index_to_gcs(self):
    """Save FAISS index to GCS"""
    try:
        storage_client = storage.Client()
        bucket_name = os.getenv("KB_BUCKET_NAME", "autosre-kb-default")
        bucket = storage_client.bucket(bucket_name)
        
        os.makedirs("/tmp", exist_ok=True)
        
        # Save index
        faiss.write_index(self.index, "/tmp/index.bin")
        bucket.blob("faiss_index.bin").upload_from_filename("/tmp/index.bin")
        
        # Save embeddings
        np.save("/tmp/embeddings.npy", self.embeddings)
        bucket.blob("kb_embeddings.npy").upload_from_filename("/tmp/embeddings.npy")
        
        logger.info("FAISS index saved to GCS")
    except Exception as e:
        logger.error(f"Error saving FAISS to GCS: {e}")
```

---

### **Step 2.3: Update GitHub Client for Secret Manager**

Update `app/github/client.py`:

```python
# Add to imports:
from google.cloud import secretmanager
import os

# Add helper function:
def get_secret(secret_id):
    """Get secret from Secret Manager"""
    try:
        client = secretmanager.SecretManagerServiceClient()
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "auto-sre-ai-multi-agent")
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        logger.warning(f"Could not fetch {secret_id} from Secret Manager: {e}")
        return os.getenv(secret_id.upper())  # Fallback to env var

# Update __init__ method:
def __init__(self, github_token: str = None):
    import os
    self.token = github_token or get_secret("github-token") or os.getenv("GITHUB_TOKEN")
    self.api_url = "https://api.github.com"
    self.headers = {
        "Authorization": f"token {self.token}",
        "Accept": "application/vnd.github.v3+json"
    }
```

---

### **Step 2.4: Update Webhook Handler**

Update webhook verification in `app/api/webhook_handler.py`:

```python
# Improve verify_github_signature function
def verify_github_signature(body: bytes, signature: str, secret: str = None) -> bool:
    """Verify GitHub webhook signature"""
    import hmac
    import hashlib
    
    if not signature:
        logger.warning("No signature provided")
        return False
    
    # Get secret from Secret Manager if not provided
    if not secret:
        try:
            from google.cloud import secretmanager
            secret = get_secret_from_manager("github-webhook-secret")
        except:
            secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    
    if not secret:
        logger.warning("No webhook secret configured")
        return False
    
    expected_signature = "sha256=" + hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)
```

---

## **Part 3: Deployment to GCP (30 minutes)**

### **Step 3.1: Build Docker Image**

```bash
# Create .gcloudignore to exclude unnecessary files
cat > .gcloudignore <<EOF
# Python
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.venv/
venv/

# Git
.git/
.gitignore

# IDE
.vscode/
.idea/
*.swp
*.swo

# Test files
tests/
dummy_service/

# Local development
*.md
.env
.env.local
quickstart.py
error_pipeline.py
EOF

# Submit build to Cloud Build
gcloud builds submit \
  --tag gcr.io/${PROJECT_ID}/autosre-ai:latest \
  --timeout=1200s

echo "✅ Docker image built and pushed to GCR"
```

---

### **Step 3.2: Deploy to Cloud Run**

```bash
# Deploy main application
gcloud run deploy autosre-ai \
  --image gcr.io/${PROJECT_ID}/autosre-ai:latest \
  --platform managed \
  --region ${REGION} \
  --service-account ${SA_EMAIL} \
  --set-env-vars GOOGLE_CLOUD_PROJECT=${PROJECT_ID} \
  --set-env-vars KB_BUCKET_NAME=${BUCKET_NAME} \
  --set-env-vars PYTHONUNBUFFERED=True \
  --memory 2Gi \
  --cpu 2 \
  --timeout 3600 \
  --allow-unauthenticated \
  --min-instances 1 \
  --max-instances 10

# Get the Cloud Run URL
export CLOUD_RUN_URL=$(gcloud run services describe autosre-ai \
  --platform managed \
  --region ${REGION} \
  --format 'value(status.url)')

echo "✅ Cloud Run deployment successful"
echo "Service URL: $CLOUD_RUN_URL"
```

---

### **Step 3.3: Deploy Cloud Function (Auto-Fix)**

```bash
# Deploy Cloud Function for auto-fix (2nd gen by default in Cloud SDK 492+)
gcloud functions deploy auto-fix \
  --runtime python311 \
  --gen2 \
  --region ${REGION} \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point auto_fix \
  --source cloud_function/ \
  --set-env-vars GOOGLE_CLOUD_PROJECT=${PROJECT_ID} \
  --memory 512MB \
  --timeout 300

# Get Cloud Function URL
export CF_URL=$(gcloud functions describe auto-fix \
  --region ${REGION} \
  --gen2 \
  --format 'value(serviceConfig.uri)')

echo "✅ Cloud Function deployed"
echo "Function URL: $CF_URL"
```

**Note on Cloud SDK 492.0.0 or later:**
- By default, new functions deploy as 2nd gen
- Explicitly use `--gen2` flag for clarity
- Use `--no-gen2` if you need 1st gen compatibility
- Learn more: https://cloud.google.com/functions/docs/concepts/version-comparison

---

### **Step 3.4: Configure GitHub Webhook**

```bash
# IMPORTANT: Make sure CLOUD_RUN_URL is set from Step 3.2
# Verify it's set correctly:
echo "Cloud Run URL: ${CLOUD_RUN_URL}"
# Should output something like: https://autosre-ai-abc123.a.run.app

# If CLOUD_RUN_URL is empty, get it from Cloud Run:
if [ -z "$CLOUD_RUN_URL" ]; then
  export CLOUD_RUN_URL=$(gcloud run services describe autosre-ai \
    --platform managed \
    --region ${REGION} \
    --format 'value(status.url)')
  echo "✅ Set CLOUD_RUN_URL: ${CLOUD_RUN_URL}"
fi

# For each service repository, add webhook:

# Example for PERSONAL/PRIVATE repo:
# Use your GitHub USERNAME instead of organization
export ORG="chaitali21082000"
export REPO="auto-sre-ai-multi-agent"

# Get webhook secret
WEBHOOK_SECRET=$(gcloud secrets versions access latest --secret=github-webhook-secret)

# Get your GitHub token (already stored in Secret Manager)
GITHUB_TOKEN=$(gcloud secrets versions access latest --secret=github-token)

# Verify all variables are set before creating webhook
echo "Verifying webhook configuration:"
echo "  ORG: ${ORG}"
echo "  REPO: ${REPO}"
echo "  CLOUD_RUN_URL: ${CLOUD_RUN_URL}"
echo "  WEBHOOK_SECRET: ${WEBHOOK_SECRET:0:10}..." # Show first 10 chars
echo "  GITHUB_TOKEN: ${GITHUB_TOKEN:0:10}..." # Show first 10 chars

# Create webhook via GitHub API
curl -X POST \
  -H "Authorization: token ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/${ORG}/${REPO}/hooks \
  -d "{
    \"name\": \"web\",
    \"active\": true,
    \"events\": [\"pull_request\", \"issues\"],
    \"config\": {
      \"url\": \"${CLOUD_RUN_URL}/api/webhooks/github\",
      \"content_type\": \"json\",
      \"secret\": \"${WEBHOOK_SECRET}\",
      \"insecure_ssl\": \"0\"
    }
  }"

echo ""
echo "✅ GitHub webhook configured"
echo "Webhook URL: ${CLOUD_RUN_URL}/api/webhooks/github"
echo "Webhook Details:"
echo "  Repository: https://github.com/${ORG}/${REPO}"
echo "  Settings: https://github.com/${ORG}/${REPO}/settings/hooks"
```

**Troubleshooting webhook creation errors:**

| Error | Cause | Solution |
|-------|-------|----------|
| `url is missing a scheme` | CLOUD_RUN_URL is empty or missing `https://` | Run Step 3.2 first, verify with `echo ${CLOUD_RUN_URL}` |
| `Validation Failed` | Token or repository doesn't exist | Check GitHub token has `repo:admin:repo_hook` scope |
| `Not Found` | ORG or REPO name is wrong | Verify with `https://github.com/${ORG}/${REPO}` |

**Finding your ORG value:**
- **Organization repo**: Use your organization name (e.g., `my-company`)
- **Personal/Private repo**: Use your GitHub username (e.g., `chaitali21082000`)
- **Verify**: Open `https://github.com/YOUR_USERNAME_OR_ORG` in browser

---

## **Part 4: Testing End-to-End (40 minutes)**

### **Step 4.1: Health Check**

```bash
# Check if service is running
curl ${CLOUD_RUN_URL}/health

# Expected response:
# {"status": "ok", "components": {"llm": "configured", ...}}
```

---

### **Step 4.2: Test Error Analysis**

```bash
# Test 1: Simple database timeout error
curl -X POST ${CLOUD_RUN_URL}/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "log": "ERROR 2026-04-08 10:45:23 Database connection timeout after 30s. Service: billing-service. Unable to acquire connection from pool."
  }'

# Expected: HIGH severity, DB_CONNECTION_TIMEOUT type, confidence ~0.85-0.95

echo "✅ Test 1: Error analysis working"
```

---

### **Step 4.3: Test KB Storage**

```bash
# Check if incident was stored in Firestore
gcloud firestore documents list --collection-id incidents --limit 3

# Check if KB was saved to Cloud Storage
gsutil ls gs://${BUCKET_NAME}/

# Expected: knowledge_base.json, faiss_index.bin, kb_embeddings.npy
```

---

### **Step 4.4: Test API Endpoints**

```bash
# Get KB statistics
curl ${CLOUD_RUN_URL}/api/kb/stats

# Get all solutions
curl ${CLOUD_RUN_URL}/api/kb/solutions

# Add manual solution
curl -X POST ${CLOUD_RUN_URL}/api/kb/solutions \
  -H "Content-Type: application/json" \
  -d '{
    "error_type": "TEST_ERROR",
    "description": "Test solution",
    "fix_type": "TEST_FIX",
    "steps": ["Step 1", "Step 2"],
    "severity": "HIGH",
    "confidence": 0.85
  }'

# Get KB health
curl ${CLOUD_RUN_URL}/api/kb/health
```

---

### **Step 4.5: Test GitHub Webhook**

**Option A: Simulate webhook locally**

```bash
# Create a test PR payload
PAYLOAD=$(cat <<'EOF'
{
  "action": "closed",
  "pull_request": {
    "merged": true,
    "title": "[AUTO-FIX] DB_CONNECTION_TIMEOUT",
    "body": "## Solution\n\n**Error Type:** DB_CONNECTION_TIMEOUT\n**Fix:** Increase connection pool size\n**Steps:**\n- Update max_pool_size to 100\n- Restart service\n**Severity:** HIGH\n**Confidence:** 0.90"
  }
}
EOF
)

# Calculate signature
WEBHOOK_SECRET=$(gcloud secrets versions access latest --secret=github-webhook-secret)
SIGNATURE="sha256=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | sed 's/^.* //')"

# Send webhook
curl -X POST ${CLOUD_RUN_URL}/api/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -H "X-Hub-Signature-256: $SIGNATURE" \
  -d "$PAYLOAD"

echo "✅ Webhook test sent"
```

**Option B: Real GitHub PR test**

1. Create a test PR in your repository
2. In PR description, add:
   ```
   ## Auto-Fix Solution
   [AUTO-FIX] DATABASE_TIMEOUT
   
   ### Error Analysis
   **Root Cause:** Connection pool exhausted
   
   ### Solution Steps
   - Increase max_pool_size from 50 to 100
   - Verify connections available
   
   **Severity:** HIGH
   **Confidence:** 0.85
   ```

3. Add label "auto-detected-fix" to PR
4. Merge PR
5. Check Cloud Run logs: `gcloud run logs read autosre-ai --limit 50`

---

### **Step 4.6: Test Alert Publishing**

```bash
# Many errors should trigger alerts

# Generate multiple errors
for i in {1..3}; do
  curl -X POST ${CLOUD_RUN_URL}/analyze \
    -H "Content-Type: application/json" \
    -d "{
      \"log\": \"ERROR: Database connection timeout attempt $i\"
    }"
done

# Pull messages from Pub/Sub subscription
gcloud pubsub subscriptions pull alerts-sub \
  --auto-ack \
  --limit 10

echo "✅ Alerts published to Pub/Sub"
```

---

### **Step 4.7: Monitor Cloud Run Logs**

```bash
# Check logs in real-time
gcloud run logs read autosre-ai --limit 100 --region ${REGION}

# Or from Cloud Logging console
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=autosre-ai" \
  --limit 50 \
  --format json

# Check for errors
gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" \
  --limit 20
```

---

## **Part 5: Load Testing (Optional, 20 minutes)**

```bash
# Install load testing tool
pip install locust

# Create locustfile.py
cat > locustfile.py <<'EOF'
from locust import HttpUser, task, between
import json

class AutoSREUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def analyze_error(self):
        self.client.post("/analyze", json={
            "log": "ERROR: Database connection timeout after 30s"
        })
    
    @task(1)
    def check_health(self):
        self.client.get("/health")
    
    @task(2)
    def get_kb_stats(self):
        self.client.get("/api/kb/stats")
EOF

# Run load test (adjust HOST to your Cloud Run URL)
locust -f locustfile.py --host ${CLOUD_RUN_URL} --users 50 --spawn-rate 10 --run-time 5m

echo "✅ Load test complete"
```

---

## **Part 6: Monitoring & Cleanup**

### **Monitor Cloud Run Metrics**

```bash
# CPU usage
gcloud run services describe autosre-ai --region ${REGION}

# Via Cloud Console
# https://console.cloud.google.com/run/detail/${REGION}/autosre-ai
```

---

### **Cleanup (Delete Resources)**

```bash
# Delete Cloud Run service
gcloud run services delete autosre-ai --region ${REGION}

# Delete Cloud Function
gcloud functions delete auto-fix

# Delete Firestore database
gcloud firestore databases delete \
  --database=default

# Delete Pub/Sub topic
gcloud pubsub topics delete alerts

# Delete Cloud Storage bucket
gsutil -m rm -r gs://${BUCKET_NAME}

# Delete Secret Manager secrets
gcloud secrets delete github-token
gcloud secrets delete github-webhook-secret

echo "✅ All resources cleaned up"
```

---

## **Troubleshooting**

### **Issue: Cloud Run fails to start**

```bash
# Check logs
gcloud run logs read autosre-ai --limit 50

# Common causes:
# 1. Missing environment variables → Add to deployment
# 2. Service account lacks permissions → Grant IAM roles
# 3. Dockerfile error → Test locally first
```

### **Issue: Firestore permission denied**

```bash
# Grant Firestore permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/datastore.user"
```

### **Issue: KB not persisting**

```bash
# Check if bucket was created
gsutil ls gs://${BUCKET_NAME}/

# If empty, manually upload initial KB
gsutil cp app/rag/knowledge_base.json gs://${BUCKET_NAME}/
```

### **Issue: GitHub webhook fails**

```bash
# Check webhook delivery attempts on GitHub
# https://github.com/YOUR_ORG/YOUR_REPO/settings/hooks

# Verify webhook secret matches
gcloud secrets versions access latest --secret=github-webhook-secret

# Test manually (see Step 4.5)
```

---

## **Summary**

| Step | Time | Task |
|------|------|------|
| 1 | 30 min | GCP Setup (APIs, Service Account, Firestore, Pub/Sub, Storage) |
| 2 | 15 min | Code Updates (Persistence, Secrets Management) |
| 3 | 30 min | Deployment (Docker Build, Cloud Run, Cloud Function, Webhook) |
| 4 | 40 min | End-to-End Testing (Health, Analysis, KB, API, Webhooks) |
| 5 | 20 min | Load Testing (Optional) |
| **Total** | **2 hours 15 min** | **Complete deployment + testing** |

---

## **What's Working After Deployment**

✅ **Core Flow:**
- Error arrives → Analyzed by Vertex AI → Searched in KB → Decision made → Incident stored

✅ **Persistence:**
- KB survives Cloud Run restarts (stored in GCS)
- FAISS index survives restarts (stored in GCS)
- Incidents stored in Firestore permanently

✅ **Learning:**
- GitHub PRs with "auto-detected-fix" label auto-update KB
- Solutions become more confident over time
- Feedback loop active

✅ **Alerts:**
- Pub/Sub publishes alerts for team notification
- Cloud Function can execute fixes

---

## **Next Steps**

1. **Monitor production** - Watch logs and metrics
2. **Optimize costs** - Adjust Cloud Run scaling
3. **Add monitoring** - Set up alerts for errors
4. **Improve fixes** - Create more GitHub workflows
