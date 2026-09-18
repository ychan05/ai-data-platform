from app.llm.base import BaseLLMAdapter, LLMResponse, LLMUsage


class StubAdapter(BaseLLMAdapter):
    async def generate(self, messages: list[dict]) -> str:
        return "SELECT 1 AS test"

    async def generate_with_usage(self, messages: list[dict]) -> LLMResponse:
        return LLMResponse(
            content="SELECT 1 AS test",
            model="stub",
            usage=LLMUsage(),
        )