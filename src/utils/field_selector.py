"""
Smart field selection for Odoo queries.
Inspired by mcp-server-odoo field importance scoring.
"""
from typing import Dict, List, Optional, Set


class SmartFieldSelector:
    """
    Selects the most relevant fields from Odoo model metadata
    based on importance scoring algorithm.
    """

    # Essential fields (always included)
    ESSENTIAL_FIELDS = {"id", "name", "display_name", "active"}

    # Field types to exclude (too large for responses)
    EXCLUDED_TYPES = {"binary", "html"}

    # Business-important field patterns
    BUSINESS_PATTERNS = {
        "state": 300,
        "status": 280,
        "email": 250,
        "phone": 240,
        "mobile": 230,
        "date": 220,
        "amount": 200,
        "total": 190,
        "price": 180,
        "quantity": 170,
        "qty": 160,
        "partner": 150,
        "company": 140,
        "user": 130,
        "create_date": 120,
        "write_date": 110,
    }

    # Field type scores
    TYPE_SCORES = {
        "char": 100,
        "text": 80,
        "integer": 90,
        "float": 85,
        "monetary": 95,
        "date": 90,
        "datetime": 85,
        "boolean": 70,
        "selection": 100,
        "many2one": 80,
        "many2many": 50,
        "one2many": 40,
    }

    @classmethod
    def select(
        cls,
        fields_info: Dict[str, Dict],
        limit: int = 15,
        exclude_fields: Optional[Set[str]] = None,
    ) -> List[str]:
        """
        Select the most important fields based on scoring.
        """
        exclude_fields = exclude_fields or set()
        scored_fields = []

        for field_name, field_meta in fields_info.items():
            # Skip excluded fields
            if field_name in exclude_fields:
                continue

            # Skip excluded types
            field_type = field_meta.get("type", "")
            if field_type in cls.EXCLUDED_TYPES:
                continue

            # Skip computed fields without store
            if field_meta.get("store") is False:
                continue

            # Calculate score
            score = cls._calculate_score(field_name, field_meta)
            scored_fields.append((field_name, score))

        # Sort by score descending
        scored_fields.sort(key=lambda x: x[1], reverse=True)

        # Always include essential fields first
        result = []
        for f in cls.ESSENTIAL_FIELDS:
            if f in fields_info and f not in exclude_fields:
                result.append(f)

        # Add top scored fields up to limit
        for field_name, score in scored_fields:
            if field_name not in result:
                result.append(field_name)
                if len(result) >= limit:
                    break

        return result

    @classmethod
    def _calculate_score(cls, field_name: str, field_meta: Dict) -> int:
        """Calculate importance score for a field."""
        score = 0

        # Essential field bonus
        if field_name in cls.ESSENTIAL_FIELDS:
            score += 1000

        # Required field bonus
        if field_meta.get("required"):
            score += 500

        # Type score
        field_type = field_meta.get("type", "")
        score += cls.TYPE_SCORES.get(field_type, 50)

        # Business pattern bonus
        field_lower = field_name.lower()
        for pattern, pattern_score in cls.BUSINESS_PATTERNS.items():
            if pattern in field_lower:
                score += pattern_score
                break

        # Stored field bonus
        if field_meta.get("store", True):
            score += 50

        # Searchable bonus
        if field_meta.get("searchable", False):
            score += 30

        return score
