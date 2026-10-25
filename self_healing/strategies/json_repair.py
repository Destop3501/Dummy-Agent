import json
import re
from typing import Any, Dict, Tuple


class JsonRepairStrategy:
    """
    Self-Healing Strategy to automatically repair malformed JSON arguments
    (e.g., unquoted keys, single quotes, trailing commas).
    """

    name = "JsonAutoRepair"

    @classmethod
    def can_handle(cls, error_mode: str, details: Dict[str, Any]) -> bool:
        return error_mode == "FormatError" or "json" in details.get("issue", "").lower()

    @classmethod
    def heal(cls, malformed_str: str) -> Tuple[bool, Dict[str, Any], str]:
        """
        Repairs common JSON syntax errors.
        """
        cleaned = malformed_str.strip()

        # Try parsing directly
        try:
            return True, json.loads(cleaned), "Parsed without modification."
        except Exception:
            pass

        # 1. Replace single quotes with double quotes
        candidate = re.sub(r"'([^']*)'", r'"\1"', cleaned)

        # 2. Add quotes to unquoted keys e.g. {city: "Paris"} -> {"city": "Paris"}
        candidate = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', candidate)

        # 3. Remove trailing commas e.g. {"a": 1,} -> {"a": 1}
        candidate = re.sub(r',\s*([}\]])', r'\1', candidate)

        try:
            parsed = json.loads(candidate)
            return True, parsed, "Repaired malformed JSON syntax automatically."
        except Exception as e:
            return False, {}, f"Unable to automatically repair JSON: {e}"
