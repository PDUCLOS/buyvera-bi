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
    ("Fenêtre mois", "9. Paramètres", "0", "Période de référence des indices (segment param_fenetre, 6 mois par défaut).",
     "SELECTEDVALUE ( param_fenetre[mois], 6 )"),

    ("Variation matière %", "2. Matières", "0.0%",
     "Moyenne de l'indice sur la fenêtre avant la campagne N+1 / même moyenne avant la campagne N − 1. Une seule matière à la fois.",
     """VAR _cN1 = [Campagne N+1]
VAR _w = [Fenêtre mois]
VAR _fin1 = DATE ( _cN1, 1, 1 )
VAR _fin0 = DATE ( _cN1 - 1, 1, 1 )
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

PAGES = ["Synthèse campagne", "Fournisseurs", "Détail article", "Matières", "Rattachement"]


# --------------------------------------------------------------------------------------
# Écriture TMDL
# --------------------------------------------------------------------------------------
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

    # Rapport : format report.json (pages vides, construites au jour 4)
    sections = [{
        "config": "{}", "displayName": p, "displayOption": 1, "filters": "[]",
        "height": 720.0, "name": f"ReportSection{i:02d}", "ordinal": i,
        "visualContainers": [], "width": 1280.0} for i, p in enumerate(PAGES)]
    config = {"version": "5.59", "themeCollection": {}, "activeSectionIndex": 0,
              "defaultDrillFilterOtherVisuals": True, "linguisticSchemaSyncVersion": 0,
              "settings": {"useNewFilterPaneExperience": True, "allowChangeFilterTypes": True,
                           "useStylableVisualContainerHeader": True, "exportDataMode": 1}, "objects": {}}
    ecrire_json(RPT / "report.json", {"config": json.dumps(config), "layoutOptimization": 0,
                                      "resourcePackages": [], "sections": sections})
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
