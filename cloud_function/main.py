def auto_fix(request):

    data = request.get_json()

    error_type = data.get("type")

    if error_type == "DB_ERROR":
        return {"status": "DB Restart Triggered"}

    return {"status": "No action taken"}