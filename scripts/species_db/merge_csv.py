"""Fusionne un ou plusieurs CSV d'especes (meme schema que species.csv) dans
la base embarquee de l'application, en dedoublonnant par nom scientifique et
en fusionnant les regions et les autres noms (colonne `autres_noms`,
separes par "|").

Une ligne source sans embranchement (ex. aliases_plongeurs.csv) ne fait
qu'enrichir une espece existante : elle n'est jamais ajoutee seule.

Usage:
    python scripts/species_db/merge_csv.py fichier1.csv [fichier2.csv ...]
    python scripts/species_db/merge_csv.py --dry-run fichier1.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parents[2] / "src" / "aquabioscope" / "data" / "species.csv"
FIELDNAMES = ["embranchement", "nom_vernaculaire", "nom_scientifique", "regions", "autres_noms"]


def _norm_sci(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


ALIAS_SEPARATOR = "|"


def _split_aliases(value: str | None) -> list[str]:
    return [a.strip() for a in (value or "").split(ALIAS_SEPARATOR) if a.strip()]


def _merge_aliases(existing: dict[str, str], new_names: list[str]) -> bool:
    aliases = _split_aliases(existing.get("autres_noms"))
    known = {_norm_sci(existing["nom_vernaculaire"]), *(_norm_sci(a) for a in aliases)}
    changed = False
    for name in new_names:
        if name and _norm_sci(name) not in known and _norm_sci(name) != _norm_sci(existing["nom_scientifique"]):
            aliases.append(name)
            known.add(_norm_sci(name))
            changed = True
    existing["autres_noms"] = ALIAS_SEPARATOR.join(aliases)
    return changed


def merge(catalog_rows: list[dict[str, str]], new_rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], int, int]:
    by_sci = {_norm_sci(r["nom_scientifique"]): r for r in catalog_rows}
    added = 0
    updated = 0
    for row in new_rows:
        key = _norm_sci(row["nom_scientifique"])
        new_regions = {r.strip() for r in row["regions"].split(",") if r.strip()}
        if key in by_sci:
            existing = by_sci[key]
            existing_regions = {r.strip() for r in existing["regions"].split(",") if r.strip()}
            merged_regions = existing_regions | new_regions
            changed = merged_regions != existing_regions
            existing["regions"] = ",".join(sorted(merged_regions))
            new_vern = (row.get("nom_vernaculaire") or "").strip()
            if new_vern and _norm_sci(existing["nom_vernaculaire"]) == key and _norm_sci(new_vern) != key:
                # l'existante n'avait que son nom scientifique : la source apporte un vrai nom
                existing["nom_vernaculaire"] = new_vern
                changed = True
            changed |= _merge_aliases(existing, [new_vern, *_split_aliases(row.get("autres_noms"))])
            updated += changed
        elif not (row.get("embranchement") or "").strip():
            continue
        else:
            catalog_rows.append(
                {
                    "embranchement": row["embranchement"],
                    "nom_vernaculaire": row["nom_vernaculaire"] or row["nom_scientifique"],
                    "nom_scientifique": row["nom_scientifique"],
                    "regions": ",".join(sorted(new_regions)),
                    "autres_noms": ALIAS_SEPARATOR.join(_split_aliases(row.get("autres_noms"))),
                }
            )
            by_sci[key] = catalog_rows[-1]
            added += 1
    return catalog_rows, added, updated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+", type=Path, help="CSV a fusionner dans species.csv")
    parser.add_argument("--dry-run", action="store_true", help="N'ecrit rien, affiche juste le bilan")
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH, help="Chemin du species.csv cible")
    args = parser.parse_args()

    catalog_rows = load_rows(args.catalog)
    total_added = total_updated = 0
    for source in args.sources:
        new_rows = load_rows(source)
        catalog_rows, added, updated = merge(catalog_rows, new_rows)
        print(f"{source.name}: {added} ajoutees, {updated} mises a jour (regions/noms fusionnes)")
        total_added += added
        total_updated += updated

    print(f"Total: {total_added} ajoutees, {total_updated} mises a jour, {len(catalog_rows)} especes au total")

    if args.dry_run:
        print("(dry-run, rien d'ecrit)")
        return

    catalog_rows.sort(key=lambda r: (r["embranchement"], r["nom_scientifique"]))
    with args.catalog.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows({k: r.get(k, "") for k in FIELDNAMES} for r in catalog_rows)
    print(f"Ecrit dans {args.catalog}")


if __name__ == "__main__":
    sys.exit(main())
