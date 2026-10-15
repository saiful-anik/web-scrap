"""Create a price-analysis dataset from Scryfall scraper output."""

import argparse
import csv
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path


PRICE_FIELDS = {
    "price_usd",
    "price_eur",
    "price_tix",
    "price_usd_foil",
    "price_eur_foil",
}
ANALYSIS_REQUIRED_FIELDS = {"price_usd", "price_usd_foil"}
CATEGORY_FIELDS = [
    "mana_cost",
    "type_line",
    "power_toughness_or_loyalty",
    "artist",
    "set_code",
    "rarity",
    "language",
    "finishes",
    "legalities",
]


def normalize_text(value):
    """Collapse whitespace while preserving meaningful card text punctuation."""
    return " ".join((value or "").replace("\u00a0", " ").split())


def normalize_price(value):
    """Return a plain decimal string, or an empty value when no price is present."""
    match = re.search(r"\d+(?:\.\d+)?", normalize_text(value).replace(",", ""))
    if not match:
        return ""
    try:
        amount = Decimal(match.group(0))
    except InvalidOperation:
        return ""
    return format(amount.normalize(), "f")


def normalize_legalities(value):
    """Standardize the semicolon-delimited ``format:status`` legality field."""
    entries = []
    for entry in (value or "").split(";"):
        format_name, separator, status = entry.partition(":")
        if not separator or not normalize_text(format_name) or not normalize_text(status):
            continue
        entries.append(
            f"{normalize_text(format_name)}:{normalize_text(status).lower().replace(' ', '_')}"
        )
    return "; ".join(entries)


def clean_row(row):
    """Normalize one raw scraper row before validation and encoding."""
    cleaned = {field: normalize_text(value) for field, value in row.items()}
    cleaned["set_code"] = cleaned.get("set_code", "").upper()
    cleaned["legalities"] = normalize_legalities(cleaned.get("legalities", ""))
    for field in PRICE_FIELDS:
        if field in cleaned:
            cleaned[field] = normalize_price(cleaned[field])
    return cleaned


def category_mappings(rows):
    """Create optional lookup codes without treating blank categories as a value."""
    return {
        field: {value: index for index, value in enumerate(
            sorted({row[field] for row in rows if row.get(field, "")}), start=1
        )}
        for field in CATEGORY_FIELDS
    }


def main():
    parser = argparse.ArgumentParser(
        description="Create a Scryfall price-analysis CSV, requiring only the two USD price fields."
    )
    parser.add_argument("--input", type=Path, default=Path("scryfall_cards.csv"))
    parser.add_argument("--output", type=Path, default=Path("scryfall_cards_clean.csv"))
    parser.add_argument("--mapping-output", type=Path, default=Path("scryfall_category_maps.csv"))
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"input file does not exist: {args.input}")
    if args.input.resolve() == args.output.resolve():
        parser.error("output must be different from the input file")

    with args.input.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            parser.error("input file must contain a header row")
        missing = ANALYSIS_REQUIRED_FIELDS - set(reader.fieldnames)
        if missing:
            parser.error(f"input is missing required columns: {', '.join(sorted(missing))}")

        analysis_rows, skipped_missing_price, skipped_duplicate = [], 0, 0
        seen = set()
        for row in reader:
            cleaned = clean_row(row)
            card_id = cleaned["scryfall_id"]
            # Price analysis needs both USD prices for a valid pairwise comparison.
            if any(not cleaned.get(field, "") for field in ANALYSIS_REQUIRED_FIELDS):
                skipped_missing_price += 1
                continue
            if card_id and card_id in seen:
                skipped_duplicate += 1
                continue
            if card_id:
                seen.add(card_id)
            analysis_rows.append(cleaned)

    mappings = category_mappings(analysis_rows)
    with args.output.open("w", encoding="utf-8-sig", newline="") as destination:
        # Keep every source column so analysis results can be traced back to cards.
        writer = csv.DictWriter(destination, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(analysis_rows)

    with args.mapping_output.open("w", encoding="utf-8-sig", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=["column", "code", "value"])
        writer.writeheader()
        for field in CATEGORY_FIELDS:
            for value, code in mappings[field].items():
                writer.writerow({"column": field, "code": code, "value": value})

    print(
        f"Saved {len(analysis_rows):,} rows with both USD prices to {args.output}; "
        f"saved optional category mappings to {args.mapping_output}; "
        f"skipped {skipped_missing_price:,} rows missing either USD price and "
        f"{skipped_duplicate:,} duplicate Scryfall IDs"
    )


if __name__ == "__main__":
    main()
