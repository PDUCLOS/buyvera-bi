# Même analyse, deux outils : Power BI vs tableau de bord Claude

Les deux versions partent des mêmes CSV (`data/processed/`) et des mêmes définitions (`CLAUDE.md`).
Le tableau de bord Claude : https://claude.ai/artifact/4619xpu2n2zfCqSv8gUegM (privé tant qu'il n'est pas partagé).

## Contrôle croisé des 5 chiffres clés (campagne 2026, fenêtre 6 mois)

| Indicateur | Power BI (DAX) | Claude (Python) | Écart |
|---|---|---|---|
| Hausse demandée 2026 | +1,2189 % | +1,2189 % | 0 |
| Hausse justifiée 2026 | −0,6434 % | −0,6434 % | 0 |
| € renégociables 2026 | 335 177,63 € | 335 177,63 € | 0 |
| € renégociables Orlenza Thermique | 120 408,33 € | 120 408,33 € | < 0,01 € |
| Hausse déjà justifiée pour 2027 | +11,23 % | +11,23 % | 0 |

Relevé Power BI : `tests/dax/10_controle_croise.dax`, via `scripts/export_claude.py`. Le tableau de bord Claude affiche ce même tableau et le recalcule à chaque ouverture.

## Comparatif

| Critère | Power BI | Tableau de bord Claude |
|---|---|---|
| Temps de construction | ~3 jours : modèle TMDL, 53 mesures DAX, 7 pages, précalcul pour la fluidité | ~1 heure à partir des mêmes CSV agrégés |
| Sécurité par utilisateur (RLS) | oui, native et testée (`docs/rls.md`) | non : un lien = une vue ; il faut un tableau par public |
| Gouvernance / source unique | modèle sémantique, rafraîchissement planifiable, mesures documentées | instantané des données agrégées, à republier à chaque campagne |
| Volumétrie | 150 000 lignes de précalcul, 62 000 lignes d'achats en direct | 4 petits fichiers agrégés en amont (3 Ko) |
| Exploration | segments synchronisés, simulateur, décalage, animation, détail article | lecture guidée : synthèse, nuage, classement, matières |
| Commentaire et explication | phrases DAX courtes, limitées par les visuels carte | un argument rédigé par fournisseur, prêt pour la note de négociation |
| Partage | licences Power BI côté lecteur | lien claude.ai, sans licence Power BI |
| Usage idéal | pilotage récurrent des achats, par acheteur | préparer un rendez-vous, note à la direction, prototype avant industrialisation |

## Ce qu'il faut retenir

- Le tableau de bord Claude sert de **prototype et de support de négociation** ; Power BI reste la **version industrialisée**, avec la sécurité par acheteur et le rafraîchissement.
- Les chiffres sont identiques parce que les définitions sont écrites une seule fois (`CLAUDE.md`) et appliquées des deux côtés.
- Limites assumées : le tableau de bord Claude ne remplace ni le modèle sémantique ni la RLS ; ses données sont un instantané agrégé, pas une connexion live.
