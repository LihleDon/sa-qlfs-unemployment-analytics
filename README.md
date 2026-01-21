# South African Unemployment Analytics Pipeline (QLFS 2020–2025)

**Showcasing end-to-end modern data engineering for South Africa's critical jobs crisis.**

South Africa faces one of the world's highest unemployment rates (~32% in 2025), with youth unemployment >45% and major disparities by province (e.g. Eastern Cape vs Western Cape), race, gender, and age. This project builds a production-grade analytics pipeline and interactive dashboard.

[![Live Dashboard](https://img.shields.io/badge/Live%20Demo-Streamlit-brightgreen)](https://your-streamlit-url.streamlit.app)

## Why This Matters
High unemployment drives inequality, poverty, and social challenges in post-apartheid South Africa...

## Tech Stack (All Free Forever)
- Ingestion: Python + pandas
- Storage: MotherDuck (DuckDB Cloud)
- Transformation: dbt Core + dbt Cloud (free dev)
- Quality: Elementary
- Orchestration: Mage.ai OSS
- Dashboard: Streamlit + Plotly
- CI/CD: GitHub Actions

## Architecture
![Architecture Diagram](docs/architecture.png)

Medallion layers: Raw → Bronze → Silver → Gold

## Key Insights (Screenshots)
![Unemployment Trends](docs/gifs/trends.gif)
![Youth by Race Heatmap](docs/gifs/youth-heatmap.gif)

## Setup Instructions
1. Clone repo...
2. Install deps...
3. Set MotherDuck token...
4. `dbt run`, `streamlit run dashboard/app.py`

## Data Lineage & Quality
[dbt lineage screenshot]  
Elementary quality report: [link/screenshot]

## Lessons Learned
...

## Bonus Features
- Automated tests & CI/CD
- Interactive provincial heatmap
- Focus on youth unemployment crisis
