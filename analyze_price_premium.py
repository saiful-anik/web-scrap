"""Analyze card prices and foil premiums from the scraped Scryfall dataset."""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PRICE_COLUMNS = ["price_usd", "price_usd_foil"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Create price and foil-premium summaries and charts.")
    parser.add_argument("--input", type=Path, default=Path("scryfall_cards.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("analysis_output"))
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error(f"input file does not exist: {args.input}")

    data = pd.read_csv(args.input)
    for column in PRICE_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["foil_premium_usd"] = data["price_usd_foil"] - data["price_usd"]
    data["foil_premium_percent"] = (data["foil_premium_usd"] / data["price_usd"]) * 100
    args.output_dir.mkdir(parents=True, exist_ok=True)

    summary = data[["price_usd", "price_usd_foil", "foil_premium_usd", "foil_premium_percent"]].describe().T
    summary.to_csv(args.output_dir / "price_premium_summary.csv")

    top_cards = data[["name", "set_code", "rarity", "price_usd", "price_usd_foil", "foil_premium_usd"]]
    top_cards = top_cards.sort_values("price_usd", ascending=False).head(10)
    top_cards.to_csv(args.output_dir / "top_value_cards.csv", index=False)

    nonfoil = data["price_usd"].dropna()
    foil = data["price_usd_foil"].dropna()
    price_cap = pd.concat([nonfoil, foil]).quantile(0.99)

    figure, axis = plt.subplots(figsize=(10, 5.5))
    axis.hist(
        [nonfoil.clip(upper=price_cap), foil.clip(upper=price_cap)],
        bins=35,
        color=["#1F4E79", "#ED7D31"],
        alpha=0.65,
        label=["Nonfoil USD", "Foil USD"],
        edgecolor="white",
    )
    axis.set_title("USD Price Distribution: Nonfoil vs Foil")
    axis.set_xlabel("USD price (both series capped at 99th percentile)")
    axis.set_ylabel("Number of cards")
    axis.legend()
    figure.tight_layout()
    figure.savefig(args.output_dir / "price_and_foil_premium_distribution.png", dpi=180)
    plt.close(figure)

    top_for_chart = top_cards.sort_values("price_usd")
    labels = top_for_chart["name"] + " (" + top_for_chart["set_code"].fillna("?") + ")"
    figure, axis = plt.subplots(figsize=(9, 6))
    positions = np.arange(len(top_for_chart))
    axis.barh(positions - 0.2, top_for_chart["price_usd"], height=0.38, color="#ED7D31", label="Nonfoil USD")
    axis.barh(positions + 0.2, top_for_chart["price_usd_foil"], height=0.38, color="#5B9BD5", label="Foil USD")
    axis.set_yticks(positions, labels)
    axis.set_title("Top 10 Cards by Nonfoil USD Price")
    axis.set_xlabel("USD price")
    axis.set_ylabel("Card")
    axis.legend()
    figure.tight_layout()
    figure.savefig(args.output_dir / "top_value_cards.png", dpi=180)
    plt.close(figure)

    print(f"Analyzed {len(data):,} records. Saved price summaries and charts to {args.output_dir}.")


if __name__ == "__main__":
    main()
