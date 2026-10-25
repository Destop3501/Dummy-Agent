from typing import Any, Dict, List, Tuple


class LoopBreakerStrategy:
    """
    Self-Healing Strategy to detect and break infinite loops, polling deadlocks,
    and condition stagnation before the agent crashes or exhausts turn limits.
    """

    name = "LoopBreakerAndPivot"

    @classmethod
    def can_handle(cls, error_mode: str, details: Dict[str, Any]) -> bool:
        return error_mode in ("InfiniteLoopRisk", "InfiniteLoopError") or "loop" in details.get("issue", "").lower()

    @classmethod
    def generate_intervention(
        cls,
        stagnant_tool: str,
        parsed_args: Dict[str, Any],
        repeated_output: str,
        turn_count: int,
    ) -> Tuple[bool, Dict[str, str], str]:
        """
        Synthesizes an advisory intervention message that guides the LLM to exit the loop
        gracefully and report its findings without crashing.
        """
        guidance = (
            f"[SYSTEM INTERVENTION - SELF-HEALING LOOP BREAKER]\n"
            f"Cyclic repetition detected at turn {turn_count}: Tool '{stagnant_tool}' with args {parsed_args} "
            f"has returned identical output '{repeated_output}' multiple times without state change.\n"
            f"The target condition cannot be reached through repeated polling. "
            f"DO NOT call '{stagnant_tool}' again. "
            f"Immediately conclude the workflow by providing a comprehensive explanation to the user stating "
            f"the constant observed value ({repeated_output}) and explaining why the requested threshold cannot be met."
        )

        message = {
            "role": "system",
            "content": guidance,
        }

        note = f"Injected loop-breaker intervention at turn {turn_count} for stagnant tool '{stagnant_tool}'."
        return True, message, note
