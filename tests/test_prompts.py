"""
Tests for prompt templates.

Tests the prompt generation and formatting.
"""
import pytest


class TestIntentClassifierPrompt:
    """Test intent classifier prompt."""

    def test_prompt_creation(self):
        """Test that intent classifier prompt is created correctly."""
        from src.agent.prompts import get_intent_classifier_prompt

        prompt = get_intent_classifier_prompt()

        assert prompt is not None

    def test_prompt_has_multilingual_support(self):
        """Test that prompt mentions multilingual support."""
        from src.agent.prompts import INTENT_CLASSIFIER_PROMPT

        # Check the system message contains multilingual instruction
        messages = INTENT_CLASSIFIER_PROMPT.messages
        system_message = str(messages[0])

        assert "ANY language" in system_message or "any language" in system_message.lower()

    def test_prompt_has_model_placeholder(self):
        """Test that prompt has placeholder for available models."""
        from src.agent.prompts import INTENT_CLASSIFIER_PROMPT

        messages = INTENT_CLASSIFIER_PROMPT.messages
        system_message = str(messages[0])

        assert "available_models" in system_message

    def test_prompt_has_all_intents(self):
        """Test that prompt includes all intent categories."""
        from src.agent.prompts import INTENT_CLASSIFIER_PROMPT

        messages = INTENT_CLASSIFIER_PROMPT.messages
        system_message = str(messages[0])

        required_intents = ["QUERY", "CREATE", "UPDATE", "DELETE", "ACTION", "ATTACH", "MESSAGE", "METADATA"]

        for intent in required_intents:
            assert intent in system_message, f"Intent {intent} should be in prompt"


class TestGeneralAssistantPrompt:
    """Test general assistant prompt."""

    def test_prompt_creation(self):
        """Test that general assistant prompt is created correctly."""
        from src.agent.prompts import get_general_assistant_prompt

        prompt = get_general_assistant_prompt()

        assert prompt is not None

    def test_prompt_has_language_rule(self):
        """Test that prompt has language matching rule."""
        from src.agent.prompts import GENERAL_ASSISTANT_PROMPT

        messages = GENERAL_ASSISTANT_PROMPT.messages
        system_message = str(messages[0])

        assert "SAME LANGUAGE" in system_message or "same language" in system_message.lower()

    def test_prompt_has_history_placeholder(self):
        """Test that prompt has history placeholder."""
        from src.agent.prompts import GENERAL_ASSISTANT_PROMPT

        messages = GENERAL_ASSISTANT_PROMPT.messages
        # Should have a MessagesPlaceholder for history
        assert len(messages) >= 2


class TestQueryGeneratorPrompt:
    """Test query generator prompt."""

    def test_prompt_creation(self):
        """Test that query generator prompt is created correctly."""
        from src.agent.prompts import get_query_generator_prompt

        prompt = get_query_generator_prompt()

        assert prompt is not None

    def test_prompt_mentions_domain_syntax(self):
        """Test that prompt explains Odoo domain syntax."""
        from src.agent.prompts import QUERY_GENERATOR_PROMPT

        messages = QUERY_GENERATOR_PROMPT.messages
        system_message = str(messages[0])

        assert "domain" in system_message.lower()


class TestActionConfirmationPrompt:
    """Test action confirmation prompt."""

    def test_prompt_creation(self):
        """Test that action confirmation prompt is created correctly."""
        from src.agent.prompts import get_action_confirmation_prompt

        prompt = get_action_confirmation_prompt()

        assert prompt is not None


class TestProcurementPrompt:
    """Test procurement domain prompt."""

    def test_prompt_creation(self):
        """Test that procurement prompt is created correctly."""
        from src.agent.prompts import get_procurement_system_prompt

        prompt = get_procurement_system_prompt()

        assert prompt is not None
        assert isinstance(prompt, str)

    def test_prompt_mentions_real_data(self):
        """Test that procurement prompt emphasizes real data."""
        from src.agent.prompts import get_procurement_system_prompt

        prompt = get_procurement_system_prompt()

        assert "REAL data" in prompt or "real data" in prompt.lower()
