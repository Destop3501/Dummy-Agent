import difflib
from typing import Any, Dict, List, Tuple


class EntityResolverStrategy:
    """
    Self-Healing Strategy to recover from domain entity lookup errors (e.g., Unknown city)
    using fuzzy matching and graceful structured domain knowledge fallback.
    """

    name = "EntityFuzzyResolution"

    KNOWN_CITIES = {
        "san francisco": "75°F (Mild & Clear)",
        "paris": "78°F (Sunny)",
        "tokyo": "80°F (Humid)",
    }

    @classmethod
    def can_handle(cls, error_mode: str, details: Dict[str, Any]) -> bool:
        return error_mode == "UnknownEntityError" or "unknown city" in str(details).lower()

    @classmethod
    def heal(cls, unknown_entity: str) -> Tuple[bool, str, str]:
        """
        Fuzzy matches entity or synthesizes a structured fallback explanation.
        """
        entity_norm = unknown_entity.strip().lower()

        # 1. Check fuzzy match against known entities
        matches = difflib.get_close_matches(entity_norm, cls.KNOWN_CITIES.keys(), n=1, cutoff=0.6)
        if matches:
            best_match = matches[0]
            val = cls.KNOWN_CITIES[best_match]
            return (
                True,
                f"Resolved '{unknown_entity}' -> '{best_match.title()}': {val}",
                f"Fuzzy match resolved '{unknown_entity}' to '{best_match}'.",
            )

        # 2. Informative domain fallback
        available_cities = ", ".join(f"{c.title()} ({t})" for c, t in cls.KNOWN_CITIES.items())
        recovery_message = (
            f"Location Notice: '{unknown_entity}' is an unmonitored or fictional location with no active weather station. "
            f"Currently supported operational stations are: {available_cities}."
        )
        return (
            True,
            recovery_message,
            f"Provided domain-aware entity resolution for unmonitored location '{unknown_entity}'.",
        )
