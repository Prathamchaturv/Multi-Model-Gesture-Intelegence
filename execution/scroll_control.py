"""Scroll execution helpers layered on top of ActionExecutor."""

from execution.cursor_control import ActionExecutor


class ScrollControl:
    """Provides explicit scroll operations using the shared action executor."""

    def __init__(self, action_executor: ActionExecutor) -> None:
        self._action_executor = action_executor

    def scroll_up(self) -> None:
        self._action_executor.execute('scroll_up')

    def scroll_down(self) -> None:
        self._action_executor.execute('scroll_down')


__all__ = [
    'ScrollControl',
]
