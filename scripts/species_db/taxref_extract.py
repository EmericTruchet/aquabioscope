"""Extrait de TAXREF (referentiel taxonomique national, MNHN / PatriNat) les
especes marines utiles a la base, au format de species.csv, pour merge_csv.py.

TAXREF apporte surtout :
- des noms francais valides (colonne NOM_VERN + table TAXVERN), y compris les
  noms regionaux de pecheurs ("dormeur", "poing-clos"...), ajoutes en
  autres_noms ;
- la presence des especes dans chaque territoire d'outre-mer, rattachee aux
  zones de plongee de l'application.

Seules les especes nouvelles qui ont un nom francais sont ajoutees (les
dizaines de milliers d'autres sont surtout du plancton ou des especes des
grands fonds, sans interet pour un plongeur). Pour les especes deja presentes,
on ne fait qu'ajouter des noms et des zones.

Donnees : Licence Ouverte Etalab, source a citer : "TAXREF, Museum national
d'Histoire naturelle". Archive a telecharger (non versionnee, ~60 Mo) :
https://assets.patrinat.fr/files/referentiel/TAXREF_v18_2025.zip

Usage:
    python scripts/species_db/taxref_extract.py DOSSIER_TAXREF_DEZIPPE --out scripts/species_db/out_taxref.csv
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parents[2] / "src" / "aquabioscope" / "data" / "species.csv"
FIELDNAMES = ["embranchement", "nom_vernaculaire", "nom_scientifique", "regions", "autres_noms"]

# Habitats TAXREF : 1 marin, 4 marin et eau douce, 5 marin et terrestre,
# 6 eau saumatre.
MARINE_HABITATS = {"1", "4", "5", "6"}

# Statuts de presence retenus : present, endemique, subendemique, cryptogene,
# introduit, envahissant (pas "occasionnel", "douteux", "absent"...).
PRESENT = {"P", "E", "S", "C", "I", "J"}

# Territoires -> zones de l'application. La metropole (FR) ne distingue pas
# Mediterranee et Atlantique : on ne s'en sert que pour les especes nouvelles.
# Guyane, Saint-Pierre-et-Miquelon et les terres australes ne correspondent a
# aucune zone (ils pollueraient la liste "Atlantique", qui est europeenne).
TERRITORY_REGIONS = {
    "MAR": "caraibes", "GUA": "caraibes", "SM": "caraibes", "SB": "caraibes",
    "REU": "ocean-indien", "MAY": "ocean-indien", "EPA": "ocean-indien",
    "PF": "pacifique", "NC": "pacifique", "WF": "pacifique", "CLI": "pacifique",
}
METROPOLE_REGIONS = ("atlantique", "mediterranee")

# (phylum, classe) -> embranchement de l'application ; classe None = toutes.
EMBRANCHEMENTS = {
    ("Chordata", "Actinopterygii"): "Poissons osseux",
    ("Chordata", "Elasmobranchii"): "Poissons cartilagineux",
    ("Chordata", "Holocephali"): "Poissons cartilagineux",
    ("Chordata", "Mammalia"): "Tétrapode",
    ("Chordata", "Ascidiacea"): "Urochordé",
    ("Chordata", "Thaliacea"): "Urochordé",
    ("Arthropoda", "Malacostraca"): "Arthropode",
    ("Arthropoda", "Hexanauplia"): "Arthropode",  # balanes, anatifes
    ("Arthropoda", "Thecostraca"): "Arthropode",
    ("Arthropoda", "Pycnogonida"): "Arthropode",
    ("Arthropoda", "Merostomata"): "Arthropode",
    ("Mollusca", None): "Mollusque",
    ("Cnidaria", None): "Cnidaire",
    ("Porifera", None): "Eponge",
    ("Echinodermata", None): "Echinoderme",
    ("Bryozoa", None): "Bryozoaire",
    ("Ctenophora", None): "Cténophore",
    ("Annelida", "Polychaeta"): "Ver",
    ("Platyhelminthes", ""): "Ver",
    ("Platyhelminthes", "Rhabditophora"): "Ver",
    ("Nemertea", None): "Ver",
    ("Sipuncula", None): "Ver",
    ("Echiura", None): "Ver",
    ("Chaetognatha", None): "Ver",
    ("Rhodophyta", None): "Végétaux",
    ("Chlorophyta", None): "Végétaux",
    ("Ochrophyta", "Phaeophyceae"): "Végétaux",
    ("", "Equisetopsida"): "Végétaux",  # posidonie, zosteres, cymodocee
}

# Familles ecartees pour les especes nouvelles : grands fonds et pleine eau
# du large (jamais vues en plongee), eau douce ou saumatre d'estuaire,
# parasites. TAXREF ne donne pas la profondeur, d'ou cette liste.
EXCLUDED_FAMILIES = {
    # poissons des grands fonds / mesopelagiques
    "Myctophidae", "Stomiidae", "Alepocephalidae", "Platytroctidae", "Gempylidae",
    "Macrouridae", "Moridae", "Gonostomatidae", "Paralepididae", "Sternoptychidae",
    "Notacanthidae", "Bathylagidae", "Phosichthyidae", "Melamphaidae", "Synaphobranchidae",
    "Melanonidae", "Oneirodidae", "Halosauridae", "Argentinidae", "Microstomatidae",
    "Oreosomatidae", "Trachichthyidae", "Epigonidae", "Setarchidae", "Bythitidae",
    "Trichiuridae", "Ophidiidae", "Lotidae", "Zoarcidae", "Nomeidae", "Centrolophidae",
    "Bramidae", "Exocoetidae", "Evermannellidae", "Scopelarchidae", "Chiasmodontidae",
    "Ceratiidae", "Melanocetidae", "Linophrynidae", "Himantolophidae", "Gigantactinidae",
    "Diretmidae", "Anoplogastridae", "Nemichthyidae", "Serrivomeridae", "Ipnopidae",
    "Opisthoproctidae", "Notosudidae", "Cetomimidae", "Caproidae",
    # requins et chimeres des grands fonds
    "Centrophoridae", "Somniosidae", "Etmopteridae", "Dalatiidae", "Pentanchidae",
    "Chimaeridae", "Rhinochimaeridae", "Pseudotriakidae", "Echinorhinidae", "Arhynchobatidae",
    "Chlamydoselachidae",
    # crevettes des grands fonds
    "Aristeidae", "Pandalidae",
    # eau douce, estuaires, mangrove
    "Atyidae", "Hydrobiidae", "Assimineidae", "Cochliopidae", "Dreissenidae", "Poeciliidae",
    "Salmonidae", "Eleotridae", "Ambassidae", "Gecarcinidae",
    # parasites
    "Sacculinidae", "Peltogastridae", "Limnoriidae",
}

# Reptiles : TAXREF les range sans classe ; on ne garde que les tortues marines.
TURTLE_FAMILIES = {"Cheloniidae", "Dermochelyidae"}

ARTICLE = re.compile(r"\s*\((?:Le|La|Les|L'|L’)\)\s*$")


def embranchement(row: dict[str, str]) -> str | None:
    if row["FAMILLE"] in TURTLE_FAMILIES:
        return "Tétrapode"
    phylum, classe = row["PHYLUM"], row["CLASSE"]
    if phylum == "Chordata" and classe == "Mammalia" and row["HABITAT"] not in {"1", "5"}:
        return None
    label = EMBRANCHEMENTS.get((phylum, classe)) or EMBRANCHEMENTS.get((phylum, None))
    if label == "Végétaux" and row["HABITAT"] != "1":
        return None  # plantes de pres sales, d'estuaires
    return label


def clean_names(raw: str) -> list[str]:
    """ "Tourteau (Le), Dormeur (Le), Termite [des ostreiculteurs] (Le)"
    -> ["Tourteau", "Dormeur", "Termite des ostreiculteurs"]."""
    names = []
    for part in raw.split(","):
        name = ARTICLE.sub("", part.strip())
        name = " ".join(name.replace("[", "").replace("]", "").split())
        if name and name not in names:
            names.append(name[0].upper() + name[1:])
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("taxref_dir", type=Path, help="Dossier de l'archive TAXREF dezippee")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    csv.field_size_limit(2**31 - 1)

    taxref_file = next(args.taxref_dir.glob("TAXREFv*.txt"))
    vern_file = next(args.taxref_dir.glob("TAXVERNv*.txt"))

    catalog = {}
    with CATALOG_PATH.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            catalog[" ".join(row["nom_scientifique"].split()).casefold()] = row

    species = {}
    ref_of = {}
    with taxref_file.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            ref_of[row["CD_NOM"]] = row["CD_REF"]
            if row["RANG"] != "ES" or row["CD_NOM"] != row["CD_REF"] or row["HABITAT"] not in MARINE_HABITATS:
                continue
            label = embranchement(row)
            if label:
                species[row["CD_REF"]] = (label, row)

    extra_names = defaultdict(list)
    with vern_file.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["LANGUE"] == "Français":
                extra_names[ref_of.get(row["CD_NOM"], row["CD_NOM"])].extend(clean_names(row["LB_VERN"]))

    out_rows = []
    new_count = 0
    for cd_ref, (label, row) in species.items():
        sci = row["LB_NOM"].strip()
        names = clean_names(row["NOM_VERN"])
        names += [n for n in extra_names.get(cd_ref, []) if n not in names]
        names = [n for n in names if n.casefold() != sci.casefold()]
        existing = catalog.get(" ".join(sci.split()).casefold())

        regions = {TERRITORY_REGIONS[t] for t in TERRITORY_REGIONS if row[t] in PRESENT}
        if existing is None:
            if not names or row["FAMILLE"] in EXCLUDED_FAMILIES:
                continue
            if row["FR"] in PRESENT:
                regions.update(METROPOLE_REGIONS)
            if not regions:
                continue  # present seulement en Guyane, aux Kerguelen...
            new_count += 1
        elif not existing["regions"]:
            regions = set()  # espece "partout" : lui ajouter une zone la restreindrait
        if existing is not None and not names and not regions:
            continue

        out_rows.append({
            "embranchement": label,
            "nom_vernaculaire": names[0] if names else "",
            "nom_scientifique": sci,
            "regions": ",".join(sorted(regions)),
            "autres_noms": "|".join(names[1:]),
        })

    with args.out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"{len(out_rows)} lignes ecrites ({new_count} especes nouvelles) dans {args.out}")


if __name__ == "__main__":
    sys.exit(main())
