"""Scrape structured Magic card data from Scryfall's public HTML pages."""

import argparse
import csv
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import unquote_plus

import requests
from bs4 import BeautifulSoup


SEARCH_URL = "https://scryfall.com/search?q=game%3Apaper&page={}"
HEADERS = {"User-Agent": "UniversityHTMLScraper/1.0 (educational project)"}

FIELDNAMES = [
    "id",
    "name",
    "scryfall_id",
    "oracle_id",
    "mana_cost",
    "type_line",
    "oracle_text",
    "flavor_text",
    "power_toughness_or_loyalty",
    "artist",
    "set_name",
    "set_code",
    "set_url",
    "collector_number",
    "rarity",
    "language",
    "finishes",
    "price_usd",
    "price_eur",
    "price_tix",
    "price_usd_foil",
    "price_eur_foil",
    "legalities",
    "image_url",
    "card_url",
]


def soup(session, url):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def detail_soup(url, delay):
    """Fetch one public card detail page after a small per-worker delay."""
    if delay:
        time.sleep(delay)
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def text(element):
    """Return normalized visible text, or an empty string for a missing element."""
    return element.get_text(" ", strip=True) if element else ""


def price(element):
    """Extract a machine-friendly decimal price from a visible price link/button."""
    match = re.search(r"\d+(?:\.\d+)?", text(element).replace(",", ""))
    return match.group(0) if match else ""


def current_printing(details):
    """Extract set and printing data from Scryfall's visible current-printing block."""
    current_set = details.select_one(".prints-current-set")
    set_details = details.select_one(".prints-current-set-details")
    detail_parts = [part.strip() for part in text(set_details).split("·") if part.strip()]

    set_name = text(details.select_one(".prints-current-set-name"))
    set_url = current_set.get("href", "") if current_set else ""
    set_code = ""
    code_match = re.search(r"\(([A-Za-z0-9]+)\)", set_name)
    if code_match:
        set_code = code_match.group(1).upper()
        set_name = re.sub(r"\s*\([A-Za-z0-9]+\)\s*$", "", set_name).strip()

    return {
        "set_name": set_name,
        "set_code": set_code,
        "set_url": set_url,
        "collector_number": detail_parts[0].lstrip("#") if detail_parts else "",
        "rarity": detail_parts[1] if len(detail_parts) > 1 else "",
        "language": detail_parts[2] if len(detail_parts) > 2 else "",
        "finishes": detail_parts[3] if len(detail_parts) > 3 else "",
    }


def foil_price(details, currency):
    """Read the separately displayed foil purchase price, when Scryfall shows one."""
    for link in details.select("a"):
        label = text(link).lower()
        if "buy foil" in label and currency in label:
            return price(link)
    return ""


def legalities(details):
    """Serialize the visible format-legalities list into one spreadsheet-friendly field."""
    values = []
    for item in details.select(".card-legality-item"):
        format_name = text(item.select_one("dt"))
        status = text(item.select_one("dd")).lower()
        if not status:
            continue
        values.append(f"{format_name}:{status.replace(' ', '_')}")
    return "; ".join(values)


def oracle_id(details):
    """Read the Oracle ID embedded in Scryfall's public all-printings search link."""
    prints_link = next((link for link in details.select("a[href]") if text(link) == "Prints"), None)
    if not prints_link:
        return ""
    match = re.search(r"oracleid:([0-9a-f-]{36})", unquote_plus(prints_link["href"]), re.I)
    return match.group(1) if match else ""


def card_record(card, details, saved):
    """Build one normalized CSV record from a search-result card and detail page."""
    image = card.select_one("img")
    name = card.select_one(".card-grid-item-invisible-label")
    high_res_image = details.select_one('meta[property="og:image"]')
    artist = text(details.select_one(".card-text-artist"))
    if artist.lower().startswith("illustrated by "):
        artist = artist[len("illustrated by "):].strip()

    record = {
        "id": saved,
        "name": text(name),
        "scryfall_id": (details.select_one("[data-card-id]") or {}).get("data-card-id", ""),
        "oracle_id": oracle_id(details),
        "mana_cost": text(details.select_one(".card-text-mana-cost")),
        "type_line": text(details.select_one(".card-text-type-line")),
        "oracle_text": text(details.select_one(".card-text-oracle")),
        "flavor_text": text(details.select_one(".card-text-flavor")),
        "power_toughness_or_loyalty": text(details.select_one(".card-text-stats")),
        "artist": artist,
        "price_usd": price(details.select_one("a.currency-usd")),
        "price_eur": price(details.select_one("a.currency-eur")),
        "price_tix": price(details.select_one("a.currency-tix")),
        "price_usd_foil": foil_price(details, "tcgplayer"),
        "price_eur_foil": foil_price(details, "cardmarket"),
        "legalities": legalities(details),
        "image_url": high_res_image.get("content", "") if high_res_image else image.get("src", ""),
        "card_url": card.get("href", ""),
    }
    record.update(current_printing(details))
    return record


def main():
    parser = argparse.ArgumentParser(description="Scrape data from Scryfall HTML pages.")
    parser.add_argument("--target", type=int, default=2000)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--workers", type=int, default=4, help="Concurrent detail-page requests (default: 4)")
    parser.add_argument("--output", type=Path, default=Path("scryfall_cards.csv"))
    args = parser.parse_args()
    if args.target < 1 or args.delay < 0 or args.workers < 1:
        parser.error("target and workers must be positive, and delay cannot be negative")

    session = requests.Session()
    session.headers.update(HEADERS)
    saved, page, seen = 0, 1, set()
    with args.output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            while saved < args.target:
                try:
                    cards = soup(session, SEARCH_URL.format(page)).select("a.card-grid-item-card")
                except requests.RequestException as error:
                    print(f"Search page {page} failed: {error}")
                    break
                if not cards:
                    break
                print(f"Search page {page} | saved: {saved:,}/{args.target:,}")
                futures = {}
                for card in cards:
                    url = card.get("href", "")
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    futures[executor.submit(detail_soup, url, args.delay)] = (card, url)
                    if len(futures) == args.target - saved:
                        break
                for future in as_completed(futures):
                    card, url = futures[future]
                    try:
                        details = future.result()
                    except requests.RequestException as error:
                        print(f"Skipping {url}: {error}")
                        continue
                    saved += 1
                    writer.writerow(card_record(card, details, saved))
                    if saved % 25 == 0:
                        file.flush()
                        print(f"Saved: {saved:,}/{args.target:,}")
                page += 1
    print(f"Saved {saved:,} rows to {args.output}")


if __name__ == "__main__":
    main()
