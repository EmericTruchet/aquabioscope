"""Recolte des especes marines depuis GBIF (echelle mondiale, sans decoupage
geographique : voir discussion projet — la recherche predictive de l'appli
filtre deja par nom, la region n'est qu'une pre-filtration secondaire).

Pour un groupe taxonomique donne (cle GBIF Backbone d'un phylum ou d'une
classe), recupere les especes les plus frequemment observees (facet sur
speciesKey, occurrences avec coordonnees, observations naturalistes), puis
resout le nom vernaculaire (francais, sinon anglais, sinon nom scientifique)
et ecrit un CSV au format species.csv (regions="" — a fusionner puis a
completer/filtrer manuellement si besoin, voir merge_csv.py).

Usage:
    python scripts/species_db/gbif_pull.py --taxon-key 43 --embranchement Cnidaire \
        --out scripts/species_db/out_cnidaires.csv --top 200 --min-count 30

Cles GBIF Backbone utiles (deja resolues pour ce projet) :
    Mollusca=52 Cnidaria=43 Echinodermata=50 Porifera=105 Bryozoa=53
    Annelida=42 Ctenophora=51 Malacostraca=229 (classe, crustaces)
    Rhodophyta=106 Chlorophyta=36 Phaeophyceae=7073593 (algues)
Les poissons (osseux/cartilagineux) ne sont PAS couverts ici : le classement
GBIF Backbone des poissons s'est revele trop incoherent (cf. commit
"Tentative GBIF" du 2026-09-15) ; la couverture actuelle vient d'iNaturalist.
Les tetrapodes marins (mammiferes, tortues, serpents marins) sont a curer a
la main (voir seed_tetrapods.csv) : trop peu d'occurrences/too de bruit
taxonomique pour une recolte fiable par popularite.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import requests

API = "https://api.gbif.org/v1"
FIELDNAMES = ["embranchement", "nom_vernaculaire", "nom_scientifique", "regions"]


def fetch_top_species(session: requests.Session, taxon_key: int, top: int, min_count: int) -> list[tuple[int, int]]:
    params = {
        "taxonKey": taxon_key,
        "hasCoordinate": "true",
        "occurrenceStatus": "PRESENT",
        "basisOfRecord": "HUMAN_OBSERVATION",
        "facet": "speciesKey",
        "facetLimit": top,
        "limit": 0,
    }
    r = session.get(f"{API}/occurrence/search", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    facet = next((f for f in data.get("facets", []) if f["field"] == "SPECIES_KEY"), None)
    if not facet:
        return []
    out = []
    for c in facet["counts"]:
        count = int(c["count"])
        if count < min_count:
            continue
        try:
            out.append((int(c["name"]), count))
        except ValueError:
            continue
    return out


def resolve_species(session: requests.Session, key: int) -> dict | None:
    r = session.get(f"{API}/species/{key}", timeout=15)
    if r.status_code != 200:
        return None
    data = r.json()
    seen = {key}
    while data.get("taxonomicStatus") not in ("ACCEPTED", None) and data.get("acceptedKey") not in (None, *seen):
        seen.add(data["acceptedKey"])
        r = session.get(f"{API}/species/{data['acceptedKey']}", timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
    if data.get("rank") != "SPECIES":
        return None
    return data


def resolve_vernacular(session: requests.Session, key: int) -> str | None:
    r = session.get(f"{API}/species/{key}/vernacularNames", timeout=15)
    if r.status_code != 200:
        return None
    names = r.json().get("results", [])
    for lang in ("fra", "fre"):
        for n in names:
            if n.get("language") == lang and n.get("vernacularName"):
                return n["vernacularName"]
    for n in names:
        if n.get("language") == "eng" and n.get("vernacularName"):
            return n["vernacularName"]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--taxon-key", type=int, required=True, help="Cle GBIF Backbone du phylum/classe")
    parser.add_argument("--embranchement", required=True, help="Libelle francais a assigner (ex: Cnidaire)")
    parser.add_argument("--out", type=Path, required=True, help="CSV de sortie")
    parser.add_argument("--top", type=int, default=200, help="Nb max d'especes candidates (par frequence d'observation)")
    parser.add_argument("--min-count", type=int, default=30, help="Seuil minimal d'occurrences pour retenir une espece")
    parser.add_argument("--delay", type=float, default=0.1, help="Delai (s) entre deux appels API")
    args = parser.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = "AquaBioScope-species-db/1 (script interne, usage ponctuel)"

    candidates = fetch_top_species(session, args.taxon_key, args.top, args.min_count)
    print(f"{len(candidates)} especes candidates (>= {args.min_count} occurrences)")

    rows: list[dict[str, str]] = []
    for i, (key, count) in enumerate(candidates, 1):
        detail = resolve_species(session, key)
        time.sleep(args.delay)
        if not detail or not detail.get("canonicalName"):
            continue
        sci_name = detail["canonicalName"]
        vernacular = resolve_vernacular(session, detail["key"])
        time.sleep(args.delay)
        rows.append(
            {
                "embranchement": args.embranchement,
                "nom_vernaculaire": vernacular or sci_name,
                "nom_scientifique": sci_name,
                "regions": "",
            }
        )
        if i % 25 == 0:
            print(f"  {i}/{len(candidates)} traitees...")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} especes ecrites dans {args.out}")


if __name__ == "__main__":
    sys.exit(main())
