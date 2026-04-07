from google.cloud import pubsub_v1
import json

publisher = pubsub_v1.PublisherClient()
topic_path = "projects/auto-sre-ai-multi-agent/topics/alerts"

def publish_alert(parsed, decision):

    message = json.dumps({
        "type": parsed["type"],
        "action": decision["action"]
    }).encode("utf-8")

    publisher.publish(topic_path, message)