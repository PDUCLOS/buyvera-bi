"""Récupère les indices matières INSEE (BDM, API SDMX) et produit les tables du modèle.

Sorties :
- data/raw/insee_<idbank>.xml        : réponse brute de l'API
- data/raw/insee_indices_long.csv    : toutes les séries, format long
- data/processed/dim_matiere.csv
- data/processed/fact_indice.csv

Méthode retenue : API SDMX (testée le 2026-11-03, réponse 200, séries mensuelles à jour).
L'export CSV des pages insee.fr/serie n'est pas utilisé : il passe par un zip et un
formulaire, l'API est plus simple et stable.
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import pandas as pd
import requests

RACINE = Path(__file__).resolve().parents[1]
RAW = RACINE / "data" / "raw"
PROCESSED = RACINE / "data" / "processed"

DEBUT = "2022-01"
URL_SDMX = "https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/{idbank}?startPeriod={debut}"
# Retard toléré avant alerte de fraîcheur (l'INSEE publie avec ~1 mois de décalage)
RETARD_MAX_MOIS = 3
# Inflation de référence de la part non matière (IPPI non retenu : hypothèse affichée)
INFLATION_NM = 0.02

# matiere_id, libellé, idbank, unité, utilisée dans les compositions ?
MATIERES = [
    ("CU", "Cuivre", "010002094", "indice base 2010, en €", True),
    ("AL", "Aluminium", "010002093", "indice base 2010, en €", True),
    ("NI", "Nickel (inox)", "010002096", "indice base 2010, en €", True),
    ("ZN", "Zinc", "010002098", "indice base 2010, en €", True),
    ("FE", "Acier / métaux ferreux", "010002103", "indice base 2010, en €", True),
    ("PL", "Plastiques (naphta)", "010002090", "indice base 2010, en €", True),
    ("CU_T", "Cuivre LME comptant (€/t)", "010767327", "€ / tonne", False),
]
SERIES_INTERDITES = {"001743680"}  # acier arrêté


def telecharger(idbank: str) -> bytes:
    if idbank in SERIES_INTERDITES:
        raise ValueError(f"Série {idbank} arrêtée, ne pas l'utiliser")
    r = requests.get(URL_SDMX.format(idbank=idbank, debut=DEBUT), timeout=60)
    r.raise_for_status()
    return r.content


def lire_sdmx(contenu: bytes) -> tuple[dict, pd.DataFrame]:
    racine = ET.fromstring(contenu)
    serie = next(e for e in racine.iter() if e.tag.endswith("Series"))
    obs = [
        {"periode": o.get("TIME_PERIOD"), "valeur": float(o.get("OBS_VALUE")),
         "qualite": o.get("OBS_QUAL")}
        for o in serie if o.tag.endswith("Obs") and o.get("OBS_VALUE") not in (None, "NaN")
    ]
    return dict(serie.attrib), pd.DataFrame(obs)


def mois_ecart(periode: str, ref: date) -> int:
    a, m = map(int, periode.split("-"))
    return (ref.year - a) * 12 + ref.month - m


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    aujourdhui = date.today()

    dims, faits, alertes = [], [], []
    for matiere_id, libelle, idbank, unite, compo in MATIERES:
        contenu = telecharger(idbank)
        (RAW / f"insee_{idbank}.xml").write_bytes(contenu)
        attrs, df = lire_sdmx(contenu)

        if attrs.get("FREQ") != "M":
            alertes.append(f"{idbank} : fréquence {attrs.get('FREQ')} (attendu M)")
        dernier = df["periode"].max()
        retard = mois_ecart(dernier, aujourdhui)
        if retard > RETARD_MAX_MOIS:
            alertes.append(f"{idbank} : dernier mois {dernier}, {retard} mois de retard")

        df["matiere_id"] = matiere_id
        faits.append(df)
        dims.append({
            "matiere_id": matiere_id, "libelle": libelle, "source": "INSEE BDM",
            "idbank": idbank, "titre_insee": attrs.get("TITLE_FR", ""), "unite": unite,
            "utilisee_composition": compo, "dernier_mois": dernier,
        })
        print(f"{matiere_id:5} {idbank} {len(df):3} mois  {df['periode'].min()} -> {dernier}")

    long = pd.concat(faits, ignore_index=True)
    long.to_csv(RAW / "insee_indices_long.csv", index=False)

    fact = long.assign(date=pd.to_datetime(long["periode"] + "-01").dt.date)
    fact = (fact.rename(columns={"valeur": "valeur_eur"})
                [["matiere_id", "date", "valeur_eur"]]
                .sort_values(["matiere_id", "date"]))
    # Part non matière (main-d'œuvre, énergie, frais) : série d'hypothèse à INFLATION_NM/an,
    # pour que la hausse justifiée reste une seule formule Σ part × variation.
    mois = sorted(fact["date"].unique())
    nm = pd.DataFrame({
        "matiere_id": "NM", "date": mois,
        "valeur_eur": [round(100 * (1 + INFLATION_NM) ** (i / 12), 4) for i in range(len(mois))],
    })
    fact = pd.concat([fact, nm], ignore_index=True)
    dims.append({
        "matiere_id": "NM", "libelle": "Non matière (main-d'œuvre, énergie, frais)",
        "source": f"Hypothèse {INFLATION_NM:.0%}/an", "idbank": "",
        "titre_insee": "", "unite": "indice base 100 en 2022-01",
        "utilisee_composition": True, "dernier_mois": str(mois[-1])[:7],
    })

    fact.to_csv(PROCESSED / "fact_indice.csv", index=False)
    pd.DataFrame(dims).to_csv(PROCESSED / "dim_matiere.csv", index=False)

    # Contrôle de continuité : aucun mois manquant entre DEBUT et le dernier mois
    for mid, g in fact.groupby("matiere_id"):
        attendu = pd.period_range(DEBUT, g["date"].max(), freq="M")
        if len(g) != len(attendu):
            alertes.append(f"{mid} : {len(attendu) - len(g)} mois manquants")

    for a in alertes:
        print("ALERTE", a)
    print(f"fact_indice : {len(fact)} lignes, dim_matiere : {len(dims)} lignes")
    return 1 if alertes else 0


if __name__ == "__main__":
    sys.exit(main())
