"""Recupere TOUS les noms francais connus de chaque espece de species.csv
(et pas seulement le premier), pour remplir la colonne `autres_noms`.

Une meme espece a souvent plusieurs noms usuels (ex. Scorpaena scrofa :
"Grande rascasse rouge", "Chapon", "Rascasse rouge") ; la recherche de
l'application les prend tous en compte. Deux sources sont croisees :
- GBIF (noms vernaculaires de toutes les checklists, langue "fra") ;
- Wikidata (etiquette francaise + alias francais, P225 = nom scientifique) ;
- WoRMS (noms vernaculaires francais du registre des especes marines).

Si une espece n'avait aucun nom francais (nom vernaculaire = nom
scientifique), le premier nom trouve devient son nom principal. Les noms
deja presents (y compris les noms de plongeurs curates a la main, voir
aliases_plongeurs.csv) ne sont jamais retires.

Usage:
    python scripts/species_db/fetch_french_names.py [--dry-run] [--workers 8]
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

import worms

CATALOG_PATH = Path(__file__).resolve().parents[2] / "src" / "aquabioscope" / "data" / "species.csv"
FIELDNAMES = ["embranchement", "nom_vernaculaire", "nom_scientifique", "regions", "autres_noms"]
ALIAS_SEPARATOR = "|"
GBIF_API = "https://api.gbif.org/v1"
SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIDATA_BATCH = 80
MAX_NAME_LEN = 60
USER_AGENT = "AquaBioScope-species-db/1 (script interne, usage ponctuel)"


def _norm(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", " ".join(name.strip().split()))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _clean(name: str) -> str | None:
    name = " ".join(name.strip().split())
    if not name or len(name) > MAX_NAME_LEN or any(c in name for c in "()[];/|"):
        return None
    return name[0].upper() + name[1:]


def gbif_french_names(session: requests.Session, sci_name: str) -> list[str]:
    try:
        r = session.get(f"{GBIF_API}/species/match", params={"name": sci_name, "strict": "true"}, timeout=20)
        key = r.json().get("usageKey") if r.status_code == 200 else None
        if not key:
            return []
        r = session.get(f"{GBIF_API}/species/{key}/vernacularNames", params={"limit": 200}, timeout=20)
        if r.status_code != 200:
            return []
        return [
            n["vernacularName"] for n in r.json().get("results", [])
            if n.get("language") in ("fra", "fre") and n.get("vernacularName")
        ]
    except (requests.RequestException, ValueError):
        return []


def wikidata_french_names(session: requests.Session, sci_names: list[str]) -> dict[str, list[str]]:
    values = " ".join(f'"{n}"' for n in sci_names if '"' not in n)
    query = f"""
    SELECT ?sciName ?name WHERE {{
      VALUES ?sciName {{ {values} }}
      ?item wdt:P225 ?sciName.
      {{ ?item rdfs:label ?name. }} UNION {{ ?item skos:altLabel ?name. }}
      FILTER(LANG(?name) = "fr")
    }}
    """
    r = session.get(
        SPARQL_URL, params={"query": query, "format": "json"},
        headers={"Accept": "application/sparql-results+json"}, timeout=60,
    )
    r.raise_for_status()
    out: dict[str, list[str]] = {}
    for b in r.json().get("results", {}).get("bindings", []):
        out.setdefault(_norm(b["sciName"]["value"]), []).append(b["name"]["value"])
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--workers", type=int, default=8, help="Requetes GBIF en parallele")
    parser.add_argument("--skip-gbif", action="store_true")
    parser.add_argument("--skip-wikidata", action="store_true")
    parser.add_argument("--skip-worms", action="store_true")
    parser.add_argument(
        "--only", type=Path,
        help="CSV (schema species.csv) : ne traiter que ses especes (ex. celles d'une nouvelle recolte)",
    )
    args = parser.parse_args()

    with args.catalog.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    todo = rows
    if args.only:
        with args.only.open(encoding="utf-8", newline="") as f:
            wanted = {_norm(r["nom_scientifique"]) for r in csv.DictReader(f)}
        todo = [r for r in rows if _norm(r["nom_scientifique"]) in wanted]
    print(f"{len(todo)} especes a traiter sur {len(rows)}")

    found: dict[str, list[str]] = {}  # nom scientifique normalise -> noms francais bruts

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    if not args.skip_wikidata:
        names = [r["nom_scientifique"] for r in todo]
        for i in range(0, len(names), WIKIDATA_BATCH):
            try:
                for k, v in wikidata_french_names(session, names[i : i + WIKIDATA_BATCH]).items():
                    found.setdefault(k, []).extend(v)
            except requests.RequestException as e:
                print(f"  Wikidata lot {i}: erreur ({e}), on saute")
            time.sleep(0.5)
        print(f"Wikidata : noms trouves pour {len(found)} especes")

    if not args.skip_worms:
        records = worms.match_names(session, [r["nom_scientifique"] for r in todo])
        ids = {name: rec["AphiaID"] for name, rec in records.items() if rec.get("AphiaID")}

        def worms_task(item: tuple[str, int]) -> tuple[str, list[str]]:
            s = requests.Session()
            s.headers["User-Agent"] = USER_AGENT
            return _norm(item[0]), worms.french_vernaculars(s, item[1])

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for k, v in pool.map(worms_task, ids.items()):
                found.setdefault(k, []).extend(v)
        print(f"WoRMS : {len(ids)} especes interrogees")

    if not args.skip_gbif:
        def task(sci: str) -> tuple[str, list[str]]:
            s = requests.Session()
            s.headers["User-Agent"] = USER_AGENT
            return _norm(sci), gbif_french_names(s, sci)

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for i, (k, v) in enumerate(pool.map(task, [r["nom_scientifique"] for r in todo]), 1):
                if v:
                    found.setdefault(k, []).extend(v)
                if i % 250 == 0:
                    print(f"  GBIF : {i}/{len(todo)} traitees")

    promoted = enriched = 0
    for row in rows:
        sci_n = _norm(row["nom_scientifique"])
        current = row["nom_vernaculaire"].strip()
        aliases = [a for a in (row.get("autres_noms") or "").split(ALIAS_SEPARATOR) if a.strip()]
        candidates = [c for c in (_clean(n) for n in found.get(sci_n, [])) if c and _norm(c) != sci_n]
        if not candidates:
            row["autres_noms"] = ALIAS_SEPARATOR.join(aliases)
            continue
        if _norm(current) == sci_n:
            row["nom_vernaculaire"] = current = candidates[0]
            promoted += 1
        known = {_norm(current), *(_norm(a) for a in aliases)}
        before = len(aliases)
        for c in candidates:
            if _norm(c) not in known:
                aliases.append(c)
                known.add(_norm(c))
        if len(aliases) > before:
            enriched += 1
        row["autres_noms"] = ALIAS_SEPARATOR.join(aliases)

    print(f"{promoted} especes ont recu un nom francais principal, {enriched} ont gagne des noms alternatifs")
    if args.dry_run:
        print("(dry-run, rien d'ecrit)")
        return
    with args.catalog.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows({k: r.get(k, "") for k in FIELDNAMES} for r in rows)
    print(f"Ecrit dans {args.catalog}")


if __name__ == "__main__":
    sys.exit(main())
