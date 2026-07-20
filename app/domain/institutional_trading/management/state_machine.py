"""Position lifecycle state machine — progressive states; EXITED terminal."""

from __future__ import annotations

from app.domain.institutional_trading.management.models import PositionLifecycleState

# Happy-path progression + emergency/time/shutdown exits from any active state.
_TRANSITIONS: dict[PositionLifecycleState, frozenset[PositionLifecycleState]] = {
    PositionLifecycleState.OPEN: frozenset(
        {
            PositionLifecycleState.BE_MOVED,
            PositionLifecycleState.EXITED,
        }
    ),
    PositionLifecycleState.BE_MOVED: frozenset(
        {
            PositionLifecycleState.PARTIAL,
            PositionLifecycleState.EXITED,
        }
    ),
    PositionLifecycleState.PARTIAL: frozenset(
        {
            PositionLifecycleState.TRAILING,
            PositionLifecycleState.EXITED,
        }
    ),
    PositionLifecycleState.TRAILING: frozenset(
        {
            PositionLifecycleState.TRAILING,  # trail updates stay in TRAILING
            PositionLifecycleState.EXITED,
        }
    ),
    PositionLifecycleState.EXITED: frozenset(),
}


class PositionStateMachine:
    """Enforce lifecycle rules. Never skip OPEN→BE→PARTIAL→TRAILING."""

    @staticmethod
    def can_transition(
        current: PositionLifecycleState, target: PositionLifecycleState
    ) -> bool:
        if current is PositionLifecycleState.EXITED:
            return False
        return target in _TRANSITIONS.get(current, frozenset())

    @staticmethod
    def assert_transition(
        current: PositionLifecycleState, target: PositionLifecycleState
    ) -> None:
        if not PositionStateMachine.can_transition(current, target):
            raise ValueError(
                f"Illegal state transition {current.value} → {target.value}"
            )

    @staticmethod
    def next_progressive(current: PositionLifecycleState) -> PositionLifecycleState | None:
        order = [
            PositionLifecycleState.OPEN,
            PositionLifecycleState.BE_MOVED,
            PositionLifecycleState.PARTIAL,
            PositionLifecycleState.TRAILING,
        ]
        try:
            i = order.index(current)
        except ValueError:
            return None
        if i + 1 < len(order):
            return order[i + 1]
        return None
