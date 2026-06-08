from openai import OpenAI
from config import settings
from database.llm_cache import llm_cache_store


class LLMService:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self.model = settings.openai_model

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        *,
        cache_namespace: str = "default",
        use_cache: bool = True,
        cache_ttl_hours: int | None = None,
        cache_metadata: dict | None = None,
    ) -> str:
        """
        通用对话接口，支持缓存
        messages: [{"role": "system"/"user"/"assistant", "content": "..."}]
        cache_namespace: 缓存命名空间，建议格式 "service:function" 如 "narrative:basic"
        use_cache: 是否启用缓存读取和写入
        cache_ttl_hours: 覆盖默认TTL，None则使用全局配置
        cache_metadata: 额外元数据，随缓存一起存储
        """
        # 尝试读取缓存
        if use_cache:
            cached = llm_cache_store.get(
                namespace=cache_namespace,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                model=self.model,
            )
            if cached is not None:
                return cached

        # 调用LLM
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
        except Exception as e:
            content = f"[LLM调用失败] {str(e)}"

        # 写入缓存（即使失败也缓存错误信息，避免重复调用失败的请求）
        if use_cache:
            llm_cache_store.set(
                namespace=cache_namespace,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                model=self.model,
                content=content,
                ttl_hours=cache_ttl_hours,
                metadata=cache_metadata,
            )

        return content

    def generate_narrative(
        self,
        prompt: str,
        context: str = "",
        *,
        cache_namespace: str = "default",
        use_cache: bool = True,
        cache_ttl_hours: int | None = None,
        cache_metadata: dict | None = None,
    ) -> str:
        """生成叙事文本，支持缓存"""
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
        return self.chat(
            messages,
            temperature=0.5,
            max_tokens=4000,
            cache_namespace=cache_namespace,
            use_cache=use_cache,
            cache_ttl_hours=cache_ttl_hours,
            cache_metadata=cache_metadata,
        )

    def test_connection(self) -> bool:
        try:
            self.chat(
                [{"role": "user", "content": "Hello"}],
                max_tokens=10,
                use_cache=False,  # 测试连接跳过缓存
            )
            return True
        except Exception:
            return False


# 全局单例
llm_service = LLMService()
