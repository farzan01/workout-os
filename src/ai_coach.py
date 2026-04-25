from __future__ import annotations

import pandas as pd
from typing import Optional

PROVIDER_DEFAULTS = {
    "OpenAI": {"model": "gpt-4o-mini", "base_url": None},
    "Anthropic": {"model": "claude-haiku-4-5-20251001", "base_url": None},
    "DeepSeek": {"model": "deepseek/deepseek-chat", "base_url": None},
    "Qwen": {"model": "openai/qwen-plus", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    "Other": {"model": "", "base_url": ""},
}


def build_system_prompt(
    exercises: list,
    df_1rm: Optional[pd.DataFrame],
    stagnation: dict,
    current_weight_kg: Optional[float],
) -> str:
    lines = [
        "You are an expert strength and conditioning coach. You have access to the user's real training data below.",
        "Give specific, evidence-based advice. Reference the data when relevant. Be concise.",
        "",
    ]

    if current_weight_kg:
        lines.append(f"User bodyweight: {current_weight_kg:.1f} kg")

    if exercises:
        lines.append(f"Current exercises being tracked: {', '.join(exercises)}")

    if df_1rm is not None and not df_1rm.empty:
        lines.append("\nRecent estimated 1RM history (last 8 sessions per exercise):")
        for ex in exercises:
            sub = df_1rm[df_1rm["exercise_title"] == ex].sort_values("session_date").tail(8)
            if sub.empty:
                continue
            rows = [f"  {row['session_date'].strftime('%b %d')}: {row['est_1rm']:.1f} kg" for _, row in sub.iterrows()]
            stag = stagnation.get(ex, {})
            flag = " ⚠️ STAGNATING" if stag.get("is_stagnating") else ""
            pr_val = stag.get("last_pr_value")
            pr_date = stag.get("last_pr_date")
            pr_info = f" | All-time PR: {pr_val} kg on {pr_date.strftime('%b %d, %Y') if pr_date else 'N/A'}" if pr_val else ""
            lines.append(f"\n{ex}{flag}{pr_info}")
            lines.extend(rows)

    return "\n".join(lines)


def ask_coach(
    question: str,
    exercises: list,
    df_1rm: Optional[pd.DataFrame],
    stagnation: dict,
    current_weight_kg: Optional[float],
    provider: str,
    api_key: str,
    model: str,
    base_url: Optional[str] = None,
) -> str:
    try:
        import litellm
    except ImportError:
        return "litellm is not installed. Run: pip install litellm"

    system_prompt = build_system_prompt(exercises, df_1rm, stagnation, current_weight_kg)

    kwargs = {
        "model": model,
        "api_key": api_key,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
    }
    if base_url:
        kwargs["base_url"] = base_url

    try:
        response = litellm.completion(**kwargs)
        return response.choices[0].message.content
    except Exception as e:
        return f"Error calling {provider} API: {e}"
