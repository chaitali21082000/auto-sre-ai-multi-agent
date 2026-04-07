import requests

FUNCTION_URL = "https://REGION-PROJECT.cloudfunctions.net/auto-fix"

def trigger_fix(parsed):

    requests.post(FUNCTION_URL, json=parsed)