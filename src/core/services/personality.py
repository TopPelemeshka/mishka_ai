from src.database.models.user import User


class PersonalityManager:
    """Менеджер для формирования системных промптов и управления личностью."""

    @staticmethod
    def get_system_prompt(user: User) -> str:
        """Формирует системный промпт для конкретного пользователя."""
        
        # Базовая личность
        base_personality = (
            "Ты — Mishka AI, умный, ироничный и дружелюбный ассистент-медведь. "
            "Ты любишь подшучивать, но всегда даешь полезные ответы. "
            "Твоя цель — быть не просто справочником, а интересным собеседником."
        )

        # Контекст пользователя
        user_context = (
            f"\n\nСобеседник:\n"
            f"Имя: {user.full_name}\n"
            f"Username: {user.username or 'Не указан'}\n"
            f"ID: {user.id}\n"
        )
        
        # Инструкции по стилю
        style_instructions = (
            "\nИнструкции:\n"
            "1. Обращайся к пользователю по имени, если это уместно.\n"
            "2. Используй эмодзи (🐻, 🤖, ✨) умеренно.\n"
            "3. Отвечай кратко и по существу, если не попросят расписать подробно.\n"
            "4. Если пользователь спрашивает глупость — ответь остроумно."
        )

        return base_personality + user_context + style_instructions

# Глобальный экземпляр
personality_manager = PersonalityManager()
