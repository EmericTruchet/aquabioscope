"""Acces a WoRMS (World Register of Marine Species), le registre de reference
des especes marines : sert a ecarter les especes non marines (escargots et
limaces terrestres, lombrics, cloportes, planaires terrestres... ramenees
par les recoltes GBIF dans des zones qui incluent de la terre ferme) et a
recuperer les noms vernaculaires francais.
"""
from __future__ import annotations

import time

import requests

API = "https://www.marinespecies.org/rest"
MATCH_BATCH = 50
USER_AGENT = "AquaBioScope-species-db/1 (script interne, usage ponctuel)"


def match_names(session: requests.Session, names: list[str]) -> dict[str, dict]:
    """Nom scientifique -> fiche WoRMS (premiere correspondance), pour les
    noms trouves. Interroge WoRMS par lots de MATCH_BATCH."""
    out: dict[str, dict] = {}
    for i in range(0, len(names), MATCH_BATCH):
        batch = names[i : i + MATCH_BATCH]
        params = [("scientificnames[]", n) for n in batch] + [("marine_only", "false")]
        for attempt in range(3):
            try:
                r = session.get(f"{API}/AphiaRecordsByMatchNames", params=params, timeout=60)
                if r.status_code == 204:
                    break
                r.raise_for_status()
                for name, records in zip(batch, r.json()):
                    if records:
                        out[name] = records[0]
                break
            except (requests.RequestException, ValueError):
                time.sleep(2 * (attempt + 1))
        time.sleep(0.2)
    return out


def is_non_marine(record: dict) -> bool:
    """Vrai si WoRMS ne classe pas l'espece comme marine et la donne d'eau
    douce ou terrestre (ex. aselle : saumatre + eau douce, ecartee). Les
    especes d'eau saumatre seule restent acceptees."""
    return not record.get("isMarine") and bool(record.get("isFreshwater") or record.get("isTerrestrial"))


def french_vernaculars(session: requests.Session, aphia_id: int) -> list[str]:
    try:
        r = session.get(f"{API}/AphiaVernacularsByAphiaID/{aphia_id}", timeout=30)
        if r.status_code != 200:
            return []
        return [v["vernacular"] for v in r.json() if v.get("language_code") == "fra" and v.get("vernacular")]
    except (requests.RequestException, ValueError):
        return []
