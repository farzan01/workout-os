import pandas as pd
from pathlib import Path
import io

DATA_PATH = Path(__file__).parent.parent / "data" / "workouts.csv"
MEASUREMENTS_PATH = Path(__file__).parent.parent / "data" / "measurements.csv"


def load_workouts(csv_source=None, days: int = 90) -> pd.DataFrame:
    """Load and clean workout CSV. csv_source can be a file path or an uploaded bytes object."""
    if csv_source is None:
        csv_source = DATA_PATH

    if isinstance(csv_source, (str, Path)):
        df = pd.read_csv(csv_source)
    else:
        df = pd.read_csv(io.BytesIO(csv_source.read()))

    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    df["start_time"] = pd.to_datetime(df["start_time"], format="%b %d, %Y, %I:%M %p")
    df["session_date"] = df["start_time"].dt.date
    df["session_date"] = pd.to_datetime(df["session_date"])

    df["weight_kg"] = pd.to_numeric(df["weight_kg"], errors="coerce")
    df["reps"] = pd.to_numeric(df["reps"], errors="coerce")
    df["duration_seconds"] = pd.to_numeric(df["duration_seconds"], errors="coerce")

    cutoff = pd.Timestamp.today() - pd.Timedelta(days=days)
    df = df[df["session_date"] >= cutoff].copy()

    df["is_warmup"] = df["set_type"] == "warmup"
    df["is_bodyweight"] = df["weight_kg"].isna() & df["reps"].notna()
    df["is_timed"] = df["duration_seconds"].notna() & df["reps"].isna() & df["weight_kg"].isna()
    df["is_cardio"] = df["weight_kg"].isna() & df["reps"].isna() & df["duration_seconds"].isna()

    df["weight_kg"] = df["weight_kg"].fillna(0.0)
    df["reps"] = df["reps"].fillna(0.0)

    return df


def get_exercises(df: pd.DataFrame) -> list[str]:
    return sorted(df["exercise_title"].dropna().unique().tolist())


def load_measurements() -> pd.DataFrame:
    if not MEASUREMENTS_PATH.exists():
        return pd.DataFrame(columns=["date", "weight_kg", "height_cm", "notes"])
    df = pd.read_csv(MEASUREMENTS_PATH, parse_dates=["date"])
    return df.sort_values("date")


def save_measurement(date, weight_kg: float, height_cm: float, notes: str = "") -> None:
    df = load_measurements()
    new_row = pd.DataFrame([{"date": pd.Timestamp(date), "weight_kg": weight_kg, "height_cm": height_cm, "notes": notes}])
    df = pd.concat([df, new_row], ignore_index=True)
    MEASUREMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(MEASUREMENTS_PATH, index=False)
