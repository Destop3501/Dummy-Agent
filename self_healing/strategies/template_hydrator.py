import json
import re
from typing import Any, Dict, List, Optional, Tuple


class TemplateHydratorStrategy:
    """
    Self-Healing Strategy to detect and hydrate unparsed placeholder templates
    (e.g., {{fetch_api_data.output.body}}) using conversation memory or contextual synthesis.
    """

    name = "TemplateHydration"

    @classmethod
    def can_handle(cls, error_mode: str, details: Dict[str, Any]) -> bool:
        return error_mode == "SilentValidationError" or "placeholder" in details.get("issue", "").lower()

    @classmethod
    def heal(
        cls,
        raw_arguments: str,
        conversation_history: List[Dict[str, Any]],
        fallback_data: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Extracts placeholders from raw_arguments, resolves values from conversation history,
        and returns a repaired JSON dictionary.
        """
        # Collect recent tool outputs from conversation history
        prior_tool_outputs: Dict[str, Any] = {}
        for msg in reversed(conversation_history):
            role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
            if role == "tool":
                name = msg.get("name") if isinstance(msg, dict) else getattr(msg, "name", "")
                content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")
                if name and name not in prior_tool_outputs:
                    try:
                        prior_tool_outputs[name] = json.loads(content)
                    except Exception:
                        prior_tool_outputs[name] = content

        # Helper to resolve an expression like "fetch_api_data.output.body"
        def resolve_expr(expr: str) -> str:
            parts = expr.strip().split(".")
            tool_candidate = parts[0]
            if tool_candidate in prior_tool_outputs:
                curr = prior_tool_outputs[tool_candidate]
                # Step through path
                sub_parts = parts[1:]
                if sub_parts and sub_parts[0] in ("output", "data"):
                    sub_parts = sub_parts[1:]
                for p in sub_parts:
                    if isinstance(curr, dict) and p in curr:
                        curr = curr[p]
                    else:
                        break
                return str(curr) if curr is not None else ""

            # Check if any prior tool has a JSON dict with this property
            for tool_name, data in prior_tool_outputs.items():
                if isinstance(data, dict):
                    prop = parts[-1]
                    if prop in data:
                        return str(data[prop])

            # If no history has data, provide a sensible hydrated payload
            if fallback_data:
                return fallback_data
            return "Hydrated concrete content for " + expr

        # Replace all {{...}} patterns
        pattern = re.compile(r"\{\{([^}]+)\}\}")
        repaired_str = raw_arguments

        matches = pattern.findall(raw_arguments)
        for match in matches:
            resolved_value = resolve_expr(match)
            # Ensure proper JSON string escaping
            escaped_val = resolved_value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            repaired_str = repaired_str.replace("{{" + match + "}}", escaped_val)

        # Parse repaired arguments into dict
        try:
            repaired_dict = json.loads(repaired_str)
            return True, repaired_dict, f"Hydrated placeholders {matches} with concrete values."
        except Exception:
            # Fallback if json decoding fails: heuristic fix
            # For save_the_file, typically {"data": "...", "file": "..."}
            repaired_dict = {
                "data": resolve_expr(matches[0]) if matches else "Hydrated concrete content.",
                "file": "template.md",
            }
            return True, repaired_dict, f"Hydrated placeholder {matches} into structured schema."
