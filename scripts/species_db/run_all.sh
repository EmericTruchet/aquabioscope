#!/usr/bin/env bash
# Lance la collecte GBIF pour tous les groupes taxonomiques cibles, puis fusionne
# le tout dans species.csv. A executer depuis la racine du projet.
set -e
cd "$(dirname "$0")/../.."
PY=.venv/Scripts/python
OUT=scripts/species_db

$PY $OUT/gbif_pull.py --taxon-key 52  --embranchement Mollusque    --out $OUT/out_mollusca.csv     --top 400 --min-count 40
$PY $OUT/gbif_pull.py --taxon-key 43  --embranchement Cnidaire     --out $OUT/out_cnidaria.csv      --top 300 --min-count 40
$PY $OUT/gbif_pull.py --taxon-key 50  --embranchement Echinoderme  --out $OUT/out_echinodermata.csv --top 250 --min-count 30
$PY $OUT/gbif_pull.py --taxon-key 105 --embranchement Eponge       --out $OUT/out_porifera.csv      --top 200 --min-count 20
$PY $OUT/gbif_pull.py --taxon-key 53  --embranchement Bryozoaire   --out $OUT/out_bryozoa.csv       --top 200 --min-count 15
$PY $OUT/gbif_pull.py --taxon-key 42  --embranchement Ver          --out $OUT/out_annelida.csv      --top 250 --min-count 20
$PY $OUT/gbif_pull.py --taxon-key 51  --embranchement Cténophore   --out $OUT/out_ctenophora.csv    --top 40  --min-count 10
$PY $OUT/gbif_pull.py --taxon-key 229 --embranchement Arthropode   --out $OUT/out_malacostraca.csv  --top 300 --min-count 30
$PY $OUT/gbif_pull.py --taxon-key 106 --embranchement Végétaux     --out $OUT/out_rhodophyta.csv    --top 150 --min-count 30
$PY $OUT/gbif_pull.py --taxon-key 36  --embranchement Végétaux     --out $OUT/out_chlorophyta.csv   --top 100 --min-count 30
$PY $OUT/gbif_pull.py --taxon-key 7073593 --embranchement Végétaux --out $OUT/out_phaeophyceae.csv  --top 100 --min-count 30

$PY $OUT/merge_csv.py $OUT/out_mollusca.csv $OUT/out_cnidaria.csv $OUT/out_echinodermata.csv \
    $OUT/out_porifera.csv $OUT/out_bryozoa.csv $OUT/out_annelida.csv $OUT/out_ctenophora.csv \
    $OUT/out_malacostraca.csv $OUT/out_rhodophyta.csv $OUT/out_chlorophyta.csv $OUT/out_phaeophyceae.csv

echo "TERMINE"
