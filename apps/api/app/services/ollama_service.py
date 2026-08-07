import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import ServiceUnavailableError
from app.schemas.support import SupportAssistantResult, SupportMessage

SYSTEM_PROMPT = """You are Relay Support, the helpful assistant inside the Relay Messenger app.
Help users understand and use Relay, including registration, sign-in, direct conversations,
real-time messages, unread messages, notifications, and connection problems. You may also
answer general information questions. Be concise, friendly, and practical. Never claim that
you changed an account or performed an action you cannot perform. Do not invent product
features. If you are uncertain, say so and suggest a safe next step. The assistant runs using
a private, locally hosted Ollama model; do not imply that prompts are sent to a cloud AI service.

You can request app actions that the Relay client executes immediately. Use a logout action when
the user asks to sign out or log out. Use a login action when the user asks to go to sign in or log
in; the client will open the login screen, but never claim that credentials, consent, or MFA can be
bypassed. Use open_chat only when the requested person exactly matches one of the available
conversation names. Otherwise use find_people with the person's name, including when the user asks
to make a friend or meet someone new. Tell the user what is happening now; do not ask them to press
an action button or ask for confirmation. Return no action for ordinary questions."""


class OllamaService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def chat(
        self,
        *,
        message: str,
        history: list[SupportMessage],
        available_conversations: list[str],
    ) -> SupportAssistantResult:
        conversation_context = ", ".join(available_conversations[:100]) or "None"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *(item.model_dump() for item in history[-20:]),
            {
                "role": "user",
                "content": (
                    f"Available conversation names: {conversation_context}\n\n"
                    f"User request: {message}"
                ),
            },
        ]
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.OLLAMA_BASE_URL.rstrip("/"),
                timeout=self.settings.OLLAMA_TIMEOUT_SECONDS,
            ) as client:
                for attempt in range(2):
                    response = await client.post(
                        "/api/chat",
                        json={
                            "model": self.settings.OLLAMA_MODEL,
                            "messages": messages,
                            "stream": False,
                            "format": SupportAssistantResult.model_json_schema(),
                            "options": {"temperature": 0},
                        },
                    )
                    response.raise_for_status()
                    try:
                        result = SupportAssistantResult.model_validate_json(
                            response.json()["message"]["content"]
                        )
                        break
                    except (KeyError, TypeError, ValueError):
                        if attempt == 1:
                            raise
                        messages.append(
                            {
                                "role": "user",
                                "content": "Return only complete JSON that exactly matches the required schema.",
                            }
                        )
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            raise ServiceUnavailableError(
                "The local support assistant is unavailable. Check that Ollama is running "
                "and the configured model is installed.",
                code="OLLAMA_UNAVAILABLE",
            ) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise ServiceUnavailableError(
                "The local support assistant returned an invalid response.",
                code="OLLAMA_INVALID_RESPONSE",
            ) from exc
        if not result.reply.strip():
            fallback_replies = {
                "login": "Opening the sign-in screen now.",
                "logout": "Logging you out now.",
                "open_chat": "Opening this conversation now.",
                "find_people": "Opening people search now.",
            }
            action_type = result.actions[0].type if result.actions else None
            result.reply = fallback_replies.get(
                action_type, "I’m ready to help. Please try asking in a different way."
            )
        return result
