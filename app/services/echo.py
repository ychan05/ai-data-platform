from datetime import datetime, timezone

from app.core.errors import ValidationError


def echo_message(message: str) -> dict[str, str]:
    if not message.strip():
        raise ValidationError("message cannot be empty")

    return {
        "echo": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }