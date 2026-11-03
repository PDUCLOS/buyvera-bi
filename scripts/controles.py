"""Contrôles automatiques des données du modèle et rapport docs/rapport_controle.md.

Code retour 1 si un contrôle bloquant échoue. Les calculs de hausse reprennent les
définitions de CLAUDE.md : ce sont les chiffres de référence pour Power BI et Claude.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
P = RACINE / "data" / "processed"
C = RACINE / "data" / "controle"
RAPPORT = RACINE / "docs" / "rapport_controle.md"

TABLES = ["dim_date", "dim_fournisseur", "dim_famille", "dim_acheteur", "dim_matiere",
          "dim_article", "bridge_composition", "fact_tarif", "fact_achats", "fact_indice"]


def fr(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f} %".replace(".", ",")


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:+.{d}f} %".replace(".", ",")


def eur(x: float) -> str:
    return f"{x:,.0f} €".replace(",", " ")


def tableau(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lignes = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lignes += ["| " + " | ".join(str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(lignes)


def agreger(d: pd.DataFrame, cles: list[str]) -> pd.DataFrame:
    """Hausses pondérées par la valeur N (prix N × volume N)."""
    d = d.assign(v1=d["prix_n1"] * d["volume_n"], vj=d["hausse_justifiee"] * d["valeur_n"])
    g = d.groupby(cles).agg(valeur_n=("valeur_n", "sum"), v1=("v1", "sum"), vj=("vj", "sum"),
                            eur=("eur_renegociables", "sum"), nb=("article_id", "count"))
    g["demandee"] = g["v1"] / g["valeur_n"] - 1
    g["justifiee"] = g["vj"] / g["valeur_n"]
    g["ecart_pts"] = (g["demandee"] - g["justifiee"]) * 100
    return g.reset_index()


def main() -> int:
    t = {n: pd.read_csv(P / f"{n}.csv") for n in TABLES}
    detail = pd.read_csv(C / "hausses_articles.csv")
    verite = pd.read_csv(C / "rattachement_verite.csv")
    var = pd.read_csv(C / "variations_matiere.csv")
    fourn = t["dim_fournisseur"].set_index("fournisseur_id")
    ko: list[str] = []
    out: list[str] = ["# Rapport de contrôle des données", "",
                      "Généré par `scripts/controles.py`. Tarifs et volumes synthétiques, indices matières réels (INSEE).", ""]

    # 1. Volumétrie
    out += ["## 1. Volumétrie", "", tableau(pd.DataFrame(
        [(n, len(t[n])) for n in TABLES], columns=["table", "lignes"])), ""]

    # 2. Contrôles bloquants
    checks = []
    somme = t["bridge_composition"].groupby("article_id")["part"].sum()
    checks.append(("Σ parts composition = 1 (±0,0001)", int(((somme - 1).abs() > 1e-4).sum())))
    checks.append(("Parts de composition hors ]0 ; 1]", int(((t["bridge_composition"]["part"] <= 0) |
                                                             (t["bridge_composition"]["part"] > 1)).sum())))
    nb_mat = t["bridge_composition"].query("matiere_id != 'NM'").groupby("article_id").size()
    checks.append(("Articles hors 2 à 4 matières", int(((nb_mat < 2) | (nb_mat > 4)).sum())))
    checks.append(("Prix négatifs ou nuls", int((t["fact_tarif"]["prix_brut"] <= 0).sum())))
    checks.append(("Quantités négatives ou nulles", int((t["fact_achats"]["quantite"] <= 0).sum())))
    ids = set(t["dim_article"]["article_id"])
    for table in ["fact_tarif", "fact_achats", "bridge_composition"]:
        checks.append((f"Clés article orphelines dans {table}", int((~t[table]["article_id"].isin(ids)).sum())))
    checks.append(("Clés matière orphelines (composition)",
                   int((~t["bridge_composition"]["matiere_id"].isin(t["dim_matiere"]["matiere_id"])).sum())))
    dates = set(t["dim_date"]["date"])
    for table in ["fact_achats", "fact_indice"]:
        checks.append((f"Dates absentes de dim_date dans {table}", int((~t[table]["date"].isin(dates)).sum())))
    checks.append(("Doublons article × campagne (fact_tarif)",
                   int(t["fact_tarif"].duplicated(["article_id", "campagne"]).sum())))
    checks.append(("Fournisseur tarif ≠ fournisseur article",
                   int((t["fact_tarif"].merge(t["dim_article"], on="article_id")
                        .eval("fournisseur_id_x != fournisseur_id_y")).sum())))
    for nom, n in checks:
        if n:
            ko.append(nom)
    out += ["## 2. Contrôles bloquants", "", tableau(pd.DataFrame(
        [(nom, n, "OK" if n == 0 else "**KO**") for nom, n in checks],
        columns=["contrôle", "anomalies", "statut"])), ""]

    # 3. Anomalies volontaires (informatives)
    manq = int(t["fact_tarif"]["prix_brut"].isna().sum())
    sans_achat = len(ids - set(t["fact_achats"]["article_id"]))
    cyc = t["dim_article"]
    val = (t["fact_achats"].assign(annee=t["fact_achats"]["date"].str[:4].astype(int))
           .merge(t["fact_tarif"].rename(columns={"campagne": "annee"}), on=["article_id", "annee"]))
    val["valeur"] = val["quantite"] * val["prix_brut"]
    par_art = val.groupby("article_id")["valeur"].sum().sort_values(ascending=False)
    top20 = par_art.head(int(len(par_art) * 0.2)).sum() / par_art.sum()
    out += ["## 3. Réalisme et anomalies volontaires", "",
            f"- Lignes tarif sans prix (volontaire, ~0,3 %) : **{manq}**",
            f"- Articles sans aucun achat : **{sans_achat}**",
            f"- Articles entrés après 2023 : **{int((cyc['campagne_debut'] > 2023).sum())}**, "
            f"sortis avant 2026 : **{int((cyc['campagne_fin'] < 2026).sum())}**",
            f"- Pareto : 20 % des articles = **{fr(top20, 0)}** de la dépense (cible ≈ 80 %)",
            ""]
    dep = val.groupby("annee")["valeur"].sum()
    out += ["Dépense valorisée au prix brut par an (2026 : janvier à septembre) :", "",
            tableau(pd.DataFrame({"année": dep.index, "dépense": [eur(v) for v in dep.values]})), ""]

    # 4. Variations matières
    pv = var.pivot(index="matiere_id", columns="campagne", values="variation")
    lib = t["dim_matiere"].set_index("matiere_id")["libelle"]
    out += ["## 4. Variation matière par campagne (moyenne 6 mois avant N+1 / avant N)", "",
            tableau(pd.DataFrame({"matière": [lib[m] for m in pv.index],
                                  **{str(c): [pct(v) for v in pv[c]] for c in pv.columns}})), ""]

    # 5. Hausse demandée vs justifiée par fournisseur
    d = detail.dropna(subset=["prix_n", "prix_n1"]).query("volume_n > 0")
    ag = agreger(d, ["fournisseur_id", "campagne"])
    ag["profil"] = ag["fournisseur_id"].map(fourn["profil"])
    ag["nom"] = ag["fournisseur_id"].map(fourn["nom"])
    rows, comportement_ko = [], []
    for f_id, g in ag.groupby("fournisseur_id"):
        prof = g["profil"].iloc[0]
        cells = []
        for r in g.itertuples():
            cells.append(f"{pct(r.demandee)} / {pct(r.justifiee)} ({r.ecart_pts:+.1f})".replace(".", ","))
        e = g["ecart_pts"]
        if prof == "honnete" and (e.abs() > 1).any():
            comportement_ko.append(f"{f_id} honnête hors ±1 pt")
        if prof == "opportuniste" and ((e < 3) | (e > 8)).any():
            comportement_ko.append(f"{f_id} opportuniste hors +3 à +8 pts")
        if prof == "cliquet":
            baisse = g.query("justifiee < 0")
            if baisse.empty:
                comportement_ko.append(f"{f_id} cliquet sans campagne à matière en baisse")
            elif (baisse["demandee"] < 0).any():
                comportement_ko.append(f"{f_id} cliquet avec baisse de prix")
        rows.append([f_id, g["nom"].iloc[0], prof, *cells, eur(g["eur"].sum())])
    camp = sorted(ag["campagne"].unique())
    out += ["## 5. Hausse demandée / justifiée par fournisseur (écart en pts)", "",
            "Pondérée par la valeur N (prix N × volume N). Le profil est caché dans le rapport Power BI.", "",
            tableau(pd.DataFrame(rows, columns=["id", "fournisseur", "profil", *map(str, camp),
                                                "€ renégociables (3 campagnes)"])), ""]
    out += ["Comportements attendus : " + ("**tous vérifiés**" if not comportement_ko
                                          else "**écarts** : " + " ; ".join(comportement_ko)), ""]

    # 6. Synthèse campagne
    tot = agreger(d, ["campagne"])
    out += ["## 6. Synthèse par campagne (chiffres de référence)", "",
            tableau(pd.DataFrame({
                "campagne": tot["campagne"], "articles": tot["nb"], "valeur N": [eur(v) for v in tot["valeur_n"]],
                "hausse demandée": [pct(v, 2) for v in tot["demandee"]],
                "hausse justifiée": [pct(v, 2) for v in tot["justifiee"]],
                "écart pts": [f"{v:+.2f}".replace(".", ",") for v in tot["ecart_pts"]],
                "€ renégociables": [eur(v) for v in tot["eur"]]})), ""]
    top = ag.query("campagne == @camp[-1]").sort_values("eur", ascending=False).head(5)
    out += [f"Top 5 à renégocier, campagne {camp[-1]} :", "",
            tableau(pd.DataFrame({"fournisseur": top["nom"],
                                  "écart pts": [f"{v:+.1f}".replace(".", ",") for v in top["ecart_pts"]],
                                  "€ renégociables": [eur(v) for v in top["eur"]]})), ""]

    # 7. Rattachement
    da = t["dim_article"]
    taux = da["statut_rattachement"].value_counts(normalize=True)
    diff = (da["ref_fournisseur"] != da["ref_erp"]).mean()
    par_f = (pd.crosstab(da["fournisseur_id"], da["statut_rattachement"], normalize="index") * 100).round(1)
    par_f = par_f[["Automatique", "Proposé", "Non rattaché"]].map(lambda v: f"{v:.1f}".replace(".", ","))
    prop = verite.query("statut_rattachement == 'Proposé'")
    precision = (prop["article_id_propose"] == prop["article_id"]).mean() if len(prop) else float("nan")
    out += ["## 7. Rattachement des références", "",
            f"- Référence tarif ≠ référence ERP (brute) : **{fr(diff)}** des articles (cible ~20 %)",
            f"- Automatique **{fr(taux.get('Automatique', 0))}** (objectif ≥ 80 %), "
            f"Proposé **{fr(taux.get('Proposé', 0))}**, Non rattaché **{fr(taux.get('Non rattaché', 0))}**",
            f"- Précision des propositions (bon article proposé) : **{fr(precision)}**", "",
            tableau(par_f.reset_index().assign(fournisseur_id=lambda x: x["fournisseur_id"]
                                               + " " + x["fournisseur_id"].map(fourn["nom"]))), ""]

    out += ["## Verdict", "", "**Contrôles bloquants OK.**" if not ko else
            "**KO** : " + " ; ".join(ko), ""]
    RAPPORT.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))
    return 1 if ko else 0


if __name__ == "__main__":
    sys.exit(main())
