def handler(event, context):
    print(f"received event: {event}")
    return {"message": "hello from stack worker", "event": event}
