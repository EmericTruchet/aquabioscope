"""Base d'espèces (faune/flore) pour le tag des photos de plongée.

La base embarquée (`data/species.csv`, ~2170 espèces) part d'un inventaire
réel validé en plongée (Stage Montjoi) complété par les espèces observées
en Méditerranée et sur la façade Atlantique française (source : API
iNaturalist, comptages d'observations par taxon, filtrée d'un seuil de
popularité minimum), plutôt qu'un import brut de toute la biodiversité
marine (qui compterait des dizaines de milliers de taxons microscopiques
ou non identifiables en plongée). Le fichier reste un CSV éditable à la
main, à corriger/compléter au fil des sessions.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from importlib import resources
from pathlib import Path

_FUZZY_MIN_QUERY_LEN = 4
_FUZZY_THRESHOLD = 0.72
_STOPWORDS = {"a", "au", "aux", "de", "des", "du", "la", "le", "les", "un", "une", "et"}

# Ordre d'affichage privilégié en plongée biologique (des plus simples aux
# vertébrés), plutôt que l'ordre alphabétique.
EMBRANCHEMENT_ORDER: list[str] = [
    "Végétaux",
    "Eponge",
    "Cnidaire",
    "Cténophore",
    "Ver",
    "Mollusque",
    "Bryozoaire",
    "Arthropode",
    "Echinoderme",
    "Urochordé",
    "Poissons osseux",
    "Poissons cartilagineux",
    "Tétrapode",
]


def _sort_key(embranchement: str) -> tuple[int, str]:
    try:
        return (EMBRANCHEMENT_ORDER.index(embranchement), "")
    except ValueError:
        return (len(EMBRANCHEMENT_ORDER), embranchement)


def _normalize(text: str) -> str:
    """Minuscule et sans accents, pour une recherche tolérante."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _words(text: str) -> list[str]:
    return [w for w in re.split(r"[^a-z0-9]+", text) if w]


def _significant_words(text: str) -> list[str]:
    """Mots de 4 caractères ou plus, hors mots-outils (articles, prépositions)
    — sert de secours quand la requête entière ne matche rien en flou."""
    return [w for w in _words(text) if len(w) >= 4 and w not in _STOPWORDS]


def _singularize(text: str) -> str:
    """Retire un 's' final de chaque mot (pluriel français courant), pour
    qu'une requête au pluriel ("anémones jaunes") retrouve une base au
    singulier ("anémone jaune") et inversement."""
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in text.split(" "))


@dataclass(frozen=True)
class SpeciesEntry:
    embranchement: str
    nom_vernaculaire: str
    nom_scientifique: str
    regions: tuple[str, ...]

    @property
    def display_label(self) -> str:
        return f"{self.nom_vernaculaire} ({self.nom_scientifique})"


def _default_csv_path() -> Path:
    return resources.files("divephoto.data") / "species.csv"


def load_species(csv_path: Path | None = None) -> list[SpeciesEntry]:
    path = csv_path or _default_csv_path()
    entries: list[SpeciesEntry] = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            regions = tuple(r.strip() for r in row["regions"].split(",") if r.strip())
            entries.append(
                SpeciesEntry(
                    embranchement=row["embranchement"].strip(),
                    nom_vernaculaire=row["nom_vernaculaire"].strip(),
                    nom_scientifique=row["nom_scientifique"].strip(),
                    regions=regions,
                )
            )
    entries.sort(key=lambda e: (_sort_key(e.embranchement), _normalize(e.nom_vernaculaire)))
    return entries


@dataclass(frozen=True)
class _Indexed:
    entry: SpeciesEntry
    vern_norm: str
    sci_norm: str
    vern_norm_sg: str  # forme "singularisee" (voir _singularize)
    sci_norm_sg: str
    fuzzy_candidates: tuple[str, ...]  # nom complet + mots, vernaculaire et scientifique


class SpeciesCatalog:
    """Recherche d'espèces (nom vernaculaire ou scientifique), filtrable par
    région. Les formes normalisées sont pré-calculées à la construction (la
    base peut compter plusieurs milliers d'entrées, et la recherche est
    appelée à chaque frappe clavier)."""

    def __init__(self, entries: list[SpeciesEntry] | None = None) -> None:
        self.entries = entries if entries is not None else load_species()
        self._index: list[_Indexed] = []
        for e in self.entries:
            vern_norm = _normalize(e.nom_vernaculaire)
            sci_norm = _normalize(e.nom_scientifique)
            candidates = tuple({vern_norm, sci_norm, *_words(vern_norm), *_words(sci_norm)})
            self._index.append(_Indexed(
                e, vern_norm, sci_norm, _singularize(vern_norm), _singularize(sci_norm), candidates
            ))

    def for_region(self, region: str | None) -> list[SpeciesEntry]:
        """Filtre par region si la base couvre cette region, sinon renvoie
        tout (la base ne couvre aujourd'hui que Mediterranee/Atlantique ;
        mieux vaut proposer toute la base que rien pour les autres zones)."""
        if not region:
            return list(self.entries)
        filtered = [e for e in self.entries if region in e.regions]
        return filtered or list(self.entries)

    def search(self, query: str, region: str | None = None, limit: int = 30) -> list[SpeciesEntry]:
        region_set = None if not region else set(self.for_region(region))
        index = self._index if region_set is None else [i for i in self._index if i.entry in region_set]

        query_n = _normalize(query.strip())
        if not query_n:
            return [i.entry for i in index[:limit]]
        query_sg = _singularize(query_n)

        starts, contains, seen = [], [], set()
        for i in index:
            if (
                i.vern_norm.startswith(query_n) or i.sci_norm.startswith(query_n)
                or i.vern_norm_sg.startswith(query_sg) or i.sci_norm_sg.startswith(query_sg)
            ):
                starts.append(i.entry)
                seen.add(i.entry)
            elif (
                query_n in i.vern_norm or query_n in i.sci_norm
                or query_sg in i.vern_norm_sg or query_sg in i.sci_norm_sg
            ):
                contains.append(i.entry)
                seen.add(i.entry)

        exact = starts + contains
        # Le flou n'intervient qu'en dernier recours (aucun resultat exact) :
        # inutile de le declencher si la recherche exacte a deja trouve
        # quelque chose d'utile.
        if exact or len(query_n) < _FUZZY_MIN_QUERY_LEN:
            return exact[:limit]

        remaining = [i for i in index if i.entry not in seen]
        # 1er passage : la requete entiere (tolere une faute de frappe simple,
        # un mot en trop/manquant - ex. "padine a queue de paon").
        fuzzy = self._fuzzy_scan(remaining, [query_n])
        if not fuzzy:
            # 2e passage : mots significatifs pris independamment (permet de
            # retrouver au moins une piste sur une requete composee ou tres
            # approximative - ex. "retepolle cavernicole" -> Reteporella).
            sig_words = _significant_words(query_n)
            if sig_words:
                fuzzy = self._fuzzy_scan(remaining, sig_words)

        return (exact + fuzzy)[:limit]

    @staticmethod
    def _fuzzy_scan(index: list[_Indexed], query_variants: list[str]) -> list[SpeciesEntry]:
        # SequenceMatcher.ratio() est le poste couteux (des lors qu'on le
        # lance sur ~2000 entrees a chaque frappe). Deux economies :
        # - set_seq2 (reconstruit un index interne) une seule fois par
        #   variante de requete, seq1 (peu couteux) varie par candidat ;
        # - un filtre de longueur quasi-gratuit ecarte d'abord les
        #   candidats trop different en taille pour esperer un ratio utile
        #   (deux chaines de longueurs tres differentes ne peuvent pas
        #   avoir un ratio de similarite eleve), avant d'appeler ratio().
        matcher = SequenceMatcher(autojunk=False)
        scored: list[tuple[float, SpeciesEntry]] = []
        for qv in query_variants:
            matcher.set_seq2(qv)
            qv_len = len(qv)
            max_len_diff = max(3, qv_len // 2)
            for item in index:
                best = 0.0
                for candidate in item.fuzzy_candidates:
                    if abs(len(candidate) - qv_len) > max_len_diff:
                        continue
                    matcher.set_seq1(candidate)
                    ratio = matcher.ratio()
                    if ratio > best:
                        best = ratio
                if best >= _FUZZY_THRESHOLD:
                    scored.append((best, item.entry))
        scored.sort(key=lambda t: -t[0])
        # dedoublonne (une entree peut matcher plusieurs variantes) en gardant le meilleur score
        best_per_entry: dict[SpeciesEntry, float] = {}
        for ratio, entry in scored:
            if ratio > best_per_entry.get(entry, -1):
                best_per_entry[entry] = ratio
        return [e for e, _ in sorted(best_per_entry.items(), key=lambda kv: -kv[1])]
