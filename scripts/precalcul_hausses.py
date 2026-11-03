"""Précalcule les hausses par article pour rendre le rapport Power BI instantané.

Prérequis : fetch_indices.py puis generate_synthetic.py.

Sorties data/processed/ :
- fact_hausse_article.csv : article × campagne N+1 × fenêtre × décalage → prix N, prix N+1,
  volume N, hausse justifiée de l'article (Σ part × variation matière), indicateur « comparable ».
  La campagne « prochaine » (dernière + 1) est incluse : prix N = tarif en vigueur, pas de prix N+1,
  variation = mois disponibles depuis la dernière campagne (anticipation).
- fact_impact_matiere.csv : article × matière × fenêtre × décalage pour la prochaine campagne →
  surcoût justifié par cette matière (part × variation × prix × volume).

Mêmes définitions que CLAUDE.md : variation = moyenne de l'indice sur la fenêtre avant N+1
(décalée de « décalage » mois) / même moyenne avant N − 1.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
P = RACINE / "data" / "processed"
FENETRES = [3, 6, 12]
DECALAGES = [0, 3, 6, 9, 12]


def main() -> None:
    idx = pd.read_csv(P / "fact_indice.csv", parse_dates=["date"])
    idx = idx.pivot(index="date", columns="matiere_id", values="valeur_eur").sort_index()
    compo = pd.read_csv(P / "bridge_composition.csv")
    tarif = pd.read_csv(P / "fact_tarif.csv").pivot(index="article_id", columns="campagne", values="prix_brut")
    achats = pd.read_csv(P / "fact_achats.csv", parse_dates=["date"])
    volume = achats.assign(annee=achats["date"].dt.year).pivot_table(
        index="article_id", columns="annee", values="quantite", aggfunc="sum")

    campagnes = sorted(tarif.columns)
    prochaine = campagnes[-1] + 1
    fin_donnees = idx.index.max() + pd.DateOffset(months=1)  # 1er jour du mois suivant le dernier indice

    def variation(fin1: pd.Timestamp, fin0: pd.Timestamp, w: int) -> pd.Series:
        def moyenne(fin: pd.Timestamp) -> pd.Series:
            fen = idx[(idx.index >= fin - pd.DateOffset(months=w)) & (idx.index < fin)]
            # fenêtre incomplète (avant 2022-01) : pas de variation
            return fen.mean() if len(fen) == w else pd.Series(np.nan, index=idx.columns)
        return moyenne(fin1) / moyenne(fin0) - 1

    lignes, impacts = [], []
    for c in campagnes[1:] + [prochaine]:
        prix_n = tarif[c - 1]
        prix_n1 = tarif[c] if c in tarif.columns else pd.Series(np.nan, index=tarif.index)
        annee_vol = c - 1 if c != prochaine else campagnes[-1] - 1
        vol = volume.get(annee_vol, pd.Series(dtype=float)).reindex(tarif.index).fillna(0)
        for w in FENETRES:
            for lag in DECALAGES:
                fin1 = (pd.Timestamp(f"{c}-01-01") if c != prochaine else fin_donnees) - pd.DateOffset(months=lag)
                fin0 = pd.Timestamp(f"{c - 1}-01-01") - pd.DateOffset(months=lag)
                var = variation(fin1, fin0, w)
                contrib = compo.assign(var=compo["matiere_id"].map(var))
                contrib["contrib"] = contrib["part"] * contrib["var"]
                # une matière sans variation rend la hausse justifiée de l'article indéterminée
                j = contrib.groupby("article_id")["contrib"].apply(lambda s: s.sum() if s.notna().all() else np.nan)
                d = pd.DataFrame({"prix_n": prix_n, "prix_n1": prix_n1, "volume_n": vol,
                                  "hausse_justifiee": j.reindex(tarif.index)})
                d = d[d["prix_n"].notna()]
                d["comparable"] = (d["volume_n"] > 0) & d["hausse_justifiee"].notna() & (
                    d["prix_n1"].notna() if c != prochaine else True)
                d = d.reset_index().rename(columns={"index": "article_id"})
                d.insert(1, "campagne", c)
                d.insert(2, "fenetre", w)
                d.insert(3, "decalage", lag)
                lignes.append(d)
                if c == prochaine:
                    base = d[d["comparable"]].set_index("article_id")
                    imp = contrib[contrib["article_id"].isin(base.index)].copy()
                    imp["impact"] = imp["contrib"] * imp["article_id"].map(base["prix_n"] * base["volume_n"])
                    imp = imp[imp["impact"].notna() & (imp["impact"] != 0)]
                    impacts.append(imp.assign(fenetre=w, decalage=lag)[
                        ["article_id", "matiere_id", "fenetre", "decalage", "impact"]])

    fha = pd.concat(lignes, ignore_index=True)
    fha["volume_n"] = fha["volume_n"].astype(int)
    fha.round({"hausse_justifiee": 8}).to_csv(P / "fact_hausse_article.csv", index=False)
    fim = pd.concat(impacts, ignore_index=True).round({"impact": 4})
    fim.to_csv(P / "fact_impact_matiere.csv", index=False)
    print(f"fact_hausse_article : {len(fha)} lignes ({fha['comparable'].sum()} comparables), "
          f"fact_impact_matiere : {len(fim)} lignes, prochaine campagne {prochaine}")


if __name__ == "__main__":
    main()
