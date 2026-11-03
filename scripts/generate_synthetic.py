"""Génère les données synthétiques Buyvera BI à partir des vrais indices matières.

Prérequis : python scripts/fetch_indices.py (fact_indice.csv, dim_matiere.csv).

Tout est fictif (fournisseurs, articles, prix, volumes) sauf les indices matières.
La hausse fournisseur se calcule ainsi : hausse justifiée (vrais indices) + biais du profil + bruit.
Graine fixe : deux exécutions donnent exactement les mêmes fichiers.

Sorties data/processed/ : dim_date, dim_fournisseur, dim_famille, dim_acheteur, dim_article,
bridge_composition, fact_tarif, fact_achats.
Sortie de contrôle : data/controle/hausses_articles.csv (calcul article par article, sert à
valider les mesures DAX et le tableau de bord Claude).
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20260103
RACINE = Path(__file__).resolve().parents[1]
PROCESSED = RACINE / "data" / "processed"
CONTROLE = RACINE / "data" / "controle"

CAMPAGNES = [2023, 2024, 2025, 2026]          # tarif applicable au 1er janvier
FIN_ACHATS = "2026-09-01"                     # dernier mois d'indice disponible
FENETRE_MOIS = 6                              # période de référence de la variation matière
SEUIL_PROPOSE = 0.80                          # similarité de désignation pour « Proposé »
NB_ARTICLES = 3000

rng = np.random.default_rng(SEED)

# --------------------------------------------------------------------------------------
# Référentiels
# --------------------------------------------------------------------------------------
ACHETEURS = [
    ("ACH1", "Camille Rouvier", "acheteur.transmission@buyvera.example", "Acheteur", "Transmission"),
    ("ACH2", "Sami Delorme", "acheteur.cvc@buyvera.example", "Acheteur", "CVC"),
    ("ACH3", "Claire Bastide", "responsable.achats@buyvera.example", "Direction", "Tous"),
]

# famille_id, libellé, univers, acheteur, nb articles, budget annuel (€), prix médian (€),
# dispersion prix, unité, composition type {matière: part}
FAMILLES = [
    ("ROUL", "Roulements", "Transmission", "ACH1", 600, 2.5e6, 25, 1.0, "PCE",
     {"FE": 0.45, "NI": 0.05, "PL": 0.05}),
    ("MOT", "Moteurs électriques", "Transmission", "ACH1", 350, 3.0e6, 450, 0.8, "PCE",
     {"FE": 0.35, "CU": 0.20, "AL": 0.10}),
    ("RED", "Réducteurs", "Transmission", "ACH1", 250, 2.5e6, 900, 0.7, "PCE",
     {"FE": 0.45, "AL": 0.10, "CU": 0.05}),
    ("COUR", "Courroies et chaînes", "Transmission", "ACH1", 300, 1.2e6, 60, 0.9, "PCE",
     {"FE": 0.30, "PL": 0.25}),
    ("PAC", "Pompes à chaleur", "CVC", "ACH2", 200, 4.0e6, 4500, 0.5, "PCE",
     {"CU": 0.15, "AL": 0.15, "FE": 0.20, "PL": 0.05}),
    ("CLIM", "Climatisation", "CVC", "ACH2", 300, 3.0e6, 1800, 0.6, "PCE",
     {"CU": 0.18, "AL": 0.17, "FE": 0.15, "PL": 0.05}),
    ("TUBE", "Tubes et raccords cuivre", "CVC", "ACH2", 650, 2.5e6, 15, 1.0, "PCE",
     {"CU": 0.60, "ZN": 0.08, "PL": 0.02}),
    ("VENT", "Ventilation", "CVC", "ACH2", 350, 1.3e6, 350, 0.8, "PCE",
     {"FE": 0.25, "ZN": 0.05, "AL": 0.10, "PL": 0.10}),
]

# fournisseur_id, nom (fictif), pays, préfixe ref, préfixe tarif, profil (caché)
FOURNISSEURS = [
    ("F01", "Rotavel", "FR", "RV", "ROT", "honnete"),
    ("F02", "Mekandra", "FR", "MK", "MKD", "honnete"),
    ("F03", "Tressile", "IT", "TS", "TRS", "honnete"),
    ("F04", "Brunelle Aéraulique", "FR", "BA", "BRA", "honnete"),
    ("F05", "Kelmaro Antriebe", "DE", "KL", "KLM", "opportuniste"),
    ("F06", "Vandrelo", "ES", "VD", "VDR", "opportuniste"),
    ("F07", "Orlenza Thermique", "FR", "OZ", "ORZ", "opportuniste"),
    ("F08", "Cuprana", "IT", "CP", "CPR", "opportuniste"),
    ("F09", "Zentrix Technik", "DE", "ZX", "ZTX", "cliquet"),
    ("F10", "Aerivo Klima", "BE", "AV", "AER", "cliquet"),
    ("F11", "Halderis", "NL", "HD", "HLD", "refs_modifiees"),
    ("F12", "Sorvane", "FR", "SV", "SRV", "refs_modifiees"),
]

# Répartition des articles d'une famille entre fournisseurs
PORTEFEUILLE = {
    "ROUL": {"F01": 0.5, "F05": 0.5},
    "MOT": {"F02": 0.4, "F06": 0.35, "F09": 0.25},
    "RED": {"F09": 0.5, "F11": 0.5},
    "COUR": {"F03": 0.55, "F12": 0.45},
    "PAC": {"F04": 0.5, "F07": 0.5},
    "CLIM": {"F07": 0.4, "F10": 0.6},
    "TUBE": {"F08": 0.55, "F10": 0.45},
    "VENT": {"F12": 0.5, "F04": 0.5},
}

# Saisonnalité mensuelle des achats (indice 1 = moyenne)
SAISON = {
    "Transmission": [1.05, 1.05, 1.1, 1.05, 1.0, 1.0, 0.95, 0.6, 1.05, 1.1, 1.05, 1.0],
    "PAC": [1.3, 1.2, 1.0, 0.8, 0.6, 0.5, 0.5, 0.6, 1.0, 1.4, 1.5, 1.6],
    "CLIM": [0.5, 0.5, 0.7, 1.0, 1.4, 1.8, 1.9, 1.3, 0.9, 0.7, 0.6, 0.7],
    "CVC": [0.85, 0.9, 1.0, 1.1, 1.1, 1.1, 1.0, 0.75, 1.1, 1.1, 1.0, 0.9],
}

# --------------------------------------------------------------------------------------
# Désignations
# --------------------------------------------------------------------------------------
def designation(famille: str) -> str:
    c = lambda xs: xs[rng.integers(len(xs))]  # noqa: E731
    if famille == "ROUL":
        serie = c(["60", "62", "63", "22", "32", "NU2", "NJ3", "UC2"])
        return (f"{c(['Roulement à billes', 'Roulement à rouleaux', 'Roulement à rotule', 'Palier auto-aligneur'])} "
                f"{serie}{rng.integers(0, 40):02d} {c(['2RS', 'ZZ', 'C3', 'K', 'E', '2Z C3'])}")
    if famille == "MOT":
        return (f"Moteur {c(['asynchrone', 'frein', 'à aimants', 'monophasé'])} "
                f"{c(['0,37', '0,75', '1,5', '2,2', '4', '5,5', '7,5', '11', '15', '22'])} kW "
                f"{c(['2P', '4P', '6P'])} {c(['B3', 'B5', 'B14', 'B35'])} {c(['IE2', 'IE3', 'IE4'])}")
    if famille == "RED":
        return (f"Réducteur {c(['roue et vis', 'coaxial', 'orthogonal', 'pendulaire', 'planétaire'])} "
                f"taille {rng.integers(30, 160)} i={c(['5', '7,5', '10', '15', '20', '28', '40', '60'])} "
                f"{c(['arbre creux', 'arbre plein', 'bride B5', 'bride B14'])}")
    if famille == "COUR":
        if rng.random() < 0.5:
            return (f"Courroie {c(['trapézoïdale', 'dentée', 'poly-V', 'crantée'])} "
                    f"{c(['SPZ', 'SPA', 'SPB', 'XPZ', 'HTD 8M', 'AT10', 'PJ'])} {rng.integers(500, 3550)}")
        return (f"Chaîne à rouleaux {c(['06B-1', '08B-1', '10B-1', '12B-2', '16B-1'])} "
                f"{c(['5 m', '10 m', 'acier zingué', 'inox'])} {c(['simple', 'duplex'])}")
    if famille == "PAC":
        return (f"Pompe à chaleur {c(['air/eau', 'air/air', 'eau/eau', 'hybride'])} "
                f"{rng.integers(4, 30)} kW {c(['monobloc', 'split', 'bi-bloc'])} {c(['R32', 'R290', 'R410A'])}")
    if famille == "CLIM":
        return (f"Climatiseur {c(['mural', 'cassette', 'gainable', 'console', 'plafonnier'])} "
                f"{c(['2,5', '3,5', '5', '7', '10', '14'])} kW {c(['inverter', 'réversible'])} "
                f"{c(['R32', 'R410A'])} {c(['blanc', 'gris', 'unité ext.', 'unité int.'])}")
    if famille == "TUBE":
        d = c(["10", "12", "14", "16", "18", "22", "28", "35", "42", "54"])
        if rng.random() < 0.4:
            return f"Tube cuivre {c(['écroui', 'recuit', 'pré-isolé'])} Ø{d}x{c(['0,8', '1', '1,2', '1,5'])} {c(['barre 5 m', 'couronne 25 m', 'couronne 50 m'])}"
        return (f"Raccord {c(['coude 90°', 'coude 45°', 'té égal', 'manchon', 'réduction', 'union', 'bouchon'])} "
                f"{c(['à souder', 'à sertir', 'laiton fileté', 'à compression'])} Ø{d}")
    if famille == "VENT":
        return (f"{c(['Ventilateur centrifuge', 'Caisson VMC', 'Extracteur hélicoïde', 'Gaine galva', 'Bouche d’extraction'])} "
                f"Ø{c(['125', '160', '200', '250', '315', '400'])} {c(['simple flux', 'double flux', 'basse conso', 'ATEX'])} "
                f"{rng.integers(100, 9000)} m³/h")
    raise ValueError(famille)


ABREVIATIONS = [("Roulement", "Roult"), ("Moteur", "Mot."), ("Réducteur", "Red."),
                ("Courroie", "Crr."), ("Pompe à chaleur", "PAC"), ("Climatiseur", "Clim."),
                ("Raccord", "Racc."), ("Ventilateur", "Ventil."), ("à souder", "a souder"),
                ("é", "e"), ("è", "e")]


def designation_proche(d: str) -> str:
    """Même article, saisie différente : abréviation, accents, casse."""
    for long_, court in rng.permutation(np.array(ABREVIATIONS, dtype=object))[:3]:
        d = d.replace(long_, court)
    return d.upper() if rng.random() < 0.4 else d


def designation_renommee(famille: str) -> str:
    """Article renommé par le fournisseur (nouvelle gamme) : désignation méconnaissable."""
    gamme = rng.choice(["NEXA", "ORION", "VEGA", "PRIMA", "TERRA", "ALTIS"])
    return f"Gamme {gamme} {famille.lower()}-{rng.integers(100, 999)} réf. catalogue {rng.integers(2026, 2030)}"


def normaliser(ref: str, prefixe_tarif: str) -> str:
    r = re.sub(r"[^0-9A-Z]", "", ref.upper())
    return r[len(prefixe_tarif):] if r.startswith(prefixe_tarif) else r


# --------------------------------------------------------------------------------------
# Indices → variation matière par campagne
# --------------------------------------------------------------------------------------
def variations_matiere(indices: pd.DataFrame) -> pd.DataFrame:
    """Variation de la moyenne des FENETRE_MOIS mois avant la campagne N+1 vs avant la campagne N."""
    lignes = []
    piv = indices.pivot(index="date", columns="matiere_id", values="valeur_eur").sort_index()
    for n, n1 in zip(CAMPAGNES[:-1], CAMPAGNES[1:]):
        def moyenne(annee: int) -> pd.Series:
            fin = pd.Timestamp(f"{annee}-01-01")
            debut = fin - pd.DateOffset(months=FENETRE_MOIS)
            return piv[(piv.index >= debut) & (piv.index < fin)].mean()
        var = moyenne(n1) / moyenne(n) - 1
        for m, v in var.items():
            lignes.append({"campagne": n1, "matiere_id": m, "variation": v})
    return pd.DataFrame(lignes)


# --------------------------------------------------------------------------------------
# Génération
# --------------------------------------------------------------------------------------
def generer_articles() -> tuple[pd.DataFrame, pd.DataFrame]:
    fourn = {f[0]: f for f in FOURNISSEURS}
    articles, compo = [], []
    numero = 0
    for fam_id, _lib, univers, _ach, nb, _budget, prix_med, sigma, unite, base in FAMILLES:
        fournisseurs = list(PORTEFEUILLE[fam_id])
        poids = np.array(list(PORTEFEUILLE[fam_id].values()))
        for _ in range(nb):
            numero += 1
            f_id = fournisseurs[rng.choice(len(fournisseurs), p=poids / poids.sum())]
            _, _, _, pref, _, _ = fourn[f_id]
            ref = f"{pref}{rng.integers(10000, 99999)}{rng.choice(['', 'A', 'B', 'S'])}"
            # Cycle de vie : 80 % présents dès 2023, puis entrées et sorties à chaque campagne
            debut = 2023 if rng.random() < 0.80 else int(rng.choice(CAMPAGNES[1:]))
            fin = 2026
            if rng.random() < 0.12 and debut < 2026:
                fin = int(rng.choice([c for c in CAMPAGNES if c >= debut and c < 2026]))
            articles.append({
                "article_id": f"A{numero:05d}", "fournisseur_id": f_id, "famille_id": fam_id,
                "ref_erp": ref, "designation": designation(fam_id), "unite": unite,
                "campagne_debut": debut, "campagne_fin": fin,
                "prix_initial": round(float(prix_med * rng.lognormal(0, sigma)), 2),
            })
            # Composition : parts type ± 25 %, parfois une matière mineure absente (2 à 4 matières)
            parts = {m: p * rng.uniform(0.75, 1.25) for m, p in base.items()}
            if len(parts) > 2 and rng.random() < 0.3:
                parts.pop(min(parts, key=parts.get))
            for m, p in parts.items():
                compo.append({"article_id": f"A{numero:05d}", "matiere_id": m, "part": round(p, 4)})
            compo.append({"article_id": f"A{numero:05d}", "matiere_id": "NM",
                          "part": round(1 - sum(round(p, 4) for p in parts.values()), 4)})
    return pd.DataFrame(articles), pd.DataFrame(compo)


def biais_fournisseurs() -> dict[tuple[str, int], float]:
    """Biais en points de hausse par fournisseur et par campagne, selon le profil caché."""
    biais = {}
    for f_id, *_, profil in FOURNISSEURS:
        base = {"honnete": rng.uniform(-0.4, 0.4), "opportuniste": rng.uniform(4.0, 7.0),
                "cliquet": rng.uniform(0.0, 0.6), "refs_modifiees": rng.uniform(0.8, 1.8)}[profil]
        for c in CAMPAGNES[1:]:
            b = base + rng.normal(0, 0.3 if profil != "opportuniste" else 0.6)
            if profil == "honnete":
                b = float(np.clip(b, -0.7, 0.7))
            if profil == "opportuniste":
                b = float(np.clip(b, 3.3, 7.7))
            biais[(f_id, c)] = b / 100
    return biais


def generer_tarifs(articles: pd.DataFrame, compo: pd.DataFrame, var: pd.DataFrame
                   ) -> tuple[pd.DataFrame, pd.DataFrame]:
    profils = {f[0]: f[5] for f in FOURNISSEURS}
    biais = biais_fournisseurs()
    # Hausse justifiée par article et campagne : Σ part × variation (matières + non matière)
    just = (compo.merge(var, on="matiere_id")
                 .assign(contrib=lambda d: d["part"] * d["variation"])
                 .groupby(["article_id", "campagne"], as_index=False)["contrib"].sum()
                 .rename(columns={"contrib": "hausse_justifiee"}))
    just = just.set_index(["article_id", "campagne"])["hausse_justifiee"]

    tarifs, detail = [], []
    for a in articles.itertuples():
        prix = a.prix_initial
        for c in CAMPAGNES:
            if c < a.campagne_debut or c > a.campagne_fin:
                continue
            if c > a.campagne_debut:
                j = float(just[(a.article_id, c)])
                bruit = rng.normal(0, 0.008)
                if profils[a.fournisseur_id] == "cliquet" and j < 0:
                    # Effet cliquet : la baisse matière n'est jamais répercutée
                    h = abs(rng.normal(0, 0.004))
                else:
                    h = j + biais[(a.fournisseur_id, c)] + bruit
                prix_prec = prix
                prix = round(prix_prec * (1 + h), 2)
                detail.append({"article_id": a.article_id, "fournisseur_id": a.fournisseur_id,
                               "campagne": c, "prix_n": prix_prec, "prix_n1": prix,
                               "hausse_justifiee": j})
            tarifs.append({"article_id": a.article_id, "fournisseur_id": a.fournisseur_id,
                           "campagne": c, "date_effet": f"{c}-01-01", "prix_brut": prix})
    fact = pd.DataFrame(tarifs)
    # Quelques prix manquants volontaires (ligne tarif reçue sans prix) : 0,3 %
    manquants = rng.random(len(fact)) < 0.003
    fact.loc[manquants, "prix_brut"] = np.nan
    return fact, pd.DataFrame(detail)


def generer_achats(articles: pd.DataFrame) -> pd.DataFrame:
    fam = {f[0]: f for f in FAMILLES}
    mois = pd.date_range("2023-01-01", FIN_ACHATS, freq="MS")
    # Poids Pareto : quelques articles portent l'essentiel de la dépense
    poids = rng.lognormal(0, 1.7, len(articles))
    articles = articles.assign(poids=poids)
    articles["part_famille"] = articles["poids"] / articles.groupby("famille_id")["poids"].transform("sum")

    lignes = []
    for a in articles.itertuples():
        _, _, univers, _, _, budget, *_ = fam[a.famille_id]
        saison = SAISON.get(a.famille_id, SAISON[univers])
        qte_annuelle = budget * a.part_famille / a.prix_initial
        tendance = {y: rng.normal(1, 0.08) for y in range(2023, 2027)}
        for m in mois:
            if m.year < a.campagne_debut or m.year > a.campagne_fin:
                continue
            lam = max(qte_annuelle / 12 * saison[m.month - 1] * tendance[m.year], 0)
            q = int(rng.poisson(lam))
            if q > 0:
                lignes.append({"article_id": a.article_id, "date": m.date(), "quantite": q})
    return pd.DataFrame(lignes)


def rattacher(articles: pd.DataFrame) -> pd.DataFrame:
    """Simule le tarif reçu (ref + désignation fournisseur) puis le rattache à l'ERP."""
    fourn = {f[0]: f for f in FOURNISSEURS}
    refs_tarif, desig_tarif, cas = [], [], []
    for a in articles.itertuples():
        _, _, _, pref, pref_tarif, profil = fourn[a.fournisseur_id]
        tirage = rng.random()
        p_format, p_change = (0.20, 0.30) if profil == "refs_modifiees" else (0.15, 0.0)
        ref, d, c = a.ref_erp, a.designation, "identique"
        if tirage < p_format:
            # Même référence, autre format : tirets, espaces, préfixe, casse
            num = ref[len(pref):]
            ref = rng.choice([f"{pref}-{num}", f"{pref} {num[:2]} {num[2:]}",
                              f"{pref_tarif}-{pref}{num}", f"{pref.lower()}.{num}"])
            c = "format"
        elif tirage < p_format + p_change:
            # Nouvelle référence fournisseur (changement de codification)
            ref = f"{pref}N{rng.integers(100000, 999999)}"
            if rng.random() < 0.65:
                d, c = designation_proche(a.designation), "nouvelle_ref"
            else:
                d, c = designation_renommee(a.famille_id), "renomme"
        refs_tarif.append(ref)
        desig_tarif.append(d)
        cas.append(c)
    articles = articles.assign(ref_fournisseur=refs_tarif, designation_tarif=desig_tarif, cas_reel=cas)

    statut, proposition, score = [], [], []
    for f_id, grp in articles.groupby("fournisseur_id", sort=False):
        pref_tarif = fourn[f_id][4]
        erp = {normaliser(r, pref_tarif): i for i, r in zip(grp["article_id"], grp["ref_erp"])}
        erp_desig = list(zip(grp["article_id"], grp["designation"].str.lower()))
        for a in grp.itertuples():
            cle = normaliser(a.ref_fournisseur, pref_tarif)
            if cle in erp:
                statut.append((a.article_id, "Automatique", erp[cle], 1.0))
                continue
            cible = a.designation_tarif.lower()
            meilleur = max(erp_desig, key=lambda x: SequenceMatcher(None, cible, x[1]).ratio())
            s = SequenceMatcher(None, cible, meilleur[1]).ratio()
            if s >= SEUIL_PROPOSE:
                statut.append((a.article_id, "Proposé", meilleur[0], round(s, 3)))
            else:
                statut.append((a.article_id, "Non rattaché", "", round(s, 3)))
    st = pd.DataFrame(statut, columns=["article_id", "statut_rattachement",
                                       "article_id_propose", "score_rattachement"])
    return articles.merge(st, on="article_id")


def dim_date() -> pd.DataFrame:
    mois = pd.date_range("2022-01-01", "2026-12-01", freq="MS")
    noms = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
    return pd.DataFrame({
        "date": mois.date, "annee": mois.year, "mois": mois.month,
        "libelle_mois": [f"{noms[m.month - 1]} {m.year}" for m in mois],
        "annee_mois": mois.strftime("%Y-%m"),
        "trimestre": "T" + mois.quarter.astype(str),
        "campagne": mois.year,  # tarif en vigueur sur le mois
    })


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    CONTROLE.mkdir(parents=True, exist_ok=True)
    indices = pd.read_csv(PROCESSED / "fact_indice.csv", parse_dates=["date"])
    indices = indices[indices["matiere_id"] != "CU_T"]

    var = variations_matiere(indices)
    articles, compo = generer_articles()
    tarifs, detail = generer_tarifs(articles, compo, var)
    achats = generer_achats(articles)
    articles = rattacher(articles)

    # Volume N (quantité achetée sur l'année de la campagne N) pour le fichier de contrôle
    vol = (achats.assign(annee=pd.to_datetime(achats["date"]).dt.year)
                 .groupby(["article_id", "annee"], as_index=False)["quantite"].sum())
    tarif_idx = tarifs.set_index(["article_id", "campagne"])["prix_brut"]
    detail["prix_n"] = [tarif_idx.get((a, c - 1)) for a, c in zip(detail["article_id"], detail["campagne"])]
    detail["prix_n1"] = [tarif_idx.get((a, c)) for a, c in zip(detail["article_id"], detail["campagne"])]
    detail = (detail.merge(vol.rename(columns={"annee": "campagne_n", "quantite": "volume_n"}).assign(
                  campagne=lambda d: d["campagne_n"] + 1)[["article_id", "campagne", "volume_n"]],
                  on=["article_id", "campagne"], how="left")
                    .fillna({"volume_n": 0}))
    detail["hausse_demandee"] = detail["prix_n1"] / detail["prix_n"] - 1
    detail["ecart"] = detail["hausse_demandee"] - detail["hausse_justifiee"]
    detail["valeur_n"] = detail["prix_n"] * detail["volume_n"]
    detail["eur_renegociables"] = detail["ecart"].clip(lower=0) * detail["valeur_n"]

    fam = pd.DataFrame([f[:4] for f in FAMILLES], columns=["famille_id", "libelle", "univers", "acheteur_id"])
    fourn = pd.DataFrame([(f[0], f[1], f[2], "EUR", f[4], f[5]) for f in FOURNISSEURS],
                         columns=["fournisseur_id", "nom", "pays", "devise", "prefixe_tarif", "profil"])
    ach = pd.DataFrame(ACHETEURS, columns=["acheteur_id", "nom", "email", "role", "perimetre"])

    articles[["article_id", "ref_fournisseur", "ref_erp", "designation", "designation_tarif",
              "famille_id", "fournisseur_id", "unite", "campagne_debut", "campagne_fin",
              "statut_rattachement", "article_id_propose", "score_rattachement"]
             ].to_csv(PROCESSED / "dim_article.csv", index=False)
    compo.to_csv(PROCESSED / "bridge_composition.csv", index=False)
    tarifs.to_csv(PROCESSED / "fact_tarif.csv", index=False)
    achats.to_csv(PROCESSED / "fact_achats.csv", index=False)
    fam.to_csv(PROCESSED / "dim_famille.csv", index=False)
    fourn.to_csv(PROCESSED / "dim_fournisseur.csv", index=False)
    ach.to_csv(PROCESSED / "dim_acheteur.csv", index=False)
    dim_date().to_csv(PROCESSED / "dim_date.csv", index=False)
    var.to_csv(CONTROLE / "variations_matiere.csv", index=False)
    detail.to_csv(CONTROLE / "hausses_articles.csv", index=False)
    articles[["article_id", "fournisseur_id", "cas_reel", "statut_rattachement",
              "article_id_propose"]].to_csv(CONTROLE / "rattachement_verite.csv", index=False)
    print("Tables générées dans", PROCESSED)


if __name__ == "__main__":
    main()
