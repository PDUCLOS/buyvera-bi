# Dictionnaire de données — Buyvera BI

Généré par `scripts/export_dictionary.py` depuis le modèle TMDL (`pbip/BuyveraBI.SemanticModel`). Ne pas modifier à la main.

23 tables · 116 colonnes · 80 mesures · 22 relations · 2 rôles

## Sommaire

- [_Mesures](#_mesures) — Table des mesures (aucune donnée).
- [bridge_composition](#bridge_composition) — Table pont article × matière : part de chaque matière dans le coût de l'article (somme = 1, non matière comprise).
- [dim_acheteur](#dim_acheteur) — Acheteurs. L'email sert à la sécurité par ligne (RLS).
- [dim_article](#dim_article) — Articles achetés, avec le résultat du rattachement référence tarif / référence ERP.
- [dim_date](#dim_date) — Calendrier journalier 2022-2026. Les faits mensuels pointent sur le 1er du mois.
- [dim_famille](#dim_famille) — Familles de produits, rattachées à un univers et à un acheteur.
- [dim_fournisseur](#dim_fournisseur) — Fournisseurs (fictifs).
- [dim_matiere](#dim_matiere) — Matières premières et part non matière, avec la série INSEE source.
- [fact_achats](#fact_achats) — Quantités achetées par article et par mois (synthétique, Pareto 80/20).
- [fact_hausse_article](#fact_hausse_article) — Précalcul (scripts/precalcul_hausses.py) : hausse par article pour chaque campagne N+1, fenêtre et décalage. Rend les mesures instantanées.
- [fact_impact_matiere](#fact_impact_matiere) — Précalcul : surcoût justifié par chaque matière pour chaque article à la prochaine campagne.
- [fact_indice](#fact_indice) — Indices matières mensuels réels (INSEE BDM) et série d'hypothèse non matière à 2 %/an.
- [fact_indice_fournisseur](#fact_indice_fournisseur) — Précalcul : indice mensuel par fournisseur (base 100 = tarif 2023) du prix fournisseur et du coût matière de son panier. L'écart montre le décalage de répercussion.
- [fact_tarif](#fact_tarif) — Prix brut public par article et par campagne tarifaire (synthétique).
- [ml_anomalies_tarif](#ml_anomalies_tarif) — Machine learning (scripts/ml_predictions.py) : lignes du tarif 2026 isolées par Isolation Forest (hausse atypique pour sa famille).
- [ml_plafond_2027](#ml_plafond_2027) — Machine learning (scripts/ml_predictions.py) : plafond de hausse justifiable 2027 projeté par fournisseur (central et fourchette à 80 %).
- [ml_prevision_indices](#ml_prevision_indices) — Machine learning (scripts/ml_predictions.py) : prévision des indices matières octobre-décembre 2026 (modèle retenu au backtest) et intervalle à 80 %.
- [ml_segments_fournisseurs](#ml_segments_fournisseurs) — Machine learning (scripts/ml_predictions.py) : segment de comportement tarifaire trouvé par KMeans (non supervisé).
- [ml_variation_2027](#ml_variation_2027) — Machine learning (scripts/ml_predictions.py) : variation matière attendue pour la campagne 2027, fenêtre juillet-décembre 2026 complétée par la prévision.
- [param_campagne](#param_campagne) — Campagne N+1 analysée (comparée à la campagne N = N+1 − 1). Table déconnectée pour le segment.
- [param_decalage](#param_decalage) — Décalage d'application : nombre de mois entre l'évolution du cours matière et sa répercussion dans le tarif.
- [param_fenetre](#param_fenetre) — Période de référence de la variation matière, en mois avant chaque campagne.
- [param_hausse](#param_hausse) — Simulateur : hausse que l'acheteur est prêt à accepter (en %), pour chiffrer la contre-proposition.

## Relations

Toutes de plusieurs vers un, filtrage dans un seul sens.

| De (plusieurs) | Vers (un) |
|---|---|
| `fact_tarif.article_id` | `dim_article.article_id` |
| `fact_tarif.date_effet` | `dim_date.date` |
| `fact_achats.article_id` | `dim_article.article_id` |
| `fact_achats.date` | `dim_date.date` |
| `fact_indice.matiere_id` | `dim_matiere.matiere_id` |
| `fact_indice.date` | `dim_date.date` |
| `bridge_composition.article_id` | `dim_article.article_id` |
| `bridge_composition.matiere_id` | `dim_matiere.matiere_id` |
| `dim_article.fournisseur_id` | `dim_fournisseur.fournisseur_id` |
| `dim_article.famille_id` | `dim_famille.famille_id` |
| `dim_famille.acheteur_id` | `dim_acheteur.acheteur_id` |
| `fact_hausse_article.article_id` | `dim_article.article_id` |
| `fact_impact_matiere.article_id` | `dim_article.article_id` |
| `fact_impact_matiere.matiere_id` | `dim_matiere.matiere_id` |
| `fact_indice_fournisseur.fournisseur_id` | `dim_fournisseur.fournisseur_id` |
| `fact_indice_fournisseur.date` | `dim_date.date` |
| `ml_prevision_indices.matiere_id` | `dim_matiere.matiere_id` |
| `ml_prevision_indices.date` | `dim_date.date` |
| `ml_variation_2027.matiere` | `dim_matiere.matiere_id` |
| `ml_plafond_2027.fournisseur_id` | `dim_fournisseur.fournisseur_id` |
| `ml_segments_fournisseurs.fournisseur_id` | `dim_fournisseur.fournisseur_id` |
| `ml_anomalies_tarif.article_id` | `dim_article.article_id` |

## Sécurité par ligne

| Rôle | Description | Filtre |
|---|---|---|
| Acheteur | Acheteur : ne voit que les familles dont il est responsable. | `dim_acheteur` : `dim_acheteur[email] = USERPRINCIPALNAME ()` |
| Direction | Direction : voit tout (aucun filtre). | aucun |

## Mesures

### 1. Hausses

| Mesure | Format | Description |
|---|---|---|
| Valeur N | `#,0 €` | Σ prix N × volume N sur le panier comparable (prix aux deux campagnes, volume N > 0). |
| Hausse demandée % | `0.0%` | Σ (prix N+1 × volume N) / Σ (prix N × volume N) − 1, pondérée par les volumes N. |
| Hausse justifiée % | `0.0%` | Σ (part matière × variation matière), non matière à 2 %/an comprise, pondérée comme la hausse demandée. |
| Écart pts | `+0.0;-0.0;0.0` | Hausse demandée − hausse justifiée, en points de pourcentage. |
| € renégociables | `#,0 €` | Σ par article de MAX(0, hausse demandée − hausse justifiée) × prix N × volume N. |
| Nb articles comparables | `#,0` | Articles du panier comparable N / N+1. |
| Effet cliquet | `0` | Nombre de campagnes où la hausse justifiée est négative alors que la hausse demandée ne l'est pas. |

### 10. Prévisions ML

| Mesure | Format | Description |
|---|---|---|
| Prévision indice | `#,0.0` | Indice prévu par le modèle retenu au backtest. |
| Prévision basse 80 % | `#,0.0` | Borne basse de l'intervalle à 80 %. |
| Prévision haute 80 % | `#,0.0` | Borne haute de l'intervalle à 80 %. |
| Variation 2027 attendue % | `+0.0%;-0.0%;0.0%` | Variation matière attendue pour 2027 (fenêtre juillet-décembre 2026 complétée par la prévision). |
| Fourchette 2027 | `` | Fourchette à 80 % de la variation 2027 attendue. |
| Plafond 2027 projeté % | `+0.0%;-0.0%;0.0%` | Hausse justifiable 2027 projetée, pondérée par prix 2026 × volume 2025. |
| Fourchette plafond 2027 | `` | Fourchette à 80 % du plafond 2027 projeté. |
| Segment ML | `` | Segment de comportement tarifaire du fournisseur (KMeans). |
| Écart moyen 3 campagnes (pts) | `+0.0;-0.0;0.0` | Écart moyen demandé − justifié sur 3 campagnes. |
| Lignes anormales | `#,0` | Lignes du tarif 2026 isolées en hausse excessive. |
| € lignes anormales | `#,0 €` | Écart en euros des lignes isolées en hausse excessive. |
| Demandée (ligne) % | `+0.0%;-0.0%;0.0%` | Hausse demandée de la ligne. |
| Justifiée (ligne) % | `+0.0%;-0.0%;0.0%` | Hausse justifiée de la ligne. |

### 2. Matières

| Mesure | Format | Description |
|---|---|---|
| Variation matière % | `0.0%` | Moyenne de l'indice sur la fenêtre avant la campagne N+1 / même moyenne avant la campagne N − 1. Une seule matière à la fois. |
| Indice moyen | `#,0.0` | Moyenne de l'indice matière sur la période filtrée. |
| Part matière moyenne | `0.0%` | Part moyenne de la matière dans le coût des articles filtrés. |
| Indice (composition) | `#,0.0` | Indice moyen limité aux matières utilisées dans les compositions (exclut le cuivre en €/t). |
| Variation (composition) % | `0.0%` | Variation matière limitée aux matières des compositions (sans la série cuivre en €/t). |
| Dernier indice chargé | `` | Libellé du dernier mois d'indice INSEE disponible (fraîcheur). |

### 3. Achats

| Mesure | Format | Description |
|---|---|---|
| Montant achats | `#,0 €` | Quantités × prix brut du tarif de l'année d'achat. |
| Quantité achetée | `#,0` | Quantités achetées. |
| Nb articles | `#,0` | Nombre d'articles. |
| Quantité N-1 | `#,0` | Quantités de la même période un an plus tôt, coupée au dernier mois d'achat connu (comparaison à date). |
| Montant N-1 | `#,0 €` | Montant des achats de la même période un an plus tôt, à date. |
| Évol. volume % | `+0.0%;-0.0%;0.0%` | Quantités vs même période N-1. |
| Évol. montant % | `+0.0%;-0.0%;0.0%` | Montant des achats vs même période N-1. |
| Effet prix % | `+0.0%;-0.0%;0.0%` | Hausse de prix subie à volumes constants : Σ qté × (prix N − prix N-1) / Σ qté × prix N-1, sur les articles achetés les deux années. |
| Surcoût prix € | `#,0 €` | Euros payés en plus par la seule hausse de prix, à volumes constants. |

### 4. Rattachement

| Mesure | Format | Description |
|---|---|---|
| % rattachés auto | `0.0%` | Articles au statut Automatique / total des articles. |
| % proposés | `0.0%` | Articles au statut Proposé (à valider) / total. |
| % non rattachés | `0.0%` | Articles au statut Non rattaché / total. |
| Objectif rattachement | `0%` | Objectif de rattachement automatique (règle Buyvera). |

### 5. Détail article

| Mesure | Format | Description |
|---|---|---|
| Indice matières article | `#,0.0` | Indice moyen des seules matières présentes dans la composition des articles filtrés. |
| Variation matière article % | `0.0%` | Variation matière affichée seulement pour les matières de la composition des articles filtrés. |
| Prix brut | `#,0.00 €` | Prix brut public, affiché quand un seul article est sélectionné. |

### 6. Négociation

| Mesure | Format | Description |
|---|---|---|
| Hausse acceptée % | `0.0%` | Hausse acceptée par l'acheteur (segment du simulateur, 2 % par défaut). |
| € économisés (contre-proposition) | `#,0 €` | Σ par article de MAX(0, hausse demandée − hausse acceptée) × prix N × volume N : gain si le fournisseur accepte la contre-proposition. |
| Couleur écart | `` | Couleur de statut de l'écart (rouge > 3 pts, orange > 1 pt, vert sinon) pour la mise en forme conditionnelle. |
| Statut fournisseur | `` | Statut lisible (icône + libellé) : À renégocier, À surveiller ou Conforme. |
| Levier matière | `` | Matière du panier du fournisseur qui a le plus baissé sur la fenêtre : argument de négociation. |
| Commentaire négociation | `` | Phrase de synthèse générée pour le fournisseur sélectionné (support de négociation). |
| Couleur variation | `` | Vert marque si la matière baisse (levier acheteur), ambre signal si elle monte. |
| Résumé signaux | `` | Nombre de matières en hausse et en baisse sur 3 mois. |
| Résumé cible | `` | Nombre de fournisseurs à renégocier, en clair. |
| Résumé 2027 | `` | Hausse déjà justifiée pour la prochaine campagne, en clair. |
| Nb fournisseurs à renégocier | `0` | Fournisseurs dont l'écart dépasse 3 points. |

### 7. Alertes

| Mesure | Format | Description |
|---|---|---|
| Dernier indice | `#,0.0` | Valeur de l'indice au dernier mois disponible. |
| Variation 3 mois % | `+0.0%;-0.0%;0.0%` | Dernier indice / indice 3 mois plus tôt − 1 (signal court terme). |
| Variation 12 mois % | `+0.0%;-0.0%;0.0%` | Dernier indice / indice 12 mois plus tôt − 1 (tendance). |
| Alerte matière | `` | Signal sur 3 mois : ▲ hausse > 5 % (le fournisseur va s'en servir), ▼ baisse > 5 % (levier acheteur), ● stable. |
| Couleur alerte | `` | Couleur du signal matière (rouge = hausse, vert = baisse, gris = stable). |
| Variation anticipée % | `+0.0%;-0.0%;0.0%` | Moyenne des 6 derniers mois disponibles / moyenne des 6 mois avant la dernière campagne − 1 : variation déjà acquise pour la prochaine campagne. |
| Plafond justifié prochaine campagne % | `+0.0%;-0.0%;0.0%` | Hausse que les matières justifient déjà pour la prochaine campagne, sur le tarif en vigueur pondéré par les volumes : au-delà, la demande est contestable. |
| Impact € prochaine campagne | `#,0 €` | Surcoût que les matières justifient déjà pour la prochaine campagne (Σ part × variation acquise × prix × volume). Si une matière est sélectionnée, seule sa contribution est comptée : articles impactés par cette matière. |
| Volume annuel | `#,0` | Quantité achetée sur la dernière année complète. |
| Action fournisseur | `` | Action recommandée selon le plafond justifié de la prochaine campagne : baisse → convoquer le fournisseur, hausse > 2 % → préparer la défense, sinon suivi. |
| Couleur action | `` | Vert = baisse à obtenir, rouge = hausse à cadrer, gris = suivi. |
| Prochaine campagne | `0` | Campagne à venir (dernière campagne + 1). |
| Argument anticipé | `` | Phrase d'anticipation : plafond de hausse défendable pour la prochaine campagne, avant réception du tarif. |
| Conseil appro | `` | Conseil d'approvisionnement avant la prochaine campagne : baisse matière → limiter les achats et attendre le nouveau tarif ; hausse > 3 % → anticiper les achats avant le 1er janvier. |
| Couleur conseil | `` | Vert = attendre la baisse, rouge = anticiper avant la hausse, gris = normal. |

### 8. Décalage

| Mesure | Format | Description |
|---|---|---|
| Décalage estimé (mois) | `0 "mois"` | Décalage d'application qui explique le mieux la hausse demandée (écart minimal entre demandé et justifié) : mesure le retard de répercussion du fournisseur. |
| Délai hausses (mois) | `0.0` | Décalage moyen de répercussion sur les campagnes où les matières montent. |
| Délai baisses (mois) | `0.0` | Décalage moyen de répercussion sur les campagnes où les matières baissent (12 = baisse jamais vraiment répercutée). |
| Asymétrie (mois) | `+0.0;-0.0;0.0` | Délai baisses − délai hausses : positif = le fournisseur répercute les hausses plus vite que les baisses. |
| Écart au meilleur décalage | `+0.0;-0.0;0.0` | Écart (pts) restant une fois le décalage du fournisseur pris en compte : ce qui reste n'est pas expliqué par les matières. |
| Indice prix fournisseur | `0.0` | Prix du tarif en vigueur, base 100 = tarif 2023 (panier fixe, en marches d'escalier aux campagnes). |
| Indice coût matière | `0.0` | Coût matière du même panier, base 100 = référence du tarif 2023 (Σ part × indice INSEE). |
| Écart prix / matière (pts) | `+0.0;-0.0;0.0` | Indice prix − indice coût matière : positif = le fournisseur facture plus que l'évolution de ses matières. |

### 9. Paramètres

| Mesure | Format | Description |
|---|---|---|
| Campagne N+1 | `0` | Campagne analysée (segment param_campagne, 2026 par défaut). |
| Campagne N | `0` | Campagne de référence = campagne N+1 − 1. |
| Décalage mois | `0` | Décalage d'application retenu (segment param_decalage, 0 mois par défaut). |
| Fenêtre mois | `0` | Période de référence des indices (segment param_fenetre, 6 mois par défaut). |

## Tables et colonnes

### bridge_composition

Table pont article × matière : part de chaque matière dans le coût de l'article (somme = 1, non matière comprise).

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `article_id` | string | non | Article. |
| `matiere_id` | string | non | Matière. |
| `part` | double | oui | Part de la matière dans le coût de l'article (0-1). |

### dim_acheteur

Acheteurs. L'email sert à la sécurité par ligne (RLS).

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `acheteur_id` | string | oui | Identifiant acheteur. |
| `nom` | string | oui | Nom de l'acheteur (fictif). |
| `email` | string | oui | Email de connexion, comparé à USERPRINCIPALNAME() par le rôle Acheteur. |
| `role` | string | oui | Rôle : Acheteur ou Direction. |
| `perimetre` | string | oui | Univers couvert. |

### dim_article

Articles achetés, avec le résultat du rattachement référence tarif / référence ERP.

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `article_id` | string | oui | Identifiant article (identité unique après rattachement). |
| `ref_fournisseur` | string | oui | Référence telle qu'écrite dans le tarif fournisseur. |
| `ref_erp` | string | oui | Référence enregistrée dans l'ERP. |
| `designation` | string | oui | Désignation ERP. |
| `designation_tarif` | string | oui | Désignation telle qu'écrite dans le tarif fournisseur. |
| `famille_id` | string | non | Famille de l'article. |
| `fournisseur_id` | string | non | Fournisseur de l'article. |
| `unite` | string | oui | Unité d'achat. |
| `campagne_debut` | int64 | oui | Première campagne tarifaire de l'article. |
| `campagne_fin` | int64 | oui | Dernière campagne tarifaire de l'article. |
| `statut_rattachement` | string | oui | Automatique, Proposé (à valider) ou Non rattaché. |
| `article_id_propose` | string | oui | Article ERP proposé par la correspondance sur la désignation. |
| `score_rattachement` | double | oui | Similarité de désignation (0-1) ; 1 si rattachement automatique. |

### dim_date

Calendrier journalier 2022-2026. Les faits mensuels pointent sur le 1er du mois.

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `date` | dateTime | oui | Date du jour. |
| `annee` | int64 | oui | Année civile. |
| `mois` | int64 | oui | Numéro du mois (1-12). |
| `libelle_mois` | string | oui | Mois en clair (« janv. 2026 »). |
| `annee_mois` | string | oui | Mois au format AAAA-MM. |
| `cle_mois` | int64 | non | Clé de tri AAAAMM. |
| `trimestre` | string | oui | Trimestre (T1 à T4). |
| `debut_mois` | boolean | non | Vrai le 1er du mois. |
| `campagne` | int64 | oui | Campagne tarifaire en vigueur à cette date (tarif au 1er janvier). |
| `mois_court` | string (calculée) | oui | Mois en clair sans l'année (axe des comparaisons année sur année). |

### dim_famille

Familles de produits, rattachées à un univers et à un acheteur.

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `famille_id` | string | oui | Identifiant famille. |
| `libelle` | string | oui | Libellé de la famille. |
| `univers` | string | oui | Univers : Transmission ou CVC. |
| `acheteur_id` | string | non | Acheteur responsable de la famille. |

### dim_fournisseur

Fournisseurs (fictifs).

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `fournisseur_id` | string | oui | Identifiant fournisseur (F01-F12). |
| `nom` | string | oui | Raison sociale fictive. |
| `pays` | string | oui | Pays (code ISO). |
| `devise` | string | oui | Devise de facturation. |
| `prefixe_tarif` | string | non | Préfixe ajouté par le fournisseur dans ses références tarif. |
| `profil` | string | non | Comportement injecté dans les données synthétiques (caché, sert aux tests). |

### dim_matiere

Matières premières et part non matière, avec la série INSEE source.

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `matiere_id` | string | oui | Identifiant matière (CU, AL, NI, ZN, FE, PL, NM, CU_T). |
| `libelle` | string | oui | Libellé de la matière. |
| `source` | string | oui | Source de la série (INSEE BDM ou hypothèse). |
| `idbank` | string | oui | Identifiant de série INSEE (idbank). |
| `titre_insee` | string | oui | Intitulé officiel de la série INSEE. |
| `unite` | string | oui | Unité de la série. |
| `utilisee_composition` | boolean | oui | Vrai si la matière entre dans les compositions d'articles. |
| `dernier_mois` | string | oui | Dernier mois disponible au chargement (fraîcheur). |

### fact_achats

Quantités achetées par article et par mois (synthétique, Pareto 80/20).

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `article_id` | string | non | Article. |
| `date` | dateTime | non | Mois d'achat (1er du mois). |
| `quantite` | int64 | oui | Quantité achetée sur le mois. |
| `prix_unitaire` | double (calculée) | non | Prix brut du tarif en vigueur l'année de l'achat. |
| `montant` | double (calculée) | non | Quantité × prix brut de l'année. |
| `prix_unitaire_n1` | double (calculée) | non | Prix brut du tarif de l'année précédant l'achat (effet prix). |

### fact_hausse_article

Précalcul (scripts/precalcul_hausses.py) : hausse par article pour chaque campagne N+1, fenêtre et décalage. Rend les mesures instantanées.

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `article_id` | string | non | Article. |
| `campagne` | int64 | non | Campagne N+1 (la dernière + 1 = prochaine campagne, anticipation). |
| `fenetre` | int64 | non | Fenêtre de référence des indices (mois). |
| `decalage` | int64 | non | Décalage d'application (mois). |
| `prix_n` | double | non | Prix brut de la campagne N. |
| `prix_n1` | double | non | Prix brut de la campagne N+1 (vide pour la prochaine campagne). |
| `volume_n` | int64 | non | Quantité achetée l'année N. |
| `hausse_justifiee` | double | non | Σ part × variation matière de l'article. |
| `comparable` | boolean | non | Vrai si l'article entre dans le panier comparable. |

### fact_impact_matiere

Précalcul : surcoût justifié par chaque matière pour chaque article à la prochaine campagne.

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `article_id` | string | non | Article. |
| `matiere_id` | string | non | Matière. |
| `fenetre` | int64 | non | Fenêtre de référence des indices (mois). |
| `decalage` | int64 | non | Décalage d'application (mois). |
| `impact` | double | non | Part × variation × prix × volume, en euros. |

### fact_indice

Indices matières mensuels réels (INSEE BDM) et série d'hypothèse non matière à 2 %/an.

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `matiere_id` | string | non | Matière. |
| `date` | dateTime | non | Mois de l'indice (1er du mois). |
| `valeur_eur` | double | oui | Valeur de l'indice (base 2010 en euros, ou €/t pour CU_T). |

### fact_indice_fournisseur

Précalcul : indice mensuel par fournisseur (base 100 = tarif 2023) du prix fournisseur et du coût matière de son panier. L'écart montre le décalage de répercussion.

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `fournisseur_id` | string | non | Fournisseur. |
| `date` | dateTime | non | Mois (1er du mois). |
| `indice_cout_matiere` | double | non | Coût matière du panier fixe du fournisseur, base 100 = référence du tarif 2023. |
| `indice_prix` | double | non | Prix du tarif en vigueur sur le même panier, base 100 = tarif 2023. |

### fact_tarif

Prix brut public par article et par campagne tarifaire (synthétique).

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `article_id` | string | non | Article. |
| `fournisseur_id` | string | non | Fournisseur (redondant : le filtre passe par dim_article). |
| `campagne` | int64 | oui | Campagne tarifaire (année d'effet). |
| `date_effet` | dateTime | non | Date d'effet du tarif (1er janvier). |
| `prix_brut` | double | oui | Prix brut public en euros. Vide si la ligne tarif est arrivée sans prix. |

### ml_anomalies_tarif

Machine learning (scripts/ml_predictions.py) : lignes du tarif 2026 isolées par Isolation Forest (hausse atypique pour sa famille).

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `article_id` | string | non | Article. |
| `fournisseur_id` | string | non | Fournisseur. |
| `demandee` | double | non | Hausse demandée de la ligne. |
| `hausse_justifiee` | double | non | Hausse justifiée de la ligne. |
| `ecart` | double | non | Écart. |
| `score_anomalie` | double | non | Score d'anomalie (plus haut = plus atypique). |
| `anomalie` | boolean | oui | Vrai si la ligne est isolée. |
| `enjeu_eur` | double | non | Écart positif × prix N × volume N. |

### ml_plafond_2027

Machine learning (scripts/ml_predictions.py) : plafond de hausse justifiable 2027 projeté par fournisseur (central et fourchette à 80 %).

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `fournisseur_id` | string | non | Fournisseur. |
| `poids` | double | non | Prix 2026 × volume 2025 du panier. |
| `plafond_central` | double | non | Plafond projeté. |
| `plafond_bas` | double | non | Borne basse. |
| `plafond_haut` | double | non | Borne haute. |

### ml_prevision_indices

Machine learning (scripts/ml_predictions.py) : prévision des indices matières octobre-décembre 2026 (modèle retenu au backtest) et intervalle à 80 %.

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `matiere_id` | string | non | Matière. |
| `date` | dateTime | non | Mois prévu (1er du mois). |
| `horizon_mois` | int64 | non | Mois d'avance. |
| `prevision` | double | non | Indice prévu. |
| `bas_80` | double | non | Borne basse à 80 %. |
| `haut_80` | double | non | Borne haute à 80 %. |
| `modele` | string | oui | Modèle retenu (le naïf si aucun ne le bat). |

### ml_segments_fournisseurs

Machine learning (scripts/ml_predictions.py) : segment de comportement tarifaire trouvé par KMeans (non supervisé).

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `fournisseur_id` | string | non | Fournisseur. |
| `segment_nom` | string | oui | Segment trouvé : aligné, opportuniste, cliquet, références instables. |
| `ecart_moyen` | double | non | Écart moyen demandé − justifié sur 3 campagnes. |
| `ecart_regularite` | double | non | Écart-type de l'écart. |
| `part_cliquet` | double | non | Part des campagnes en effet cliquet. |
| `rattachement_auto` | double | non | Taux de rattachement automatique. |

### ml_variation_2027

Machine learning (scripts/ml_predictions.py) : variation matière attendue pour la campagne 2027, fenêtre juillet-décembre 2026 complétée par la prévision.

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `matiere` | string | non | Matière. |
| `variation_centrale` | double | non | Variation centrale. |
| `variation_basse` | double | non | Borne basse à 80 %. |
| `variation_haute` | double | non | Borne haute à 80 %. |

### param_campagne

Campagne N+1 analysée (comparée à la campagne N = N+1 − 1). Table déconnectée pour le segment.

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `campagne` | int64 | oui | Campagne N+1 analysée (comparée à la campagne N = N+1 − 1). Table déconnectée pour le segment. |

### param_decalage

Décalage d'application : nombre de mois entre l'évolution du cours matière et sa répercussion dans le tarif.

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `decalage_mois` | int64 | oui | Décalage d'application : nombre de mois entre l'évolution du cours matière et sa répercussion dans le tarif. |

### param_fenetre

Période de référence de la variation matière, en mois avant chaque campagne.

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `mois` | int64 | oui | Période de référence de la variation matière, en mois avant chaque campagne. |

### param_hausse

Simulateur : hausse que l'acheteur est prêt à accepter (en %), pour chiffrer la contre-proposition.

| Colonne | Type | Visible | Description |
|---|---|---|---|
| `hausse_acceptee` | int64 | oui | Simulateur : hausse que l'acheteur est prêt à accepter (en %), pour chiffrer la contre-proposition. |
