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
        # 思考模式开关（DeepSeek 推理模型），通过 extra_body 传给 API
        thinking_mode = settings.thinking_mode.strip().lower()
        if thinking_mode not in ("enabled", "disabled"):
            thinking_mode = "enabled"
        self.thinking_mode = thinking_mode

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
                # DeepSeek 思考模式开关需放在 extra_body 中（OpenAI SDK 无此参数）
                extra_body={"thinking": {"type": self.thinking_mode}},
            )
            choice = response.choices[0]
            content = choice.message.content
            # 推理模型（如 deepseek-v4-flash）的思考token与回答token共用 max_tokens，
            # 额度被思考耗尽时会静默返回空内容（finish_reason="length"），需显式识别
            if not content and getattr(choice, "finish_reason", None) == "length":
                content = (
                    f"[LLM调用失败] 模型因 max_tokens={max_tokens} 过小未产出内容"
                    "（推理模型的思考token会占用该额度），请调大 max_tokens 后重试"
                )
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
            content = self.chat(
                [{"role": "user", "content": "Hello"}],
                # 推理模型的思考token会占用 max_tokens，额度太小会得到空内容
                max_tokens=500,
                use_cache=False,  # 测试连接跳过缓存
            )
            # chat() 内部不抛异常，需通过返回值判断调用是否真正成功
            return bool(content) and not content.startswith("[LLM调用失败]")
        except Exception:
            return False


# 全局单例
llm_service = LLMService()
