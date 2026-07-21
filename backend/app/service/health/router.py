"""Health endpoint."""


class HealthRouter:
    @staticmethod
    def status() -> dict:
        return {"status": "ok"}
