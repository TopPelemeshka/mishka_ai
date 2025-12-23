import pytest
from src.core.services.personality import PersonalityManager
from src.database.models.user import User

def test_get_system_prompt_basic():
    """Базовый промпт без фактов."""
    user = User(id=1, username="mishka", full_name="Mishka Bear")
    manager = PersonalityManager()
    
    prompt = manager.get_system_prompt(user)
    
    assert "Mishka AI" in prompt
    assert "Mishka Bear" in prompt
    assert "<LONG_TERM_MEMORY>" not in prompt

def test_get_system_prompt_with_facts():
    """Промпт с инъекцией фактов."""
    user = User(id=1, username="test", full_name="Tester")
    facts = "- Любит мед"
    manager = PersonalityManager()
    
    prompt = manager.get_system_prompt(user, facts=facts)
    
    assert "<LONG_TERM_MEMORY>" in prompt
    assert "- Любит мед" in prompt
