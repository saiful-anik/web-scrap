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

## Clean the data

The cleanup script preserves the original scraped CSV and writes a separate, analysis-ready file. It collapses irregular whitespace, standardizes price fields as plain decimal values, normalizes set codes and legality values, removes duplicate Scryfall print IDs, and drops every row that has a missing value in any source column.

The cleaned dataset does not repeat categorical text. It replaces each repeated category with a numeric ID, so every `Common` rarity has the same `rarity_id`, every set has the same `set_code_id`, and so on. The code-to-value lookup is saved separately in `scryfall_category_maps.csv`.

```powershell
python .\clean_scryfall_data.py
```

This reads `scryfall_cards.csv` and creates `scryfall_cards_clean.csv` plus `scryfall_category_maps.csv`. To use different paths:

```powershell
python .\clean_scryfall_data.py --input cards.csv --output cards_clean.csv --mapping-output category_maps.csv
```
