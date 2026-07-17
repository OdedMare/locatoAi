"""Bounded retry for transient OpenAI-compatible failures."""

import time

from openai import APIConnectionError, APITimeoutError, RateLimitError


class CompletionRetry:
    _ERRORS = (RateLimitError, APIConnectionError, APITimeoutError)
    _ATTEMPTS = 2
    _DELAY_SECONDS = 0.3

    @classmethod
    def create(cls, client, model: str, kwargs: dict):
        last_error = None
        for attempt in range(cls._ATTEMPTS):
            try:
                return client.chat.completions.create(
                    model=model, temperature=0, **kwargs
                )
            except cls._ERRORS as exc:
                last_error = exc
                if attempt + 1 < cls._ATTEMPTS:
                    time.sleep(cls._DELAY_SECONDS)
        raise last_error
