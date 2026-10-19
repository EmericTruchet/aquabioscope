"""Retire de species.csv les especes que WoRMS classe comme non marines,
ramenees par d'anciennes recoltes GBIF mondiales sans filtre de milieu :
- les especes terrestres (escargots, limaces, lombrics, cloportes...) ;
- les especes d'eau douce (beaucoup de poissons d'aquarium observes en
  France via iNaturalist, d'ou des regions trompeuses), SAUF celles de
  eau_douce_lacs.txt : faune et flore couramment vues en plongee en lac ou
  en gravière (perche, brochet, ecrevisses...).

Les especes introuvables dans WoRMS sont conservees (prudence : faute de
frappe, synonyme recent...) et simplement listees pour verification.

Usage:
    python scripts/species_db/worms_filter.py [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import requests

import worms

KEEP_FRESHWATER_PATH = Path(__file__).with_name("eau_douce_lacs.txt")
CATALOG_PATH = Path(__file__).resolve().parents[2] / "src" / "aquabioscope" / "data" / "species.csv"
FIELDNAMES = ["embranchement", "nom_vernaculaire", "nom_scientifique", "regions", "autres_noms"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    args = parser.parse_args()

    with args.catalog.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    session = requests.Session()
    session.headers["User-Agent"] = worms.USER_AGENT
    records = worms.match_names(session, [r["nom_scientifique"] for r in rows])
    keep_freshwater = {
        line.strip().casefold() for line in KEEP_FRESHWATER_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }

    kept, removed, unknown = [], [], []
    for row in rows:
        record = records.get(row["nom_scientifique"])
        if record is None:
            unknown.append(row)
            kept.append(row)
        elif worms.is_non_marine(record) and row["nom_scientifique"].strip().casefold() not in keep_freshwater:
            removed.append(row)
        else:
            kept.append(row)

    for row in removed:
        print(f"  retire : {row['embranchement']} - {row['nom_vernaculaire']} ({row['nom_scientifique']})")
    print(f"{len(removed)} especes non marines retirees, {len(unknown)} introuvables dans WoRMS (conservees)")
    for row in unknown:
        print(f"  introuvable : {row['nom_scientifique']}")

    if args.dry_run:
        print("(dry-run, rien d'ecrit)")
        return
    with args.catalog.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows({k: r.get(k, "") for k in FIELDNAMES} for r in kept)
    print(f"{len(kept)} especes ecrites dans {args.catalog}")


if __name__ == "__main__":
    sys.exit(main())
