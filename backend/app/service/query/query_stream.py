"""Server-sent events for one blocking query execution."""

import json
from queue import Empty, Queue
from threading import Thread
from typing import Any, Callable, Dict

from fastapi.responses import StreamingResponse

_DONE = object()


class QueryStream:
    def __init__(self, work: Callable[[], Any], on_error: Callable[[Exception], dict]):
        self._work = work
        self._on_error = on_error
        self._queue = Queue()

    def emit(self, event: Dict[str, Any]) -> None:
        self._queue.put(self._frame("trace", event))

    def response(self, request_id: str) -> StreamingResponse:
        Thread(target=self._run, daemon=True).start()
        return StreamingResponse(
            self._events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "X-Request-ID": request_id,
            },
        )

    def _run(self) -> None:
        try:
            result = self._work().model_dump(mode="json")
            self._queue.put(self._frame("result", result))
        except Exception as exc:
            self._queue.put(self._frame("error", self._on_error(exc)))
        finally:
            self._queue.put(_DONE)

    def _events(self):
        while True:
            try:
                item = self._queue.get(timeout=15)
            except Empty:
                yield ": keep-alive\n\n"
                continue
            if item is _DONE:
                return
            yield item

    @staticmethod
    def _frame(event: str, data: Dict[str, Any]) -> str:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return "event: {}\ndata: {}\n\n".format(event, payload)
