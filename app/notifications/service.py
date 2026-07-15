import json


class NotificationService:
    def __init__(self, settings): self.path = settings.notification_log_path
    def send(self, event: str, payload: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle: handle.write(json.dumps({"event": event, **payload}, default=str) + "\n")

