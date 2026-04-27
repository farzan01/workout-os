# 💪 Workout OS

[![Streamlit](https://img.shields.io/badge/Built%20with-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://python.org)

A local analytics dashboard for [Hevy](https://hevy.com) workout data — the charts and insights Hevy's free tier doesn't give you.

---

## Features

| Tab | What it shows |
|-----|---------------|
| 📊 **Volume** | Total tonnage (weight × reps) per exercise over time |
| 🏋️ **Est. 1RM** | Epley-formula 1RM trend, gold-star PR markers, stagnation warnings |
| 📋 **Workout Log** | Filterable raw set-level table |
| 📅 **Frequency** | Workout density heatmap by week and day of week |
| ⚖️ **Measurements** | Body weight, BMI, 7-day rolling average |
| 🤖 **AI Coach** | Ask questions about your training — powered by your own API key |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/farzan01/workout-os.git
cd workout-os

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your workout data (one of two ways):
#    a) Place workouts.csv in the data/ folder:
cp ~/Downloads/workouts.csv data/workouts.csv
#    b) Or upload it via the sidebar file uploader inside the app

# 4. Run
streamlit run app.py
```

App opens at **http://localhost:8501**.

---

## Getting Your Data

Export from Hevy: **Settings → Export Workout Data** → downloads `workouts.csv`.

Or automate it: a weekly [Claude scheduled task](.claude/scheduled-tasks/hevy-csv-weekly-download/SKILL.md) can download and place the file automatically every Sunday evening (requires Hevy login in the Dia browser).

---

## AI Coach

The AI Coach tab works with any major LLM provider — bring your own API key:

| Provider | Default model |
|----------|--------------|
| OpenAI | `gpt-4o-mini` |
| Anthropic | `claude-haiku-4-5-20251001` |
| DeepSeek | `deepseek/deepseek-chat` |
| Qwen | `openai/qwen-plus` |
| Other | Custom base URL + model |

The coach is automatically injected with your last 8 sessions of estimated 1RM and any stagnation flags so its answers are grounded in your actual data.

---

## Tech Stack

- **[Streamlit](https://streamlit.io)** — UI framework
- **[Plotly](https://plotly.com/python/)** — Interactive charts
- **[Pandas](https://pandas.pydata.org)** — Data loading and analysis
- **[LiteLLM](https://github.com/BerriAI/litellm)** — Model-agnostic LLM client
- Python 3.9+
