"""Construit le projet Power BI (PBIP) : modèle sémantique en TMDL + squelette de rapport.

Usage : python scripts/build_pbip.py [--dossier-donnees "C:\\...\\data\\processed\\"]

Le modèle est décrit ici (tables, colonnes, relations, mesures, rôles) puis écrit en TMDL.
Les lineageTag sont dérivés des noms (uuid5) : relancer le script ne crée pas de diff inutile.
Ne pas modifier les fichiers TMDL à la main sans reporter la modification ici.
"""
from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
PBIP = RACINE / "pbip"
NOM = "BuyveraBI"
SM = PBIP / f"{NOM}.SemanticModel"
RPT = PBIP / f"{NOM}.Report"
NS = uuid.UUID("6f1c2d3e-4b5a-4c6d-8e9f-0a1b2c3d4e5f")
T = "\t"


def tag(*parts: str) -> str:
    return str(uuid.uuid5(NS, "/".join(parts)))


def q(nom: str) -> str:
    """Nom TMDL : entre apostrophes s'il contient autre chose que lettres, chiffres, _."""
    return nom if nom.replace("_", "").isalnum() and nom.isascii() else "'" + nom.replace("'", "''") + "'"


# --------------------------------------------------------------------------------------
# Description du modèle
# --------------------------------------------------------------------------------------
# Colonne : (nom, type TMDL, description, options)
# options : hidden, key, sort=<col>, fmt=<format>, summ=<sum|none>
S, I, D, DT, B = "string", "int64", "double", "dateTime", "boolean"
M_TYPES = {S: "type text", I: "Int64.Type", D: "type number", DT: "type date", B: "type logical"}

TABLES = {
    "dim_date": dict(
        desc="Calendrier journalier 2022-2026. Les faits mensuels pointent sur le 1er du mois.",
        date_table=True,
        cols=[
            ("date", DT, "Date du jour.", dict(key=True, fmt="Short Date")),
            ("annee", I, "Année civile.", {}),
            ("mois", I, "Numéro du mois (1-12).", {}),
            ("libelle_mois", S, "Mois en clair (« janv. 2026 »).", dict(sort="cle_mois")),
            ("annee_mois", S, "Mois au format AAAA-MM.", {}),
            ("cle_mois", I, "Clé de tri AAAAMM.", dict(hidden=True)),
            ("trimestre", S, "Trimestre (T1 à T4).", {}),
            ("debut_mois", B, "Vrai le 1er du mois.", dict(hidden=True)),
            ("campagne", I, "Campagne tarifaire en vigueur à cette date (tarif au 1er janvier).", {}),
        ]),
    "dim_fournisseur": dict(
        desc="Fournisseurs (fictifs).",
        cols=[
            ("fournisseur_id", S, "Identifiant fournisseur (F01-F12).", {}),
            ("nom", S, "Raison sociale fictive.", {}),
            ("pays", S, "Pays (code ISO).", {}),
            ("devise", S, "Devise de facturation.", {}),
            ("prefixe_tarif", S, "Préfixe ajouté par le fournisseur dans ses références tarif.", dict(hidden=True)),
            ("profil", S, "Comportement injecté dans les données synthétiques (caché, sert aux tests).", dict(hidden=True)),
        ]),
    "dim_famille": dict(
        desc="Familles de produits, rattachées à un univers et à un acheteur.",
        cols=[
            ("famille_id", S, "Identifiant famille.", {}),
            ("libelle", S, "Libellé de la famille.", {}),
            ("univers", S, "Univers : Transmission ou CVC.", {}),
            ("acheteur_id", S, "Acheteur responsable de la famille.", dict(hidden=True)),
        ]),
    "dim_acheteur": dict(
        desc="Acheteurs. L'email sert à la sécurité par ligne (RLS).",
        cols=[
            ("acheteur_id", S, "Identifiant acheteur.", {}),
            ("nom", S, "Nom de l'acheteur (fictif).", {}),
            ("email", S, "Email de connexion, comparé à USERPRINCIPALNAME() par le rôle Acheteur.", {}),
            ("role", S, "Rôle : Acheteur ou Direction.", {}),
            ("perimetre", S, "Univers couvert.", {}),
        ]),
    "dim_matiere": dict(
        desc="Matières premières et part non matière, avec la série INSEE source.",
        cols=[
            ("matiere_id", S, "Identifiant matière (CU, AL, NI, ZN, FE, PL, NM, CU_T).", {}),
            ("libelle", S, "Libellé de la matière.", {}),
            ("source", S, "Source de la série (INSEE BDM ou hypothèse).", {}),
            ("idbank", S, "Identifiant de série INSEE (idbank).", {}),
            ("titre_insee", S, "Intitulé officiel de la série INSEE.", {}),
            ("unite", S, "Unité de la série.", {}),
            ("utilisee_composition", B, "Vrai si la matière entre dans les compositions d'articles.", {}),
            ("dernier_mois", S, "Dernier mois disponible au chargement (fraîcheur).", {}),
        ]),
    "dim_article": dict(
        desc="Articles achetés, avec le résultat du rattachement référence tarif / référence ERP.",
        cols=[
            ("article_id", S, "Identifiant article (identité unique après rattachement).", {}),
            ("ref_fournisseur", S, "Référence telle qu'écrite dans le tarif fournisseur.", {}),
            ("ref_erp", S, "Référence enregistrée dans l'ERP.", {}),
            ("designation", S, "Désignation ERP.", {}),
            ("designation_tarif", S, "Désignation telle qu'écrite dans le tarif fournisseur.", {}),
            ("famille_id", S, "Famille de l'article.", dict(hidden=True)),
            ("fournisseur_id", S, "Fournisseur de l'article.", dict(hidden=True)),
            ("unite", S, "Unité d'achat.", {}),
            ("campagne_debut", I, "Première campagne tarifaire de l'article.", {}),
            ("campagne_fin", I, "Dernière campagne tarifaire de l'article.", {}),
            ("statut_rattachement", S, "Automatique, Proposé (à valider) ou Non rattaché.", {}),
            ("article_id_propose", S, "Article ERP proposé par la correspondance sur la désignation.", {}),
            ("score_rattachement", D, "Similarité de désignation (0-1) ; 1 si rattachement automatique.", dict(fmt="0.00")),
        ]),
    "bridge_composition": dict(
        desc="Table pont article × matière : part de chaque matière dans le coût de l'article (somme = 1, non matière comprise).",
        cols=[
            ("article_id", S, "Article.", dict(hidden=True)),
            ("matiere_id", S, "Matière.", dict(hidden=True)),
            ("part", D, "Part de la matière dans le coût de l'article (0-1).", dict(fmt="0.0%", summ="none")),
        ]),
    "fact_tarif": dict(
        desc="Prix brut public par article et par campagne tarifaire (synthétique).",
        clean=["prix_brut"],
        cols=[
            ("article_id", S, "Article.", dict(hidden=True)),
            ("fournisseur_id", S, "Fournisseur (redondant : le filtre passe par dim_article).", dict(hidden=True)),
            ("campagne", I, "Campagne tarifaire (année d'effet).", {}),
            ("date_effet", DT, "Date d'effet du tarif (1er janvier).", dict(hidden=True, fmt="Short Date")),
            ("prix_brut", D, "Prix brut public en euros. Vide si la ligne tarif est arrivée sans prix.", dict(fmt="#,0.00", summ="none")),
        ]),
    "fact_achats": dict(
        desc="Quantités achetées par article et par mois (synthétique, Pareto 80/20).",
        cols=[
            ("article_id", S, "Article.", dict(hidden=True)),
            ("date", DT, "Mois d'achat (1er du mois).", dict(hidden=True, fmt="Short Date")),
            ("quantite", I, "Quantité achetée sur le mois.", dict(fmt="#,0", summ="sum")),
        ],
        calc_cols=[
            ("prix_unitaire", D, "Prix brut du tarif en vigueur l'année de l'achat.",
             "LOOKUPVALUE ( fact_tarif[prix_brut], fact_tarif[article_id], fact_achats[article_id], fact_tarif[campagne], YEAR ( fact_achats[date] ) )",
             dict(hidden=True, fmt="#,0.00", summ="none")),
            ("montant", D, "Quantité × prix brut de l'année.",
             "fact_achats[quantite] * fact_achats[prix_unitaire]", dict(hidden=True, fmt="#,0", summ="sum")),
        ]),
    "fact_indice": dict(
        desc="Indices matières mensuels réels (INSEE BDM) et série d'hypothèse non matière à 2 %/an.",
        cols=[
            ("matiere_id", S, "Matière.", dict(hidden=True)),
            ("date", DT, "Mois de l'indice (1er du mois).", dict(hidden=True, fmt="Short Date")),
            ("valeur_eur", D, "Valeur de l'indice (base 2010 en euros, ou €/t pour CU_T).", dict(fmt="#,0.0", summ="none")),
        ]),
}

TABLES["fact_hausse_article"] = dict(
    desc="Précalcul (scripts/precalcul_hausses.py) : hausse par article pour chaque campagne N+1, fenêtre et décalage. Rend les mesures instantanées.",
    cols=[
        ("article_id", S, "Article.", dict(hidden=True)),
        ("campagne", I, "Campagne N+1 (la dernière + 1 = prochaine campagne, anticipation).", dict(hidden=True)),
        ("fenetre", I, "Fenêtre de référence des indices (mois).", dict(hidden=True)),
        ("decalage", I, "Décalage d'application (mois).", dict(hidden=True)),
        ("prix_n", D, "Prix brut de la campagne N.", dict(hidden=True)),
        ("prix_n1", D, "Prix brut de la campagne N+1 (vide pour la prochaine campagne).", dict(hidden=True)),
        ("volume_n", I, "Quantité achetée l'année N.", dict(hidden=True)),
        ("hausse_justifiee", D, "Σ part × variation matière de l'article.", dict(hidden=True)),
        ("comparable", B, "Vrai si l'article entre dans le panier comparable.", dict(hidden=True)),
    ])
TABLES["fact_impact_matiere"] = dict(
    desc="Précalcul : surcoût justifié par chaque matière pour chaque article à la prochaine campagne.",
    cols=[
        ("article_id", S, "Article.", dict(hidden=True)),
        ("matiere_id", S, "Matière.", dict(hidden=True)),
        ("fenetre", I, "Fenêtre de référence des indices (mois).", dict(hidden=True)),
        ("decalage", I, "Décalage d'application (mois).", dict(hidden=True)),
        ("impact", D, "Part × variation × prix × volume, en euros.", dict(hidden=True)),
    ])

TABLES["fact_indice_fournisseur"] = dict(
    desc="Précalcul : indice mensuel par fournisseur (base 100 = tarif 2023) du prix fournisseur et du coût matière de son panier. L'écart montre le décalage de répercussion.",
    clean=["indice_prix"],
    cols=[
        ("fournisseur_id", S, "Fournisseur.", dict(hidden=True)),
        ("date", DT, "Mois (1er du mois).", dict(hidden=True, fmt="Short Date")),
        ("indice_cout_matiere", D, "Coût matière du panier fixe du fournisseur, base 100 = référence du tarif 2023.", dict(hidden=True)),
        ("indice_prix", D, "Prix du tarif en vigueur sur le même panier, base 100 = tarif 2023.", dict(hidden=True)),
    ])
TABLES["fact_achats"]["calc_cols"].append(
    ("prix_unitaire_n1", D, "Prix brut du tarif de l'année précédant l'achat (effet prix).",
     "LOOKUPVALUE ( fact_tarif[prix_brut], fact_tarif[article_id], fact_achats[article_id], fact_tarif[campagne], YEAR ( fact_achats[date] ) - 1 )",
     dict(hidden=True, fmt="#,0.00", summ="none")))
TABLES["dim_date"].setdefault("calc_cols", []).append(
    ("mois_court", S, "Mois en clair sans l'année (axe des comparaisons année sur année).",
     'FORMAT ( dim_date[date], "mmm" )', dict(sort="mois")))

ML = "Machine learning (scripts/ml_predictions.py) : "
TABLES["ml_prevision_indices"] = dict(
    desc=ML + "prévision des indices matières octobre-décembre 2026 (modèle retenu au backtest) et intervalle à 80 %.",
    cols=[("matiere_id", S, "Matière.", dict(hidden=True)),
          ("date", DT, "Mois prévu (1er du mois).", dict(hidden=True, fmt="Short Date")),
          ("horizon_mois", I, "Mois d'avance.", dict(hidden=True)),
          ("prevision", D, "Indice prévu.", dict(hidden=True)),
          ("bas_80", D, "Borne basse à 80 %.", dict(hidden=True)),
          ("haut_80", D, "Borne haute à 80 %.", dict(hidden=True)),
          ("modele", S, "Modèle retenu (le naïf si aucun ne le bat).", {})])
TABLES["ml_variation_2027"] = dict(
    desc=ML + "variation matière attendue pour la campagne 2027, fenêtre juillet-décembre 2026 complétée par la prévision.",
    cols=[("matiere", S, "Matière.", dict(hidden=True)),
          ("variation_centrale", D, "Variation centrale.", dict(hidden=True)),
          ("variation_basse", D, "Borne basse à 80 %.", dict(hidden=True)),
          ("variation_haute", D, "Borne haute à 80 %.", dict(hidden=True))])
TABLES["ml_plafond_2027"] = dict(
    desc=ML + "plafond de hausse justifiable 2027 projeté par fournisseur (central et fourchette à 80 %).",
    cols=[("fournisseur_id", S, "Fournisseur.", dict(hidden=True)),
          ("poids", D, "Prix 2026 × volume 2025 du panier.", dict(hidden=True)),
          ("plafond_central", D, "Plafond projeté.", dict(hidden=True)),
          ("plafond_bas", D, "Borne basse.", dict(hidden=True)),
          ("plafond_haut", D, "Borne haute.", dict(hidden=True))])
TABLES["ml_segments_fournisseurs"] = dict(
    desc=ML + "segment de comportement tarifaire trouvé par KMeans (non supervisé).",
    cols=[("fournisseur_id", S, "Fournisseur.", dict(hidden=True)),
          ("segment_nom", S, "Segment trouvé : aligné, opportuniste, cliquet, références instables.", {}),
          ("ecart_moyen", D, "Écart moyen demandé − justifié sur 3 campagnes.", dict(hidden=True)),
          ("ecart_regularite", D, "Écart-type de l'écart.", dict(hidden=True)),
          ("part_cliquet", D, "Part des campagnes en effet cliquet.", dict(hidden=True)),
          ("rattachement_auto", D, "Taux de rattachement automatique.", dict(hidden=True))])
TABLES["ml_anomalies_tarif"] = dict(
    desc=ML + "lignes du tarif 2026 isolées par Isolation Forest (hausse atypique pour sa famille).",
    cols=[("article_id", S, "Article.", dict(hidden=True)),
          ("fournisseur_id", S, "Fournisseur.", dict(hidden=True)),
          ("demandee", D, "Hausse demandée de la ligne.", dict(hidden=True)),
          ("hausse_justifiee", D, "Hausse justifiée de la ligne.", dict(hidden=True)),
          ("ecart", D, "Écart.", dict(hidden=True)),
          ("score_anomalie", D, "Score d'anomalie (plus haut = plus atypique).", dict(hidden=True)),
          ("anomalie", B, "Vrai si la ligne est isolée.", {}),
          ("enjeu_eur", D, "Écart positif × prix N × volume N.", dict(hidden=True))])

TABLES["dim_entite"] = dict(
    desc="Sites du groupe client (fictif) : un site historique et deux sites rachetés.",
    cols=[("entite_id", S, "Identifiant du site.", dict(hidden=True)),
          ("nom", S, "Nom du site.", {}),
          ("pays", S, "Pays.", {}),
          ("origine", S, "Site historique ou racheté (année).", {})])
TABLES["fact_achats_entite"] = dict(
    desc="Achats répartis par site avec le prix réellement payé dans l'ERP du site (scripts/generate_groupe.py).",
    cols=[("article_id", S, "Article.", dict(hidden=True)),
          ("date", DT, "Mois d'achat.", dict(hidden=True, fmt="Short Date")),
          ("entite_id", S, "Site.", dict(hidden=True)),
          ("quantite", I, "Quantité achetée par le site.", dict(hidden=True)),
          ("prix_tarif", D, "Prix du tarif groupe en vigueur.", dict(hidden=True)),
          ("prix_paye", D, "Prix payé dans l'ERP du site.", dict(hidden=True)),
          ("statut_prix", S, "Conforme, Prix historique du site, Retard d'application ou Écart durable.", {}),
          ("meilleur_prix_groupe", D, "Plus bas prix moyen payé par un site du groupe pour l'article dans l'année.", dict(hidden=True)),
          ("surcout_vs_meilleur", D, "Quantité × (prix payé − meilleur prix du groupe).", dict(hidden=True)),
          ("ecart_application", D, "Quantité × (prix payé − prix du tarif), sur les lignes en retard ou en écart.", dict(hidden=True))])
TABLES["fact_negociation"] = dict(
    desc="Résultat de chaque campagne par fournisseur : hausse demandée, obtenue, économie (saisie de l'acheteur, fichier modifiable).",
    cols=[("fournisseur_id", S, "Fournisseur.", dict(hidden=True)),
          ("campagne", I, "Campagne.", {}),
          ("valeur_n", D, "Valeur N du panier comparable.", dict(hidden=True)),
          ("hausse_demandee", D, "Hausse demandée.", dict(hidden=True)),
          ("hausse_justifiee", D, "Hausse justifiée par les matières.", dict(hidden=True)),
          ("hausse_obtenue", D, "Hausse finalement accordée.", dict(hidden=True)),
          ("eur_renegociables", D, "Potentiel renégociable de la campagne.", dict(hidden=True)),
          ("economie_eur", D, "(demandée − obtenue) × valeur N.", dict(hidden=True))])

# Relations : (table plusieurs, colonne, table un, colonne). Toutes 1→N, filtrage unidirectionnel.
RELATIONS = [
    ("fact_tarif", "article_id", "dim_article", "article_id"),
    ("fact_tarif", "date_effet", "dim_date", "date"),
    ("fact_achats", "article_id", "dim_article", "article_id"),
    ("fact_achats", "date", "dim_date", "date"),
    ("fact_indice", "matiere_id", "dim_matiere", "matiere_id"),
    ("fact_indice", "date", "dim_date", "date"),
    ("bridge_composition", "article_id", "dim_article", "article_id"),
    ("bridge_composition", "matiere_id", "dim_matiere", "matiere_id"),
    ("dim_article", "fournisseur_id", "dim_fournisseur", "fournisseur_id"),
    ("dim_article", "famille_id", "dim_famille", "famille_id"),
    ("dim_famille", "acheteur_id", "dim_acheteur", "acheteur_id"),
    ("fact_hausse_article", "article_id", "dim_article", "article_id"),
    ("fact_impact_matiere", "article_id", "dim_article", "article_id"),
    ("fact_impact_matiere", "matiere_id", "dim_matiere", "matiere_id"),
    ("fact_indice_fournisseur", "fournisseur_id", "dim_fournisseur", "fournisseur_id"),
    ("fact_indice_fournisseur", "date", "dim_date", "date"),
    ("ml_prevision_indices", "matiere_id", "dim_matiere", "matiere_id"),
    ("ml_prevision_indices", "date", "dim_date", "date"),
    ("ml_variation_2027", "matiere", "dim_matiere", "matiere_id"),
    ("ml_plafond_2027", "fournisseur_id", "dim_fournisseur", "fournisseur_id"),
    ("ml_segments_fournisseurs", "fournisseur_id", "dim_fournisseur", "fournisseur_id"),
    ("ml_anomalies_tarif", "article_id", "dim_article", "article_id"),
    ("fact_achats_entite", "article_id", "dim_article", "article_id"),
    ("fact_achats_entite", "date", "dim_date", "date"),
    ("fact_achats_entite", "entite_id", "dim_entite", "entite_id"),
    ("fact_negociation", "fournisseur_id", "dim_fournisseur", "fournisseur_id"),
]

# Tables de paramètres (déconnectées) : nom → (colonne, valeurs, valeur par défaut, description)
PARAMETRES = {
    "param_campagne": ("campagne", [2024, 2025, 2026], 2026,
                       "Campagne N+1 analysée (comparée à la campagne N = N+1 − 1). Table déconnectée pour le segment."),
    "param_hausse": ("hausse_acceptee", [0, 1, 2, 3, 4, 5], 2,
                     "Simulateur : hausse que l'acheteur est prêt à accepter (en %), pour chiffrer la contre-proposition."),
    "param_decalage": ("decalage_mois", [0, 3, 6, 9, 12], 0,
                       "Décalage d'application : nombre de mois entre l'évolution du cours matière et sa répercussion dans le tarif."),
    "param_fenetre": ("mois", [3, 6, 12], 6,
                      "Période de référence de la variation matière, en mois avant chaque campagne."),
}

# Bloc commun : panier d'articles comparables entre N et N+1 (prix aux deux campagnes, volume N > 0)
PANIER = """VAR _cN1 = [Campagne N+1]
VAR _cN = _cN1 - 1
VAR _articles =
    ADDCOLUMNS (
        VALUES ( dim_article[article_id] ),
        "@pN", CALCULATE ( SUM ( fact_tarif[prix_brut] ), REMOVEFILTERS ( dim_date ), fact_tarif[campagne] = _cN ),
        "@pN1", CALCULATE ( SUM ( fact_tarif[prix_brut] ), REMOVEFILTERS ( dim_date ), fact_tarif[campagne] = _cN1 ),
        "@vN", CALCULATE ( SUM ( fact_achats[quantite] ), REMOVEFILTERS ( dim_date ), dim_date[annee] = _cN )
    )
VAR _panier = FILTER ( _articles, NOT ISBLANK ( [@pN] ) && NOT ISBLANK ( [@pN1] ) && [@vN] > 0 )"""

# Variation par matière calculée une fois, puis hausse justifiée par article = Σ part × variation
PANIER_JUSTIFIE = PANIER + """
VAR _variations =
    CALCULATETABLE (
        ADDCOLUMNS ( VALUES ( dim_matiere[matiere_id] ), "@var", [Variation matière %] ),
        REMOVEFILTERS ( dim_matiere )
    )
VAR _panierJ =
    ADDCOLUMNS (
        _panier,
        "@j",
            SUMX (
                CALCULATETABLE ( bridge_composition, REMOVEFILTERS ( dim_matiere ) ),
                VAR _m = bridge_composition[matiere_id]
                RETURN bridge_composition[part] * MAXX ( FILTER ( _variations, dim_matiere[matiere_id] = _m ), [@var] )
            )
    )"""

# Mesures : (nom, dossier, format, description, expression)
MESURES = [
    ("Campagne N+1", "9. Paramètres", "0", "Campagne analysée (segment param_campagne, 2026 par défaut).",
     "SELECTEDVALUE ( param_campagne[campagne], 2026 )"),
    ("Campagne N", "9. Paramètres", "0", "Campagne de référence = campagne N+1 − 1.",
     "[Campagne N+1] - 1"),
    ("Décalage mois", "9. Paramètres", "0",
     "Décalage d'application retenu (segment param_decalage, 0 mois par défaut).",
     "SELECTEDVALUE ( param_decalage[decalage_mois], 0 )"),
    ("Fenêtre mois", "9. Paramètres", "0", "Période de référence des indices (segment param_fenetre, 6 mois par défaut).",
     "SELECTEDVALUE ( param_fenetre[mois], 6 )"),

    ("Variation matière %", "2. Matières", "0.0%",
     "Moyenne de l'indice sur la fenêtre avant la campagne N+1 / même moyenne avant la campagne N − 1. Une seule matière à la fois.",
     """VAR _cN1 = [Campagne N+1]
VAR _w = [Fenêtre mois]
VAR _lag = [Décalage mois]
VAR _fin1 = EDATE ( DATE ( _cN1, 1, 1 ), - _lag )
VAR _fin0 = EDATE ( DATE ( _cN1 - 1, 1, 1 ), - _lag )
VAR _moy1 =
    CALCULATE ( AVERAGE ( fact_indice[valeur_eur] ), REMOVEFILTERS ( dim_date ),
        dim_date[date] >= EDATE ( _fin1, - _w ), dim_date[date] < _fin1 )
VAR _moy0 =
    CALCULATE ( AVERAGE ( fact_indice[valeur_eur] ), REMOVEFILTERS ( dim_date ),
        dim_date[date] >= EDATE ( _fin0, - _w ), dim_date[date] < _fin0 )
VAR _ratio = DIVIDE ( _moy1, _moy0 )
RETURN
    IF ( HASONEVALUE ( dim_matiere[matiere_id] ) && NOT ISBLANK ( _ratio ), _ratio - 1 )"""),
    ("Indice moyen", "2. Matières", "#,0.0", "Moyenne de l'indice matière sur la période filtrée.",
     "AVERAGE ( fact_indice[valeur_eur] )"),
    ("Part matière moyenne", "2. Matières", "0.0%", "Part moyenne de la matière dans le coût des articles filtrés.",
     "AVERAGE ( bridge_composition[part] )"),

    ("Valeur N", "1. Hausses", "#,0 €", "Σ prix N × volume N sur le panier comparable (prix aux deux campagnes, volume N > 0).",
     PANIER + "\nRETURN\n    SUMX ( _panier, [@pN] * [@vN] )"),
    ("Hausse demandée %", "1. Hausses", "0.0%",
     "Σ (prix N+1 × volume N) / Σ (prix N × volume N) − 1, pondérée par les volumes N.",
     PANIER + """
VAR _avant = SUMX ( _panier, [@pN] * [@vN] )
VAR _apres = SUMX ( _panier, [@pN1] * [@vN] )
VAR _ratio = DIVIDE ( _apres, _avant )
RETURN
    IF ( NOT ISBLANK ( _ratio ), _ratio - 1 )"""),
    ("Hausse justifiée %", "1. Hausses", "0.0%",
     "Σ (part matière × variation matière), non matière à 2 %/an comprise, pondérée comme la hausse demandée.",
     PANIER_JUSTIFIE + """
RETURN
    DIVIDE ( SUMX ( _panierJ, [@j] * [@pN] * [@vN] ), SUMX ( _panierJ, [@pN] * [@vN] ) )"""),
    ("Écart pts", "1. Hausses", "+0.0;-0.0;0.0", "Hausse demandée − hausse justifiée, en points de pourcentage.",
     """VAR _d = [Hausse demandée %]
VAR _j = [Hausse justifiée %]
RETURN
    IF ( NOT ISBLANK ( _d ) && NOT ISBLANK ( _j ), ( _d - _j ) * 100 )"""),
    ("€ renégociables", "1. Hausses", "#,0 €",
     "Σ par article de MAX(0, hausse demandée − hausse justifiée) × prix N × volume N.",
     PANIER_JUSTIFIE + """
RETURN
    SUMX ( _panierJ, MAX ( 0, DIVIDE ( [@pN1], [@pN] ) - 1 - [@j] ) * [@pN] * [@vN] )"""),
    ("Nb articles comparables", "1. Hausses", "#,0", "Articles du panier comparable N / N+1.",
     PANIER + "\nRETURN\n    COUNTROWS ( _panier )"),
    ("Effet cliquet", "1. Hausses", "0",
     "Nombre de campagnes où la hausse justifiée est négative alors que la hausse demandée ne l'est pas.",
     """SUMX (
    ALL ( param_campagne[campagne] ),
    VAR _j = [Hausse justifiée %]
    VAR _d = [Hausse demandée %]
    RETURN IF ( NOT ISBLANK ( _j ) && _j < 0 && _d >= 0, 1, 0 )
)"""),

    ("Montant achats", "3. Achats", "#,0 €", "Quantités × prix brut du tarif de l'année d'achat.",
     "SUM ( fact_achats[montant] )"),
    ("Quantité achetée", "3. Achats", "#,0", "Quantités achetées.",
     "SUM ( fact_achats[quantite] )"),
    ("Nb articles", "3. Achats", "#,0", "Nombre d'articles.",
     "COUNTROWS ( dim_article )"),

    ("% rattachés auto", "4. Rattachement", "0.0%", "Articles au statut Automatique / total des articles.",
     """VAR _auto = CALCULATE ( COUNTROWS ( dim_article ), dim_article[statut_rattachement] = "Automatique" )
RETURN
    DIVIDE ( _auto, COUNTROWS ( dim_article ) )"""),
    ("% proposés", "4. Rattachement", "0.0%", "Articles au statut Proposé (à valider) / total.",
     """VAR _n = CALCULATE ( COUNTROWS ( dim_article ), dim_article[statut_rattachement] = "Proposé" )
RETURN
    DIVIDE ( _n, COUNTROWS ( dim_article ) )"""),
    ("% non rattachés", "4. Rattachement", "0.0%", "Articles au statut Non rattaché / total.",
     """VAR _n = CALCULATE ( COUNTROWS ( dim_article ), dim_article[statut_rattachement] = "Non rattaché" )
RETURN
    DIVIDE ( _n, COUNTROWS ( dim_article ) )"""),
    ("Objectif rattachement", "4. Rattachement", "0%", "Objectif de rattachement automatique (règle Buyvera).",
     "0.8"),

    ("Indice (composition)", "2. Matières", "#,0.0",
     "Indice moyen limité aux matières utilisées dans les compositions (exclut le cuivre en €/t).",
     "CALCULATE ( [Indice moyen], KEEPFILTERS ( dim_matiere[utilisee_composition] = TRUE () ) )"),
    ("Indice matières article", "5. Détail article", "#,0.0",
     "Indice moyen des seules matières présentes dans la composition des articles filtrés.",
     """CALCULATE (
    [Indice moyen],
    KEEPFILTERS ( TREATAS ( VALUES ( bridge_composition[matiere_id] ), dim_matiere[matiere_id] ) ),
    KEEPFILTERS ( dim_matiere[utilisee_composition] = TRUE () )
)"""),
    ("Variation matière article %", "5. Détail article", "0.0%",
     "Variation matière affichée seulement pour les matières de la composition des articles filtrés.",
     "IF ( NOT ISBLANK ( [Part matière moyenne] ), [Variation matière %] )"),
    ("Prix brut", "5. Détail article", "#,0.00 €", "Prix brut public, affiché quand un seul article est sélectionné.",
     "IF ( HASONEVALUE ( dim_article[article_id] ), SUM ( fact_tarif[prix_brut] ) )"),

    ("Variation (composition) %", "2. Matières", "0.0%",
     "Variation matière limitée aux matières des compositions (sans la série cuivre en €/t).",
     "IF ( SELECTEDVALUE ( dim_matiere[utilisee_composition] ) = TRUE (), [Variation matière %] )"),

    ("Hausse acceptée %", "6. Négociation", "0.0%", "Hausse acceptée par l'acheteur (segment du simulateur, 2 % par défaut).",
     "DIVIDE ( SELECTEDVALUE ( param_hausse[hausse_acceptee], 2 ), 100 )"),
    ("€ économisés (contre-proposition)", "6. Négociation", "#,0 €",
     "Σ par article de MAX(0, hausse demandée − hausse acceptée) × prix N × volume N : gain si le fournisseur accepte la contre-proposition.",
     "VAR _acc = [Hausse acceptée %]\n" + PANIER + """
RETURN
    SUMX ( _panier, MAX ( 0, DIVIDE ( [@pN1], [@pN] ) - 1 - _acc ) * [@pN] * [@vN] )"""),
    ("Couleur écart", "6. Négociation", "",
     "Couleur de statut de l'écart (rouge > 3 pts, orange > 1 pt, vert sinon) pour la mise en forme conditionnelle.",
     """VAR _e = [Écart pts]
RETURN
    SWITCH ( TRUE (), ISBLANK ( _e ), "#56655F", _e > 3, "#C9781C", _e > 1, "#D9A441", "#0F5C4A" )"""),
    ("Statut fournisseur", "6. Négociation", "",
     "Statut lisible (icône + libellé) : À renégocier, À surveiller ou Conforme.",
     """VAR _e = [Écart pts]
RETURN
    SWITCH ( TRUE (), ISBLANK ( _e ), BLANK (), _e > 3, "▲ À renégocier", _e > 1, "◆ À surveiller", "● Conforme" )"""),
    ("Levier matière", "6. Négociation", "",
     "Matière du panier du fournisseur qui a le plus baissé sur la fenêtre : argument de négociation.",
     """VAR _t =
    FILTER (
        ADDCOLUMNS ( VALUES ( dim_matiere[libelle] ), "@v", [Variation matière article %] ),
        NOT ISBLANK ( [@v] )
    )
VAR _min = TOPN ( 1, _t, [@v], ASC )
RETURN
    IF ( COUNTROWS ( _t ) > 0,
        MAXX ( _min, dim_matiere[libelle] & " " & FORMAT ( [@v], "+0.0 %;-0.0 %" ) ) )"""),
    ("Commentaire négociation", "6. Négociation", "",
     "Phrase de synthèse générée pour le fournisseur sélectionné (support de négociation).",
     """VAR _f = SELECTEDVALUE ( dim_fournisseur[nom] )
VAR _d = [Hausse demandée %]
VAR _j = [Hausse justifiée %]
VAR _e = [Écart pts]
VAR _eur = [€ renégociables]
VAR _lev = [Levier matière]
VAR _cli = [Effet cliquet]
RETURN
    IF ( ISBLANK ( _f ), "Choisissez un fournisseur pour générer sa fiche.",
        "Demande " & FORMAT ( _d, "+0.0 %;-0.0 %" ) & " pour " & FORMAT ( _j, "+0.0 %;-0.0 %" ) & " justifiés"
            & IF ( _eur > 0, " · à renégocier " & FORMAT ( _eur, "# ##0 €" ), " · conforme" )
            & IF ( NOT ISBLANK ( _lev ), " · levier " & _lev, "" )
            & IF ( _cli > 0, " · cliquet " & _cli & " camp.", "" ) )"""),

    ("Dernier indice", "7. Alertes", "#,0.0", "Valeur de l'indice au dernier mois disponible.",
     """VAR _last = CALCULATE ( MAX ( fact_indice[date] ), ALL ( fact_indice ) )
VAR _compo = SELECTEDVALUE ( dim_matiere[utilisee_composition] ) = TRUE ()
VAR _v = CALCULATE ( AVERAGE ( fact_indice[valeur_eur] ), REMOVEFILTERS ( dim_date ), dim_date[date] = _last )
RETURN
    IF ( HASONEVALUE ( dim_matiere[matiere_id] ) && _compo, _v )"""),
    ("Variation 3 mois %", "7. Alertes", "+0.0%;-0.0%;0.0%", "Dernier indice / indice 3 mois plus tôt − 1 (signal court terme).",
     """VAR _last = CALCULATE ( MAX ( fact_indice[date] ), ALL ( fact_indice ) )
VAR _compo = SELECTEDVALUE ( dim_matiere[utilisee_composition] ) = TRUE ()
VAR _v1 = CALCULATE ( AVERAGE ( fact_indice[valeur_eur] ), REMOVEFILTERS ( dim_date ), dim_date[date] = _last )
VAR _v0 = CALCULATE ( AVERAGE ( fact_indice[valeur_eur] ), REMOVEFILTERS ( dim_date ), dim_date[date] = EDATE ( _last, -3 ) )
VAR _r = DIVIDE ( _v1, _v0 )
RETURN
    IF ( HASONEVALUE ( dim_matiere[matiere_id] ) && _compo && NOT ISBLANK ( _r ), _r - 1 )"""),
    ("Variation 12 mois %", "7. Alertes", "+0.0%;-0.0%;0.0%", "Dernier indice / indice 12 mois plus tôt − 1 (tendance).",
     """VAR _last = CALCULATE ( MAX ( fact_indice[date] ), ALL ( fact_indice ) )
VAR _compo = SELECTEDVALUE ( dim_matiere[utilisee_composition] ) = TRUE ()
VAR _v1 = CALCULATE ( AVERAGE ( fact_indice[valeur_eur] ), REMOVEFILTERS ( dim_date ), dim_date[date] = _last )
VAR _v0 = CALCULATE ( AVERAGE ( fact_indice[valeur_eur] ), REMOVEFILTERS ( dim_date ), dim_date[date] = EDATE ( _last, -12 ) )
VAR _r = DIVIDE ( _v1, _v0 )
RETURN
    IF ( HASONEVALUE ( dim_matiere[matiere_id] ) && _compo && NOT ISBLANK ( _r ), _r - 1 )"""),
    ("Alerte matière", "7. Alertes", "",
     "Signal sur 3 mois : ▲ hausse > 5 % (le fournisseur va s'en servir), ▼ baisse > 5 % (levier acheteur), ● stable.",
     """VAR _v = [Variation 3 mois %]
RETURN
    SWITCH ( TRUE (), ISBLANK ( _v ), BLANK (), _v > 0.05, "▲ Hausse : à anticiper", _v < -0.05, "▼ Baisse : convoquer le fournisseur", "● Stable" )"""),
    ("Couleur alerte", "7. Alertes", "", "Couleur du signal matière (rouge = hausse, vert = baisse, gris = stable).",
     """VAR _v = [Variation 3 mois %]
RETURN
    SWITCH ( TRUE (), ISBLANK ( _v ), "#56655F", _v > 0.05, "#C9781C", _v < -0.05, "#0F5C4A", "#56655F" )"""),
    ("Variation anticipée %", "7. Alertes", "+0.0%;-0.0%;0.0%",
     "Moyenne des 6 derniers mois disponibles / moyenne des 6 mois avant la dernière campagne − 1 : variation déjà acquise pour la prochaine campagne.",
     """VAR _last = CALCULATE ( MAX ( fact_indice[date] ), ALL ( fact_indice ) )
VAR _compo = SELECTEDVALUE ( dim_matiere[utilisee_composition] ) = TRUE ()
VAR _cBase = MAXX ( ALL ( param_campagne[campagne] ), param_campagne[campagne] )
VAR _fin0 = DATE ( _cBase, 1, 1 )
VAR _moy1 = CALCULATE ( AVERAGE ( fact_indice[valeur_eur] ), REMOVEFILTERS ( dim_date ),
    dim_date[date] > EDATE ( _last, -6 ), dim_date[date] <= _last )
VAR _moy0 = CALCULATE ( AVERAGE ( fact_indice[valeur_eur] ), REMOVEFILTERS ( dim_date ),
    dim_date[date] >= EDATE ( _fin0, -6 ), dim_date[date] < _fin0 )
VAR _r = DIVIDE ( _moy1, _moy0 )
RETURN
    IF ( HASONEVALUE ( dim_matiere[matiere_id] ) && _compo && NOT ISBLANK ( _r ), _r - 1 )"""),
    ("Plafond justifié prochaine campagne %", "7. Alertes", "+0.0%;-0.0%;0.0%",
     "Hausse que les matières justifient déjà pour la prochaine campagne, sur le tarif en vigueur pondéré par les volumes : au-delà, la demande est contestable.",
     """VAR _cBase = MAXX ( ALL ( param_campagne[campagne] ), param_campagne[campagne] )
VAR _variations =
    CALCULATETABLE (
        ADDCOLUMNS ( VALUES ( dim_matiere[matiere_id] ), "@var", [Variation anticipée %] ),
        REMOVEFILTERS ( dim_matiere )
    )
VAR _articles =
    ADDCOLUMNS (
        VALUES ( dim_article[article_id] ),
        "@p", CALCULATE ( SUM ( fact_tarif[prix_brut] ), REMOVEFILTERS ( dim_date ), fact_tarif[campagne] = _cBase ),
        "@v", CALCULATE ( SUM ( fact_achats[quantite] ), REMOVEFILTERS ( dim_date ), dim_date[annee] = _cBase - 1 )
    )
VAR _panier = FILTER ( _articles, NOT ISBLANK ( [@p] ) && [@v] > 0 )
VAR _panierJ =
    ADDCOLUMNS (
        _panier,
        "@j",
            SUMX (
                CALCULATETABLE ( bridge_composition, REMOVEFILTERS ( dim_matiere ) ),
                VAR _m = bridge_composition[matiere_id]
                RETURN bridge_composition[part] * MAXX ( FILTER ( _variations, dim_matiere[matiere_id] = _m ), [@var] )
            )
    )
RETURN
    DIVIDE ( SUMX ( _panierJ, [@j] * [@p] * [@v] ), SUMX ( _panierJ, [@p] * [@v] ) )"""),
    ("Impact € prochaine campagne", "7. Alertes", "#,0 €",
     "Surcoût que les matières justifient déjà pour la prochaine campagne (Σ part × variation acquise × prix × volume). Si une matière est sélectionnée, seule sa contribution est comptée : articles impactés par cette matière.",
     """VAR _cBase = MAXX ( ALL ( param_campagne[campagne] ), param_campagne[campagne] )
VAR _variations =
    CALCULATETABLE (
        ADDCOLUMNS ( VALUES ( dim_matiere[matiere_id] ), "@var", [Variation anticipée %] ),
        REMOVEFILTERS ( dim_matiere )
    )
VAR _articles =
    ADDCOLUMNS (
        VALUES ( dim_article[article_id] ),
        "@p", CALCULATE ( SUM ( fact_tarif[prix_brut] ), REMOVEFILTERS ( dim_date ), fact_tarif[campagne] = _cBase ),
        "@v", CALCULATE ( SUM ( fact_achats[quantite] ), REMOVEFILTERS ( dim_date ), dim_date[annee] = _cBase - 1 )
    )
VAR _panier = FILTER ( _articles, NOT ISBLANK ( [@p] ) && [@v] > 0 )
VAR _impact =
    SUMX (
        _panier,
        [@p] * [@v]
            * SUMX (
                CALCULATETABLE ( bridge_composition ),
                VAR _m = bridge_composition[matiere_id]
                RETURN bridge_composition[part] * MAXX ( FILTER ( _variations, dim_matiere[matiere_id] = _m ), [@var] )
            )
    )
RETURN
    IF ( _impact <> 0, _impact )"""),
    ("Volume annuel", "7. Alertes", "#,0", "Quantité achetée sur la dernière année complète.",
     """VAR _cBase = MAXX ( ALL ( param_campagne[campagne] ), param_campagne[campagne] )
RETURN
    CALCULATE ( SUM ( fact_achats[quantite] ), REMOVEFILTERS ( dim_date ), dim_date[annee] = _cBase - 1 )"""),
    ("Action fournisseur", "7. Alertes", "",
     "Action recommandée selon le plafond justifié de la prochaine campagne : baisse → convoquer le fournisseur, hausse > 2 % → préparer la défense, sinon suivi.",
     """VAR _p = [Plafond justifié prochaine campagne %]
RETURN
    SWITCH ( TRUE (), ISBLANK ( _p ), BLANK (),
        _p < 0, "▼ Convoquer le fournisseur",
        _p > 0.02, "▲ Préparer la défense",
        "● Suivi" )"""),
    ("Couleur action", "7. Alertes", "", "Vert = baisse à obtenir, rouge = hausse à cadrer, gris = suivi.",
     """VAR _p = [Plafond justifié prochaine campagne %]
RETURN
    SWITCH ( TRUE (), ISBLANK ( _p ), "#56655F", _p < 0, "#0F5C4A", _p > 0.02, "#C9781C", "#56655F" )"""),
    ("Décalage estimé (mois)", "8. Décalage", "0 \"mois\"",
     "Décalage d'application qui explique le mieux la hausse demandée (écart minimal entre demandé et justifié) : mesure le retard de répercussion du fournisseur.",
     """VAR _t = ADDCOLUMNS ( ALL ( param_decalage[decalage_mois] ), "@e", ABS ( [Écart pts] ) )
VAR _best = TOPN ( 1, FILTER ( _t, NOT ISBLANK ( [@e] ) ), [@e], ASC, param_decalage[decalage_mois], ASC )
RETURN
    MAXX ( _best, param_decalage[decalage_mois] )"""),
    ("Délai hausses (mois)", "8. Décalage", "0.0",
     "Décalage moyen de répercussion sur les campagnes où les matières montent.",
     """AVERAGEX (
    FILTER ( ALL ( param_campagne[campagne] ), [Hausse justifiée %] > 0 ),
    [Décalage estimé (mois)]
)"""),
    ("Délai baisses (mois)", "8. Décalage", "0.0",
     "Décalage moyen de répercussion sur les campagnes où les matières baissent (12 = baisse jamais vraiment répercutée).",
     """AVERAGEX (
    FILTER ( ALL ( param_campagne[campagne] ), [Hausse justifiée %] < 0 ),
    [Décalage estimé (mois)]
)"""),
    ("Asymétrie (mois)", "8. Décalage", "+0.0;-0.0;0.0",
     "Délai baisses − délai hausses : positif = le fournisseur répercute les hausses plus vite que les baisses.",
     """VAR _h = [Délai hausses (mois)]
VAR _b = [Délai baisses (mois)]
RETURN
    IF ( NOT ISBLANK ( _h ) && NOT ISBLANK ( _b ), _b - _h )"""),
    ("Écart au meilleur décalage", "8. Décalage", "+0.0;-0.0;0.0",
     "Écart (pts) restant une fois le décalage du fournisseur pris en compte : ce qui reste n'est pas expliqué par les matières.",
     """VAR _lag = [Décalage estimé (mois)]
RETURN
    CALCULATE ( [Écart pts], param_decalage[decalage_mois] = _lag )"""),
    ("Prochaine campagne", "7. Alertes", "0", "Campagne à venir (dernière campagne + 1).",
     "MAXX ( ALL ( param_campagne[campagne] ), param_campagne[campagne] ) + 1"),
    ("Argument anticipé", "7. Alertes", "",
     "Phrase d'anticipation : plafond de hausse défendable pour la prochaine campagne, avant réception du tarif.",
     """VAR _p = [Plafond justifié prochaine campagne %]
RETURN
    [Prochaine campagne] & " : " & FORMAT ( _p, "+0.0 %;-0.0 %" ) & " déjà justifiés par les matières. Au-delà : à contester."
"""),

    ("Dernier indice chargé", "2. Matières", "", "Libellé du dernier mois d'indice INSEE disponible (fraîcheur).",
     """VAR _d = CALCULATE ( MAX ( fact_indice[date] ), REMOVEFILTERS ( fact_indice ), REMOVEFILTERS ( dim_date ) )
RETURN
    "Indices INSEE à fin " & FORMAT ( _d, "mmmm yyyy" )"""),
]

def _panier_rapide(campagne: str) -> str:
    return f"""VAR _c = {campagne}
VAR _w = [Fenêtre mois]
VAR _lag = [Décalage mois]
VAR _t =
    CALCULATETABLE (
        fact_hausse_article,
        fact_hausse_article[campagne] = _c,
        fact_hausse_article[fenetre] = _w,
        fact_hausse_article[decalage] = _lag,
        fact_hausse_article[comparable] = TRUE ()
    )"""


PN, PN1, VN, J = ("fact_hausse_article[prix_n]", "fact_hausse_article[prix_n1]",
                  "fact_hausse_article[volume_n]", "fact_hausse_article[hausse_justifiee]")
RAPIDES = {
    "Valeur N": _panier_rapide("[Campagne N+1]") + f"\nRETURN\n    SUMX ( _t, {PN} * {VN} )",
    "Hausse demandée %": _panier_rapide("[Campagne N+1]") + f"""
VAR _r = DIVIDE ( SUMX ( _t, {PN1} * {VN} ), SUMX ( _t, {PN} * {VN} ) )
RETURN
    IF ( NOT ISBLANK ( _r ), _r - 1 )""",
    "Hausse justifiée %": _panier_rapide("[Campagne N+1]") + f"""
RETURN
    DIVIDE ( SUMX ( _t, {J} * {PN} * {VN} ), SUMX ( _t, {PN} * {VN} ) )""",
    "€ renégociables": _panier_rapide("[Campagne N+1]") + f"""
RETURN
    SUMX ( _t, MAX ( 0, DIVIDE ( {PN1}, {PN} ) - 1 - {J} ) * {PN} * {VN} )""",
    "Nb articles comparables": _panier_rapide("[Campagne N+1]") + "\nRETURN\n    COUNTROWS ( _t )",
    "€ économisés (contre-proposition)": "VAR _acc = [Hausse acceptée %]\n" + _panier_rapide("[Campagne N+1]") + f"""
RETURN
    SUMX ( _t, MAX ( 0, DIVIDE ( {PN1}, {PN} ) - 1 - _acc ) * {PN} * {VN} )""",
    "Plafond justifié prochaine campagne %": _panier_rapide("[Prochaine campagne]") + f"""
RETURN
    DIVIDE ( SUMX ( _t, {J} * {PN} * {VN} ), SUMX ( _t, {PN} * {VN} ) )""",
    "Impact € prochaine campagne": """VAR _w = [Fenêtre mois]
VAR _lag = [Décalage mois]
VAR _r =
    CALCULATE (
        SUM ( fact_impact_matiere[impact] ),
        fact_impact_matiere[fenetre] = _w,
        fact_impact_matiere[decalage] = _lag
    )
RETURN
    IF ( _r <> 0, _r )""",
}
MESURES = [(n, f, fmt, d, RAPIDES.get(n, e)) for n, f, fmt, d, e in MESURES]
assert all(n in [x[0] for x in MESURES] for n in RAPIDES)

MESURES += [
    ("Indice prix fournisseur", "8. Décalage", "0.0",
     "Prix du tarif en vigueur, base 100 = tarif 2023 (panier fixe, en marches d'escalier aux campagnes).",
     "AVERAGE ( fact_indice_fournisseur[indice_prix] )"),
    ("Indice coût matière", "8. Décalage", "0.0",
     "Coût matière du même panier, base 100 = référence du tarif 2023 (Σ part × indice INSEE).",
     "AVERAGE ( fact_indice_fournisseur[indice_cout_matiere] )"),
    ("Écart prix / matière (pts)", "8. Décalage", "+0.0;-0.0;0.0",
     "Indice prix − indice coût matière : positif = le fournisseur facture plus que l'évolution de ses matières.",
     """VAR _p = [Indice prix fournisseur]
VAR _c = [Indice coût matière]
RETURN
    IF ( NOT ISBLANK ( _p ) && NOT ISBLANK ( _c ), _p - _c )"""),
    ("Quantité N-1", "3. Achats", "#,0",
     "Quantités de la même période un an plus tôt, coupée au dernier mois d'achat connu (comparaison à date).",
     """VAR _fin = EOMONTH ( CALCULATE ( MAX ( fact_achats[date] ), REMOVEFILTERS () ), 0 )
RETURN
    CALCULATE ( [Quantité achetée], SAMEPERIODLASTYEAR ( dim_date[date] ), dim_date[date] <= EDATE ( _fin, -12 ) )"""),
    ("Montant N-1", "3. Achats", "#,0 €",
     "Montant des achats de la même période un an plus tôt, à date.",
     """VAR _fin = EOMONTH ( CALCULATE ( MAX ( fact_achats[date] ), REMOVEFILTERS () ), 0 )
RETURN
    CALCULATE ( [Montant achats], SAMEPERIODLASTYEAR ( dim_date[date] ), dim_date[date] <= EDATE ( _fin, -12 ) )"""),
    ("Évol. volume %", "3. Achats", "+0.0%;-0.0%;0.0%", "Quantités vs même période N-1.",
     "DIVIDE ( [Quantité achetée] - [Quantité N-1], [Quantité N-1] )"),
    ("Évol. montant %", "3. Achats", "+0.0%;-0.0%;0.0%", "Montant des achats vs même période N-1.",
     "DIVIDE ( [Montant achats] - [Montant N-1], [Montant N-1] )"),
    ("Effet prix %", "3. Achats", "+0.0%;-0.0%;0.0%",
     "Hausse de prix subie à volumes constants : Σ qté × (prix N − prix N-1) / Σ qté × prix N-1, sur les articles achetés les deux années.",
     """VAR _t = FILTER ( fact_achats, NOT ISBLANK ( fact_achats[prix_unitaire] ) && NOT ISBLANK ( fact_achats[prix_unitaire_n1] ) )
RETURN
    DIVIDE (
        SUMX ( _t, fact_achats[quantite] * ( fact_achats[prix_unitaire] - fact_achats[prix_unitaire_n1] ) ),
        SUMX ( _t, fact_achats[quantite] * fact_achats[prix_unitaire_n1] )
    )"""),
    ("Surcoût prix €", "3. Achats", "#,0 €", "Euros payés en plus par la seule hausse de prix, à volumes constants.",
     """VAR _t = FILTER ( fact_achats, NOT ISBLANK ( fact_achats[prix_unitaire] ) && NOT ISBLANK ( fact_achats[prix_unitaire_n1] ) )
RETURN
    SUMX ( _t, fact_achats[quantite] * ( fact_achats[prix_unitaire] - fact_achats[prix_unitaire_n1] ) )"""),
    ("Couleur variation", "6. Négociation", "", "Vert marque si la matière baisse (levier acheteur), ambre signal si elle monte.",
     """VAR _v = [Variation matière article %]
RETURN
    IF ( ISBLANK ( _v ), "#56655F", IF ( _v < 0, "#0F5C4A", "#C9781C" ) )"""),
    ("Résumé signaux", "6. Négociation", "", "Nombre de matières en hausse et en baisse sur 3 mois.",
     """VAR _h = COUNTROWS ( FILTER ( VALUES ( dim_matiere[libelle] ), [Variation 3 mois %] > 0.05 ) )
VAR _b = COUNTROWS ( FILTER ( VALUES ( dim_matiere[libelle] ), [Variation 3 mois %] < -0.05 ) )
RETURN
    FORMAT ( _h + 0, "0" ) & " ▲   " & FORMAT ( _b + 0, "0" ) & " ▼"
"""),
    ("Résumé cible", "6. Négociation", "", "Nombre de fournisseurs à renégocier, en clair.",
     "FORMAT ( [Nb fournisseurs à renégocier] + 0, \"0\" ) & \" fournisseurs\""),
    ("Résumé 2027", "6. Négociation", "", "Hausse déjà justifiée pour la prochaine campagne, en clair.",
     "[Prochaine campagne] & \" : \" & FORMAT ( [Plafond justifié prochaine campagne %], \"+0.0 %\" )"),
    ("Nb fournisseurs à renégocier", "6. Négociation", "0", "Fournisseurs dont l'écart dépasse 3 points.",
     "COUNTROWS ( FILTER ( VALUES ( dim_fournisseur[nom] ), [Écart pts] > 3 ) )"),
    ("Prévision indice", "10. Prévisions ML", "#,0.0", "Indice prévu par le modèle retenu au backtest.",
     "AVERAGE ( ml_prevision_indices[prevision] )"),
    ("Prévision basse 80 %", "10. Prévisions ML", "#,0.0", "Borne basse de l'intervalle à 80 %.",
     "AVERAGE ( ml_prevision_indices[bas_80] )"),
    ("Prévision haute 80 %", "10. Prévisions ML", "#,0.0", "Borne haute de l'intervalle à 80 %.",
     "AVERAGE ( ml_prevision_indices[haut_80] )"),
    ("Variation 2027 attendue %", "10. Prévisions ML", "+0.0%;-0.0%;0.0%",
     "Variation matière attendue pour 2027 (fenêtre juillet-décembre 2026 complétée par la prévision).",
     "AVERAGE ( ml_variation_2027[variation_centrale] )"),
    ("Fourchette 2027", "10. Prévisions ML", "", "Fourchette à 80 % de la variation 2027 attendue.",
     """VAR _b = AVERAGE ( ml_variation_2027[variation_basse] )
VAR _h = AVERAGE ( ml_variation_2027[variation_haute] )
RETURN
    IF ( NOT ISBLANK ( _b ), FORMAT ( _b, "+0.0 %;-0.0 %" ) & " à " & FORMAT ( _h, "+0.0 %;-0.0 %" ) )"""),
    ("Plafond 2027 projeté %", "10. Prévisions ML", "+0.0%;-0.0%;0.0%",
     "Hausse justifiable 2027 projetée, pondérée par prix 2026 × volume 2025.",
     "DIVIDE ( SUMX ( ml_plafond_2027, ml_plafond_2027[poids] * ml_plafond_2027[plafond_central] ), SUM ( ml_plafond_2027[poids] ) )"),
    ("Fourchette plafond 2027", "10. Prévisions ML", "", "Fourchette à 80 % du plafond 2027 projeté.",
     """VAR _w = SUM ( ml_plafond_2027[poids] )
VAR _b = DIVIDE ( SUMX ( ml_plafond_2027, ml_plafond_2027[poids] * ml_plafond_2027[plafond_bas] ), _w )
VAR _h = DIVIDE ( SUMX ( ml_plafond_2027, ml_plafond_2027[poids] * ml_plafond_2027[plafond_haut] ), _w )
RETURN
    IF ( NOT ISBLANK ( _b ), FORMAT ( _b, "+0.0 %;-0.0 %" ) & " à " & FORMAT ( _h, "+0.0 %;-0.0 %" ) )"""),
    ("Segment ML", "10. Prévisions ML", "", "Segment de comportement tarifaire du fournisseur (KMeans).",
     "SELECTEDVALUE ( ml_segments_fournisseurs[segment_nom] )"),
    ("Écart moyen 3 campagnes (pts)", "10. Prévisions ML", "+0.0;-0.0;0.0", "Écart moyen demandé − justifié sur 3 campagnes.",
     "AVERAGE ( ml_segments_fournisseurs[ecart_moyen] ) * 100"),
    ("Lignes anormales", "10. Prévisions ML", "#,0", "Lignes du tarif 2026 isolées en hausse excessive.",
     "CALCULATE ( COUNTROWS ( ml_anomalies_tarif ), ml_anomalies_tarif[anomalie] = TRUE (), ml_anomalies_tarif[ecart] > 0 )"),
    ("€ lignes anormales", "10. Prévisions ML", "#,0 €", "Écart en euros des lignes isolées en hausse excessive.",
     "CALCULATE ( SUM ( ml_anomalies_tarif[enjeu_eur] ), ml_anomalies_tarif[anomalie] = TRUE (), ml_anomalies_tarif[ecart] > 0 )"),
    ("Demandée (ligne) %", "10. Prévisions ML", "+0.0%;-0.0%;0.0%", "Hausse demandée de la ligne.",
     "AVERAGE ( ml_anomalies_tarif[demandee] )"),
    ("Justifiée (ligne) %", "10. Prévisions ML", "+0.0%;-0.0%;0.0%", "Hausse justifiée de la ligne.",
     "AVERAGE ( ml_anomalies_tarif[hausse_justifiee] )"),
    ("Montant payé", "11. Groupe", "#,0 €", "Quantités × prix payé dans l'ERP des sites.",
     "SUMX ( fact_achats_entite, fact_achats_entite[quantite] * fact_achats_entite[prix_paye] )"),
    ("Surcoût vs meilleur prix groupe", "11. Groupe", "#,0 €",
     "Ce que les sites paient au-dessus du meilleur prix obtenu par un site du groupe pour le même article la même année.",
     "SUM ( fact_achats_entite[surcout_vs_meilleur] )"),
    ("% surcoût groupe", "11. Groupe", "0.0%", "Surcoût vs meilleur prix groupe / montant payé.",
     "DIVIDE ( [Surcoût vs meilleur prix groupe], [Montant payé] )"),
    ("Prix payé moyen", "11. Groupe", "#,0.00 €", "Montant payé / quantité.",
     "DIVIDE ( [Montant payé], SUM ( fact_achats_entite[quantite] ) )"),
    ("Meilleur prix groupe", "11. Groupe", "#,0.00 €", "Meilleur prix moyen payé par un site du groupe (un article à la fois).",
     "IF ( HASONEVALUE ( dim_article[article_id] ), AVERAGE ( fact_achats_entite[meilleur_prix_groupe] ) )"),
    ("Écart d'application €", "11. Groupe", "+#,0 €;-#,0 €;0 €",
     "Prix payé − prix du tarif, sur les lignes où l'ERP n'applique pas le tarif : positif = payé trop cher.",
     "SUM ( fact_achats_entite[ecart_application] )"),
    ("Payé en trop (application)", "11. Groupe", "#,0 €", "Somme des écarts d'application défavorables (payé au-dessus du tarif).",
     "SUMX ( FILTER ( fact_achats_entite, fact_achats_entite[ecart_application] > 0 ), fact_achats_entite[ecart_application] )"),
    ("Articles en écart d'application", "11. Groupe", "#,0", "Articles avec au moins une ligne en retard ou en écart durable.",
     """CALCULATE ( DISTINCTCOUNT ( fact_achats_entite[article_id] ),
    fact_achats_entite[statut_prix] IN { "Retard d'application", "Écart durable" } )"""),
    ("Économies obtenues €", "12. Gains", "#,0 €", "Hausse refusée au fournisseur × valeur N : ce que la négociation a réellement rapporté.",
     "SUM ( fact_negociation[economie_eur] )"),
    ("Potentiel renégociable €", "12. Gains", "#,0 €", "€ renégociables des campagnes (écart à la hausse justifiée).",
     "SUM ( fact_negociation[eur_renegociables] )"),
    ("Taux de transformation", "12. Gains", "0%", "Économies obtenues / potentiel renégociable.",
     "DIVIDE ( [Économies obtenues €], [Potentiel renégociable €] )"),
    ("Hausse demandée (négo) %", "12. Gains", "+0.0%;-0.0%;0.0%", "Hausse demandée, pondérée par la valeur N.",
     "DIVIDE ( SUMX ( fact_negociation, fact_negociation[valeur_n] * fact_negociation[hausse_demandee] ), SUM ( fact_negociation[valeur_n] ) )"),
    ("Hausse obtenue %", "12. Gains", "+0.0%;-0.0%;0.0%", "Hausse finalement accordée, pondérée par la valeur N.",
     "DIVIDE ( SUMX ( fact_negociation, fact_negociation[valeur_n] * fact_negociation[hausse_obtenue] ), SUM ( fact_negociation[valeur_n] ) )"),
    ("Hausse justifiée (négo) %", "12. Gains", "+0.0%;-0.0%;0.0%", "Hausse justifiée par les matières, pondérée par la valeur N.",
     "DIVIDE ( SUMX ( fact_negociation, fact_negociation[valeur_n] * fact_negociation[hausse_justifiee] ), SUM ( fact_negociation[valeur_n] ) )"),
    ("Conseil appro", "7. Alertes", "",
     "Conseil d'approvisionnement avant la prochaine campagne : baisse matière → limiter les achats et attendre le nouveau tarif ; hausse > 3 % → anticiper les achats avant le 1er janvier.",
     """VAR _p = [Plafond justifié prochaine campagne %]
RETURN
    SWITCH ( TRUE (), ISBLANK ( _p ), BLANK (),
        _p < 0, "▼ Limiter les achats, attendre la baisse",
        _p > 0.03, "▲ Anticiper les achats",
        "● Achats normaux" )"""),
    ("Couleur conseil", "7. Alertes", "", "Vert = attendre la baisse, rouge = anticiper avant la hausse, gris = normal.",
     """VAR _p = [Plafond justifié prochaine campagne %]
RETURN
    SWITCH ( TRUE (), ISBLANK ( _p ), "#56655F", _p < 0, "#0F5C4A", _p > 0.03, "#C9781C", "#56655F" )"""),
]

ROLES = {
    "Acheteur": ("Acheteur : ne voit que les familles dont il est responsable.",
                 {"dim_acheteur": "dim_acheteur[email] = USERPRINCIPALNAME ()"}),
    "Direction": ("Direction : voit tout (aucun filtre).", {}),
}

# --------------------------------------------------------------------------------------
# Rapport : pages et visuels (format report.json). Champ : ("m", mesure) ou ("c", table, colonne)
# --------------------------------------------------------------------------------------
CAMPAGNE = ("c", "param_campagne", "campagne")
FOURN = ("c", "dim_fournisseur", "nom")


# Charte Buyvera (design system « Buyvera ») ; séries validées au contrôle daltonisme du skill dataviz
SERIES = ["#16876A", "#C9781C", "#3C7DC4", "#B4508A", "#6E9A2A", "#7B5CC4", "#D0563F", "#2AA0B3"]
NAVY, NAVY_2, ACCENT, FOND, BORD = "#12211D", "#1C2E29", "#0F5C4A", "#ECEAE3", "#DCD8CE"
PAPIER, TUILE_SIGNAL, TEXTE_SIGNAL = "#F6F4EE", "#F8E9D6", "#7A4610"
HAUT = 56  # hauteur du bandeau de navigation
TEXTE, TEXTE_2, MUET, GRILLE = "#12211D", "#56655F", "#56655F", "#E6E2D8"
MENTHE, SIGNAL = "#7FD1B3", "#C9781C"
TEAL, AMBRE, GRIS = ACCENT, "#eda100", MUET


def m(nom: str) -> tuple:
    return ("m", nom)


def v(typ, x, y, w, h, roles=None, titre=None, ordre=None, objets=None, filtres=None, texte=None):
    return dict(typ=typ, x=x, y=y, w=w, h=h, roles=roles or {}, titre=titre, ordre=ordre,
                objets=objets or {}, filtres=filtres or [], texte=texte)


def entete(titre: str, sous_titre: str) -> list[dict]:
    return [v("textbox", 20, 8, 900, 70, texte=(titre, sous_titre), objets={"entete": True}),
            v("card", 960, 18, 300, 40, {"Values": [m("Dernier indice chargé")]},
              objets={"police": 10, "fond": TUILE_SIGNAL, "valeur": TEXTE_SIGNAL, "sans_bord": True})]


def segment(champ, x, y, w=240, h=62, titre=None, unique=False):
    """Segment déroulant, synchronisé entre toutes les pages (le choix suit l'utilisateur)."""
    nom_sync = champ[-1]
    return v("slicer", x, y, w, h, {"Values": [champ]},
             objets={"dropdown": True, "entete": titre, "unique": unique, "sync": nom_sync})


def bouton(texte, cible, x, y, w=220, h=40):
    return v("nav", x, y, w, h, objets={"cible": cible, "texte": texte, "actif": True})


def retour(x=1060, y=92, w=200):
    return v("nav", x, y, w, 40, objets={"cible": 0, "texte": "←  Retour", "actif": True, "retour": True})


def etape(num, titre, question, cible, x, y, w=236, h=250):
    """Carte d'étape du parcours : numéro, titre, question, bouton vers la page."""
    return [v("shape", x, y, w, h, objets={"couleur": "#FFFFFF"}),
            v("textbox", x + 16, y + 14, w - 32, 140, texte=(f"{num}  {titre}", question), objets={"etape": True}),
            v("nav", x + 16, y + h - 58, w - 32, 42, objets={"cible": cible, "texte": "Ouvrir  →", "actif": True})]


def tuile(x, y, w, h, mesure, titre, cle=False, filtres=None, police=None):
    o = {"fond": ACCENT, "valeur": "#FFFFFF", "titre_c": "#D6EFE5"} if cle else {}
    if police:
        o["police"] = police
    return v("card", x, y, w, h, {"Values": [m(mesure)]}, titre=titre, objets=o, filtres=filtres or [])


KPI_CAMPAGNE = [
    tuile(20 + i * 250, 150, 235, 100, n, n, cle=(n == "€ renégociables"))
    for i, n in enumerate(["€ renégociables", "Hausse demandée %", "Hausse justifiée %", "Écart pts", "Valeur N"])
]

PAGES = [
    ("Parcours négociation", entete(
        "Préparer la négociation en 5 étapes",
        "De l'alerte matière au rendez-vous fournisseur. Chaque étape donne son chiffre clé et ouvre la page qui répond.") + [
        tuile(20, 92, 300, 84, "€ renégociables", "€ renégociables · campagne 2026", cle=True),
        tuile(335, 92, 300, 84, "Nb fournisseurs à renégocier", "Fournisseurs à renégocier"),
        tuile(650, 92, 300, 84, "Effet prix %", "Effet prix 2026 à volumes constants", filtres=[(("c", "dim_date", "annee"), [2026])]),
        tuile(965, 92, 295, 84, "Plafond justifié prochaine campagne %", "Déjà justifié pour 2027"),
        *[x for i, (titre, question, mesure, cible, f) in enumerate([
            ("1  Détecter", "Quelles matières montent ou baissent ?", "Résumé signaux", "Alertes matières", []),
            ("2  Chiffrer", "Combien renégocier sur la campagne ?", "€ renégociables", "Synthèse campagne", []),
            ("3  Cibler", "Qui demande plus que ses matières ?", "Résumé cible", "Fournisseurs", []),
            ("4  Comprendre", "Prix et volumes, année sur année", "Effet prix %", "Prix & volumes", [(("c", "dim_date", "annee"), [2026])]),
            ("5  Négocier", "Argument et contre-proposition", "Résumé 2027", "Fiche négociation", []),
        ]) for x in (
            v("shape", 20, 192 + i * 102, 620, 92, objets={"couleur": "#FFFFFF"}),
            v("textbox", 36, 200 + i * 102, 290, 76, texte=(titre, question), objets={"etape": True}),
            v("card", 326, 204 + i * 102, 200, 68, {"Values": [m(mesure)]}, objets={"police": 15, "sans_bord": True, "fond": "#FFFFFF"},
              filtres=f),
            v("nav", 534, 218 + i * 102, 92, 40, objets={"cible": cible, "texte": "Ouvrir  →", "actif": True, "centre": True}),
        )],
        v("card", 660, 192, 600, 120, {"Values": [m("Argument anticipé")]}, titre="À retenir",
          objets={"police": 13, "fond": NAVY, "valeur": "#EEF2EF", "titre_c": MENTHE}),
        v("lineChart", 660, 326, 600, 366,
          {"Category": [("c", "dim_date", "date")], "Y": [m("Indice prix fournisseur"), m("Indice coût matière")]},
          titre="Décalage : prix fournisseurs vs coût de leurs matières (base 100 = 2023)", objets={"continu": True}),
    ]),
    ("Synthèse campagne", entete(
        "Cette hausse fournisseur est-elle justifiée ?",
        "Hausse demandée vs hausse justifiée par l'évolution réelle des matières (INSEE). Tarifs et volumes fictifs.") + [
        segment(CAMPAGNE, 20, 80, titre="Campagne (N+1)"),
        segment(("c", "dim_famille", "univers"), 280, 80, titre="Univers"),
        *KPI_CAMPAGNE,
        v("clusteredBarChart", 20, 270, 620, 430, {"Category": [FOURN], "Y": [m("€ renégociables")]},
          titre="€ renégociables par fournisseur", ordre=(m("€ renégociables"), 2), objets={"labels": True}),
        v("clusteredBarChart", 660, 270, 600, 430, {"Category": [("c", "dim_famille", "libelle")], "Y": [m("Écart pts")]},
          titre="Écart (pts) par famille · rouge > 3 pts, orange > 1 pt", ordre=(m("Écart pts"), 2),
          objets={"labels": True, "couleur_barres": "Couleur écart"}),
    ]),
    ("Fournisseurs", entete(
        "Fournisseurs : demandé vs justifié",
        "Un point par fournisseur : plus il est haut pour une même hausse justifiée, plus la hausse demandée est contestable.") + [
        segment(CAMPAGNE, 20, 80, titre="Campagne (N+1)"),
        segment(("c", "dim_famille", "univers"), 280, 80, titre="Univers"),
        v("scatterChart", 20, 150, 560, 550,
          {"Category": [FOURN], "X": [m("Hausse justifiée %")], "Y": [m("Hausse demandée %")], "Play": [CAMPAGNE]},
          titre="▶ Lancez l'animation : chaque fournisseur, campagne après campagne", objets={"catlabels": True}),
        v("tableEx", 600, 150, 660, 550,
          {"Values": [FOURN, m("Statut fournisseur"), m("Hausse demandée %"), m("Hausse justifiée %"), m("Écart pts"),
                      m("€ renégociables"), m("Effet cliquet")]},
          titre="Classement · clic droit sur un fournisseur → Extraire → Fiche négociation", ordre=(m("€ renégociables"), 2),
          objets={"noms": {FOURN: "Fournisseur", m("Statut fournisseur"): "Statut", m("Hausse demandée %"): "Demandée",
                           m("Hausse justifiée %"): "Justifiée", m("Écart pts"): "Écart (pts)",
                           m("€ renégociables"): "€ renégociables", m("Effet cliquet"): "Cliquet"},
                  "couleur_texte": (m("Statut fournisseur"), "Couleur écart")}),
        segment(FOURN, 540, 80, w=260, titre="Fournisseur"),
        bouton("Fiche négociation  →", "Fiche négociation", 1060, 92, w=200),
    ]),
    ("Détail article", entete(
        "Détail article",
        "Choisir un article : composition matière, indices de ses matières et historique de prix sur 4 campagnes.") + [
        segment(FOURN, 20, 80, w=240, titre="Fournisseur"),
        segment(("c", "dim_article", "designation"), 280, 80, w=420, titre="Article"),
        segment(CAMPAGNE, 720, 80, titre="Campagne (N+1)"),
        retour(),
        v("card", 20, 150, 200, 90, {"Values": [m("Hausse demandée %")]}, titre="Hausse demandée %"),
        v("card", 230, 150, 200, 90, {"Values": [m("Hausse justifiée %")]}, titre="Hausse justifiée %"),
        v("card", 440, 150, 200, 90, {"Values": [m("Écart pts")]}, titre="Écart pts"),
        v("tableEx", 20, 255, 620, 220,
          {"Values": [("c", "dim_matiere", "libelle"), m("Part matière moyenne"), m("Variation matière article %")]},
          titre="Composition et variation matière", ordre=(m("Part matière moyenne"), 2),
          objets={"noms": {("c", "dim_matiere", "libelle"): "Matière", m("Part matière moyenne"): "Part du coût",
                           m("Variation matière article %"): "Variation"}}),
        v("tableEx", 20, 490, 620, 210, {"Values": [("c", "fact_tarif", "campagne"), m("Prix brut")]},
          titre="Historique du prix brut", ordre=(("c", "fact_tarif", "campagne"), 1),
          objets={"noms": {("c", "fact_tarif", "campagne"): "Campagne", m("Prix brut"): "Prix brut"}}),
        v("lineChart", 660, 150, 600, 550,
          {"Category": [("c", "dim_date", "date")], "Series": [("c", "dim_matiere", "libelle")],
           "Y": [m("Indice matières article")]},
          titre="Indices des matières de l'article (base 2010, €)", objets={"continu": True}),
    ]),
    ("Matières", entete(
        "Matières premières",
        "Indices INSEE mensuels en euros. La variation compare la moyenne de la fenêtre avant N+1 à celle avant N.") + [
        segment(CAMPAGNE, 20, 80, titre="Campagne (N+1)"),
        segment(("c", "param_fenetre", "mois"), 280, 80, titre="Fenêtre de référence (mois)"),
        segment(("c", "param_decalage", "decalage_mois"), 540, 80, titre="Décalage d'application (mois)"),
        segment(FOURN, 800, 80, w=260, titre="Fournisseur"),
        v("lineChart", 20, 460, 370, 240,
          {"Category": [("c", "param_decalage", "decalage_mois")], "Y": [m("Écart pts")]},
          titre="Écart selon le décalage (point bas = retard du fournisseur)",
          ordre=(("c", "param_decalage", "decalage_mois"), 1), objets={"labels": True}),
        v("clusteredBarChart", 400, 460, 380, 240,
          {"Category": [FOURN], "Y": [m("Délai hausses (mois)"), m("Délai baisses (mois)")]},
          titre="Délai de répercussion : hausses vs baisses (mois)", ordre=(m("Délai baisses (mois)"), 2)),
        v("lineChart", 20, 150, 760, 300,
          {"Category": [("c", "dim_date", "date")], "Series": [("c", "dim_matiere", "libelle")],
           "Y": [m("Indice (composition)")]},
          titre="Indices matières (base 2010, en €)", objets={"continu": True}),
        v("clusteredBarChart", 800, 150, 460, 550,
          {"Category": [("c", "dim_matiere", "libelle")], "Y": [m("Variation (composition) %")]},
          titre="Variation matière sur la fenêtre", ordre=(m("Variation (composition) %"), 2), objets={"labels": True}),
    ]),
    ("Rattachement", entete(
        "Rattachement des références",
        "Référence tarif fournisseur vs référence ERP. Objectif : 80 % de rattachement automatique.") + [
        segment(FOURN, 20, 80, w=240, titre="Fournisseur"),
        v("card", 20, 150, 300, 100, {"Values": [m("% rattachés auto")]}, titre="Rattachement automatique"),
        v("card", 335, 150, 300, 100, {"Values": [m("% proposés")]}, titre="Proposé (à valider)"),
        v("card", 650, 150, 300, 100, {"Values": [m("% non rattachés")]}, titre="Non rattaché"),
        v("card", 965, 150, 295, 100, {"Values": [m("Objectif rattachement")]}, titre="Objectif"),
        v("tableEx", 20, 270, 460, 430,
          {"Values": [FOURN, m("Nb articles"), m("% rattachés auto"), m("% proposés"), m("% non rattachés")]},
          titre="Taux par fournisseur", ordre=(m("% rattachés auto"), 1),
          objets={"noms": {FOURN: "Fournisseur", m("Nb articles"): "Articles", m("% rattachés auto"): "Auto",
                           m("% proposés"): "Proposé", m("% non rattachés"): "Non ratt."}}),
        v("tableEx", 500, 270, 760, 430,
          {"Values": [("c", "dim_article", "statut_rattachement"), ("c", "dim_article", "ref_fournisseur"),
                      ("c", "dim_article", "designation_tarif"), ("c", "dim_article", "designation"),
                      ("c", "dim_article", "score_rattachement")]},
          titre="Articles à valider", ordre=(("c", "dim_article", "score_rattachement"), 2),
          objets={"noms": {("c", "dim_article", "statut_rattachement"): "Statut",
                           ("c", "dim_article", "ref_fournisseur"): "Réf. tarif",
                           ("c", "dim_article", "designation_tarif"): "Désignation tarif",
                           ("c", "dim_article", "designation"): "Désignation ERP proche",
                           ("c", "dim_article", "score_rattachement"): "Score"}},
          filtres=[(("c", "dim_article", "statut_rattachement"), ["Proposé", "Non rattaché"])]),
    ]),
    ("Alertes matières", entete(
        "Alertes & anticipation",
        "Ce qui bouge sur les matières, et ce que chaque fournisseur pourra légitimement demander à la prochaine campagne.") + [
        segment(("c", "dim_famille", "univers"), 20, 80, titre="Univers"),
        v("card", 280, 80, 980, 62, {"Values": [m("Argument anticipé")]}, objets={"police": 12}),
        v("tableEx", 20, 155, 640, 270,
          {"Values": [("c", "dim_matiere", "libelle"), m("Alerte matière"), m("Dernier indice"),
                      m("Variation 3 mois %"), m("Variation 12 mois %"), m("Variation anticipée %")]},
          titre="Signaux matières · cliquez une matière pour voir les articles impactés", ordre=(m("Variation 3 mois %"), 2),
          objets={"noms": {("c", "dim_matiere", "libelle"): "Matière", m("Alerte matière"): "Signal",
                           m("Dernier indice"): "Indice", m("Variation 3 mois %"): "3 mois",
                           m("Variation 12 mois %"): "12 mois", m("Variation anticipée %"): "Acquis campagne"},
                  "couleur_texte": (m("Alerte matière"), "Couleur alerte")}),
        v("tableEx", 20, 435, 640, 265,
          {"Values": [FOURN, m("Plafond justifié prochaine campagne %"), m("Impact € prochaine campagne"),
                      m("Action fournisseur"), m("Conseil appro")]},
          titre="Plan d'action fournisseurs pour la prochaine campagne",
          ordre=(m("Plafond justifié prochaine campagne %"), 1),
          objets={"noms": {FOURN: "Fournisseur", m("Plafond justifié prochaine campagne %"): "Plafond justifié",
                           m("Impact € prochaine campagne"): "Impact €", m("Action fournisseur"): "Négociation",
                           m("Conseil appro"): "Appro"},
                  "couleur_texte": (m("Action fournisseur"), "Couleur action")}),
        v("tableEx", 680, 155, 580, 545,
          {"Values": [("c", "dim_article", "designation"), m("Impact € prochaine campagne"), m("Volume annuel"),
                      m("Conseil appro")]},
          titre="Articles exposés · clic droit → Extraire → Détail article",
          ordre=(m("Impact € prochaine campagne"), 2),
          objets={"noms": {("c", "dim_article", "designation"): "Article", FOURN: "Fournisseur",
                           ("c", "dim_famille", "libelle"): "Famille", m("Volume annuel"): "Volume / an",
                           m("Impact € prochaine campagne"): "Impact €", m("Conseil appro"): "Appro"},
                  "couleur_texte": (m("Conseil appro"), "Couleur conseil")}),
    ]),
    ("Prix & volumes", entete(
        "Prix et volumes, année sur année",
        "Ce que les hausses ont coûté à volumes constants, et comment les volumes évoluent. Comparaison à date (même période N-1).") + [
        segment(("c", "dim_famille", "univers"), 20, 80, titre="Univers"),
        segment(FOURN, 280, 80, w=260, titre="Fournisseur"),
        v("card", 20, 150, 300, 96, {"Values": [m("Montant achats")]}, titre="Achats 2026 à date",
          filtres=[(("c", "dim_date", "annee"), [2026])]),
        v("card", 335, 150, 300, 96, {"Values": [m("Évol. montant %")]}, titre="Montant vs 2025 à date",
          filtres=[(("c", "dim_date", "annee"), [2026])]),
        v("card", 650, 150, 300, 96, {"Values": [m("Évol. volume %")]}, titre="Volumes vs 2025 à date",
          filtres=[(("c", "dim_date", "annee"), [2026])]),
        v("card", 965, 150, 295, 96, {"Values": [m("Effet prix %")]}, titre="Effet prix (volumes constants)",
          filtres=[(("c", "dim_date", "annee"), [2026])]),
        v("lineChart", 20, 260, 610, 440,
          {"Category": [("c", "dim_date", "mois_court")], "Series": [("c", "dim_date", "annee")], "Y": [m("Quantité achetée")]},
          titre="Volumes par mois : une courbe par année", ordre=(("c", "dim_date", "mois_court"), 1),
          filtres=[(("c", "dim_date", "annee"), [2024, 2025, 2026])]),
        v("tableEx", 650, 260, 610, 440,
          {"Values": [FOURN, m("Montant achats"), m("Évol. montant %"), m("Évol. volume %"), m("Effet prix %"), m("Surcoût prix €")]},
          titre="Par fournisseur, 2026 à date vs 2025 · clic droit → Extraire → Fiche", ordre=(m("Surcoût prix €"), 2),
          objets={"noms": {FOURN: "Fournisseur", m("Montant achats"): "Achats", m("Évol. montant %"): "Montant",
                           m("Évol. volume %"): "Volume", m("Effet prix %"): "Effet prix", m("Surcoût prix €"): "Surcoût €"}},
          filtres=[(("c", "dim_date", "annee"), [2026])]),
    ]),
    ("Prix payés", entete(
        "Prix payés dans le groupe",
        "Le même article, partout : surcoût vs le meilleur prix du groupe, et tarifs mal appliqués dans les ERP des sites.") + [
        segment(("c", "dim_date", "annee"), 20, 80, w=180, titre="Année"),
        segment(("c", "dim_entite", "nom"), 215, 80, w=220, titre="Site"),
        segment(FOURN, 450, 80, w=260, titre="Fournisseur"),
        tuile(20, 152, 300, 84, "Surcoût vs meilleur prix groupe", "Surcoût vs meilleur prix du groupe", cle=True),
        tuile(335, 152, 300, 84, "% surcoût groupe", "Part du montant payé"),
        tuile(650, 152, 300, 84, "Payé en trop (application)", "Payé au-dessus du tarif (ERP)"),
        tuile(965, 152, 295, 84, "Articles en écart d'application", "Articles à corriger dans les ERP"),
        v("clusteredBarChart", 20, 250, 400, 220, {"Category": [("c", "dim_entite", "nom")], "Y": [m("Surcoût vs meilleur prix groupe")]},
          titre="Surcoût par site", ordre=(m("Surcoût vs meilleur prix groupe"), 2), objets={"labels": True}),
        v("clusteredBarChart", 440, 250, 820, 220, {"Category": [("c", "fact_achats_entite", "statut_prix")], "Y": [m("Écart d'application €")]},
          titre="Écart d'application par cause : retard = ancien tarif encore appliqué, écart durable = prix mal saisi",
          ordre=(m("Écart d'application €"), 2), objets={"labels": True},
          filtres=[(("c", "fact_achats_entite", "statut_prix"), ["Retard d'application", "Écart durable"])]),
        v("tableEx", 20, 484, 620, 216,
          {"Values": [("c", "dim_article", "designation"), ("c", "dim_entite", "nom"), m("Prix payé moyen"),
                      m("Meilleur prix groupe"), m("Surcoût vs meilleur prix groupe")]},
          titre="Aligner sur le meilleur prix du groupe · clic droit → Extraire → Détail article",
          ordre=(m("Surcoût vs meilleur prix groupe"), 2),
          objets={"noms": {("c", "dim_article", "designation"): "Article", ("c", "dim_entite", "nom"): "Site",
                           m("Prix payé moyen"): "Payé", m("Meilleur prix groupe"): "Meilleur", m("Surcoût vs meilleur prix groupe"): "Surcoût"},
                  "largeurs": {("c", "dim_article", "designation"): 210, ("c", "dim_entite", "nom"): 95,
                               m("Prix payé moyen"): 70, m("Meilleur prix groupe"): 70, m("Surcoût vs meilleur prix groupe"): 70}}),
        v("tableEx", 660, 484, 600, 216,
          {"Values": [("c", "dim_article", "designation"), ("c", "dim_entite", "nom"), ("c", "fact_achats_entite", "statut_prix"),
                      m("Écart d'application €")]},
          titre="Tarifs mal appliqués : à transmettre à l'approvisionneur du site", ordre=(m("Écart d'application €"), 2),
          objets={"noms": {("c", "dim_article", "designation"): "Article", ("c", "dim_entite", "nom"): "Site",
                           ("c", "fact_achats_entite", "statut_prix"): "Cause", m("Écart d'application €"): "Écart"},
                  "largeurs": {("c", "dim_article", "designation"): 230, ("c", "dim_entite", "nom"): 95,
                               ("c", "fact_achats_entite", "statut_prix"): 110, m("Écart d'application €"): 70}},
          filtres=[(("c", "fact_achats_entite", "statut_prix"), ["Retard d'application", "Écart durable"])]),
    ]),
    ("Gains", entete(
        "Gains de négociation",
        "Ce que les négociations ont réellement rapporté, face au potentiel chiffré avant chaque campagne.") + [
        segment(("c", "dim_famille", "univers"), 20, 80, titre="Univers"),
        tuile(20, 152, 300, 84, "Économies obtenues €", "Économies obtenues · 3 campagnes", cle=True),
        tuile(335, 152, 300, 84, "Potentiel renégociable €", "Potentiel renégociable"),
        tuile(650, 152, 300, 84, "Taux de transformation", "Taux de transformation"),
        tuile(965, 152, 295, 84, "Hausse obtenue %", "Hausse accordée (moyenne pondérée)"),
        v("clusteredColumnChart", 20, 250, 620, 450,
          {"Category": [("c", "fact_negociation", "campagne")], "Y": [m("Potentiel renégociable €"), m("Économies obtenues €")]},
          titre="Potentiel vs économies obtenues, par campagne", ordre=(("c", "fact_negociation", "campagne"), 1), objets={"labels": True}),
        v("tableEx", 660, 250, 600, 450,
          {"Values": [FOURN, m("Hausse demandée (négo) %"), m("Hausse justifiée (négo) %"), m("Hausse obtenue %"),
                      m("Économies obtenues €"), m("Taux de transformation")]},
          titre="Par fournisseur · clic droit → Extraire → Fiche négociation", ordre=(m("Économies obtenues €"), 2),
          objets={"noms": {FOURN: "Fournisseur", m("Hausse demandée (négo) %"): "Demandée", m("Hausse justifiée (négo) %"): "Justifiée",
                           m("Hausse obtenue %"): "Obtenue", m("Économies obtenues €"): "Économie", m("Taux de transformation"): "Taux"}}),
    ]),
    ("Prévisions", entete(
        "Prévisions (machine learning)",
        "Chaque modèle est testé sur le passé contre une référence naïve et n'est gardé que s'il la bat. Détail : docs/ml_rapport.md.") + [
        tuile(20, 92, 300, 84, "Plafond 2027 projeté %", "Hausse justifiable 2027 projetée", cle=True),
        v("card", 335, 92, 300, 84, {"Values": [m("Fourchette plafond 2027")]}, titre="Fourchette à 80 %", objets={"police": 14}),
        tuile(650, 92, 300, 84, "Lignes anormales", "Lignes tarifaires anormales 2026"),
        tuile(965, 92, 295, 84, "€ lignes anormales", "Écart sur ces lignes"),
        segment(("c", "dim_matiere", "libelle"), 20, 190, w=240, titre="Matière", unique=True),
        v("lineChart", 20, 262, 760, 200,
          {"Category": [("c", "dim_date", "date")],
           "Y": [m("Indice (composition)"), m("Prévision indice"), m("Prévision basse 80 %"), m("Prévision haute 80 %")]},
          titre="Indice réel et prévision à 3 mois (fourchette à 80 %)", objets={"continu": True},
          filtres=[(("c", "dim_date", "annee"), [2025, 2026])]),
        v("tableEx", 800, 190, 460, 272,
          {"Values": [("c", "dim_matiere", "libelle"), m("Variation 2027 attendue %"), m("Fourchette 2027")]},
          titre="Variation matière attendue pour la campagne 2027", ordre=(m("Variation 2027 attendue %"), 2),
          objets={"noms": {("c", "dim_matiere", "libelle"): "Matière", m("Variation 2027 attendue %"): "Attendue",
                           m("Fourchette 2027"): "Fourchette 80 %"}}),
        v("tableEx", 20, 476, 560, 224,
          {"Values": [FOURN, m("Segment ML"), m("Écart moyen 3 campagnes (pts)"), m("Plafond 2027 projeté %")]},
          titre="Segments de comportement (KMeans) · clic droit → Extraire → Fiche", ordre=(m("Écart moyen 3 campagnes (pts)"), 2),
          objets={"noms": {FOURN: "Fournisseur", m("Segment ML"): "Segment", m("Écart moyen 3 campagnes (pts)"): "Écart moyen",
                           m("Plafond 2027 projeté %"): "Plafond 2027"}}),
        v("tableEx", 600, 476, 660, 224,
          {"Values": [("c", "dim_article", "designation"), FOURN, m("Demandée (ligne) %"), m("Justifiée (ligne) %"), m("€ lignes anormales")]},
          titre="Lignes tarifaires anormales (Isolation Forest) · à vérifier en priorité", ordre=(m("€ lignes anormales"), 2),
          objets={"noms": {("c", "dim_article", "designation"): "Article", FOURN: "Fournisseur",
                           m("Demandée (ligne) %"): "Demandée", m("Justifiée (ligne) %"): "Justifiée", m("€ lignes anormales"): "Écart €"}},
          filtres=[(("c", "ml_anomalies_tarif", "anomalie"), [True])]),
    ]),
    ("Fiche négociation", entete(
        "Fiche négociation",
        "Tout pour préparer le rendez-vous : chiffres, argument matière, historique et contre-proposition chiffrée.") + [
        segment(FOURN, 20, 80, w=300, titre="Fournisseur", unique=True),
        segment(CAMPAGNE, 340, 80, titre="Campagne (N+1)"),
        segment(("c", "param_hausse", "hausse_acceptee"), 600, 80, w=260, titre="Simulateur : hausse acceptée (%)"),
        retour(),
        v("card", 20, 150, 240, 96, {"Values": [m("Statut fournisseur")]}, titre="Statut campagne", objets={"police": 14}),
        v("card", 270, 150, 240, 96, {"Values": [m("Hausse demandée %")]}, titre="Hausse demandée"),
        v("card", 520, 150, 240, 96, {"Values": [m("Hausse justifiée %")]}, titre="Hausse justifiée"),
        v("card", 770, 150, 240, 96, {"Values": [m("€ renégociables")]}, titre="€ renégociables"),
        v("card", 1020, 150, 240, 96, {"Values": [m("€ économisés (contre-proposition)")]},
          titre="Gain de la contre-proposition"),
        v("card", 20, 258, 1240, 70, {"Values": [m("Commentaire négociation")]}, titre="Synthèse pour le rendez-vous",
          objets={"police": 13}),
        v("card", 20, 336, 500, 52, {"Values": [m("Argument anticipé")]}, objets={"police": 11}),
        v("card", 530, 336, 360, 52, {"Values": [m("Action fournisseur")]}, objets={"police": 11}),
        v("card", 900, 336, 360, 52, {"Values": [m("Conseil appro")]}, objets={"police": 11}),
        v("lineChart", 20, 400, 610, 300,
          {"Category": [("c", "dim_date", "date")], "Y": [m("Indice prix fournisseur"), m("Indice coût matière")]},
          titre="Décalage : son prix vs le coût de ses matières (base 100 = 2023)", objets={"continu": True}),
        v("clusteredBarChart", 650, 400, 610, 300,
          {"Category": [("c", "dim_matiere", "libelle")], "Y": [m("Variation matière article %")]},
          titre="Matières de son panier : vert = baisse (levier), ambre = hausse", ordre=(m("Variation matière article %"), 1),
          objets={"labels": True, "couleur_barres": "Couleur variation"}),
    ]),
]


# --------------------------------------------------------------------------------------
# Écriture TMDL
# --------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------
# Design : thème, barre de navigation latérale, zone de contenu
# --------------------------------------------------------------------------------------
# Palette catégorielle validée (skill dataviz : l'ordre garantit la lisibilité daltonisme)
LARGEUR_NAV = 200
# Ordre de navigation : le parcours de négociation, puis les pages de détail
ORDRE = ["Parcours négociation", "Synthèse campagne", "Alertes matières", "Fournisseurs", "Fiche négociation",
         "Prix & volumes", "Prix payés", "Prévisions", "Gains", "Détail article", "Matières", "Rattachement"]
PAGES.sort(key=lambda p: ORDRE.index(p[0]))
ICONES = ["➜", "◉", "⚑", "◎", "✎", "€", "▦", "◷", "✓", "▤", "≋", "⇄"]
COURT = {"Parcours négociation": "Parcours"}  # libellés de navigation raccourcis
# Pages cibles d'extraction (clic droit → Extraire) : champ transmis
EXTRACTION = {"Fiche négociation": ("dim_fournisseur", "nom"), "Détail article": ("dim_article", "designation")}


def section_config(i: int, nom: str, visuels=None) -> tuple[str, str]:
    fond_page = {"background": [{"properties": {"color": {"solid": {"color": lit(FOND)}}, "transparency": lit(0)}}],
                 "outspace": [{"properties": {"color": {"solid": {"color": lit(FOND)}}, "transparency": lit(0)}}]}
    cfg: dict = {"objects": fond_page}
    if visuels is not None:
        RELATIONS_PAGE.clear()
        sans_interaction([visuel(i, j, d) for j, d in enumerate(barre_navigation(i) + [recaler(x) for x in visuels])])
        if RELATIONS_PAGE:
            cfg["relationships"] = list(RELATIONS_PAGE)
    filtres = []
    if nom in EXTRACTION:
        t, c = EXTRACTION[nom]
        champ = {"Column": {"Expression": {"SourceRef": {"Entity": t}}, "Property": c}}
        filtres.append({"name": f"Extraction{i}", "expression": champ, "type": "Categorical", "howCreated": 5})
        cfg["pageBinding"] = {"name": f"Liaison{i}", "type": "Drillthrough",
                              "parameters": [{"name": f"Param{i}", "boundFilter": f"Extraction{i}", "fieldExpr": champ}]}
    return json.dumps(cfg, ensure_ascii=False), json.dumps(filtres, ensure_ascii=False)

THEME = {
    "name": "Buyvera",
    "dataColors": SERIES,
    "background": "#FFFFFF", "foreground": TEXTE, "tableAccent": TEAL,
    "good": "#0F5C4A", "neutral": "#D9A441", "bad": "#C9781C",
    "textClasses": {
        "title": {"fontFace": "Segoe UI Semibold", "fontSize": 11, "color": TEXTE},
        "label": {"fontFace": "Segoe UI", "fontSize": 9, "color": TEXTE_2},
        "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 26, "color": TEXTE},
        "header": {"fontFace": "Segoe UI Semibold", "fontSize": 10, "color": TEXTE_2},
    },
    "visualStyles": {
        "*": {"*": {
            "background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}}, "transparency": 0}],
            "border": [{"show": True, "color": {"solid": {"color": BORD}}, "radius": 12}],
            "dropShadow": [{"show": False}],
            "padding": [{"top": 12, "bottom": 12, "left": 16, "right": 16}],
            "title": [{"show": True, "fontColor": {"solid": {"color": TEXTE}}, "fontSize": 12,
                       "fontFamily": "Segoe UI Semibold"}],
            "categoryAxis": [{"labelColor": {"solid": {"color": TEXTE_2}}, "gridlineShow": False,
                              "innerPadding": 35}],
            "valueAxis": [{"labelColor": {"solid": {"color": MUET}}, "gridlineColor": {"solid": {"color": GRILLE}},
                           "gridlineStyle": "solid", "gridlineThickness": 1}],
            "labels": [{"color": {"solid": {"color": TEXTE_2}}, "fontSize": 9, "labelPosition": "OutsideEnd"}],
            "legend": [{"labelColor": {"solid": {"color": TEXTE_2}}, "position": "Top"}],
        }},
        "page": {"*": {
            "background": [{"color": {"solid": {"color": FOND}}, "transparency": 0}],
            "outspace": [{"color": {"solid": {"color": FOND}}, "transparency": 0}],
        }},
        **{t: {"*": {"background": [{"show": False}], "border": [{"show": False}],
                     "dropShadow": [{"show": False}], "title": [{"show": False}],
                     "padding": [{"top": 0, "bottom": 0, "left": 0, "right": 0}]}}
           for t in ("textbox", "actionButton", "shape")},
        "tableEx": {"*": {"grid": [{"gridHorizontal": True, "gridHorizontalColor": {"solid": {"color": BORD}},
                                     "rowPadding": 3}],
                          "columnHeaders": [{"fontColor": {"solid": {"color": "#FFFFFF"}},
                                             "backColor": {"solid": {"color": NAVY_2}}}],
                          "values": [{"backColorSecondary": {"solid": {"color": "#FAF8F3"}}}]}},
        "slicer": {"*": {"header": [{"fontColor": {"solid": {"color": TEXTE_2}}, "textSize": 9}],
                         "items": [{"fontColor": {"solid": {"color": TEXTE}}}]}},
        "card": {"*": {"labels": [{"color": {"solid": {"color": TEXTE}}, "fontSize": 24, "fontFamily": "Segoe UI Semibold"}],
                       "categoryLabels": [{"show": False}],
                       "title": [{"fontColor": {"solid": {"color": TEXTE_2}}, "fontSize": 10, "fontFamily": "Segoe UI"}]}},
        "lineChart": {"*": {"lineStyles": [{"strokeWidth": 2}]}},
    },
}


NAV = ["Parcours négociation", "Synthèse campagne", "Alertes matières", "Fournisseurs", "Prix & volumes",
       "Prix payés", "Prévisions", "Fiche négociation", "Gains", "Matières", "Rattachement"]  # Détail article : par extraction uniquement
NAV_COURT = {"Parcours négociation": "Parcours", "Synthèse campagne": "Synthèse", "Alertes matières": "Alertes",
             "Fournisseurs": "Fournisseurs", "Prix & volumes": "Prix & vol.", "Prix payés": "Prix payés", "Gains": "Gains", "Prévisions": "Prévisions", "Fiche négociation": "Négocier",
             "Matières": "Matières", "Rattachement": "Réfs"}


def barre_navigation(page: int) -> list[dict]:
    """Bandeau encre en haut : logo buyvera, un onglet par page du parcours (onglet actif en vert marque)."""
    nom_page = PAGES[page][0]
    l = [v("shape", 0, 0, 1280, HAUT, objets={"couleur": NAVY}),
         v("textbox", 20, 10, 170, 40, texte=("Buyvera BI", ""), objets={"blanc": True, "logo": True})]
    # largeur de chaque onglet proportionnelle à son libellé
    poids = [len(NAV_COURT[n]) + 4 for n in NAV]
    unite, x = (1280 - 200 - 16) / sum(poids), 200.0
    for nom, pw in zip(NAV, poids):
        l.append(v("nav", round(x), 10, round(pw * unite - 4), 36,
                   objets={"cible": nom, "texte": NAV_COURT[nom], "actif": nom == nom_page, "onglet": True}))
        x += pw * unite
    return l


def recaler(d: dict) -> dict:
    """Décale un visuel conçu sur 0-720 px sous le bandeau de navigation."""
    return {**d, "y": d["y"] + HAUT}


def desc(texte: str, indent: str) -> list[str]:
    return [f"{indent}/// {texte}"]


def expr_lignes(expr: str, indent: str) -> list[str]:
    return [f"{indent}{l}" if l else "" for l in expr.splitlines()]


def colonne(table: str, nom: str, typ: str, d: str, opt: dict, expr: str | None = None) -> list[str]:
    tete = f"{T}column {q(nom)}" + (f" = {expr}" if expr else "")
    l = desc(d, T) + [tete, f"{T}{T}dataType: {typ}"]
    if opt.get("fmt"):
        l.append(f"{T}{T}formatString: {opt['fmt']}")
    if opt.get("key"):
        l.append(f"{T}{T}isKey")
    if opt.get("hidden"):
        l.append(f"{T}{T}isHidden")
    l.append(f"{T}{T}lineageTag: {tag(table, nom)}")
    l.append(f"{T}{T}summarizeBy: {opt.get('summ', 'none')}")
    if not expr:
        l.append(f"{T}{T}sourceColumn: {nom}")
    if opt.get("sort"):
        l.append(f"{T}{T}sortByColumn: {opt['sort']}")
    if typ == DT:
        l += ["", f"{T}{T}annotation UnderlyingDateTimeDataType = Date"]
    l += ["", f"{T}{T}annotation SummarizationSetBy = User", ""]
    return l


def partition_csv(table: str, cols: list, nettoyer: list[str]) -> list[str]:
    types = ", ".join(f'{{"{c[0]}", {M_TYPES[c[1]]}}}' for c in cols)
    m = [
        "let",
        f'    Source = Csv.Document ( File.Contents ( DossierDonnees & "{table}.csv" ), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv] ),',
        "    Entetes = Table.PromoteHeaders ( Source, [PromoteAllScalars = true] ),",
    ]
    etape = "Entetes"
    if nettoyer:
        liste = ", ".join(f'"{c}"' for c in nettoyer)
        m.append(f"    Vides = Table.ReplaceValue ( Entetes, \"\", null, Replacer.ReplaceValue, {{{liste}}} ),")
        etape = "Vides"
    m += [f'    Types = Table.TransformColumnTypes ( {etape}, {{{types}}}, "en-US" )', "in", "    Types"]
    return [f"{T}partition {table} = m", f"{T}{T}mode: import", f"{T}{T}source =",
            *expr_lignes("\n".join(m), T * 4), ""]


def table_tmdl(nom: str, spec: dict) -> str:
    l = desc(spec["desc"], "") + [f"table {nom}", f"{T}lineageTag: {tag(nom)}"]
    if spec.get("date_table"):
        l.append(f"{T}dataCategory: Time")
    l.append("")
    for c in spec["cols"]:
        l += colonne(nom, *c)
    for nom_c, typ, d, expr, opt in spec.get("calc_cols", []):
        l += colonne(nom, nom_c, typ, d, opt, expr=expr)
    l += partition_csv(nom, spec["cols"], spec.get("clean", []))
    l += [f"{T}annotation PBI_ResultType = Table", ""]
    return "\n".join(l)


def table_parametre(nom: str, col: str, valeurs: list[int], d: str) -> str:
    lignes = ", ".join(f"{{ {v} }}" for v in valeurs)
    return "\n".join(desc(d, "") + [
        f"table {nom}", f"{T}lineageTag: {tag(nom)}", "",
        f"{T}/// {d}",
        f"{T}column {col}", f"{T}{T}dataType: int64", f"{T}{T}formatString: 0",
        f"{T}{T}lineageTag: {tag(nom, col)}", f"{T}{T}summarizeBy: none",
        f"{T}{T}isNameInferred", f"{T}{T}sourceColumn: [{col}]", "",
        f"{T}{T}annotation SummarizationSetBy = User", "",
        f"{T}partition {nom} = calculated", f"{T}{T}mode: import",
        f'{T}{T}source = DATATABLE ( "{col}", INTEGER, {{ {lignes} }} )', "",
        f"{T}annotation PBI_Id = {tag(nom, 'id').replace('-', '')}", "",
    ])


def table_mesures() -> str:
    l = desc("Table des mesures (aucune donnée).", "") + ["table _Mesures", f"{T}lineageTag: {tag('_Mesures')}", ""]
    for nom, dossier, fmt, d, expr in MESURES:
        l += desc(d, T)
        if "\n" in expr:
            l += [f"{T}measure {q(nom)} = ```", *expr_lignes(expr, T * 3), f"{T}{T}{T}```"]
        else:
            l.append(f"{T}measure {q(nom)} = {expr}")
        if fmt:
            l.append(f"{T}{T}formatString: {fmt}")
        l += [f"{T}{T}displayFolder: {dossier}", f"{T}{T}lineageTag: {tag('_Mesures', nom)}", ""]
    l += [f"{T}column masque", f"{T}{T}dataType: int64", f"{T}{T}isHidden", f"{T}{T}formatString: 0",
          f"{T}{T}lineageTag: {tag('_Mesures', 'masque')}", f"{T}{T}summarizeBy: none",
          f"{T}{T}isNameInferred", f"{T}{T}sourceColumn: [masque]", "",
          f"{T}{T}annotation SummarizationSetBy = User", "",
          f"{T}partition _Mesures = calculated", f"{T}{T}mode: import",
          f'{T}{T}source = ROW ( "masque", 0 )', ""]
    return "\n".join(l)


def lit(valeur) -> dict:
    """Littéral de requête Power BI (texte entre apostrophes, booléen, nombre suivi de D/L)."""
    if isinstance(valeur, bool):
        txt = "true" if valeur else "false"
    elif isinstance(valeur, str):
        txt = "'" + valeur.replace("'", "''") + "'"
    else:
        txt = f"{valeur}D"
    return {"expr": {"Literal": {"Value": txt}}}


class Requete:
    """Construit le prototypeQuery d'un visuel (alias de tables, champs sélectionnés)."""

    def __init__(self) -> None:
        self.alias: dict[str, str] = {}

    def source(self, table: str) -> dict:
        if table not in self.alias:
            self.alias[table] = f"t{len(self.alias)}"
        return {"SourceRef": {"Source": self.alias[table]}}

    def expr(self, champ: tuple) -> dict:
        if champ[0] == "m":
            return {"Measure": {"Expression": self.source("_Mesures"), "Property": champ[1]}}
        return {"Column": {"Expression": self.source(champ[1]), "Property": champ[2]}}

    @staticmethod
    def ref(champ: tuple) -> str:
        return f"_Mesures.{champ[1]}" if champ[0] == "m" else f"{champ[1]}.{champ[2]}"

    def frm(self) -> list[dict]:
        return [{"Name": a, "Entity": t, "Type": 0} for t, a in self.alias.items()]


def visuel(page: int, i: int, d: dict) -> dict:
    nom = tag("visuel", str(page), str(i)).replace("-", "")[:20]
    pos = {"x": d["x"], "y": d["y"], "z": i * 1000, "width": d["w"], "height": d["h"]}
    sv: dict = {"visualType": d["typ"], "drillFilterOtherVisuals": True}
    vc: dict = {}
    if d["typ"] == "textbox":
        titre, sous = d["texte"]
        blanc, petit = d["objets"].get("blanc"), d["objets"].get("petit")
        if d["objets"].get("etape"):
            t1, t2 = "15pt", "11pt"
        c1, c2 = ("#EEF2EF", "#9DB0A8") if blanc else ((ACCENT, TEXTE) if d["objets"].get("etape") else (TEXTE, GRIS))
        if not d["objets"].get("etape"):
            t1, t2 = ("10pt", "8pt") if petit else (("16pt", "9pt") if blanc else ("18pt", "10pt"))
        style = {"fontWeight": "bold", "fontSize": t1, "color": c1, "fontFamily": "Segoe UI Semibold"}
        runs = ([{"value": "Buy", "textStyle": style}, {"value": "vera", "textStyle": {**style, "color": MENTHE}},
                 {"value": " BI", "textStyle": style}] if titre == "Buyvera BI"
                else [{"value": titre, "textStyle": style}])
        paras = [{"textRuns": runs}]
        if sous:
            paras.append({"textRuns": [{"value": sous, "textStyle": {"fontSize": t2, "color": c2}}]})
        sv["objects"] = {"general": [{"properties": {"paragraphs": paras}}]}
    elif d["typ"] == "shape":
        sv["objects"] = {
            "fill": [{"properties": {"show": lit(True)}},
                     {"properties": {"fillColor": {"solid": {"color": lit(d["objets"]["couleur"])}},
                                     "transparency": lit(0)}, "selector": {"id": "default"}}],
            "outline": [{"properties": {"show": lit(d["objets"]["couleur"] == "#FFFFFF")}},
                        {"properties": {"lineColor": {"solid": {"color": lit(BORD)}}, "weight": lit(1)},
                         "selector": {"id": "default"}}],
            "shape": [{"properties": {"tileShape": lit("rectangleRounded" if d["objets"]["couleur"] == "#FFFFFF" else "rectangle"),
                                      "roundEdge": lit(12)}}],
            "line": [{"properties": {"weight": lit(0), "lineColor": {"solid": {"color": lit(d["objets"]["couleur"])}}}}]}
    elif d["typ"] == "nav":
        sv["visualType"] = "actionButton"
        o = d["objets"]
        fond, texte = (ACCENT, "#FFFFFF") if o["actif"] else (NAVY, "#9DB0A8")
        if o.get("onglet") and o["actif"]:
            fond, texte = (NAVY_2, MENTHE)
        def etat(sel: str, props: dict) -> dict:
            return {"properties": props, "selector": {"id": sel}}
        sv["objects"] = {
            "icon": [{"properties": {"show": lit(False)}}, etat("default", {"shapeType": lit("blank")})],
            "text": [{"properties": {"show": lit(True)}},
                     etat("default", {"text": lit(o["texte"]), "fontColor": {"solid": {"color": lit(texte)}},
                                      "fontSize": lit(10 if o.get("onglet") else 11), "fontFamily": lit("Segoe UI Semibold"),
                                      "horizontalAlignment": lit("center" if o.get("onglet") or o.get("centre") else "left"),
                                      "leftMargin": lit(14)}),
                     etat("hover", {"text": lit(o["texte"]), "fontColor": {"solid": {"color": lit("#FFFFFF")}}})],
            "fill": [{"properties": {"show": lit(True)}},
                     etat("default", {"fillColor": {"solid": {"color": lit(fond)}}, "transparency": lit(0)}),
                     etat("hover", {"fillColor": {"solid": {"color": lit(ACCENT if o["actif"] else NAVY_2)}},
                                    "transparency": lit(0)})],
            "outline": [{"properties": {"show": lit(False)}}],
            "shape": [{"properties": {"tileShape": lit("rectangleRounded"), "roundEdge": lit(8)}}],
        }
        cible = o["cible"]
        if isinstance(cible, str):
            cible = [n for n, _ in PAGES].index(cible)
        lien = ({"show": lit(True), "type": lit("Back")} if o.get("retour") else
                {"show": lit(True), "type": lit("PageNavigation"), "navigationSection": lit(f"ReportSection{cible:02d}")})
        vc["visualLink"] = [{"properties": lien}]
        vc["title"] = [{"properties": {"show": lit(False)}}]
    else:
        q = Requete()
        select, proj = [], {}
        for role, champs in d["roles"].items():
            proj[role] = []
            for c in champs:
                ref = q.ref(c)
                if ref not in [s["Name"] for s in select]:
                    select.append({**q.expr(c), "Name": ref, "NativeReferenceName": c[-1]})
                proj[role].append({"queryRef": ref})
        proto = {"Version": 2, "From": None, "Select": select}
        if d["ordre"]:
            proto["OrderBy"] = [{"Direction": d["ordre"][1], "Expression": q.expr(d["ordre"][0])}]
        proto["From"] = q.frm()
        sv["projections"] = proj
        sv["prototypeQuery"] = proto
        objets: dict = {}
        if d["objets"].get("labels"):
            objets["labels"] = [{"properties": {"show": lit(True)}}]
        if d["objets"].get("dropdown"):
            objets["data"] = [{"properties": {"mode": lit("Dropdown")}}]
            objets["selection"] = [{"properties": {"strictSingleSelect": lit(bool(d["objets"].get("unique")))}}]
        if d["objets"].get("sync"):
            sv["syncGroup"] = {"groupName": d["objets"]["sync"], "fieldChanges": True, "filterChanges": True}
        if d["objets"].get("couleur_barres"):
            mes = {"expr": {"Measure": {"Expression": {"SourceRef": {"Entity": "_Mesures"}},
                                        "Property": d["objets"]["couleur_barres"]}}}
            objets["dataPoint"] = [{"properties": {"fill": {"solid": {"color": mes}}},
                                    "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}]
        if d["objets"].get("couleur_texte"):
            col, coul = d["objets"]["couleur_texte"]
            mes = {"expr": {"Measure": {"Expression": {"SourceRef": {"Entity": "_Mesures"}}, "Property": coul}}}
            objets["values"] = [{"properties": {"fontColor": {"solid": {"color": mes}}},
                                 "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                                              "metadata": q.ref(col)}}]
        if d["objets"].get("largeurs"):
            objets["columnWidth"] = [{"properties": {"value": lit(float(px))}, "selector": {"metadata": q.ref(c)}}
                                     for c, px in d["objets"]["largeurs"].items()]
        if d["objets"].get("wrap"):
            objets["wordWrap"] = [{"properties": {"show": lit(True)}}]
        if d["objets"].get("catlabels"):
            objets["categoryLabels"] = [{"properties": {"show": lit(True)}}]
        if d["objets"].get("continu"):
            objets["categoryAxis"] = [{"properties": {"axisType": lit("Scalar")}}]
        if d["objets"].get("entete"):
            objets["header"] = [{"properties": {"text": lit(d["objets"]["entete"]), "show": lit(True)}}]
        if d["typ"] == "card":
            objets["categoryLabels"] = [{"properties": {"show": lit(False)}}]
            lab = {}
            if d["objets"].get("police"):
                lab["fontSize"] = lit(d["objets"]["police"])
            if d["objets"].get("valeur"):
                lab["color"] = {"solid": {"color": lit(d["objets"]["valeur"])}}
            if lab:
                objets["labels"] = [{"properties": lab}]
            if d["objets"].get("fond"):
                vc["background"] = [{"properties": {"show": lit(True), "color": {"solid": {"color": lit(d["objets"]["fond"])}},
                                                     "transparency": lit(0)}}]
            if d["objets"].get("sans_bord") or d["objets"].get("fond"):
                vc["border"] = [{"properties": {"show": lit(False)}}]
            if d["objets"].get("titre_c"):
                vc.setdefault("title", [{"properties": {}}])
                vc["title"][0]["properties"]["fontColor"] = {"solid": {"color": lit(d["objets"]["titre_c"])}}
        if objets:
            sv["objects"] = objets
        if d["objets"].get("noms"):
            sv["columnProperties"] = {q.ref(c): {"displayName": n} for c, n in d["objets"]["noms"].items()}
        if d["titre"]:
            ancien = vc.get("title", [{"properties": {}}])[0]["properties"]
            vc["title"] = [{"properties": {**ancien, "show": lit(True), "text": lit(d["titre"])}}]
    if vc:
        sv["vcObjects"] = vc

    filtres = []
    for j, (champ, valeurs) in enumerate(d["filtres"]):
        fq = Requete()
        e = fq.expr(champ)
        filtres.append({
            "name": f"Filtre{page}{i}{j}",
            "expression": {"Column": {"Expression": {"SourceRef": {"Entity": champ[1]}}, "Property": champ[2]}},
            "filter": {"Version": 2, "From": fq.frm(), "Where": [{"Condition": {"In": {
                "Expressions": [e], "Values": [[{"Literal": {"Value": f"{x}L"} if isinstance(x, int) and not isinstance(x, bool)
                                              else lit(x)["expr"]["Literal"]}] for x in valeurs]}}}]},
            "type": "Categorical", "howCreated": 1})
    config = {"name": nom, "layouts": [{"id": 0, "position": pos}], "singleVisual": sv}
    return {"x": d["x"], "y": d["y"], "z": i * 1000, "width": d["w"], "height": d["h"],
            "config": json.dumps(config, ensure_ascii=False), "filters": json.dumps(filtres, ensure_ascii=False)}


# Visuels qui ne doivent pas être filtrés par un segment de la même page : (en-tête du segment, début du titre cible)
SANS_INTERACTION = [("Matière", "Variation matière attendue")]


def sans_interaction(conteneurs: list[dict]) -> list[dict]:
    """Coupe l'interaction segment → visuel listée dans SANS_INTERACTION (stockée dans la config du segment)."""
    cfgs = [json.loads(c["config"]) for c in conteneurs]
    def titre(c):
        t = c["singleVisual"].get("vcObjects", {}).get("title", [{}])[0].get("properties", {}).get("text")
        return t["expr"]["Literal"]["Value"].strip("'") if t else ""
    def entete(c):
        h = c["singleVisual"].get("objects", {}).get("header", [{}])[0].get("properties", {}).get("text")
        return h["expr"]["Literal"]["Value"].strip("'") if h else ""
    for src, cible in SANS_INTERACTION:
        s = next((c for c in cfgs if c["singleVisual"]["visualType"] == "slicer" and entete(c) == src), None)
        t = next((c for c in cfgs if titre(c).startswith(cible)), None)
        if s and t:
            RELATIONS_PAGE.append({"source": s["name"], "target": t["name"], "type": 3})
    return conteneurs


RELATIONS_PAGE: list[dict] = []


def ecrire(chemin: Path, texte: str) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte if texte.endswith("\n") else texte + "\n", encoding="utf-8", newline="\n")


def ecrire_json(chemin: Path, data: dict) -> None:
    ecrire(chemin, json.dumps(data, ensure_ascii=False, indent=2))


def construire(dossier_donnees: str) -> None:
    if (SM / "definition").exists():
        shutil.rmtree(SM / "definition")
    d = SM / "definition"
    toutes = list(TABLES) + list(PARAMETRES) + ["_Mesures"]

    ecrire(d / "database.tmdl", f"database\n{T}compatibilityLevel: 1567\n")
    ecrire(d / "model.tmdl", "\n".join([
        "model Model",
        f"{T}culture: fr-FR",
        f"{T}defaultPowerBIDataSourceVersion: powerBI_V3",
        f"{T}discourageImplicitMeasures",
        f"{T}sourceQueryCulture: fr-FR",
        f"{T}dataAccessOptions",
        f"{T}{T}legacyRedirects",
        f"{T}{T}returnErrorValuesAsNull",
        "",
        f"annotation PBI_QueryOrder = {json.dumps(['DossierDonnees'] + list(TABLES))}",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
        "annotation PBIDesktopVersion = 2.149.1429.0 (25.11)",
        "",
        *[f"ref table {q(t)}" for t in toutes],
        "",
        *[f"ref role {r}" for r in ROLES],
        "",
        "ref cultureInfo fr-FR",
    ]))
    ecrire(d / "cultures" / "fr-FR.tmdl", "cultureInfo fr-FR\n")
    ecrire(d / "expressions.tmdl", "\n".join([
        "/// Dossier des CSV du modèle (data/processed). À adapter si le projet est déplacé.",
        f'expression DossierDonnees = "{dossier_donnees}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]',
        f"{T}lineageTag: {tag('DossierDonnees')}",
        "",
        f"{T}annotation PBI_ResultType = Text",
        "",
        f"{T}annotation PBI_NavigationStepName = Navigation",
    ]))

    rel = []
    for tf, cf, tu, cu in RELATIONS:
        rel += [f"relationship {tag('rel', tf, cf, tu)}", f"{T}fromColumn: {tf}.{cf}", f"{T}toColumn: {tu}.{cu}", ""]
    ecrire(d / "relationships.tmdl", "\n".join(rel))

    for nom, spec in TABLES.items():
        ecrire(d / "tables" / f"{nom}.tmdl", table_tmdl(nom, spec))
    for nom, (col, valeurs, _defaut, txt) in PARAMETRES.items():
        ecrire(d / "tables" / f"{nom}.tmdl", table_parametre(nom, col, valeurs, txt))
    ecrire(d / "tables" / "_Mesures.tmdl", table_mesures())

    for role, (txt, filtres) in ROLES.items():
        l = [f"/// {txt}", f"role {role}", f"{T}modelPermission: read", ""]
        for t, f in filtres.items():
            l += [f"{T}tablePermission {t} = {f}", ""]
        ecrire(d / "roles" / f"{role}.tmdl", "\n".join(l))

    ecrire_json(SM / "definition.pbism", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.0", "settings": {}})
    ecrire_json(SM / ".platform", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": NOM},
        "config": {"version": "2.0", "logicalId": tag("logical", "sm")}})

    # Rapport : format report.json
    sections = [{
        "config": section_config(i, p, visuels)[0], "displayName": p, "displayOption": 1, "filters": section_config(i, p)[1],
        **({"visibility": 1} if p == "Détail article" else {}),
        "height": 720.0 + HAUT, "name": f"ReportSection{i:02d}", "ordinal": i,
        "visualContainers": [visuel(i, j, d) for j, d in
                             enumerate(barre_navigation(i) + [recaler(x) for x in visuels])],
        "width": 1280.0} for i, (p, visuels) in enumerate(PAGES)]
    ecrire_json(RPT / "StaticResources" / "RegisteredResources" / "BuyveraTheme.json", THEME)
    theme = {"customTheme": {"name": "BuyveraTheme.json", "version": "5.59", "type": 1}}
    config = {"version": "5.59", "themeCollection": theme, "activeSectionIndex": 0,
              "defaultDrillFilterOtherVisuals": True, "linguisticSchemaSyncVersion": 0,
              "settings": {"useNewFilterPaneExperience": True, "allowChangeFilterTypes": True,
                           "useStylableVisualContainerHeader": True, "exportDataMode": 1}, "objects": {}}
    ecrire_json(RPT / "report.json", {"config": json.dumps(config), "layoutOptimization": 0,
                                      "resourcePackages": [{"resourcePackage": {
                                          "disabled": False, "name": "RegisteredResources", "type": 1,
                                          "items": [{"name": "BuyveraTheme.json", "path": "BuyveraTheme.json",
                                                     "type": 201}]}}],
                                      "sections": sections})
    ecrire_json(RPT / "definition.pbir", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/1.0.0/schema.json",
        "version": "1.0",
        "datasetReference": {"byPath": {"path": f"../{NOM}.SemanticModel"}, "byConnection": None}})
    ecrire_json(RPT / ".platform", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": NOM},
        "config": {"version": "2.0", "logicalId": tag("logical", "rpt")}})
    ecrire_json(PBIP / f"{NOM}.pbip", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": f"{NOM}.Report"}}],
        "settings": {"enableAutoRecovery": True}})
    print(f"PBIP écrit dans {PBIP} : {len(toutes)} tables, {len(RELATIONS)} relations, "
          f"{len(MESURES)} mesures, {len(ROLES)} rôles, {len(PAGES)} pages")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dossier-donnees", default=str(RACINE / "data" / "processed") + "\\")
    construire(ap.parse_args().dossier_donnees)
