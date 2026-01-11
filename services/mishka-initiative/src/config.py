from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    INITIATIVE_THRESHOLD: int = 70
    BOT_USERNAME: str = "mishka_bot"
    LLM_PROVIDER_URL: str = "http://mishka-llm-provider:8000/v1/chat/completions"
    LLM_MODEL: str = "gemini-1.5-flash"
    MEMORY_API_URL: str = "http://mishka-memory:8000"
    
    # Queue names
    QUEUE_CHAT_EVENTS: str = "chat_events"
    QUEUE_BRAIN_TASKS: str = "brain_tasks"

settings = Settings()
