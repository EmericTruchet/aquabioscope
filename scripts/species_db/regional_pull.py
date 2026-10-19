"""Recolte GBIF par zone de plongee : pour chaque region de l'application
(voir aquabioscope.session.REGIONS) et chaque groupe taxonomique, recupere
les especes les plus observees par des naturalistes (iNaturalist et autres
observations humaines) dans la zone, ecarte les especes non marines via
WoRMS, et ecrit un CSV au format species.csv avec la region renseignee.

Fusionne ensuite avec merge_csv.py : les especes deja presentes gagnent
la region (la fusion fait l'union des regions), les nouvelles sont
ajoutees. C'est ce qui permet au filtre par region de l'application de
fonctionner aussi pour la Mer Rouge, les Caraibes, l'Indo-Pacifique...

Les zones sont des rectangles grossiers (format WKT, sens anti-horaire),
decoupes pour ne pas se chevaucher entre regions voisines ; ils incluent
de la terre ferme, d'ou le filtre WoRMS.

Usage:
    python scripts/species_db/regional_pull.py --out scripts/species_db/out_regional.csv
    python scripts/species_db/regional_pull.py --regions mer-rouge --groups Ver --out ...
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from gbif_pull import API as GBIF_API, resolve_species, resolve_vernacular
import worms

FIELDNAMES = ["embranchement", "nom_vernaculaire", "nom_scientifique", "regions", "autres_noms"]
CACHE_PATH = Path(__file__).with_name("cache_regional_pull.json")


def _box(min_x: float, min_y: float, max_x: float, max_y: float) -> str:
    return (
        f"POLYGON(({min_x} {min_y},{max_x} {min_y},{max_x} {max_y},"
        f"{min_x} {max_y},{min_x} {min_y}))"
    )


REGION_GEOMETRIES: dict[str, list[str]] = {
    "mediterranee": [_box(-5.6, 30, 36.5, 46)],
    "atlantique": [_box(-20, 35, -6, 62), _box(-6, 43, -1, 62), _box(-1, 46, 12, 62)],
    "mer-rouge": [_box(32, 12, 44, 30)],
    "caraibes": [_box(-90, 8, -59, 27)],
    "ocean-indien": [_box(35, -35, 80, 11)],
    "indo-pacifique": [_box(90, -25, 160, 25)],
    "pacifique": [_box(160, -30, 180, 30), _box(-180, -30, -92, 30), _box(-92, -30, -77, 7)],
}

# Poissons osseux : dans l'index d'occurrences GBIF, ils n'ont pas de classe
# (classKey vide, la cle 204 "Actinopterygii" ne renvoie rien) ; on passe
# donc par leurs ordres, combines en une seule requete.
BONY_FISH_ORDERS = (
    587,   # Perciformes (labres, girelles, serrans, merous, castagnoles, gobies, blennies...)
    590,   # Scorpaeniformes (rascasses, grondins)
    772,   # Tetraodontiformes (balistes, poissons-ballons, poissons-coffres)
    495,   # Anguilliformes (murenes, congres)
    773,   # Syngnathiformes (hippocampes, syngnathes, poissons-trompettes)
    549,   # Gadiformes (mostelles, tacauds, lieus)
    588,   # Pleuronectiformes (poissons plats)
    499,   # Beryciformes (poissons-ecureuils, poissons-soldats)
    1305,  # Lophiiformes (baudroies, poissons-grenouilles)
    538,   # Clupeiformes (sardines, anchois)
    1067,  # Mugiliformes (mulets)
    497,   # Aulopiformes (poissons-lezards)
    498,   # Beloniformes (orphies, aiguillettes)
    496,   # Atheriniformes (atherines)
    888,   # Zeiformes (saint-pierre)
    1308,  # Ophidiiformes (donzelles)
    1163,  # Gobiesociformes (lepadogasters)
    1106,  # Batrachoidiformes (poissons-crapauds)
    1166,  # Lampriformes
    1162,  # Elopiformes (tarpons)
    1104,  # Albuliformes
)

# (cle(s) GBIF Backbone, embranchement de l'appli, nb d'especes max par region)
GROUPS: list[tuple[int | tuple[int, ...], str, int]] = [
    (BONY_FISH_ORDERS, "Poissons osseux", 350),
    (121, "Poissons cartilagineux", 40),
    (52, "Mollusque", 200),
    (43, "Cnidaire", 120),
    (50, "Echinoderme", 80),
    (105, "Eponge", 60),
    (53, "Bryozoaire", 30),
    (42, "Ver", 60),
    (108, "Ver", 50),        # Platyhelminthes (vers plats, planaires marines)
    (63, "Ver", 15),         # Nemertea
    (74, "Ver", 10),         # Sipuncula
    (51, "Cténophore", 15),
    (229, "Arthropode", 120),  # Malacostraca (crabes, crevettes, homards...)
    (354, "Arthropode", 10),   # Pycnogonida
    (356, "Urochordé", 50),    # Ascidiacea
    (207, "Urochordé", 10),    # Thaliacea (salpes)
    (106, "Végétaux", 50),
    (36, "Végétaux", 30),
    (7073593, "Végétaux", 30),
]
CANDIDATE_FACTOR = 3  # candidats demandes a GBIF par place : beaucoup sont terrestres et seront ecartes
MIN_COUNT = 3


def top_species_keys(
    session: requests.Session, taxon_key: int | tuple[int, ...], geometries: list[str], limit: int,
) -> list[int]:
    keys = taxon_key if isinstance(taxon_key, tuple) else (taxon_key,)
    params: list[tuple[str, str | int]] = [("taxonKey", k) for k in keys] + [
        ("hasCoordinate", "true"), ("occurrenceStatus", "PRESENT"),
        ("basisOfRecord", "HUMAN_OBSERVATION"), ("facet", "speciesKey"),
        ("facetLimit", limit), ("limit", 0),
    ] + [("geometry", g) for g in geometries]
    for attempt in range(3):
        try:
            r = session.get(f"{GBIF_API}/occurrence/search", params=params, timeout=120)
            r.raise_for_status()
            facet = next((f for f in r.json().get("facets", []) if f["field"] == "SPECIES_KEY"), None)
            if not facet:
                return []
            return [int(c["name"]) for c in facet["counts"] if int(c["count"]) >= MIN_COUNT]
        except (requests.RequestException, ValueError):
            time.sleep(5 * (attempt + 1))
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--regions", nargs="*", default=list(REGION_GEOMETRIES))
    parser.add_argument("--groups", nargs="*", help="Embranchements a recolter (defaut : tous)")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    cache: dict = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}
    species_cache: dict[str, dict | None] = cache.setdefault("species", {})  # cle GBIF -> {sci, vern} ou None
    worms_cache: dict[str, bool] = cache.setdefault("non_marine", {})        # nom sci -> non marin ?

    def save_cache() -> None:
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    session = requests.Session()
    session.headers["User-Agent"] = worms.USER_AGENT

    def resolve(key: int) -> tuple[int, dict | None]:
        s = requests.Session()
        s.headers["User-Agent"] = worms.USER_AGENT
        try:
            detail = resolve_species(s, key)
            if not detail or not detail.get("canonicalName"):
                return key, None
            return key, {"sci": detail["canonicalName"], "vern": resolve_vernacular(s, detail["key"]) or ""}
        except requests.RequestException:
            return key, None

    rows: dict[str, dict[str, str]] = {}  # nom sci -> ligne
    groups = [g for g in GROUPS if not args.groups or g[1] in args.groups]
    for region in args.regions:
        for taxon_key, embranchement, top in groups:
            keys = top_species_keys(session, taxon_key, REGION_GEOMETRIES[region], top * CANDIDATE_FACTOR)
            missing = [k for k in keys if str(k) not in species_cache]
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                for k, info in pool.map(resolve, missing):
                    species_cache[str(k)] = info
            infos = [species_cache[str(k)] for k in keys if species_cache.get(str(k))]

            unknown = [i["sci"] for i in infos if i["sci"] not in worms_cache]
            for name, record in worms.match_names(session, unknown).items():
                worms_cache[name] = worms.is_non_marine(record)

            kept = 0
            for info in infos:
                if kept >= top:
                    break
                # Absent de WoRMS (ou lot en erreur, non mis en cache) :
                # sans doute pas une espece marine, on l'ecarte.
                if worms_cache.get(info["sci"], True):
                    continue
                kept += 1
                row = rows.setdefault(info["sci"], {
                    "embranchement": embranchement,
                    "nom_vernaculaire": info["vern"] or info["sci"],
                    "nom_scientifique": info["sci"],
                    "regions": "",
                    "autres_noms": "",
                })
                regions = {r for r in row["regions"].split(",") if r} | {region}
                row["regions"] = ",".join(sorted(regions))
            label = "ordres" if isinstance(taxon_key, tuple) else f"taxon {taxon_key}"
            print(f"{region:15s} {embranchement:22s} ({label}): {len(keys)} candidats, {kept} retenus")
            save_cache()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(sorted(rows.values(), key=lambda r: (r["embranchement"], r["nom_scientifique"])))
    print(f"{len(rows)} especes ecrites dans {args.out}")


if __name__ == "__main__":
    sys.exit(main())
