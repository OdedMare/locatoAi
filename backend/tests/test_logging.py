from app.common.logging import ConsoleFirstLogger


class RecordingLogger:
    def __init__(self, name, calls, context=None):
        self.name = name
        self.calls = calls
        self.context = context or {}

    def bind(self, **context):
        return RecordingLogger(
            self.name, self.calls, {**self.context, **context}
        )

    def info(self, event, **context):
        self.calls.append((self.name, event, {**self.context, **context}))


def test_console_first_logger_preserves_order_and_bound_context():
    calls = []
    logger = ConsoleFirstLogger(
        RecordingLogger("console", calls), RecordingLogger("jsonl", calls)
    ).bind(request_id="request-1")

    logger.info("query_pipeline", stage="layer_selection")

    assert [call[0] for call in calls] == ["console", "jsonl"]
    assert all(call[2]["request_id"] == "request-1" for call in calls)
