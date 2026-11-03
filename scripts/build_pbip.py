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
    SWITCH ( TRUE (), ISBLANK ( _e ), "#898781", _e > 3, "#d03b3b", _e > 1, "#ec835a", "#0ca30c" )"""),
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
    IF ( ISBLANK ( _f ), "Choisissez un fournisseur pour générer sa fiche de négociation.",
        _f & " demande " & FORMAT ( _d, "+0.0 %;-0.0 %" ) & " quand les matières n'en justifient que "
            & FORMAT ( _j, "+0.0 %;-0.0 %" ) & " (écart " & FORMAT ( _e, "+0.0;-0.0" ) & " pts). "
            & IF ( _eur > 0, "Montant à renégocier : " & FORMAT ( _eur, "# ##0 €" ) & ". ", "Hausse conforme aux matières. " )
            & IF ( NOT ISBLANK ( _lev ), "Levier : " & _lev & " sur la période. ", "" )
            & IF ( _cli > 0, "Effet cliquet sur " & _cli & " campagne(s) : les baisses matières n'ont pas été répercutées.", "" ) )"""),

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
    SWITCH ( TRUE (), ISBLANK ( _v ), BLANK (), _v > 0.05, "▲ Hausse : à anticiper", _v < -0.05, "▼ Baisse : convoquer le commercial", "● Stable" )"""),
    ("Couleur alerte", "7. Alertes", "", "Couleur du signal matière (rouge = hausse, vert = baisse, gris = stable).",
     """VAR _v = [Variation 3 mois %]
RETURN
    SWITCH ( TRUE (), ISBLANK ( _v ), "#898781", _v > 0.05, "#d03b3b", _v < -0.05, "#0ca30c", "#898781" )"""),
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
     "Action recommandée selon le plafond justifié de la prochaine campagne : baisse → convoquer le commercial du fournisseur, hausse > 2 % → préparer la défense, sinon suivi.",
     """VAR _p = [Plafond justifié prochaine campagne %]
RETURN
    SWITCH ( TRUE (), ISBLANK ( _p ), BLANK (),
        _p < 0, "▼ Convoquer le commercial : baisse à obtenir",
        _p > 0.02, "▲ Préparer la défense : hausse à cadrer",
        "● Suivi : hausse limitée" )"""),
    ("Couleur action", "7. Alertes", "", "Vert = baisse à obtenir, rouge = hausse à cadrer, gris = suivi.",
     """VAR _p = [Plafond justifié prochaine campagne %]
RETURN
    SWITCH ( TRUE (), ISBLANK ( _p ), "#898781", _p < 0, "#0ca30c", _p > 0.02, "#d03b3b", "#898781" )"""),
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
     """VAR _f = SELECTEDVALUE ( dim_fournisseur[nom], "l'ensemble des fournisseurs" )
VAR _p = [Plafond justifié prochaine campagne %]
RETURN
    "Campagne " & [Prochaine campagne] & " : les matières justifient déjà " & FORMAT ( _p, "+0.0 %;-0.0 %" )
        & " pour " & _f & ". Au-delà, la demande est à contester."
"""),

    ("Dernier indice chargé", "2. Matières", "", "Libellé du dernier mois d'indice INSEE disponible (fraîcheur).",
     """VAR _d = CALCULATE ( MAX ( fact_indice[date] ), REMOVEFILTERS ( fact_indice ), REMOVEFILTERS ( dim_date ) )
RETURN
    "Indices INSEE à fin " & FORMAT ( _d, "mmmm yyyy" )"""),
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


def m(nom: str) -> tuple:
    return ("m", nom)


def v(typ, x, y, w, h, roles=None, titre=None, ordre=None, objets=None, filtres=None, texte=None):
    return dict(typ=typ, x=x, y=y, w=w, h=h, roles=roles or {}, titre=titre, ordre=ordre,
                objets=objets or {}, filtres=filtres or [], texte=texte)


def entete(titre: str, sous_titre: str) -> list[dict]:
    return [v("textbox", 20, 6, 880, 72, texte=(titre, sous_titre)),
            v("card", 920, 14, 340, 48, {"Values": [m("Dernier indice chargé")]}, objets={"police": 11})]


def segment(champ, x, y, w=240, h=62, titre=None, unique=False):
    """Segment déroulant, synchronisé entre toutes les pages (le choix suit l'utilisateur)."""
    nom_sync = champ[-1]
    return v("slicer", x, y, w, h, {"Values": [champ]},
             objets={"dropdown": True, "entete": titre, "unique": unique, "sync": nom_sync})


def bouton(texte, cible, x, y, w=220, h=40):
    return v("nav", x, y, w, h, objets={"cible": cible, "texte": texte, "actif": True})


KPI_CAMPAGNE = [
    v("card", 20 + i * 250, 150, 235, 100, {"Values": [m(n)]}, titre=n)
    for i, n in enumerate(["Hausse demandée %", "Hausse justifiée %", "Écart pts", "€ renégociables", "Valeur N"])
]

PAGES = [
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
          {"Category": [FOURN], "X": [m("Hausse justifiée %")], "Y": [m("Hausse demandée %")]},
          titre="Hausse demandée × hausse justifiée", objets={"catlabels": True}),
        v("tableEx", 600, 150, 660, 550,
          {"Values": [FOURN, m("Statut fournisseur"), m("Hausse demandée %"), m("Hausse justifiée %"), m("Écart pts"),
                      m("€ renégociables"), m("Effet cliquet")]},
          titre="Classement des fournisseurs · cliquez une ligne pour filtrer la page", ordre=(m("€ renégociables"), 2),
          objets={"noms": {FOURN: "Fournisseur", m("Statut fournisseur"): "Statut", m("Hausse demandée %"): "Demandée",
                           m("Hausse justifiée %"): "Justifiée", m("Écart pts"): "Écart (pts)",
                           m("€ renégociables"): "€ renégociables", m("Effet cliquet"): "Cliquet"},
                  "couleur_texte": (m("Statut fournisseur"), "Couleur écart")}),
        segment(FOURN, 540, 80, w=260, titre="Fournisseur"),
        bouton("Ouvrir la fiche négociation  →", 6, 1020, 92, w=240),
    ]),
    ("Détail article", entete(
        "Détail article",
        "Choisir un article : composition matière, indices de ses matières et historique de prix sur 4 campagnes.") + [
        segment(FOURN, 20, 80, w=240, titre="Fournisseur"),
        segment(("c", "dim_article", "designation"), 280, 80, w=420, titre="Article"),
        segment(CAMPAGNE, 720, 80, titre="Campagne (N+1)"),
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
                      m("Action fournisseur")]},
          titre="Plan d'action fournisseurs pour la prochaine campagne",
          ordre=(m("Plafond justifié prochaine campagne %"), 1),
          objets={"noms": {FOURN: "Fournisseur", m("Plafond justifié prochaine campagne %"): "Plafond justifié",
                           m("Impact € prochaine campagne"): "Impact €", m("Action fournisseur"): "Action"},
                  "couleur_texte": (m("Action fournisseur"), "Couleur action")}),
        v("tableEx", 680, 155, 580, 545,
          {"Values": [("c", "dim_article", "designation"), m("Impact € prochaine campagne"), m("Volume annuel"), FOURN]},
          titre="Articles exposés : à partager avec les appros et les commerciaux",
          ordre=(m("Impact € prochaine campagne"), 2),
          objets={"noms": {("c", "dim_article", "designation"): "Article", FOURN: "Fournisseur",
                           ("c", "dim_famille", "libelle"): "Famille", m("Volume annuel"): "Volume / an",
                           m("Impact € prochaine campagne"): "Impact €"}}),
    ]),
    ("Fiche négociation", entete(
        "Fiche négociation",
        "Tout pour préparer le rendez-vous : chiffres, argument matière, historique et contre-proposition chiffrée.") + [
        segment(FOURN, 20, 80, w=300, titre="Fournisseur", unique=True),
        segment(CAMPAGNE, 340, 80, titre="Campagne (N+1)"),
        segment(("c", "param_hausse", "hausse_acceptee"), 600, 80, w=260, titre="Simulateur : hausse acceptée (%)"),
        v("card", 20, 150, 240, 96, {"Values": [m("Statut fournisseur")]}, titre="Statut campagne", objets={"police": 14}),
        v("card", 270, 150, 240, 96, {"Values": [m("Hausse demandée %")]}, titre="Hausse demandée"),
        v("card", 520, 150, 240, 96, {"Values": [m("Hausse justifiée %")]}, titre="Hausse justifiée"),
        v("card", 770, 150, 240, 96, {"Values": [m("€ renégociables")]}, titre="€ renégociables"),
        v("card", 1020, 150, 240, 96, {"Values": [m("€ économisés (contre-proposition)")]},
          titre="Gain de la contre-proposition"),
        v("multiRowCard", 20, 258, 1240, 70, {"Values": [m("Commentaire négociation")]}, titre="Synthèse pour le rendez-vous"),
        v("card", 20, 336, 820, 52, {"Values": [m("Argument anticipé")]}, titre=None,
          objets={"police": 11, "wrap": True}),
        v("card", 850, 336, 410, 52, {"Values": [m("Action fournisseur")]}, titre=None,
          objets={"police": 11, "wrap": True}),
        v("clusteredColumnChart", 20, 400, 610, 300,
          {"Category": [CAMPAGNE], "Y": [m("Hausse demandée %"), m("Hausse justifiée %")]},
          titre="Historique : demandé vs justifié par campagne", ordre=(CAMPAGNE, 1), objets={"labels": True}),
        v("clusteredBarChart", 650, 400, 610, 300,
          {"Category": [("c", "dim_matiere", "libelle")], "Y": [m("Variation matière article %")]},
          titre="Matières de son panier : variation sur la fenêtre", ordre=(m("Variation matière article %"), 1),
          objets={"labels": True}),
    ]),
]


# --------------------------------------------------------------------------------------
# Écriture TMDL
# --------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------
# Design : thème, barre de navigation latérale, zone de contenu
# --------------------------------------------------------------------------------------
# Palette catégorielle validée (skill dataviz : l'ordre garantit la lisibilité daltonisme)
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
NAVY, NAVY_2, ACCENT, FOND, BORD = "#0F172A", "#1E293B", "#2a78d6", "#F4F5F7", "#E5E7EB"
TEXTE, TEXTE_2, MUET, GRILLE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
TEAL, AMBRE, GRIS = ACCENT, "#eda100", MUET
LARGEUR_NAV = 200
ICONES = ["◉", "◎", "▤", "≋", "⇄", "⚑", "✎"]

THEME = {
    "name": "Buyvera",
    "dataColors": SERIES,
    "background": "#FFFFFF", "foreground": TEXTE, "tableAccent": TEAL,
    "good": "#0ca30c", "neutral": "#fab219", "bad": "#d03b3b",
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
            "dropShadow": [{"show": True, "color": {"solid": {"color": NAVY}}, "transparency": 92,
                            "position": "Outer", "preset": "Bottom", "shadowBlur": 8, "shadowDistance": 1}],
            "padding": [{"top": 8, "bottom": 8, "left": 12, "right": 12}],
            "title": [{"show": True, "fontColor": {"solid": {"color": TEXTE}}, "fontSize": 11,
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
                          "values": [{"backColorSecondary": {"solid": {"color": "#F8FAFC"}}}]}},
        "slicer": {"*": {"header": [{"fontColor": {"solid": {"color": TEXTE_2}}, "textSize": 9}],
                         "items": [{"fontColor": {"solid": {"color": TEXTE}}}]}},
        "card": {"*": {"labels": [{"color": {"solid": {"color": TEXTE}}, "fontSize": 24}],
                       "categoryLabels": [{"show": False}]}},
        "lineChart": {"*": {"lineStyles": [{"strokeWidth": 2}]}},
    },
}


def barre_navigation(page: int) -> list[dict]:
    """Bandeau bleu marine à gauche : logo, un bouton par page (page active en teal), sources."""
    l = [v("shape", 0, 0, LARGEUR_NAV, 720, objets={"couleur": NAVY}),
         v("textbox", 18, 22, 170, 70, texte=("Buyvera BI", "Analyse des hausses tarifaires"),
           objets={"blanc": True})]
    for i, (nom, _) in enumerate(PAGES):
        l.append(v("nav", 12, 120 + i * 52, LARGEUR_NAV - 24, 42,
                   objets={"cible": i, "texte": f"{ICONES[i]}   {nom}", "actif": i == page}))
    l.append(v("textbox", 14, 622, 180, 84,
               texte=("Sources", "Indices INSEE réels · tarifs, volumes et fournisseurs fictifs"),
               objets={"blanc": True, "petit": True}))
    return l


def recaler(d: dict) -> dict:
    """Place un visuel conçu sur 20-1260 px dans la zone de contenu, à droite de la barre."""
    ech = (1280 - LARGEUR_NAV - 30) / 1240
    return {**d, "x": round(LARGEUR_NAV + 10 + (d["x"] - 20) * ech), "w": round(d["w"] * ech)}


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
        c1, c2 = ("#FFFFFF", "#94A3B8") if blanc else (TEXTE, GRIS)
        t1, t2 = ("10pt", "8pt") if petit else (("16pt", "9pt") if blanc else ("20pt", "10pt"))
        sv["objects"] = {"general": [{"properties": {"paragraphs": [
            {"textRuns": [{"value": titre, "textStyle": {"fontWeight": "bold", "fontSize": t1, "color": c1,
                                                         "fontFamily": "Segoe UI Semibold"}}]},
            {"textRuns": [{"value": sous, "textStyle": {"fontSize": t2, "color": c2}}]}]}}]}
    elif d["typ"] == "shape":
        sv["objects"] = {
            "shape": [{"properties": {"tileShape": lit("rectangle")}}],
            "fill": [{"properties": {"show": lit(True)}},
                     {"properties": {"fillColor": {"solid": {"color": lit(d["objets"]["couleur"])}},
                                     "transparency": lit(0)}, "selector": {"id": "default"}}],
            "outline": [{"properties": {"show": lit(False)}}],
            "line": [{"properties": {"weight": lit(0), "lineColor": {"solid": {"color": lit(d["objets"]["couleur"])}}}}]}
    elif d["typ"] == "nav":
        sv["visualType"] = "actionButton"
        o = d["objets"]
        fond, texte = (ACCENT, "#FFFFFF") if o["actif"] else (NAVY, "#CBD5E1")
        def etat(sel: str, props: dict) -> dict:
            return {"properties": props, "selector": {"id": sel}}
        sv["objects"] = {
            "icon": [{"properties": {"show": lit(False)}}, etat("default", {"shapeType": lit("blank")})],
            "text": [{"properties": {"show": lit(True)}},
                     etat("default", {"text": lit(o["texte"]), "fontColor": {"solid": {"color": lit(texte)}},
                                      "fontSize": lit(11), "fontFamily": lit("Segoe UI Semibold"),
                                      "horizontalAlignment": lit("left"), "leftMargin": lit(14)}),
                     etat("hover", {"text": lit(o["texte"]), "fontColor": {"solid": {"color": lit("#FFFFFF")}}})],
            "fill": [{"properties": {"show": lit(True)}},
                     etat("default", {"fillColor": {"solid": {"color": lit(fond)}}, "transparency": lit(0)}),
                     etat("hover", {"fillColor": {"solid": {"color": lit(ACCENT if o["actif"] else NAVY_2)}},
                                    "transparency": lit(0)})],
            "outline": [{"properties": {"show": lit(False)}}],
            "shape": [{"properties": {"tileShape": lit("rectangleRounded"), "roundEdge": lit(8)}}],
        }
        vc["visualLink"] = [{"properties": {"show": lit(True), "type": lit("PageNavigation"),
                                            "navigationSection": lit(f"ReportSection{o['cible']:02d}")}}]
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
            if d["objets"].get("police"):
                objets["labels"] = [{"properties": {"fontSize": lit(d["objets"]["police"])}}]
        if objets:
            sv["objects"] = objets
        if d["objets"].get("noms"):
            sv["columnProperties"] = {q.ref(c): {"displayName": n} for c, n in d["objets"]["noms"].items()}
        if d["titre"]:
            vc["title"] = [{"properties": {"show": lit(True), "text": lit(d["titre"])}}]
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
                "Expressions": [e], "Values": [[{"Literal": lit(x)["expr"]["Literal"]}] for x in valeurs]}}}]},
            "type": "Categorical", "howCreated": 1})
    config = {"name": nom, "layouts": [{"id": 0, "position": pos}], "singleVisual": sv}
    return {"x": d["x"], "y": d["y"], "z": i * 1000, "width": d["w"], "height": d["h"],
            "config": json.dumps(config, ensure_ascii=False), "filters": json.dumps(filtres, ensure_ascii=False)}


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
        "config": json.dumps({"objects": {"background": [{"properties": {"color": {"solid": {"color": lit(FOND)}}, "transparency": lit(0)}}], "outspace": [{"properties": {"color": {"solid": {"color": lit(FOND)}}, "transparency": lit(0)}}]}}), "displayName": p, "displayOption": 1, "filters": "[]",
        "height": 720.0, "name": f"ReportSection{i:02d}", "ordinal": i,
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
