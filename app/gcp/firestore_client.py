from google.cloud import firestore

db = firestore.Client()

def store_incident(log, parsed, decision):

    doc = {
        "log": log,
        "type": parsed["type"],
        "severity": parsed["severity"],
        "decision": decision
    }

    db.collection("incidents").add(doc)