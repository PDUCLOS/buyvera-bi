# Buyvera BI : idées d'amélioration

Classées par effort. ★ = fort impact en entretien.

## Rapides (≤ ½ jour)

- ★ **Simulateur de contre-proposition** : paramètre What-if « hausse acceptée (%) » → € économisés vs demande, par fournisseur. L'acheteur sort de la page avec un chiffre à poser sur la table.
- ★ **Fiche négociation par fournisseur** (page d'extraction / drill-through) : hausse demandée, justifiée, top 3 matières, levier (« cuivre −6 % sur 6 mois »), historique cliquet. Imprimable en PDF.
- **Décalage temporel paramétrable** : lag 0/3/6 mois entre indice et prix (le fournisseur répercute avec retard). Paramètre de champ + sélecteur.
- **Bandes de tolérance** sur le nuage : zone grisée ±1 pt autour de la diagonale = « juste ».
- **Info-bulles de page** : survol d'un fournisseur → mini courbe des matières qui pèsent dans son panier.
- **Indicateur de fraîcheur** : date du dernier indice INSEE chargé, en en-tête de chaque page.

## Moyennes (1 jour)

- ★ **Score de confiance fournisseur** (0–100) : régularité de l'écart sur 4 campagnes + cliquet + qualité des références. Classement A/B/C.
- **Effet devise** : fournisseurs en USD / GBP, conversion BCE mensuelle → séparer hausse matière, hausse devise, marge.
- **Décomposition en cascade (waterfall)** : prix N → +matières → +non matière → +marge non justifiée → prix N+1.
- **Alertes** : fournisseur dont l'écart dépasse +3 pts → abonnement / alerte de données (Power BI Service).
- **Tests de mesures** : notebook Python qui recalcule 3 articles à la main et compare aux résultats DAX (via MCP ou export), dans le CI GitHub.
- **Calcul de groupe** (calculation group) : bascule Valeur / % / Écart sans dupliquer les mesures.

## Plus ambitieuses

- ★ **Prévision matière N+2** (Prophet ou ARIMA simple sur les indices) → « budget de hausse probable » avant la réception des tarifs.
- **Rattachement assisté** : similarité TF-IDF ou embeddings sur la désignation pour le statut `Proposé`, score affiché, validation par l'acheteur (writeback via Power Apps ou Translytical task flow Fabric).
- **Fabric** : Lakehouse + pipeline planifié pour les indices INSEE (rafraîchissement mensuel réel), modèle Direct Lake.
- **Agent de données** : Copilot / agent Fabric ou agent Claude qui répond « pourquoi la hausse de F07 est-elle trop forte ? » en s'appuyant sur les mesures documentées en TMDL.
- **Version anglaise** du rapport (traductions TMDL déjà prévues) → candidatures internationales.

## Pour le storytelling

- Ouvrir la démo sur **un seul chiffre** : « 412 k€ renégociables sur la campagne 2026 ».
- Montrer **un fournisseur honnête et un opportuniste** côte à côte : même mix matières, écarts opposés.
- Finir sur la **page Rattachement** : le pont vers le métier « intégration après acquisition ».
- Avoir la **capture RLS** prête (acheteur CVC ne voit que CVC).
- Dire franchement : tarifs et volumes synthétiques, indices réels.

## Risques à surveiller

| Risque | Parade |
|---|---|
| Série INSEE arrêtée ou en retard | contrôle de fraîcheur dans `fetch_indices.py`, repli Banque mondiale |
| Bridge mal compris (doubles comptes) | mesures toujours via `SUMX` sur l'article, jamais de relation bidirectionnelle |
| Chiffres PBI ≠ Claude | une seule source de définitions (`docs/mesures.md`) reprise des deux côtés |
| Données trop « parfaites » | bruit, articles orphelins, quelques prix manquants volontaires |
