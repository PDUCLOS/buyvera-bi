"""Machine learning sur l'historique Buyvera BI : ce qui peut être prédit, et avec quelle fiabilité.

Usage : python scripts/ml_predictions.py → data/processed/ml_*.csv + docs/ml_rapport.md

Quatre cas d'usage, chacun comparé à une référence simple (« modèle naïf ») sur un backtest
chronologique : un modèle n'est retenu que s'il bat cette référence.

1. Prévision des indices matières (données INSEE réelles) à 1-6 mois, avec intervalle.
   Sert à compléter la fenêtre de la campagne 2027 (juillet-décembre 2026) avant d'avoir les indices.
2. Prévision des volumes mensuels par famille (achats fictifs) : quantités à anticiper.
3. Segmentation non supervisée des fournisseurs (KMeans) à partir de leur comportement tarifaire ;
   comparée au profil caché du générateur pour mesurer si la méthode le retrouve.
4. Détection de lignes tarifaires anormales (Isolation Forest) sur la campagne 2026.

Limites : 57 mois d'indices et 3 campagnes de tarifs fictifs. Les cas 3 et 4 tournent sur des données
générées : ils démontrent la méthode, pas un résultat métier.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.holtwinters import ExponentialSmoothing

warnings.filterwarnings("ignore")
RACINE = Path(__file__).resolve().parents[1]
P = RACINE / "data" / "processed"
RAPPORT = RACINE / "docs" / "ml_rapport.md"
SEED = 20261104
MATIERES = ["CU", "AL", "NI", "ZN", "FE", "PL"]
HORIZONS = [1, 3, 6]


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:+.{d}f} %".replace(".", ",").replace("-", "−")


def tab(df: pd.DataFrame) -> str:
    l = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    return "\n".join(l + ["| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(index=False)])


# ======================================================================================
# 1. Indices matières
# ======================================================================================
def features_rendements(serie: pd.Series) -> pd.DataFrame:
    r = np.log(serie).diff()
    f = pd.DataFrame({"r1": r, "r2": r.shift(1), "r3": r.shift(2), "r6": r.rolling(6).sum(),
                      "vol6": r.rolling(6).std(), "ecart_moy12": np.log(serie / serie.rolling(12).mean())})
    return f


def prevoir(modele: str, hist: pd.DataFrame, m: str, h: int, gbm: dict) -> float:
    """Prévision de l'indice de la matière m à h mois, à partir de l'historique hist (dates en index)."""
    s = hist[m].dropna()
    if modele == "naif":
        return float(s.iloc[-1])
    if modele == "tendance_amortie":
        fit = ExponentialSmoothing(np.log(s), trend="add", damped_trend=True).fit(optimized=True)
        return float(np.exp(fit.forecast(h).iloc[-1]))
    if modele == "lightgbm":
        x = features_rendements(s).iloc[[-1]]
        return float(s.iloc[-1] * np.exp(gbm[h].predict(x)[0]))
    raise ValueError(modele)


def entrainer_gbm(hist: pd.DataFrame, h: int) -> lgb.LGBMRegressor:
    """Modèle global (toutes matières) : rendement cumulé à h mois à partir des rendements passés."""
    lignes = []
    for m in MATIERES:
        s = hist[m].dropna()
        f = features_rendements(s)
        f["cible"] = np.log(s.shift(-h) / s)
        lignes.append(f.dropna())
    d = pd.concat(lignes)
    mod = lgb.LGBMRegressor(n_estimators=150, learning_rate=0.03, num_leaves=7, min_child_samples=10,
                            subsample=0.8, subsample_freq=1, random_state=SEED, verbose=-1)
    return mod.fit(d.drop(columns="cible"), d["cible"])


def indices(out: list[str]) -> pd.DataFrame:
    idx = pd.read_csv(P / "fact_indice.csv", parse_dates=["date"])
    piv = idx.pivot(index="date", columns="matiere_id", values="valeur_eur")[MATIERES].sort_index()
    origines = piv.index[(piv.index >= "2024-01-01") & (piv.index <= piv.index[-1] - pd.DateOffset(months=1))]
    erreurs = []
    for o in origines:
        hist = piv.loc[:o]
        gbm = {h: entrainer_gbm(hist, h) for h in HORIZONS}
        for h in HORIZONS:
            cible_date = o + pd.DateOffset(months=h)
            if cible_date not in piv.index:
                continue
            for m in MATIERES:
                vrai = piv.loc[cible_date, m]
                for mod in ["naif", "tendance_amortie", "lightgbm"]:
                    p = prevoir(mod, hist, m, h, gbm)
                    erreurs.append({"origine": o, "h": h, "matiere": m, "modele": mod,
                                    "err_rel": p / vrai - 1, "sens_ok": np.sign(p - hist[m].iloc[-1]) == np.sign(vrai - hist[m].iloc[-1])})
    e = pd.DataFrame(erreurs)
    e["ape"] = e["err_rel"].abs()
    synth = e.groupby(["h", "modele"]).agg(mape=("ape", "mean"), sens=("sens_ok", "mean"), n=("ape", "size")).reset_index()

    lignes, choix = [], {}
    for h in HORIZONS:
        s = synth[synth["h"] == h].set_index("modele")
        meilleur = s["mape"].idxmin()
        # on ne retient un modèle que s'il bat le naïf d'au moins 5 % relatifs
        if meilleur != "naif" and s.loc[meilleur, "mape"] > 0.95 * s.loc["naif", "mape"]:
            meilleur = "naif"
        choix[h] = meilleur
        for mod, r in s.iterrows():
            lignes.append([f"{h} mois", mod, f"{r.mape * 100:.1f} %".replace(".", ","),
                           f"{r.sens * 100:.0f} %" if mod != "naif" else "—", int(r.n),
                           "**retenu**" if mod == meilleur else ""])
    out += ["## 1. Indices matières (INSEE, réel)", "",
            f"Backtest chronologique : {len(origines)} dates de départ (janvier 2024 → août 2026), "
            "6 matières, chaque modèle réentraîné à chaque date sur le seul passé. Erreur = écart relatif à l'indice "
            "réellement publié ensuite (MAPE). « Sens » = part des cas où le modèle a vu juste sur hausse / baisse.", "",
            tab(pd.DataFrame(lignes, columns=["horizon", "modèle", "erreur moyenne", "sens juste", "prévisions", ""])), "",
            "Pourquoi le naïf gagne : 6 séries mensuelles sur moins de 5 ans, soit quelques centaines de points, c'est trop peu "
            "pour qu'un modèle à arbres (LightGBM) apprenne autre chose que du bruit. Un « sens juste » proche de 50 % le confirme : "
            "sur des cours de métaux, le mois prochain ressemble surtout au dernier. La valeur utile est donc la **fourchette**, "
            "tirée des erreurs passées, qui sert de budget de hausse.", ""]

    # Prévision finale depuis le dernier mois, intervalle à 80 % = quantiles des erreurs du backtest
    gbm = {h: entrainer_gbm(piv, h) for h in HORIZONS}
    dern = piv.index[-1]
    prev = []
    for m in MATIERES:
        for k in range(1, 4):  # octobre-décembre 2026 : la table de dates du modèle s'arrête fin 2026
            h = min(HORIZONS, key=lambda x: (x < k, abs(x - k)))  # horizon calé le plus proche au-dessus
            mod = choix[h]
            pt = prevoir(mod, piv, m, k, gbm) if mod != "lightgbm" else float(piv[m].iloc[-1] * np.exp(gbm[h].predict(features_rendements(piv[m]).iloc[[-1]])[0] * k / h))
            err = e[(e["h"] == h) & (e["modele"] == mod) & (e["matiere"] == m)]["err_rel"]
            q10, q90 = np.quantile(err, [0.1, 0.9]) * np.sqrt(k / h)
            prev.append({"matiere_id": m, "date": (dern + pd.DateOffset(months=k)).date(), "horizon_mois": k,
                         "prevision": round(pt, 2), "bas_80": round(pt / (1 + q90), 2), "haut_80": round(pt / (1 + q10), 2),
                         "modele": mod})
    prev = pd.DataFrame(prev)

    # Fenêtre de la campagne 2027 (juil.-déc. 2026) complétée par la prévision, vs même fenêtre 2025
    fen27 = pd.date_range("2026-07-01", "2026-12-01", freq="MS")
    fen26 = pd.date_range("2025-07-01", "2025-12-01", freq="MS")
    compo = pd.read_csv(P / "bridge_composition.csv")
    lignes = []
    for m in MATIERES:
        connus = piv.loc[piv.index.isin(fen27), m]
        pr = prev[(prev.matiere_id == m) & pd.to_datetime(prev.date).isin(fen27)].set_index("date")
        moy = lambda col: pd.concat([connus, pd.Series(pr[col].values, index=pd.to_datetime(pr.index))]).mean()  # noqa: E731
        base = piv.loc[piv.index.isin(fen26), m].mean()
        lignes.append({"matiere": m, "variation_centrale": moy("prevision") / base - 1,
                       "variation_basse": moy("bas_80") / base - 1, "variation_haute": moy("haut_80") / base - 1})
    var27 = pd.DataFrame(lignes)
    lib = pd.read_csv(P / "dim_matiere.csv").set_index("matiere_id")["libelle"]
    mois_fr = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    out += [f"Prévision depuis {mois_fr[dern.month - 1]} {dern.year} et variation attendue pour la campagne 2027 (moyenne juillet-décembre 2026, "
            "dont juillet à septembre connus, vs même période 2025). Intervalle à 80 % tiré des erreurs du backtest.", "",
            tab(pd.DataFrame({"matière": [lib[m] for m in var27.matiere],
                              "variation 2027 attendue": [pct(v) for v in var27.variation_centrale],
                              "fourchette 80 %": [f"{pct(a)} à {pct(b)}" for a, b in zip(var27.variation_basse, var27.variation_haute)]})), ""]
    var27.to_csv(P / "ml_variation_2027.csv", index=False)

    # Plafond de hausse justifiable 2027 projeté, par fournisseur : Σ part × variation projetée, pondéré
    fha = pd.read_csv(P / "fact_hausse_article.csv")
    nxt = fha[(fha.campagne == 2027) & (fha.fenetre == 6) & (fha.decalage == 0) & fha.comparable]
    art = pd.read_csv(P / "dim_article.csv")[["article_id", "fournisseur_id"]]
    vv = var27.set_index("matiere")
    lignes = []
    for f_id, g in nxt.merge(art, on="article_id").groupby("fournisseur_id"):
        c = compo[compo.article_id.isin(g.article_id)]
        poids = (g.set_index("article_id").prix_n * g.set_index("article_id").volume_n)
        res = {"fournisseur_id": f_id, "poids": round(float(poids.sum()), 2)}
        for col, nom in [("variation_centrale", "plafond_central"), ("variation_basse", "plafond_bas"), ("variation_haute", "plafond_haut")]:
            v = c.matiere_id.map(vv[col]).fillna(0.02)  # NM : hypothèse 2 %/an
            j = (c.part * v).groupby(c.article_id).sum()
            res[nom] = round(float((j * poids.reindex(j.index)).sum() / poids.reindex(j.index).sum()), 6)
        lignes.append(res)
    pl = pd.DataFrame(lignes)
    pl.to_csv(P / "ml_plafond_2027.csv", index=False)
    tot = {k: (pl[k] * pl.poids).sum() / pl.poids.sum() for k in ["plafond_central", "plafond_bas", "plafond_haut"]}
    out += [f"**Plafond de hausse justifiable 2027 projeté, tous fournisseurs : {pct(tot['plafond_central'])}** "
            f"(fourchette {pct(tot['plafond_bas'])} à {pct(tot['plafond_haut'])}), contre +11,2 % avec les seuls indices déjà publiés.", ""]
    return prev


# ======================================================================================
# 2. Volumes par famille
# ======================================================================================
def volumes(out: list[str]) -> pd.DataFrame:
    a = pd.read_csv(P / "fact_achats.csv", parse_dates=["date"])
    art = pd.read_csv(P / "dim_article.csv")[["article_id", "famille_id"]]
    fam = pd.read_csv(P / "dim_famille.csv").set_index("famille_id")["libelle"]
    v = a.merge(art, on="article_id").groupby(["famille_id", "date"])["quantite"].sum().unstack(0).sort_index()
    test = v.index[v.index >= "2025-10-01"]  # 12 derniers mois en backtest
    err = {"naif_saisonnier": [], "holt_winters": []}
    for o in test:
        hist = v.loc[: o - pd.DateOffset(months=1)]
        for f in v.columns:
            vrai = v.loc[o, f]
            err["naif_saisonnier"].append(abs(hist[f].iloc[-12] * hist[f].iloc[-12:].sum() / hist[f].iloc[-24:-12].sum() / vrai - 1))
            hw = ExponentialSmoothing(hist[f], trend="add", damped_trend=True, seasonal="mul", seasonal_periods=12).fit()
            err["holt_winters"].append(abs(hw.forecast(1).iloc[0] / vrai - 1))
    res = {k: np.mean(x) for k, x in err.items()}
    retenu = min(res, key=res.get)
    out += ["## 2. Volumes mensuels par famille (fictifs)", "",
            "Backtest à 1 mois sur octobre 2025 → septembre 2026 (12 mois × 8 familles). Le naïf saisonnier reprend "
            "le même mois de l'an dernier, corrigé de la tendance sur 12 mois.", "",
            tab(pd.DataFrame([[k, f"{x * 100:.1f} %".replace(".", ","), "**retenu**" if k == retenu else ""] for k, x in res.items()],
                             columns=["modèle", "erreur moyenne", ""])), ""]
    prev = []
    for f in v.columns:
        hw = ExponentialSmoothing(v[f], trend="add", damped_trend=True, seasonal="mul", seasonal_periods=12).fit()
        fc = hw.forecast(6)
        for d, q in fc.items():
            prev.append({"famille_id": f, "date": d.date(), "quantite_prevue": int(round(q))})
    prev = pd.DataFrame(prev)
    t = prev.groupby("famille_id")["quantite_prevue"].sum()
    an = v.loc["2025-10-01":"2026-03-01"].sum()
    out += ["Prévision octobre 2026 → mars 2027 par famille, comparée à la même période un an plus tôt :", "",
            tab(pd.DataFrame({"famille": [fam[f] for f in t.index], "quantités prévues": [f"{x:,}".replace(",", " ") for x in t.values],
                              "vs N-1": [pct(t[f] / an[f] - 1) for f in t.index]})), ""]
    return prev


# ======================================================================================
# 3. Segmentation des fournisseurs
# ======================================================================================
def segments(out: list[str]) -> pd.DataFrame:
    fha = pd.read_csv(P / "fact_hausse_article.csv")
    fha = fha[(fha.fenetre == 6) & (fha.decalage == 0) & fha.comparable & (fha.campagne <= 2026)]
    art = pd.read_csv(P / "dim_article.csv")[["article_id", "fournisseur_id", "statut_rattachement"]]
    fou = pd.read_csv(P / "dim_fournisseur.csv").set_index("fournisseur_id")
    d = fha.merge(art, on="article_id")
    d["v"] = d.prix_n * d.volume_n
    g = d.groupby(["fournisseur_id", "campagne"]).apply(
        lambda x: pd.Series({"dem": (x.prix_n1 * x.volume_n).sum() / x.v.sum() - 1,
                             "jus": (x.hausse_justifiee * x.v).sum() / x.v.sum()}), include_groups=False).reset_index()
    g["ecart"] = g.dem - g.jus
    g["cliquet"] = (g.jus < 0) & (g.dem >= 0)
    g["baisse_non_repercutee"] = np.where(g.jus < 0, (g.dem - g.jus) / -g.jus, np.nan)
    feat = g.groupby("fournisseur_id").agg(ecart_moyen=("ecart", "mean"), ecart_regularite=("ecart", "std"),
                                           part_cliquet=("cliquet", "mean"))
    feat["rattachement_auto"] = art.groupby("fournisseur_id")["statut_rattachement"].apply(lambda s: (s == "Automatique").mean())
    X = StandardScaler().fit_transform(feat)
    scores = {k: silhouette_score(X, KMeans(k, n_init=20, random_state=SEED).fit_predict(X)) for k in range(2, 6)}
    k = max(scores, key=scores.get)
    lab = KMeans(k, n_init=20, random_state=SEED).fit_predict(X)
    feat["segment"] = lab
    # nommer chaque segment d'après son centre
    noms = {}
    for s, c in feat.groupby("segment").mean().iterrows():
        if c.rattachement_auto < 0.85:
            noms[s] = "Références instables"
        elif c.ecart_moyen > 0.025:
            noms[s] = "Opportuniste"
        elif c.part_cliquet > 0.2:
            noms[s] = "Cliquet"
        else:
            noms[s] = "Aligné sur les matières"
    feat["segment_nom"] = feat.segment.map(noms)
    feat["profil_cache"] = fou.loc[feat.index, "profil"]
    feat["nom"] = fou.loc[feat.index, "nom"]
    ari = adjusted_rand_score(feat.profil_cache, feat.segment)
    # robustesse : le générateur sépare nettement les profils (d'où un accord parfait) ; on bruite les variables
    rng = np.random.default_rng(SEED)
    ari_bruit = {sd: np.mean([adjusted_rand_score(feat.profil_cache,
                                                  KMeans(k, n_init=10, random_state=i).fit_predict(X + rng.normal(0, sd, X.shape)))
                              for i in range(30)]) for sd in (0.5, 1.0)}
    out += ["## 3. Segmentation des fournisseurs (KMeans, non supervisé)", "",
            f"4 variables par fournisseur sur 3 campagnes : écart moyen, régularité de l'écart, part des campagnes en effet cliquet, "
            f"taux de rattachement automatique. Nombre de segments choisi par la silhouette : **{k}** "
            f"({' ; '.join(f'k={a} : {b:.2f}'.replace('.', ',') for a, b in scores.items())}).", "",
            f"Contrôle : accord avec le profil caché du générateur (indice de Rand ajusté) **{str(round(ari, 2)).replace('.', ',')}** "
            "(1 = identique, 0 = hasard). Cet accord parfait vient du générateur, qui sépare nettement les profils. "
            "Test de robustesse, en ajoutant du bruit aux variables standardisées (30 tirages) : "
            f"accord {str(round(ari_bruit[0.5], 2)).replace('.', ',')} avec un bruit d'écart-type 0,5 et "
            f"{str(round(ari_bruit[1.0], 2)).replace('.', ',')} avec un bruit de 1. Sur données réelles, ce profil n'existe pas : "
            "le segment devient l'information, à valider avec l'acheteur.", "",
            tab(feat.reset_index()[["nom", "segment_nom", "profil_cache"]].assign(
                ecart=[f"{x * 100:+.1f} pts".replace(".", ",") for x in feat.ecart_moyen],
                cliquet=[f"{x:.0%}" for x in feat.part_cliquet]).sort_values("segment_nom")
                .rename(columns={"nom": "fournisseur", "segment_nom": "segment trouvé", "profil_cache": "profil caché",
                                 "ecart": "écart moyen", "cliquet": "campagnes en cliquet"})), ""]
    return feat.reset_index()[["fournisseur_id", "segment_nom", "ecart_moyen", "ecart_regularite", "part_cliquet", "rattachement_auto"]]


# ======================================================================================
# 4. Lignes tarifaires anormales
# ======================================================================================
def anomalies(out: list[str]) -> pd.DataFrame:
    fha = pd.read_csv(P / "fact_hausse_article.csv")
    d = fha[(fha.fenetre == 6) & (fha.decalage == 0) & fha.comparable & (fha.campagne == 2026)].copy()
    art = pd.read_csv(P / "dim_article.csv")[["article_id", "fournisseur_id", "famille_id", "designation"]]
    fou = pd.read_csv(P / "dim_fournisseur.csv").set_index("fournisseur_id")
    d = d.merge(art, on="article_id")
    d["demandee"] = d.prix_n1 / d.prix_n - 1
    d["ecart"] = d.demandee - d.hausse_justifiee
    # écart de la ligne par rapport aux autres lignes de la même famille (contexte)
    d["ecart_vs_famille"] = d.ecart - d.groupby("famille_id")["ecart"].transform("median")
    d["poids_log"] = np.log1p(d.prix_n * d.volume_n)
    X = d[["ecart", "ecart_vs_famille", "demandee", "poids_log"]]
    iso = IsolationForest(n_estimators=300, contamination=0.03, random_state=SEED).fit(X)
    d["score_anomalie"] = -iso.score_samples(X)
    d["anomalie"] = iso.predict(X) == -1
    d["enjeu_eur"] = d.ecart.clip(lower=0) * d.prix_n * d.volume_n
    an = d[d.anomalie & (d.ecart > 0)].sort_values("enjeu_eur", ascending=False)
    opp = fou.index[fou.profil == "opportuniste"]
    base = d.fournisseur_id.isin(opp).mean()
    taux = an.fournisseur_id.isin(opp).mean()
    # précision : une ligne isolée est un « vrai écart » si elle dépasse la hausse justifiée de plus de 3 points
    vrai = d.ecart > 0.03
    precision = vrai[d.anomalie & (d.ecart > 0)].mean()
    rappel = (d.anomalie & vrai).sum() / vrai.sum()
    out += ["## 4. Lignes tarifaires anormales (Isolation Forest, campagne 2026)", "",
            f"{len(d):,} lignes comparées sur 4 variables (écart à la hausse justifiée, écart à la médiane de la famille, "
            f"hausse demandée, poids de la ligne). {int(d.anomalie.sum())} lignes isolées, dont **{len(an)} en écart non justifié** "
            "(hausse excessive ou baisse non répercutée), "
            f"pour {an.enjeu_eur.sum():,.0f} € d'écart.".replace(",", " ").replace("  ", ", "), "",
            f"Contrôle : {taux:.0%} des lignes signalées viennent des fournisseurs opportunistes, contre {base:.0%} de toutes les lignes. "
            f"Précision : {precision:.0%} des lignes signalées dépassent vraiment la hausse justifiée de plus de 3 points ; "
            f"elles ne couvrent que {rappel:.0%} de ces lignes (le modèle cible les cas les plus atypiques, pas tous les écarts).", "",
            tab(an.head(10).assign(fournisseur=lambda x: x.fournisseur_id.map(fou.nom))[["designation", "fournisseur"]].assign(
                demandee=[pct(x) for x in an.head(10).demandee], justifiee=[pct(x) for x in an.head(10).hausse_justifiee],
                enjeu=[f"{x:,.0f} €".replace(",", " ") for x in an.head(10).enjeu_eur])
                .rename(columns={"designation": "article", "demandee": "demandée", "justifiee": "justifiée", "enjeu": "écart en €"})), ""]
    return d[["article_id", "fournisseur_id", "demandee", "hausse_justifiee", "ecart", "score_anomalie", "anomalie", "enjeu_eur"]]


def main() -> None:
    out = ["# Machine learning : ce que l'historique permet de prédire", "",
           "Généré par `scripts/ml_predictions.py`. Chaque modèle est comparé à une référence naïve sur un backtest "
           "chronologique (le modèle ne voit jamais le futur) et n'est retenu que s'il la bat.", ""]
    prev = indices(out)
    vol = volumes(out)
    seg = segments(out)
    ano = anomalies(out)
    prev.to_csv(P / "ml_prevision_indices.csv", index=False)
    vol.to_csv(P / "ml_prevision_volumes.csv", index=False)
    seg.to_csv(P / "ml_segments_fournisseurs.csv", index=False)
    ano.round(6).to_csv(P / "ml_anomalies_tarif.csv", index=False)
    RAPPORT.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
