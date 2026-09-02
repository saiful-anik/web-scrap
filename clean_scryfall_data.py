"""Create a complete-case, category-encoded dataset from Scryfall scraper output."""

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
REQUIRED_FIELDS = {"name", "scryfall_id", "card_url"}
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
    """Assign repeatable one-based integer codes to every categorical value."""
    return {
        field: {value: index for index, value in enumerate(sorted({row[field] for row in rows}), start=1)}
        for field in CATEGORY_FIELDS
    }


def encoded_row(row, mappings, row_id):
    """Return the numeric analysis record; raw categorical text stays in the lookup file."""
    record = {"id": row_id}
    for field in PRICE_FIELDS:
        record[field] = row[field]
    for field in CATEGORY_FIELDS:
        record[f"{field}_id"] = mappings[field][row[field]]
    return record


def main():
    parser = argparse.ArgumentParser(description="Create a complete-case, encoded Scryfall analysis CSV.")
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
        missing = REQUIRED_FIELDS - set(reader.fieldnames)
        if missing:
            parser.error(f"input is missing required columns: {', '.join(sorted(missing))}")

        complete_rows, skipped, seen = [], 0, set()
        for row in reader:
            cleaned = clean_row(row)
            card_id = cleaned["scryfall_id"]
            # Data-science output uses complete cases only: any blank input field removes the row.
            if any(not cleaned.get(field, "") for field in reader.fieldnames) or card_id in seen:
                skipped += 1
                continue
            seen.add(card_id)
            complete_rows.append(cleaned)

    mappings = category_mappings(complete_rows)
    encoded_fields = ["id", *sorted(PRICE_FIELDS), *(f"{field}_id" for field in CATEGORY_FIELDS)]
    with args.output.open("w", encoding="utf-8-sig", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=encoded_fields)
        writer.writeheader()
        for row_id, row in enumerate(complete_rows, start=1):
            writer.writerow(encoded_row(row, mappings, row_id))

    with args.mapping_output.open("w", encoding="utf-8-sig", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=["column", "code", "value"])
        writer.writeheader()
        for field in CATEGORY_FIELDS:
            for value, code in mappings[field].items():
                writer.writerow({"column": field, "code": code, "value": value})

    print(
        f"Saved {len(complete_rows):,} complete, encoded rows to {args.output}; "
        f"saved category mappings to {args.mapping_output}; skipped {skipped:,} incomplete or duplicate rows"
    )


if __name__ == "__main__":
    main()
