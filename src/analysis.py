import pandas as pd


def compute_volume(df: pd.DataFrame, exercises: list[str]) -> pd.DataFrame:
    """Total tonnage per exercise per session (weight_kg × reps, all non-cardio sets)."""
    mask = (
        df["exercise_title"].isin(exercises)
        & ~df["is_cardio"]
        & (df["weight_kg"] > 0)
        & (df["reps"] > 0)
    )
    sub = df[mask].copy()
    sub["volume"] = sub["weight_kg"] * sub["reps"]
    grouped = (
        sub.groupby(["exercise_title", "session_date"])["volume"]
        .sum()
        .reset_index()
    )
    return grouped


def compute_1rm(df: pd.DataFrame, exercises: list[str], bodyweight_kg: float = 0.0) -> pd.DataFrame:
    """Best estimated 1RM per exercise per session using Epley formula.

    bodyweight_kg is added to weight for bodyweight exercises (e.g. pull-ups).
    """
    mask = (
        df["exercise_title"].isin(exercises)
        & (df["set_type"] == "normal")
        & (df["reps"] > 0)
    )
    sub = df[mask].copy()

    sub["effective_weight"] = sub["weight_kg"].copy()
    if bodyweight_kg > 0:
        bw_mask = sub["is_bodyweight"]
        sub.loc[bw_mask, "effective_weight"] = bodyweight_kg + sub.loc[bw_mask, "weight_kg"]

    # Epley: 1RM = w × (1 + r/30); only meaningful when reps < ~37
    valid = sub["effective_weight"] > 0
    sub.loc[valid, "est_1rm"] = sub.loc[valid, "effective_weight"] * (1 + sub.loc[valid, "reps"] / 30)

    grouped = (
        sub.dropna(subset=["est_1rm"])
        .groupby(["exercise_title", "session_date"])["est_1rm"]
        .max()
        .reset_index()
    )
    return grouped


def detect_stagnation(df_1rm: pd.DataFrame, window: int = 8, threshold_pct: float = 2.5) -> dict:
    """Return {exercise: {is_stagnating, last_pr_date, last_pr_value}} for each exercise."""
    results = {}
    for exercise, grp in df_1rm.groupby("exercise_title"):
        grp = grp.sort_values("session_date")
        if len(grp) < 2:
            results[exercise] = {"is_stagnating": False, "last_pr_date": None, "last_pr_value": None}
            continue

        recent = grp.tail(window)
        rolling_max = recent["est_1rm"].max()
        pr_row = grp.loc[grp["est_1rm"].idxmax()]
        last_pr_date = pr_row["session_date"]
        last_pr_value = pr_row["est_1rm"]

        # Stagnating if no improvement > threshold_pct over the last `window` sessions
        if len(recent) >= 4:
            earliest_recent = recent.iloc[0]["est_1rm"]
            pct_change = (rolling_max - earliest_recent) / max(earliest_recent, 1) * 100
            is_stagnating = pct_change <= threshold_pct
        else:
            is_stagnating = False

        results[exercise] = {
            "is_stagnating": is_stagnating,
            "last_pr_date": last_pr_date,
            "last_pr_value": round(last_pr_value, 1),
        }
    return results


def compute_frequency_heatmap(df: pd.DataFrame) -> pd.DataFrame:
    """Return daily workout counts for a GitHub-style heatmap."""
    sessions = df.drop_duplicates(subset=["title", "session_date"])[["session_date"]].copy()
    sessions["count"] = 1
    daily = sessions.groupby("session_date")["count"].sum().reset_index()
    daily["week"] = daily["session_date"].dt.isocalendar().week.astype(int)
    daily["weekday"] = daily["session_date"].dt.weekday
    daily["year"] = daily["session_date"].dt.isocalendar().year.astype(int)
    return daily


def get_pr_markers(df_1rm: pd.DataFrame) -> pd.DataFrame:
    """Return rows that represent all-time PRs per exercise (for scatter overlay)."""
    idx = df_1rm.groupby("exercise_title")["est_1rm"].idxmax()
    return df_1rm.loc[idx].copy()
