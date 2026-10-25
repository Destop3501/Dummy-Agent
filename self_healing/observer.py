import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ObservationEvent:
    is_anomaly: bool
    error_mode: Optional[str] = None
    tool_name: Optional[str] = None
    raw_input: Optional[str] = None
    parsed_input: Optional[Dict[str, Any]] = None
    output_content: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class HealthObserver:
    """
    Monitors agent execution turns, tool arguments, outputs, and loop cycles to detect anomalies.
    """

    def __init__(self, repeat_threshold: int = 2):
        self.repeat_threshold = repeat_threshold
        self.call_history: List[Dict[str, Any]] = []

    def observe_arguments(self, tool_name: str, raw_arguments: str) -> ObservationEvent:
        """
        Inspects raw arguments for JSON malformation and unparsed template syntax.
        """
        # 1. Check for template hallucination like {{variable}}
        if "{{" in raw_arguments or "}}" in raw_arguments:
            placeholders = re.findall(r"\{\{([^}]+)\}\}", raw_arguments)
            return ObservationEvent(
                is_anomaly=True,
                error_mode="SilentValidationError",
                tool_name=tool_name,
                raw_input=raw_arguments,
                details={
                    "issue": "Unparsed template placeholder detected in tool arguments",
                    "placeholders": placeholders,
                    "raw_arguments": raw_arguments,
                },
            )

        # 2. Check for JSON validity
        try:
            parsed = json.loads(raw_arguments)
            return ObservationEvent(
                is_anomaly=False,
                tool_name=tool_name,
                raw_input=raw_arguments,
                parsed_input=parsed,
            )
        except json.JSONDecodeError as e:
            return ObservationEvent(
                is_anomaly=True,
                error_mode="FormatError",
                tool_name=tool_name,
                raw_input=raw_arguments,
                details={
                    "issue": "Malformed JSON arguments",
                    "json_error": str(e),
                    "raw_arguments": raw_arguments,
                },
            )

    def observe_tool_execution(
        self, tool_name: str, parsed_args: Dict[str, Any], output: str, exception: Optional[Exception] = None
    ) -> ObservationEvent:
        """
        Observes the outcome of a tool execution for HTTP errors, domain entity errors, or exceptions.
        """
        record = {
            "tool_name": tool_name,
            "args": parsed_args,
            "output": output,
            "has_error": False,
        }

        # Check for exception
        if exception is not None:
            record["has_error"] = True
            self.call_history.append(record)
            return ObservationEvent(
                is_anomaly=True,
                error_mode="ToolExecutionError",
                tool_name=tool_name,
                parsed_input=parsed_args,
                output_content=str(exception),
                details={"exception": str(exception)},
            )

        # Check for error in output string
        if isinstance(output, str) and output.startswith("Error:"):
            record["has_error"] = True
            self.call_history.append(record)

            # Specific classification
            if "404" in output or "Not Found" in output:
                specific_mode = "ToolExecutionError_404"
            elif "Unknown city" in output or "Unknown entity" in output:
                specific_mode = "UnknownEntityError"
            else:
                specific_mode = "ToolExecutionError"

            return ObservationEvent(
                is_anomaly=True,
                error_mode=specific_mode,
                tool_name=tool_name,
                parsed_input=parsed_args,
                output_content=output,
                details={"error_output": output},
            )

        self.call_history.append(record)
        return ObservationEvent(
            is_anomaly=False,
            tool_name=tool_name,
            parsed_input=parsed_args,
            output_content=output,
        )

    def observe_loop_stagnation(self, current_step: int, tool_name: str, parsed_args: Dict[str, Any], output: str) -> Optional[ObservationEvent]:
        """
        Detects repetitive polling cycles where the same tool is repeatedly called with identical parameters
        producing the same output, indicating an infinite loop or condition deadlock.
        """
        if len(self.call_history) < self.repeat_threshold:
            return None

        recent_calls = self.call_history[-self.repeat_threshold :]
        matches = 0
        for call in recent_calls:
            if (
                call.get("tool_name") == tool_name
                and call.get("args") == parsed_args
                and call.get("output") == output
            ):
                matches += 1

        if matches >= self.repeat_threshold:
            return ObservationEvent(
                is_anomaly=True,
                error_mode="InfiniteLoopRisk",
                tool_name=tool_name,
                parsed_input=parsed_args,
                output_content=output,
                details={
                    "step_count": current_step,
                    "repeat_count": matches,
                    "stagnant_tool": tool_name,
                    "repeated_output": output,
                    "issue": f"Tool '{tool_name}' called repeatedly ({matches} times) with invariant output '{output}'. Stagnation loop detected.",
                },
            )
        return None
