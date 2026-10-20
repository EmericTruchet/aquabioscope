#!/usr/bin/env bash
# Reconstruit / enrichit species.csv. A executer depuis la racine du projet.
# Chaque etape enrichit la base existante (rien n'est perdu) ; compter
# environ 1 h au total (API GBIF, WoRMS, Wikidata).
set -e
cd "$(dirname "$0")/../.."
PY=.venv/Scripts/python
OUT=scripts/species_db
export PYTHONIOENCODING=utf-8

# 1. Retire les especes non marines (terrestres, eau douce hors eau_douce_lacs.txt)
$PY $OUT/worms_filter.py
# 2. Especes les plus observees dans chaque zone de plongee (avec leur region)
$PY $OUT/regional_pull.py --out $OUT/out_regional.csv
# 3. Fusion + noms usuels de plongeurs
$PY $OUT/merge_csv.py $OUT/out_regional.csv $OUT/aliases_plongeurs.csv
# 4. Tous les noms francais connus (GBIF, Wikidata, WoRMS)
$PY $OUT/fetch_french_names.py
# 5. TAXREF (MNHN) : noms francais officiels et regionaux, outre-mer.
#    Archive a telecharger et dezipper a part (~60 Mo) :
#    https://assets.patrinat.fr/files/referentiel/TAXREF_v18_2025.zip
if [ -n "$TAXREF_DIR" ]; then
  $PY $OUT/taxref_extract.py "$TAXREF_DIR" --out $OUT/out_taxref.csv
  $PY $OUT/merge_csv.py $OUT/out_taxref.csv
else
  echo "TAXREF_DIR non defini : etape TAXREF sautee"
fi

echo "TERMINE"
