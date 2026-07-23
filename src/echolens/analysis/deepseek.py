"""DeepSeek-backed transcript analysis."""

import json
from typing import Any

from echolens.analysis.models import AnalysisResult
from echolens.core.config import Settings, get_settings


SYSTEM_PROMPT = """你是 EchoLens 的内容分析器，服务对象是长期追踪财经博主以掌握股票、基金等金融市场信息的用户。请根据用户提供的视频转写文本，输出严格 JSON，不要输出 Markdown 或额外说明。

JSON 必须包含：
{
  "summary": "一段信息密度高、覆盖完整的中文摘要（通常 150-400 字），须交代：博主的核心市场判断/结论、支撑这一判断的关键论据、提到的风险或不确定性、以及给出的可执行建议或需要持续关注的信号。禁止写成一两句空泛概括。",
  "tags": ["3 到 8 个简短中文标签，优先覆盖资产类别（如 A股/美股/基金/黄金）、行业或板块、宏观主题（如利率/流动性/政策）、以及提到的具体标的或指数名称"],
  "key_points": ["3 到 10 条关键观点，每条应尽量具体到：涉及的具体资产/行业/指数及博主的多空方向判断、提到的关键数据或阈值（点位、涨跌幅、利率、时间周期等）、催化剂或时间线、以及风险提示；避免写成不含具体信息的泛泛总结"],
  "market_insights": [
    {
      "subject": "股票、行业板块、指数、商品、汇率或宏观主题",
      "subject_type": "stock | industry | index | commodity | currency | macro | market",
      "stance": "strong_bullish | bullish | neutral | cautious | bearish | strong_bearish | unclear",
      "conclusion": "一条可独立理解的市场结论",
      "source_type": "explicit | inferred",
      "time_horizon": "intraday | short_term | medium_term | long_term | unspecified",
      "confidence": "high | medium | low",
      "reasoning": ["转写中支持该结论的具体依据"],
      "risks": ["博主提到或从其论据直接可见的风险与不确定性"],
      "evidence_quote": "转写中的简短直接依据；没有明确原话时为 null"
    }
  ]
}

市场结论规则：
1. 只提取对中国大陆股票市场研究有帮助的方向、行业、指数、个股、宏观和风险信息；没有可靠市场信息时 market_insights 输出空数组。
2. source_type=explicit 仅用于博主明确表达看多、看空、谨慎、观望、持有或回避等态度；source_type=inferred 用于博主未直接表态，但其多个论据可支持一个有限推断。
3. inferred 结论必须降低 confidence，并在 conclusion 中明确使用“倾向于”“可能”“显示”等措辞，不得伪装成博主原话。
4. 信息不足、前后矛盾或方向无法判断时使用 unclear，不得强行生成交易方向。
5. 不得自行补充实时行情、估值、政策、财报或转写中没有的信息；不得把常识包装成博主观点。
6. 不得擅自给出买入、卖出、仓位或价格目标，除非博主明确表达；即使明确表达，也只记录其观点，不替用户作交易决定。
7. stance 语义按中国大陆市场习惯展示：看多/上涨为红色，看空/下跌为绿色，但 JSON 仅输出枚举值。

只根据转写内容总结，不要补充文本中没有的信息；如果转写内容与金融市场无关，仍按 summary、tags、key_points 正常总结原内容，并令 market_insights 为 []。"""


class DeepSeekAnalyzer:
    """Call the OpenAI-compatible DeepSeek Chat Completions API."""

    def __init__(self, settings: Settings | None = None, client: Any | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            if not self.settings.llm_api_key:
                raise ValueError("LLM_API_KEY is required for DeepSeek analysis")

            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.settings.llm_api_key,
                base_url=self.settings.llm_base_url,
            )
        return self._client

    def analyze(self, transcript_text: str, description: str | None = None) -> AnalysisResult:
        """Analyze one transcript and return validated structured content."""

        transcript = transcript_text.strip()
        if not transcript:
            raise ValueError("Transcript text is empty")

        context: list[str] = []
        if description and description.strip():
            context.append(f"视频描述：{description.strip()}")
        context.append(f"转写文本：\n{transcript}")

        response = self._get_client().chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "\n\n".join(context)},
            ],
            response_format={"type": "json_object"},
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )

        choice = response.choices[0]
        if getattr(choice, "finish_reason", None) == "length":
            raise ValueError("DeepSeek response was truncated by max_tokens")

        content = choice.message.content
        if not content or not content.strip():
            raise ValueError("DeepSeek returned empty content")
        return AnalysisResult.model_validate(json.loads(content))
