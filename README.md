# Scryfall HTML Card Scraper

This university project extracts data from Scryfall's public HTML pages—not from its API or JSON responses.

For each Magic: The Gathering card, it collects:

- `name` — from the HTML search-result card
- `image_url` — from the HTML image element
- `price_usd` — from the HTML card-detail page
- `card_url` — source detail-page URL

## Run

```powershell
python -m pip install -r .\requirements.txt
python .\scrape_scryfall_html.py --target 2000
```

Scryfall search pages display 60 cards at a time. The scraper follows those HTML result pages, then visits each card's public HTML detail page to read its visible USD price. It logs progress every 25 saved cards.

The output file is `scryfall_cards.csv`. Every run starts from the beginning and creates a fresh CSV.

Use a different output file if needed:

```powershell
python .\scrape_scryfall_html.py --target 2200 --output cards.csv
```
