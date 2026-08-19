"""Scrape Scryfall HTML card names, USD prices, and image URLs."""

import argparse
import csv
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup


SEARCH_URL = "https://scryfall.com/search?q=game%3Apaper&page={}"
HEADERS = {"User-Agent": "UniversityHTMLScraper/1.0 (educational project)"}


def soup(session, url):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def main():
    parser = argparse.ArgumentParser(description="Scrape data from Scryfall HTML pages.")
    parser.add_argument("--target", type=int, default=2000)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--output", type=Path, default=Path("scryfall_cards.csv"))
    args = parser.parse_args()
    if args.target < 1 or args.delay < 0:
        parser.error("target must be positive and delay cannot be negative")

    session = requests.Session()
    session.headers.update(HEADERS)
    saved, page, seen = 0, 1, set()
    with args.output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["id", "name", "price_usd", "image_url", "card_url"])
        writer.writeheader()
        while saved < args.target:
            try:
                cards = soup(session, SEARCH_URL.format(page)).select("a.card-grid-item-card")
            except requests.RequestException as error:
                print(f"Search page {page} failed: {error}")
                break
            if not cards:
                break
            print(f"Search page {page} | saved: {saved:,}/{args.target:,}")
            for card in cards:
                image, name = card.select_one("img"), card.select_one(".card-grid-item-invisible-label")
                url = card.get("href", "")
                if not (image and name and url) or url in seen:
                    continue
                try:
                    price = soup(session, url).select_one("a.currency-usd")
                except requests.RequestException as error:
                    print(f"Skipping {url}: {error}")
                    continue
                if not price:
                    continue
                saved += 1
                seen.add(url)
                writer.writerow({"id": saved, "name": name.get_text(" ", strip=True), "price_usd": price.get_text(" ", strip=True), "image_url": image.get("src", ""), "card_url": url})
                if saved % 25 == 0:
                    file.flush()
                    print(f"Saved: {saved:,}/{args.target:,}")
                if saved == args.target:
                    break
                time.sleep(args.delay)
            page += 1
    print(f"Saved {saved:,} rows to {args.output}")


if __name__ == "__main__":
    main()
