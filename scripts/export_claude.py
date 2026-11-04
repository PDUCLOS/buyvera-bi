"""Volet 2 : exporte les agrégats du tableau de bord Claude (mêmes données, mêmes définitions que Power BI).

Prérequis : precalcul_hausses.py. Sorties claude-dashboard/ :
- campagnes.csv, fournisseurs_2026.csv, matieres.csv : calculés ici en pandas, indépendamment du DAX
- groupe_sites.csv, groupe_articles.csv : vision groupe (generate_groupe.py), surcoût vs meilleur prix du groupe
  et tarifs mal appliqués dans les ERP
- gains_campagnes.csv, gains_fournisseurs.csv : résultats de négociation (économies, taux de transformation)
- controle_powerbi.csv : les 7 chiffres clés lus dans le modèle ouvert dans Power BI Desktop
  (scripts/dax_query.ps1). Si Desktop n'est pas ouvert, le fichier existant est conservé.
"""
from __future__ import annotations

import csv
import io
import subprocess
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
P = RACINE / "data" / "processed"
OUT = RACINE / "claude-dashboard"
CAMPAGNE = 2026
FENETRE, DECALAGE = 6, 0


def agreger(d: pd.DataFrame) -> pd.Series:
    v = d["prix_n"] * d["volume_n"]
    dem = (d["prix_n1"] * d["volume_n"]).sum() / v.sum() - 1
    jus = (d["hausse_justifiee"] * v).sum() / v.sum()
    eur = ((d["prix_n1"] / d["prix_n"] - 1 - d["hausse_justifiee"]).clip(lower=0) * v).sum()
    return pd.Series({"valeur_n": v.sum(), "hausse_demandee": dem, "hausse_justifiee": jus,
                      "ecart_pts": (dem - jus) * 100, "eur_renegociables": eur, "nb_articles": len(d)})


def statut(e: float) -> str:
    return "À renégocier" if e > 3 else ("À surveiller" if e > 1 else "Conforme")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    fha = pd.read_csv(P / "fact_hausse_article.csv")
    fha = fha[(fha["fenetre"] == FENETRE) & (fha["decalage"] == DECALAGE) & fha["comparable"]]
    art = pd.read_csv(P / "dim_article.csv")[["article_id", "fournisseur_id", "famille_id"]]
    fou = pd.read_csv(P / "dim_fournisseur.csv")[["fournisseur_id", "nom"]]
    fam = pd.read_csv(P / "dim_famille.csv")[["famille_id", "univers"]]
    fha = fha.merge(art, on="article_id").merge(fou, on="fournisseur_id").merge(fam, on="famille_id")
    prochaine = fha["campagne"].max()

    hist = fha[fha["campagne"] < prochaine]
    camp = hist.groupby("campagne").apply(agreger, include_groups=False).reset_index()
    camp["plafond_prochaine"] = (lambda d: (d["hausse_justifiee"] * d["prix_n"] * d["volume_n"]).sum()
                                 / (d["prix_n"] * d["volume_n"]).sum())(fha[fha["campagne"] == prochaine])
    camp.round(6).to_csv(OUT / "campagnes.csv", index=False)

    # Fournisseurs, campagne analysée
    par_c = hist.groupby(["nom", "campagne"]).apply(agreger, include_groups=False).reset_index()
    cliquet = (par_c.assign(c=(par_c["hausse_justifiee"] < 0) & (par_c["hausse_demandee"] >= 0))
               .groupby("nom")["c"].sum())
    f26 = par_c[par_c["campagne"] == CAMPAGNE].drop(columns="campagne").set_index("nom")
    f26["univers"] = hist.groupby("nom")["univers"].agg(lambda s: " / ".join(sorted(s.unique())))
    f26["effet_cliquet"] = cliquet
    nxt = fha[fha["campagne"] == prochaine]
    f26["plafond_prochaine"] = nxt.groupby("nom").apply(
        lambda d: (d["hausse_justifiee"] * d["prix_n"] * d["volume_n"]).sum() / (d["prix_n"] * d["volume_n"]).sum(),
        include_groups=False)

    # Levier : matière du panier du fournisseur qui a le plus baissé sur la fenêtre de la campagne
    idx = pd.read_csv(P / "fact_indice.csv", parse_dates=["date"]).pivot(index="date", columns="matiere_id",
                                                                          values="valeur_eur")
    def moy(fin: str) -> pd.Series:
        f = pd.Timestamp(fin)
        return idx[(idx.index >= f - pd.DateOffset(months=FENETRE)) & (idx.index < f)].mean()
    var = moy(f"{CAMPAGNE}-01-01") / moy(f"{CAMPAGNE - 1}-01-01") - 1
    dmat = pd.read_csv(P / "dim_matiere.csv").set_index("matiere_id")["libelle"]
    compo = pd.read_csv(P / "bridge_composition.csv").merge(art, on="article_id").merge(fou, on="fournisseur_id")
    compo = compo[compo["matiere_id"] != "NM"]
    lev = {}
    for nom, g in compo.groupby("nom"):
        mats = g["matiere_id"].unique()
        m = min(mats, key=lambda x: var[x])
        lev[nom] = (dmat[m], var[m])
    f26["levier_matiere"] = [lev[n][0] for n in f26.index]
    f26["levier_variation"] = [lev[n][1] for n in f26.index]
    f26["statut"] = f26["ecart_pts"].map(statut)
    f26 = f26.reset_index().rename(columns={"nom": "fournisseur"}).sort_values("eur_renegociables", ascending=False)
    cols = ["fournisseur", "univers", "statut", "valeur_n", "hausse_demandee", "hausse_justifiee", "ecart_pts",
            "eur_renegociables", "effet_cliquet", "levier_matiere", "levier_variation", "plafond_prochaine", "nb_articles"]
    f26[cols].round(6).to_csv(OUT / "fournisseurs_2026.csv", index=False)

    # Matières : signaux récents et variation acquise pour la prochaine campagne
    last = idx.index.max()
    fin_next = last + pd.DateOffset(months=1)
    rows = []
    for m in [c for c in idx.columns if c not in ("CU_T",)]:
        s = idx[m]
        v3 = s[last] / s[last - pd.DateOffset(months=3)] - 1
        v12 = s[last] / s[last - pd.DateOffset(months=12)] - 1
        acq = (s[(s.index >= fin_next - pd.DateOffset(months=6)) & (s.index < fin_next)].mean()
               / s[(s.index >= pd.Timestamp(f"{prochaine - 1}-01-01") - pd.DateOffset(months=6))
                   & (s.index < pd.Timestamp(f"{prochaine - 1}-01-01"))].mean() - 1)
        sig = "Hausse : à anticiper" if v3 > 0.05 else ("Baisse : convoquer le fournisseur" if v3 < -0.05 else "Stable")
        rows.append({"matiere": dmat[m], "variation_campagne": var[m], "variation_3m": v3, "variation_12m": v12,
                     "acquis_prochaine": acq, "signal": sig, "dernier_mois": last.strftime("%Y-%m")})
    pd.DataFrame(rows).round(6).to_csv(OUT / "matieres.csv", index=False)

    exporter_groupe_gains()
    lire_powerbi()
    print("Exports écrits dans", OUT)


def exporter_groupe_gains() -> None:
    """Vision groupe (prix payés par site) et gains de négociation."""
    ent = pd.read_csv(P / "dim_entite.csv")
    ach = pd.read_csv(P / "fact_achats_entite.csv").merge(ent, on="entite_id")
    ach["montant"] = ach["quantite"] * ach["prix_paye"]
    retard = ach["statut_prix"] == "Retard d'application"
    durable = ach["statut_prix"] == "Écart durable"
    ach["ecart_retard"] = ach["ecart_application"].where(retard, 0)
    ach["ecart_durable"] = ach["ecart_application"].where(durable, 0)
    ach["paye_en_trop"] = ach["ecart_application"].clip(lower=0)
    sites = ach.groupby(["nom", "origine"]).agg(
        montant=("montant", "sum"), surcout=("surcout_vs_meilleur", "sum"), ecart_retard=("ecart_retard", "sum"),
        ecart_durable=("ecart_durable", "sum"), paye_en_trop=("paye_en_trop", "sum")).reset_index()
    a_corriger = ach[retard | durable].groupby("nom")["article_id"].nunique()
    sites["articles_a_corriger"] = sites["nom"].map(a_corriger).fillna(0).astype(int)
    sites["pct_surcout"] = sites["surcout"] / sites["montant"]
    sites = sites.rename(columns={"nom": "site"}).sort_values("surcout", ascending=False)
    sites.round(6).to_csv(OUT / "groupe_sites.csv", index=False)

    lib = pd.read_csv(P / "dim_article.csv")[["article_id", "designation"]]
    art = (ach.groupby(["article_id", "nom"]).agg(surcout=("surcout_vs_meilleur", "sum"),
                                                  statut=("statut_prix", lambda s: s.value_counts().index[0]))
           .reset_index().merge(lib, on="article_id").sort_values("surcout", ascending=False).head(10))
    art["cle"] = art["article_id"] + "-" + art["nom"]
    art = art.rename(columns={"nom": "site", "designation": "article"})
    art[["cle", "article", "site", "statut", "surcout"]].round(2).to_csv(OUT / "groupe_articles.csv", index=False)

    neg = pd.read_csv(P / "fact_negociation.csv").merge(
        pd.read_csv(P / "dim_fournisseur.csv")[["fournisseur_id", "nom"]], on="fournisseur_id")
    def agg(d: pd.DataFrame) -> pd.Series:
        v = d["valeur_n"]
        return pd.Series({"valeur_n": v.sum(),
                          "hausse_demandee": (d["hausse_demandee"] * v).sum() / v.sum(),
                          "hausse_justifiee": (d["hausse_justifiee"] * v).sum() / v.sum(),
                          "hausse_obtenue": (d["hausse_obtenue"] * v).sum() / v.sum(),
                          "potentiel": d["eur_renegociables"].sum(), "economies": d["economie_eur"].sum()})
    camp = neg.groupby("campagne").apply(agg, include_groups=False).reset_index()
    camp["taux_transformation"] = camp["economies"] / camp["potentiel"]
    camp.round(6).to_csv(OUT / "gains_campagnes.csv", index=False)
    fou = neg.groupby("nom").apply(agg, include_groups=False).reset_index().rename(columns={"nom": "fournisseur"})
    fou["taux_transformation"] = (fou["economies"] / fou["potentiel"]).where(fou["potentiel"] > 0)
    fou.sort_values("economies", ascending=False).round(6).to_csv(OUT / "gains_fournisseurs.csv", index=False)


def lire_powerbi() -> None:
    """Relève les 7 chiffres clés dans le modèle Power BI ouvert (moteur local)."""
    dax = RACINE / "tests" / "dax" / "10_controle_croise.dax"
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            str(RACINE / "scripts" / "dax_query.ps1"), "-Fichier", str(dax)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        print("Power BI non joignable : controle_powerbi.csv inchangé")
        return
    lignes = [l for l in r.stdout.splitlines() if "\t" in l]
    if r.returncode or len(lignes) < 2:
        print("Power BI non joignable : controle_powerbi.csv inchangé")
        return
    lu = list(csv.reader(io.StringIO("\n".join(lignes)), delimiter="\t"))
    entete = [c.strip("[]") for c in lu[0]]
    with open(OUT / "controle_powerbi.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["indicateur", "valeur_powerbi"])
        for i, v in zip(entete, lu[1]):
            w.writerow([i, v])
    print("controle_powerbi.csv relevé dans Power BI Desktop")


if __name__ == "__main__":
    main()
