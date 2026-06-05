from openai import OpenAI
from config import settings


class LLMService:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self.model = settings.openai_model

    def chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """
        通用对话接口
        messages: [{"role": "system"/"user"/"assistant", "content": "..."}]
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"[LLM调用失败] {str(e)}"

    def generate_narrative(self, prompt: str, context: str = "") -> str:
        """生成叙事文本"""
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一位资深医院叙事生成助手。"
                    "请基于提供的科室历史数据和上下文，生成结构化、专业的医疗叙事简报。"
                    "语言要求：中文。风格：专业、清晰、有条理。"
                ),
            },
            {
                "role": "user",
                "content": f"{prompt}\n\n上下文信息:\n{context}" if context else prompt,
            },
        ]
        return self.chat(messages, temperature=0.5, max_tokens=4000)

    def test_connection(self) -> bool:
        try:
            self.chat([{"role": "user", "content": "Hello"}], max_tokens=10)
            return True
        except Exception:
            return False


# 全局单例
llm_service = LLMService()
