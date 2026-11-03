# Buyvera BI : règles du projet

Référence complète : `PROJET_BUYVERA_BI.md`. Idées d'évolution : `docs/idees.md`.

## Données
- Indices matières **réels** (INSEE BDM, Banque mondiale en contrôle). Tarifs, volumes, fournisseurs, articles **synthétiques**.
- Aucune vraie marque, aucun vrai fournisseur, aucun prix net, aucune remise, aucune donnée client.
- Ne pas utiliser la série acier INSEE `001743680` (arrêtée).
- Génération reproductible : graine aléatoire fixe (`SEED` dans `scripts/generate_synthetic.py`).
- `data/raw/` = brut téléchargé, `data/processed/` = une table du modèle par CSV (séparateur `,`, décimale `.`, UTF-8).

## Pipeline
1. `python scripts/fetch_indices.py` → `data/raw/insee_*.csv`, `data/processed/fact_indice.csv`, `dim_matiere.csv`
2. `python scripts/generate_synthetic.py` → autres tables + `data/controle/` (calcul article par article, vérité rattachement)
3. `python scripts/controles.py` → `docs/rapport_controle.md` (code retour 1 si un contrôle bloquant échoue)
Toujours relancer les contrôles après une modification des scripts. Le rapport de contrôle fait foi pour les chiffres de référence.
- La part non matière est la « matière » `NM` : série d'hypothèse à 2 %/an dans `fact_indice`, présente dans `bridge_composition`. La hausse justifiée est donc Σ part × variation sur toutes les lignes du pont.
- `article_id` = identité vraie de l'article (rattachement supposé validé) ; `statut_rattachement` montre ce que l'automate a trouvé seul.

## Définitions des mesures (source unique pour Power BI ET le tableau de bord Claude)
- Hausse demandée % = Σ(prix N+1 × volume N) / Σ(prix N × volume N) − 1 (articles présents aux deux campagnes).
- Variation matière % = moyenne indice 6 mois avant campagne N+1 / moyenne 6 mois avant campagne N − 1.
- Hausse justifiée % = Σ(part matière × variation matière) + part non matière × inflation de référence (2 %/an, hypothèse affichée).
- Agrégée (fournisseur, famille, total), la hausse justifiée est pondérée comme la demandée : Σ(justifiée article × prix N × volume N) / Σ(prix N × volume N).
- Périmètre : articles avec un prix aux deux campagnes et un volume N > 0 (volume N = quantités achetées sur l'année N).
- Écart pts = demandée − justifiée. € renégociables = Σ article MAX(0, écart) × prix N × volume annuel.

## DAX / modèle
- Modèle en étoile, relations 1→N, filtrage unidirectionnel. Jamais de relation bidirectionnelle sur `bridge_composition` : passer par `SUMX` sur l'article.
- `VAR` partout, `DIVIDE` au lieu de `/`, dossier d'affichage par thème, description (FR) sur chaque mesure, table et colonne.
- Format PBIP + TMDL, versionné Git. Commit avant chaque série de modifications du modèle.

## Style
- Code et commentaires en français, noms de colonnes en snake_case.
