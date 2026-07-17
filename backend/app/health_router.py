"""Health-check route handler."""


class HealthRouter:
    @staticmethod
    def status() -> dict:
        return {"status": "ok"}
