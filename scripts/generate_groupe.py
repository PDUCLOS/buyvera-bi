"""Vision groupe, prix payés et résultats de négociation (données fictives).

Prérequis : generate_synthetic.py puis precalcul_hausses.py. Ne modifie aucune table existante.

Sorties data/processed/ :
- dim_entite.csv : 3 sites d'un groupe fictif (un historique, deux rachetés).
- fact_achats_entite.csv : les achats de fact_achats répartis entre les sites (quantités totales inchangées),
  avec le prix payé dans l'ERP du site et son statut :
    Conforme · Prix historique du site (contrat repris au rachat, au-dessus du tarif groupe) ·
    Retard d'application (l'ERP applique encore le tarif de l'an passé en début d'année) ·
    Écart durable (prix saisi différent du tarif toute l'année).
  Meilleur prix du groupe = plus bas prix moyen payé par un site pour l'article dans l'année.
- fact_negociation.csv : résultat de chaque campagne par fournisseur : hausse demandée, hausse obtenue,
  potentiel renégociable et économie obtenue en euros. Fichier modifiable : c'est la saisie de l'acheteur.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
P = RACINE / "data" / "processed"
SEED = 20261105
rng = np.random.default_rng(SEED)

ENTITES = [
    ("E1", "Ardéa Lyon", "FR", "Site historique"),
    ("E2", "Ardéa Stuttgart", "DE", "Racheté en 2024"),
    ("E3", "Ardéa Poznań", "PL", "Racheté en 2025"),
]
P_SITE = {"E2": 0.6, "E3": 0.5}        # probabilité qu'un site achète aussi l'article
P_HISTORIQUE = 0.35                     # part des articles d'un site racheté sous contrat historique
P_RETARD, P_ECART = 0.10, 0.03          # par site × article × année


def main() -> None:
    achats = pd.read_csv(P / "fact_achats.csv", parse_dates=["date"])
    tarif = pd.read_csv(P / "fact_tarif.csv").pivot(index="article_id", columns="campagne", values="prix_brut")
    connu = tarif.notna()  # tarif réellement publié (article présent à la campagne)
    tarif = tarif.ffill(axis=1).bfill(axis=1)  # ligne sans prix : dernier prix connu, sinon le premier publié
    # article dont l'unique ligne tarif est arrivée sans prix : prix médian de sa famille pour l'année
    fam = pd.read_csv(P / "dim_article.csv").set_index("article_id")["famille_id"]
    med = tarif.groupby(fam.reindex(tarif.index)).transform("median")
    tarif = tarif.fillna(med)
    articles = achats["article_id"].unique()

    # Répartition de chaque article entre les sites
    parts = {}
    for a in articles:
        sites = ["E1"] + [e for e, p in P_SITE.items() if rng.random() < p]
        w = rng.dirichlet(np.ones(len(sites)) * 2)
        parts[a] = dict(zip(sites, w))
    # Contrats historiques des sites rachetés
    prime = {(e, a): rng.uniform(0.02, 0.10) for a in articles for e in parts[a]
             if e != "E1" and rng.random() < P_HISTORIQUE}
    annees = sorted(achats["date"].dt.year.unique())
    retard = {(e, a, y): int(rng.integers(1, 4)) for a in articles for e in parts[a] for y in annees
              if y > annees[0] and rng.random() < P_RETARD}
    ecart = {(e, a, y): rng.choice([-1, 1]) * rng.uniform(0.03, 0.08) for a in articles for e in parts[a]
             for y in annees if rng.random() < P_ECART}

    lignes = []
    for r in achats.itertuples():
        sites = list(parts[r.article_id])
        q = rng.multinomial(r.quantite, list(parts[r.article_id].values()))
        y, mo = r.date.year, r.date.month
        t = tarif.at[r.article_id, y]
        for e, qe in zip(sites, q):
            if qe == 0:
                continue
            statut, prix = "Conforme", t
            if (e, r.article_id) in prime:
                statut, prix = "Prix historique du site", t * (1 + prime[(e, r.article_id)])
            if (e, r.article_id, y) in ecart:
                statut, prix = "Écart durable", t * (1 + ecart[(e, r.article_id, y)])
            elif (e, r.article_id, y) in retard and mo <= retard[(e, r.article_id, y)] and y - 1 in tarif.columns                     and connu.at[r.article_id, y - 1]:
                statut, prix = "Retard d'application", tarif.at[r.article_id, y - 1]
            lignes.append({"article_id": r.article_id, "date": r.date.date(), "entite_id": e, "quantite": int(qe),
                           "prix_tarif": round(t, 2), "prix_paye": round(prix, 2), "statut_prix": statut})
    f = pd.DataFrame(lignes)
    f["annee"] = pd.to_datetime(f["date"]).dt.year
    f["montant"] = f.quantite * f.prix_paye
    moy = f.groupby(["article_id", "annee", "entite_id"]).apply(
        lambda x: x.montant.sum() / x.quantite.sum(), include_groups=False).rename("pm").reset_index()
    best = moy.groupby(["article_id", "annee"])["pm"].min().rename("meilleur_prix_groupe")
    f = f.merge(best, on=["article_id", "annee"])
    f["surcout_vs_meilleur"] = (f.quantite * (f.prix_paye - f.meilleur_prix_groupe)).round(2)
    f["ecart_application"] = (f.quantite * (f.prix_paye - f.prix_tarif)).where(
        f.statut_prix.isin(["Retard d'application", "Écart durable"]), 0).round(2)
    f["meilleur_prix_groupe"] = f.meilleur_prix_groupe.round(4)
    f = f.drop(columns=["annee", "montant"])
    assert f.quantite.sum() == achats.quantite.sum(), "quantités totales modifiées"
    assert not f[["prix_tarif", "prix_paye", "meilleur_prix_groupe"]].isna().any().any(), "prix manquants"
    f.to_csv(P / "fact_achats_entite.csv", index=False)
    pd.DataFrame(ENTITES, columns=["entite_id", "nom", "pays", "origine"]).to_csv(P / "dim_entite.csv", index=False)

    # Résultats de négociation par fournisseur et campagne
    fha = pd.read_csv(P / "fact_hausse_article.csv")
    fha = fha[(fha.fenetre == 6) & (fha.decalage == 0) & fha.comparable & (fha.campagne <= 2026)]
    fha = fha.merge(pd.read_csv(P / "dim_article.csv")[["article_id", "fournisseur_id"]], on="article_id")
    fha["v"] = fha.prix_n * fha.volume_n
    fha["reneg"] = (fha.prix_n1 / fha.prix_n - 1 - fha.hausse_justifiee).clip(lower=0) * fha.v
    neg = []
    for (f_id, c), g in fha.groupby(["fournisseur_id", "campagne"]):
        dem = (g.prix_n1 * g.volume_n).sum() / g.v.sum() - 1
        jus = (g.hausse_justifiee * g.v).sum() / g.v.sum()
        e = dem - jus
        recup = rng.uniform(0.3, 0.8) if e > 0.01 else rng.uniform(0.0, 0.3)
        obt = dem - recup * max(e, 0)
        neg.append({"fournisseur_id": f_id, "campagne": c, "valeur_n": round(g.v.sum(), 2),
                    "hausse_demandee": round(dem, 6), "hausse_justifiee": round(jus, 6), "hausse_obtenue": round(obt, 6),
                    "eur_renegociables": round(g.reneg.sum(), 2), "economie_eur": round((dem - obt) * g.v.sum(), 2)})
    pd.DataFrame(neg).to_csv(P / "fact_negociation.csv", index=False)

    s = f.groupby("statut_prix").agg(lignes=("quantite", "size"), surcout=("surcout_vs_meilleur", "sum"),
                                     ecart=("ecart_application", "sum"))
    print(s.round(0))
    print("surcoût vs meilleur prix groupe :", round(f.surcout_vs_meilleur.sum()), "€ ; lignes :", len(f))
    n = pd.DataFrame(neg)
    print(n.groupby("campagne")[["eur_renegociables", "economie_eur"]].sum().round(0))


if __name__ == "__main__":
    main()
