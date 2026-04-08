from google.cloud import pubsub_v1
import json

publisher = pubsub_v1.PublisherClient()
import os
project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "auto-sre-ai-multi-agent-492710")
topic_path = f"projects/{project_id}/topics/alerts"

def publish_alert(parsed, decision):

    message = json.dumps({
        "type": parsed["type"],
        "action": decision["action"]
    }).encode("utf-8")

    publisher.publish(topic_path, message)