import pytest
from src.utils.field_selector import SmartFieldSelector


class TestSmartFieldSelector:
    def test_essential_fields_always_included(self):
        """Test that essential fields are always included in results."""
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "display_name": {"type": "char"},
            "random_field": {"type": "char"},
        }
        result = SmartFieldSelector.select(fields_info, limit=3)
        assert "id" in result
        assert "name" in result

    def test_limits_fields(self):
        """Test that field count is limited to specified limit."""
        fields_info = {f"field_{i}": {"type": "char"} for i in range(50)}
        fields_info["id"] = {"type": "integer"}
        fields_info["name"] = {"type": "char"}

        result = SmartFieldSelector.select(fields_info, limit=10)
        assert len(result) <= 10

    def test_excludes_binary_fields(self):
        """Test that binary fields are excluded from results."""
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "image": {"type": "binary"},
            "attachment": {"type": "binary"},
        }
        result = SmartFieldSelector.select(fields_info)
        assert "image" not in result
        assert "attachment" not in result

    def test_excludes_html_fields(self):
        """Test that HTML fields are excluded from results."""
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "description_html": {"type": "html"},
            "notes_html": {"type": "html"},
        }
        result = SmartFieldSelector.select(fields_info)
        assert "description_html" not in result
        assert "notes_html" not in result

    def test_prioritizes_business_fields(self):
        """Test that business-important fields are prioritized."""
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "state": {"type": "selection"},
            "email": {"type": "char"},
            "random_xyz": {"type": "char"},
        }
        result = SmartFieldSelector.select(fields_info, limit=4)
        assert "state" in result
        assert "email" in result

    def test_exclude_fields_parameter(self):
        """Test that specified fields are excluded from results."""
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "display_name": {"type": "char"},
            "email": {"type": "char"},
            "phone": {"type": "char"},
        }
        exclude = {"email", "phone"}
        result = SmartFieldSelector.select(fields_info, exclude_fields=exclude)
        assert "email" not in result
        assert "phone" not in result

    def test_exclude_essential_fields(self):
        """Test that even essential fields can be excluded if specified."""
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "display_name": {"type": "char"},
            "active": {"type": "boolean"},
        }
        exclude = {"name", "display_name"}
        result = SmartFieldSelector.select(fields_info, exclude_fields=exclude)
        assert "name" not in result
        assert "display_name" not in result
        assert "id" in result  # Not excluded
        assert "active" in result  # Not excluded

    def test_skips_non_stored_computed_fields(self):
        """Test that computed fields without store are skipped."""
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "computed_field": {"type": "char", "store": False},
            "stored_computed": {"type": "char", "store": True},
        }
        result = SmartFieldSelector.select(fields_info)
        assert "computed_field" not in result
        assert "stored_computed" in result

    def test_required_fields_prioritized(self):
        """Test that required fields get higher scores."""
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "required_field": {"type": "char", "required": True},
            "optional_field": {"type": "char", "required": False},
        }
        result = SmartFieldSelector.select(fields_info, limit=4)
        assert "required_field" in result
        # Required field should appear before optional (higher score)
        assert result.index("required_field") < result.index("optional_field")

    def test_type_score_priority(self):
        """Test that different field types get appropriate scores."""
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "monetary_field": {"type": "monetary"},
            "many2many_field": {"type": "many2many"},
        }
        result = SmartFieldSelector.select(fields_info, limit=4)
        # Monetary should be prioritized over many2many
        assert "monetary_field" in result
        # Both should be included within limit
        assert "many2many_field" in result

    def test_business_pattern_matching(self):
        """Test that business patterns are correctly matched."""
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "partner_id": {"type": "many2one"},
            "company_id": {"type": "many2one"},
            "user_id": {"type": "many2one"},
            "random_id": {"type": "many2one"},
        }
        result = SmartFieldSelector.select(fields_info, limit=6)
        # Business pattern fields should be included
        assert "partner_id" in result
        assert "company_id" in result
        assert "user_id" in result

    def test_searchable_field_bonus(self):
        """Test that searchable fields get bonus points."""
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "searchable_field": {"type": "char", "searchable": True},
            "non_searchable": {"type": "char", "searchable": False},
        }
        result = SmartFieldSelector.select(fields_info, limit=4)
        assert "searchable_field" in result

    def test_calculate_score_essential_field(self):
        """Test score calculation for essential fields."""
        score = SmartFieldSelector._calculate_score(
            "name", {"type": "char", "required": False}
        )
        # Essential field bonus (1000) + char type (100) + stored (50) = 1150
        assert score >= 1000

    def test_calculate_score_required_field(self):
        """Test score calculation for required fields."""
        score = SmartFieldSelector._calculate_score(
            "custom_field", {"type": "char", "required": True}
        )
        # Required bonus (500) + char type (100) + stored (50) = 650
        assert score >= 500

    def test_calculate_score_business_pattern(self):
        """Test score calculation for fields matching business patterns."""
        score = SmartFieldSelector._calculate_score(
            "state", {"type": "selection", "required": False}
        )
        # state pattern (300) + selection type (100) + stored (50) = 450
        assert score >= 300

    def test_calculate_score_unknown_type(self):
        """Test score calculation for unknown field types."""
        score = SmartFieldSelector._calculate_score(
            "custom_field", {"type": "unknown_type"}
        )
        # Unknown type gets default (50) + stored (50) = 100
        assert score >= 50

    def test_calculate_score_multiple_bonuses(self):
        """Test score calculation with multiple bonuses."""
        score = SmartFieldSelector._calculate_score(
            "state",
            {
                "type": "selection",
                "required": True,
                "searchable": True,
                "store": True,
            },
        )
        # state pattern (300) + required (500) + selection (100) + stored (50) + searchable (30) = 980
        assert score >= 900

    def test_empty_fields_info(self):
        """Test handling of empty fields_info dictionary."""
        fields_info = {}
        result = SmartFieldSelector.select(fields_info)
        assert result == []

    def test_all_fields_excluded(self):
        """Test when all fields are excluded."""
        fields_info = {
            "image": {"type": "binary"},
            "html_content": {"type": "html"},
            "computed": {"type": "char", "store": False},
        }
        result = SmartFieldSelector.select(fields_info)
        assert result == []

    def test_default_limit(self):
        """Test that default limit is 15."""
        fields_info = {f"field_{i}": {"type": "char"} for i in range(30)}
        fields_info["id"] = {"type": "integer"}
        fields_info["name"] = {"type": "char"}

        result = SmartFieldSelector.select(fields_info)
        assert len(result) <= 15

    def test_stored_field_default_true(self):
        """Test that fields without 'store' key are treated as stored."""
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "field_without_store": {"type": "char"},  # No 'store' key
        }
        result = SmartFieldSelector.select(fields_info)
        assert "field_without_store" in result

    def test_field_ordering_by_score(self):
        """Test that fields are ordered by score (essential first, then by score)."""
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "display_name": {"type": "char"},
            "state": {"type": "selection"},  # High business pattern score
            "random_field": {"type": "char"},  # Low score
            "email": {"type": "char"},  # Medium-high business pattern score
        }
        result = SmartFieldSelector.select(fields_info, limit=6)

        # Essential fields should come first
        essential_in_result = [f for f in result if f in SmartFieldSelector.ESSENTIAL_FIELDS]
        assert len(essential_in_result) > 0

        # state and email should be included due to business patterns
        assert "state" in result
        assert "email" in result

    def test_case_insensitive_pattern_matching(self):
        """Test that pattern matching is case-insensitive."""
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "STATE": {"type": "selection"},
            "Email": {"type": "char"},
            "PARTNER_ID": {"type": "many2one"},
        }
        result = SmartFieldSelector.select(fields_info, limit=6)
        assert "STATE" in result
        assert "Email" in result
        assert "PARTNER_ID" in result

    def test_active_field_included(self):
        """Test that 'active' essential field is included."""
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "active": {"type": "boolean"},
        }
        result = SmartFieldSelector.select(fields_info)
        assert "active" in result

    def test_date_fields_prioritized(self):
        """Test that date-related fields are prioritized."""
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "create_date": {"type": "datetime"},
            "write_date": {"type": "datetime"},
            "random_date": {"type": "date"},
        }
        result = SmartFieldSelector.select(fields_info, limit=6)
        assert "create_date" in result
        assert "write_date" in result

    def test_many2many_and_one2many_lower_priority(self):
        """Test that many2many and one2many fields have lower priority."""
        fields_info = {
            "id": {"type": "integer"},
            "name": {"type": "char"},
            "partner_id": {"type": "many2one"},
            "tag_ids": {"type": "many2many"},
            "line_ids": {"type": "one2many"},
            "description": {"type": "text"},
        }
        result = SmartFieldSelector.select(fields_info, limit=5)
        # many2one should be prioritized over many2many and one2many
        assert "partner_id" in result
        # description (text) should be included before many2many/one2many
        assert "description" in result
