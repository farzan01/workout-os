import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import date, timedelta

from src.data_loader import load_workouts, get_exercises, load_measurements, save_measurement, DATA_PATH
from src.analysis import compute_volume, compute_1rm, detect_stagnation, compute_frequency_heatmap, get_pr_markers
from src.ai_coach import PROVIDER_DEFAULTS, ask_coach

st.set_page_config(page_title="Workout OS", page_icon="💪", layout="wide")

st.title("💪 Workout OS")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Data")
    uploaded = st.file_uploader("Upload Hevy CSV", type="csv", help="Export from Hevy → Settings → Export Workout Data")

    days = st.slider("History (days)", min_value=30, max_value=365, value=90, step=30)

    st.divider()
    st.header("Bodyweight")
    bodyweight_kg = st.number_input(
        "Your bodyweight (kg)",
        min_value=0.0, max_value=250.0, value=0.0, step=0.5,
        help="Used to calculate 1RM for bodyweight exercises like Pull-ups. Leave 0 to skip.",
    )

# ── Load data ────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading workouts…")
def get_df(file_bytes, days):
    if file_bytes is not None:
        import io
        class _Wrap:
            def read(self): return file_bytes
        return load_workouts(_Wrap(), days=days)
    if DATA_PATH.exists():
        return load_workouts(days=days)
    return None

file_bytes = uploaded.read() if uploaded else None
df = get_df(file_bytes, days)

if df is None or df.empty:
    st.warning("No workout data found. Upload a Hevy CSV export or place `workouts.csv` in the `data/` folder.")
    st.stop()

all_exercises = get_exercises(df)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_volume, tab_1rm, tab_log, tab_freq, tab_measurements, tab_coach = st.tabs(
    ["📊 Volume", "🏋️ Est. 1RM", "📋 Workout Log", "📅 Frequency", "⚖️ Measurements", "🤖 AI Coach"]
)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: VOLUME
# ─────────────────────────────────────────────────────────────────────────────
with tab_volume:
    st.subheader("Volume per Exercise")
    selected_vol = st.multiselect(
        "Select exercises", all_exercises,
        default=all_exercises[:3] if len(all_exercises) >= 3 else all_exercises,
        key="vol_select",
    )

    if selected_vol:
        df_vol = compute_volume(df, selected_vol)
        if df_vol.empty:
            st.info("No weighted sets found for the selected exercises in this period.")
        else:
            fig = px.line(
                df_vol, x="session_date", y="volume", color="exercise_title",
                markers=True,
                labels={"session_date": "Date", "volume": "Total Volume (kg)", "exercise_title": "Exercise"},
                title=f"Total Volume (kg lifted) — last {days} days",
            )
            fig.update_traces(marker_size=8)
            fig.update_layout(hovermode="x unified", legend_title_text="Exercise")
            st.plotly_chart(fig)
    else:
        st.info("Select at least one exercise above.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: ESTIMATED 1RM
# ─────────────────────────────────────────────────────────────────────────────
with tab_1rm:
    st.subheader("Estimated 1-Rep Max (Epley Formula)")
    if bodyweight_kg > 0:
        st.caption(f"Using {bodyweight_kg} kg bodyweight for bodyweight exercises.")

    selected_str = st.multiselect(
        "Select exercises", all_exercises,
        default=all_exercises[:3] if len(all_exercises) >= 3 else all_exercises,
        key="str_select",
    )

    if selected_str:
        df_1rm = compute_1rm(df, selected_str, bodyweight_kg=bodyweight_kg)
        stagnation = detect_stagnation(df_1rm)

        # Stagnation banners
        stagnating = [ex for ex, s in stagnation.items() if s["is_stagnating"]]
        if stagnating:
            st.warning(
                f"⚠️ **Stagnation detected** in: {', '.join(stagnating)}. "
                "No meaningful 1RM improvement over the last 8 sessions. "
                "Consider a deload, rep range change, or exercise variation."
            )

        if df_1rm.empty:
            st.info("No weighted normal sets found. Add bodyweight in sidebar for bodyweight exercises.")
        else:
            pr_markers = get_pr_markers(df_1rm)

            fig = px.line(
                df_1rm, x="session_date", y="est_1rm", color="exercise_title",
                markers=True,
                labels={"session_date": "Date", "est_1rm": "Est. 1RM (kg)", "exercise_title": "Exercise"},
                title=f"Estimated 1RM — last {days} days",
            )
            fig.update_traces(marker_size=7)

            # PR star overlay
            for _, row in pr_markers.iterrows():
                fig.add_trace(go.Scatter(
                    x=[row["session_date"]], y=[row["est_1rm"]],
                    mode="markers",
                    marker=dict(symbol="star", size=16, color="gold", line=dict(color="orange", width=1)),
                    name=f"PR – {row['exercise_title']}",
                    showlegend=True,
                ))

            fig.update_layout(hovermode="x unified", legend_title_text="Exercise")
            st.plotly_chart(fig)

            # PR summary table
            with st.expander("Personal Records"):
                pr_rows = []
                for ex, s in stagnation.items():
                    pr_rows.append({
                        "Exercise": ex,
                        "All-time PR (kg)": s["last_pr_value"],
                        "PR Date": s["last_pr_date"].strftime("%b %d, %Y") if s["last_pr_date"] else "—",
                        "Stagnating?": "⚠️ Yes" if s["is_stagnating"] else "✅ No",
                    })
                st.dataframe(pd.DataFrame(pr_rows), width="stretch", hide_index=True)
    else:
        st.info("Select at least one exercise above.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: WORKOUT LOG
# ─────────────────────────────────────────────────────────────────────────────
with tab_log:
    st.subheader("Workout Log")
    log_exercises = st.multiselect(
        "Filter by exercise (optional)", all_exercises, key="log_select"
    )

    log_df = df.copy()
    if log_exercises:
        log_df = log_df[log_df["exercise_title"].isin(log_exercises)]

    display_cols = ["session_date", "title", "exercise_title", "set_type", "set_index", "weight_kg", "reps", "duration_seconds"]
    display_cols = [c for c in display_cols if c in log_df.columns]
    st.dataframe(
        log_df[display_cols].sort_values(["session_date", "exercise_title", "set_index"], ascending=[False, True, True]),
        width="stretch", hide_index=True,
    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4: FREQUENCY HEATMAP
# ─────────────────────────────────────────────────────────────────────────────
with tab_freq:
    st.subheader("Workout Frequency")

    freq_df = compute_frequency_heatmap(df)

    if freq_df.empty:
        st.info("No session data to display.")
    else:
        # Calendar heatmap using a scatter with day/week axes
        freq_df["date_str"] = freq_df["session_date"].dt.strftime("%b %d, %Y")
        freq_df["day_name"] = freq_df["session_date"].dt.strftime("%a")

        fig = px.density_heatmap(
            freq_df,
            x="week", y="weekday",
            z="count",
            color_continuous_scale="Greens",
            labels={"week": "Week of Year", "weekday": "Day (0=Mon)", "count": "Sessions"},
            title=f"Workout frequency — last {days} days",
        )
        fig.update_layout(yaxis=dict(
            tickvals=[0,1,2,3,4,5,6],
            ticktext=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        ))
        st.plotly_chart(fig)

        total_sessions = len(df.drop_duplicates(subset=["title", "session_date"]))
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Sessions", total_sessions)
        col2.metric("Avg / Week", f"{total_sessions / max(days/7, 1):.1f}")
        most_common_day = freq_df.groupby("day_name")["count"].sum().idxmax() if not freq_df.empty else "—"
        col3.metric("Most Active Day", most_common_day)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 5: MEASUREMENTS
# ─────────────────────────────────────────────────────────────────────────────
with tab_measurements:
    st.subheader("Body Measurements")

    m_df = load_measurements()
    last_height = float(m_df["height_cm"].iloc[-1]) if not m_df.empty else 175.0
    last_weight = float(m_df["weight_kg"].iloc[-1]) if not m_df.empty else 70.0

    with st.form("log_measurement"):
        c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
        m_date = c1.date_input("Date", value=date.today())
        m_weight = c2.number_input("Weight (kg)", min_value=20.0, max_value=300.0, value=last_weight, step=0.1)
        m_height = c3.number_input("Height (cm)", min_value=100.0, max_value=250.0, value=last_height, step=0.5)
        m_notes = c4.text_input("Notes (optional)")
        submitted = st.form_submit_button("Log measurement")

    if submitted:
        save_measurement(m_date, m_weight, m_height, m_notes)
        st.success("Measurement saved!")
        st.rerun()

    m_df = load_measurements()
    if m_df.empty:
        st.info("No measurements logged yet. Use the form above to get started.")
    else:
        m_df["bmi"] = m_df["weight_kg"] / ((m_df["height_cm"] / 100) ** 2)
        m_df["weight_7d_avg"] = m_df["weight_kg"].rolling(7, min_periods=1).mean()

        col_w, col_bmi = st.columns(2)
        with col_w:
            fig_w = px.line(m_df, x="date", y=["weight_kg", "weight_7d_avg"],
                            markers=True, title="Body Weight Over Time",
                            labels={"value": "Weight (kg)", "variable": ""},
                            color_discrete_map={"weight_kg": "#636EFA", "weight_7d_avg": "#EF553B"})
            st.plotly_chart(fig_w)

        with col_bmi:
            fig_bmi = px.line(m_df, x="date", y="bmi",
                              markers=True, title="BMI Over Time",
                              labels={"bmi": "BMI"})
            st.plotly_chart(fig_bmi)

        if len(m_df) >= 1:
            current_w = m_df["weight_kg"].iloc[-1]
            start_w = m_df["weight_kg"].iloc[0]
            delta = current_w - start_w
            cols = st.columns(3)
            cols[0].metric("Current Weight", f"{current_w:.1f} kg")
            cols[1].metric("Starting Weight", f"{start_w:.1f} kg")
            cols[2].metric("Total Change", f"{delta:+.1f} kg")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 6: AI COACH
# ─────────────────────────────────────────────────────────────────────────────
with tab_coach:
    st.subheader("AI Coach")
    st.caption("Ask your AI coach about exercise alternatives, progression, or anything training-related.")

    col_prov, col_key, col_model = st.columns([1, 2, 2])
    provider = col_prov.selectbox("Provider", list(PROVIDER_DEFAULTS.keys()))
    defaults = PROVIDER_DEFAULTS[provider]

    api_key = col_key.text_input("API Key", type="password", placeholder="sk-…")
    model = col_model.text_input("Model", value=defaults["model"], placeholder="Model name")

    base_url = None
    if provider in ("Qwen", "Other"):
        base_url = st.text_input("Base URL", value=defaults["base_url"] or "", placeholder="https://…")

    # Context exercises for the coach
    coach_exercises = st.multiselect(
        "Include these exercises as context", all_exercises,
        default=all_exercises[:5] if len(all_exercises) >= 5 else all_exercises,
        key="coach_exercises",
    )

    # Quick-prompt chips
    st.write("**Quick prompts:**")
    chip_cols = st.columns(3)
    chips = [
        "What exercises can replace the ones I'm stagnating on?",
        "Why might I be stagnating and how do I break through?",
        "Build me a 4-week progression plan based on my current numbers.",
    ]
    for i, chip in enumerate(chips):
        if chip_cols[i].button(chip, use_container_width=True):
            st.session_state["coach_input"] = chip

    question = st.text_area(
        "Your question",
        value=st.session_state.get("coach_input", ""),
        placeholder="e.g. What can I do instead of Lat Pulldown?",
        height=100,
    )

    if st.button("Ask", type="primary"):
        if not api_key:
            st.error("Enter an API key to use the AI Coach.")
        elif not question.strip():
            st.error("Enter a question.")
        else:
            m_df_coach = load_measurements()
            current_weight = float(m_df_coach["weight_kg"].iloc[-1]) if not m_df_coach.empty else None

            df_1rm_coach = compute_1rm(df, coach_exercises, bodyweight_kg=bodyweight_kg) if coach_exercises else None
            stag_coach = detect_stagnation(df_1rm_coach) if df_1rm_coach is not None and not df_1rm_coach.empty else {}

            with st.spinner("Thinking…"):
                answer = ask_coach(
                    question=question,
                    exercises=coach_exercises,
                    df_1rm=df_1rm_coach,
                    stagnation=stag_coach,
                    current_weight_kg=current_weight,
                    provider=provider,
                    api_key=api_key,
                    model=model,
                    base_url=base_url or None,
                )
            st.markdown("### Response")
            st.markdown(answer)
