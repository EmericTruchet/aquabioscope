"""Complete les noms vernaculaires manquants dans species.csv via Wikidata.

Wikidata (CC0, projet cousin structure de Wikipedia) associe a chaque taxon
(propriete P225 = nom scientifique) une etiquette dans chaque langue, tiree
des liens interwiki vers Wikipedia. On l'utilise ici uniquement pour les
lignes ou le nom vernaculaire est actuellement identique au nom scientifique
(= aucun nom francais connu), sans toucher aux noms deja renseignes (GBIF ou
curation manuelle) meme s'ils sont en anglais.

Usage:
    python scripts/species_db/wikidata_backfill.py [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import requests

CATALOG_PATH = Path(__file__).resolve().parents[2] / "src" / "aquabioscope" / "data" / "species.csv"
FIELDNAMES = ["embranchement", "nom_vernaculaire", "nom_scientifique", "regions"]
SPARQL_URL = "https://query.wikidata.org/sparql"
BATCH_SIZE = 80


def _norm(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


def query_batch(session: requests.Session, names: list[str]) -> dict[str, str]:
    values = " ".join(f'"{n}"' for n in names)
    query = f"""
    SELECT ?sciName ?itemLabel WHERE {{
      VALUES ?sciName {{ {values} }}
      ?item wdt:P225 ?sciName.
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "fr". }}
    }}
    """
    r = session.get(
        SPARQL_URL,
        params={"query": query, "format": "json"},
        headers={"Accept": "application/sparql-results+json"},
        timeout=30,
    )
    r.raise_for_status()
    out: dict[str, str] = {}
    for b in r.json().get("results", {}).get("bindings", []):
        sci = b.get("sciName", {}).get("value")
        label = b.get("itemLabel", {})
        # Le label n'est en francais que si le SERVICE a trouve une etiquette fr ;
        # sinon wikibase:label renvoie l'IRI de l'entite (pas de xml:lang) qu'on ignore.
        if sci and label.get("xml:lang") == "fr" and _norm(label["value"]) != _norm(sci):
            out[_norm(sci)] = label["value"]
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    args = parser.parse_args()

    with args.catalog.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    todo = [r for r in rows if _norm(r["nom_vernaculaire"]) == _norm(r["nom_scientifique"])]
    print(f"{len(todo)} especes sans nom francais connu, interrogation de Wikidata...")

    session = requests.Session()
    session.headers["User-Agent"] = "AquaBioScope-species-db/1 (script interne, usage ponctuel)"

    found_total = 0
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i : i + BATCH_SIZE]
        names = [r["nom_scientifique"] for r in batch]
        try:
            labels = query_batch(session, names)
        except requests.RequestException as e:
            print(f"  lot {i}: erreur reseau ({e}), on saute")
            continue
        for row in batch:
            label = labels.get(_norm(row["nom_scientifique"]))
            if label:
                row["nom_vernaculaire"] = label
                found_total += 1
        print(f"  {min(i + BATCH_SIZE, len(todo))}/{len(todo)} traitees, {found_total} noms trouves jusqu'ici")
        time.sleep(0.5)

    print(f"Total : {found_total} noms francais recuperes via Wikidata")

    if args.dry_run:
        print("(dry-run, rien d'ecrit)")
        return

    with args.catalog.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Ecrit dans {args.catalog}")


if __name__ == "__main__":
    sys.exit(main())
