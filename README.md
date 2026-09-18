# HealthLens India

Compare Indian packaged foods using nutrition-label data. The first release covers **malted drink powders** and **chocolates**, and answers simple questions such as which product has less sugar or more protein per 100g.

The app does **not** say a product is healthy, diagnose anyone, or give medical advice. Verdicts stay factual, for example: *better fit for lower sugar based on the nutrition label*.

## What you can do

- Explore products sorted for **lower sugar** or **higher protein**
- Compare two products in the same category, per 100g and per serving
- Read how the data and calculations work on the Methodology page

This version uses a local CSV. There is no login, payments, barcode scanner, live prices, or AI chat.

## Folder structure

```text
healthlens-india/
  app.py
  data.py
  compare.py
  ui.py
  requirements.txt
  README.md
  .gitignore
  data/
    products.csv
    sample_products.csv
  tests/
    test_compare.py
```

- `data/products.csv` — production catalog (headers only until you add verified labels)
- `data/sample_products.csv` — fictional `DEMO …` rows for local development

## Setup

Create and activate a virtual environment, then install dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run the app

```bash
streamlit run app.py
```

If `products.csv` has no usable rows, the app loads the sample file and shows:

> You are viewing fictional demo data. Add manually verified products to data/products.csv before publishing.

Replace the fictional sample data before any public deployment. Do not invent nutrition numbers for real brands.

## Run tests

```bash
pytest
```

## Add a verified product

Edit `data/products.csv`. Keep the header row, then add one product per line. All nutrients are **per 100g**. Per-serving values are calculated in the app from `serving_size_g`.

Use `verification_status` of `Verified`, `Needs review`, or `Demo`. Dates must be `YYYY-MM-DD`. Categories must be `Malted drink powders` or `Chocolates`.

Example first data row (replace every field with values copied from a real pack or official page):

```text
product_id,slug,name,brand,category,variant,pack_size_g,serving_size_g,calories_kcal_100g,protein_g_100g,sugar_g_100g,fibre_g_100g,sodium_mg_100g,label_source_url,last_verified,verification_status,notes
HL-001,your-product-slug,Product name,Brand name,Malted drink powders,Variant name,500,30,380,12.0,32.0,3.5,280,https://official-product-page.example,2026-09-18,Verified,Copied from pack nutrition table.
```

## Deploy on Streamlit Community Cloud

1. Push this repository to GitHub.
2. Open [share.streamlit.io](https://share.streamlit.io) and sign in.
3. Choose the repo, branch, and main file `app.py`.
4. Deploy. No API keys or secrets are required.
5. Confirm `data/products.csv` contains verified products before sharing the app publicly.

## Disclaimer

HealthLens India is educational. It is not medical advice, a diagnosis tool, or a recommendation for children or clinical diets. Always read the pack in your hand. Formulations and serving sizes change.
