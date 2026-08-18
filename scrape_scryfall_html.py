"""Scrape Scryfall card data directly from its public HTML pages.

The script does not use the Scryfall API: it parses search-result HTML and
then the linked card-detail HTML pages for the displayed USD price.
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup


BASE_SEARCH_URL = "https://scryfall.com/search?q=game%3Apaper&page={}"
HEADERS = {"User-Agent": "UniversityHTMLScraper/1.0 (educational project)"}


def text(node: object) -> str:
    return node.get_text(" ", strip=True) if node else ""  # type: ignore[union-attr]


def soup_from(session: requests.Session, url: str) -> BeautifulSoup:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def search_cards(session: requests.Session, page: int) -> list[dict[str, str]]:
    """Read card name, image, and detail URL from one visible results page."""
    soup = soup_from(session, BASE_SEARCH_URL.format(page))
    cards: list[dict[str, str]] = []
    for card in soup.select("a.card-grid-item-card"):
        image = card.select_one("img")
        url = card.get("href", "")
        name = text(card.select_one(".card-grid-item-invisible-label"))
        if image and url and name:
            cards.append({"name": name, "image_url": image.get("src", ""), "card_url": url})
    return cards


def usd_price(session: requests.Session, card_url: str) -> str:
    """Extract the first displayed USD price from a card-detail HTML page."""
    soup = soup_from(session, card_url)
    price = soup.select_one("a.currency-usd")
    return text(price)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Scryfall HTML card names, USD prices, and image URLs.")
    parser.add_argument("--target", type=int, default=2_000, help="Rows to save (default: 2000)")
    parser.add_argument("--delay", type=float, default=0.2, help="Seconds between detail-page requests (default: 0.2)")
    parser.add_argument("--output", type=Path, default=Path("scryfall_cards.csv"))
    args = parser.parse_args()
    if args.target < 1 or args.delay < 0:
        parser.error("target must be positive and delay cannot be negative")

    page = 1
    saved_urls: set[str] = set()
    session = requests.Session()
    session.headers.update(HEADERS)

    with args.output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["id", "name", "price_usd", "image_url", "card_url"])
        writer.writeheader()

        while len(saved_urls) < args.target:
            try:
                cards = search_cards(session, page)
            except requests.RequestException as error:
                print(f"Search page {page} failed: {error}")
                break
            if not cards:
                print(f"No more result cards found after search page {page}.")
                break

            print(f"Search page {page} | cards found: {len(cards)} | saved: {len(saved_urls):,}/{args.target:,}")
            for index, card in enumerate(cards):
                if card["card_url"] in saved_urls:
                    continue
                try:
                    price = usd_price(session, card["card_url"])
                except requests.RequestException as error:
                    print(f"Skipping failed card page: {card['name']} ({error})")
                    continue
                if price:
                    writer.writerow({"id": len(saved_urls) + 1, **card, "price_usd": price})
                    saved_urls.add(card["card_url"])
                if len(saved_urls) % 25 == 0:
                    file.flush()
                    print(f"Saved: {len(saved_urls):,}/{args.target:,}")
                if len(saved_urls) >= args.target:
                    break
                time.sleep(args.delay)

            page += 1

    if len(saved_urls) >= args.target:
        print(f"Target reached: {len(saved_urls):,} rows saved to {args.output}")
    else:
        print(f"No more cards found. Saved {len(saved_urls):,} rows to {args.output}")


if __name__ == "__main__":
    main()
