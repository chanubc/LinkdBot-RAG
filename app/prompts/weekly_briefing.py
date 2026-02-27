def build_briefing_prompt(
    best: dict,
    tvd: float,
    delta: dict[str, float],
    current_cats: list[str],
) -> str:
    """Build a weekly briefing prompt for the LLM."""
    if tvd > 0.1:
        top_gains = sorted(
            [(c, d) for c, d in delta.items() if d > 0],
            key=lambda t: t[1],
            reverse=True,
        )[:2]
        top_losses = sorted(
            [(c, d) for c, d in delta.items() if d < 0],
            key=lambda t: t[1],
        )[:2]
        drift_lines = []
        for c, d in top_gains:
            drift_lines.append(f"  ▲ {c} (+{d:.0%})")
        for c, d in top_losses:
            drift_lines.append(f"  ▼ {c} ({d:.0%})")
        drift_summary = "Interest drift:\n" + "\n".join(drift_lines)
    else:
        drift_summary = "Interest drift: stable (no significant change)"

    categories_str = ", ".join(current_cats[:10]) if current_cats else "none"

    return f"""\
Generate a weekly knowledge report for the user.

[This week's interest categories]: {categories_str}
[{drift_summary}]

[Link to revisit]
Title: {best.get('title', 'No title')}
Summary: {best.get('summary', '')}
Category: {best.get('category', '')}

Based on the above information:
1. Summarize this week's interest trends in one sentence
2. Explain why the recommended link is useful right now (2-3 sentences)
3. Provide an encouraging closing remark

Write in Korean, in a friendly and concise tone. Total 5-7 sentences."""
