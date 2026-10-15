# Scryfall HTML Card Scraper

This university project extracts data from Scryfall's public HTML pages—not from its API or JSON responses.

For each Magic: The Gathering card, it collects visible HTML information including:

- card name, Scryfall print ID, and Oracle ID
- mana cost, type line, rules text, flavour text, card stats, and artist
- set, collector number, rarity, language, and finishes
- nonfoil USD/EUR/TIX prices and displayed USD/EUR foil prices
- format legalities, a high-resolution image URL, and source URLs

## Run

```powershell
python -m pip install -r .\requirements.txt
python .\scrape_scryfall_html.py --target 2000
```

Scryfall search pages display 60 cards at a time. The scraper follows those HTML result pages, then visits each card's public HTML detail page to read its visible data. It uses four concurrent detail-page requests by default and logs progress every 25 saved cards. Lower the request rate with `--workers 1` or increase `--delay` if needed.

The output file is `scryfall_cards.csv`. Every run starts from the beginning and creates a fresh CSV.

Use a different output file if needed:

```powershell
python .\scrape_scryfall_html.py --target 2200 --output cards.csv
```

## Generate price and foil-premium analytics

The price analysis uses `scryfall_cards_clean.csv`. The cleaner keeps a row when both `price_usd` and `price_usd_foil` are present, because those are the fields required for a paired comparison. Missing values in other fields do not remove a row. The analysis calculates descriptive statistics, identifies the ten highest-value nonfoil cards within the matched-price dataset, and creates two charts.

```powershell
python .\clean_scryfall_data.py
python .\analyze_price_premium.py
```

By default, the script reads `scryfall_cards_clean.csv` and saves these files in `analysis_output`:

- `price_premium_summary.csv` — descriptive statistics for nonfoil price, foil price, and foil premium
- `top_value_cards.csv` — the ten highest-value cards by nonfoil USD price
- `missingness_by_field.png` — missing-value counts and percentages in the raw source file
- `price_and_foil_premium_distribution.png` — overlapping nonfoil-versus-foil USD price distributions
- `top_value_cards.png` — nonfoil and foil USD prices for the ten highest-value cards

The chart views cap extreme values at the combined 99th percentile only to keep the plots readable; the summary CSVs retain the original price values. To use another source CSV or output folder:

```powershell
python .\analyze_price_premium.py --input cards.csv --output-dir results
```

## Clean the data

The cleanup script preserves the original scraped CSV and writes a separate analysis file. It collapses irregular whitespace, standardizes price fields as plain decimal values, normalizes set codes and legality values, and removes duplicate Scryfall print IDs. A row is removed only when `price_usd` or `price_usd_foil` is missing, since both prices are required by the paired price analysis. Missing values in other fields remain blank.

The cleaned dataset keeps all original source columns so card names and set information remain available alongside the prices. An optional category lookup for nonblank values is saved separately in `scryfall_category_maps.csv`.

```powershell
python .\clean_scryfall_data.py
```

This reads `scryfall_cards.csv` and creates `scryfall_cards_clean.csv` plus `scryfall_category_maps.csv`. To use different paths:

```powershell
python .\clean_scryfall_data.py --input cards.csv --output cards_clean.csv --mapping-output category_maps.csv
```
