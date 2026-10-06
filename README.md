# 🍽️ Boston Food Inspections Dashboard

[![Streamlit App](https://img.shields.io/badge/Streamlit-App-FF4B4B?logo=streamlit&logoColor=white)](https://share.streamlit.io)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An open-source, interactive dashboard for exploring **food establishment health inspections** published by the **City of Boston**. Filter by neighborhood, restaurant name, inspection result, and date range — all in a single, user-friendly web interface.

> ⚠️ **Pilot project.** This is an exploratory visualization tool. The author assumes no responsibility for decisions or conclusions derived from its outputs. Always verify with the official City of Boston records.

---

## ✨ Features

- 🔍 **Filter inspections** by:
  - Restaurant name (partial, case-insensitive)
  - Neighborhood (multi-select)
  - Inspection result (Pass / Fail, etc.)
  - Date range
- 📊 **Live KPIs**: total records, filtered results, pass rate, fail count
- 📋 **Interactive table** with the filtered results
- 📈 **Summary charts**: results distribution and top neighborhoods
- 📥 **CSV export** of the filtered dataset
- ☁️ **No installation required** — runs entirely in the cloud (Google Colab + Streamlit)

---

## 🗂️ Data Source

- **Dataset:** [Food Establishment Inspections](https://data.boston.gov/dataset/food-establishment-inspections)
- **Provider:** City of Boston Open Data
- **Records:** ~97,000 inspections
- **License:** [Open Data Commons PDDL](https://opendatacommons.org/licenses/pddl/)
- **API endpoint used:** https://data.boston.gov/api/3/action/datastore_search?resource_id=4582bec6-2b4f-4f9e-bc55-cbaa73117f4c



---

## 🛠️ Tech Stack

| Layer | Tool |
|---|---|
| Frontend | [Streamlit](https://streamlit.io/) |
| Data handling | [pandas](https://pandas.pydata.org/) |
| HTTP requests | [requests](https://requests.readthedocs.io/) |
| Hosting | Streamlit Community Cloud (free tier) |
| Development | Google Colab + Cloudflare Tunnel |

---

## 🚀 Running Locally

If you want to run this dashboard on your own machine:

```bash
# 1. Clone the repository
git clone https://github.com/renatoerss/boston-food-inspections.git
cd boston-food-inspections

# 2. (Recommended) Create a virtual environment
python -m venv .venv
source .venv/bin/activate    # Linux / macOS
# .venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
streamlit run app.py
