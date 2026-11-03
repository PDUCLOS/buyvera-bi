# Buyvera BI : cette hausse fournisseur est-elle justifiée ?

Projet portfolio Power BI. Il sert de vitrine pour les candidatures Data Analyst / BI dans l'industrie, la distribution et les achats.

---

## 1. Le pitch (à dire en entretien)

> Chaque année, les fournisseurs envoient leurs nouveaux tarifs avec une hausse « justifiée par les matières premières ». J'ai construit un tableau de bord qui compare la hausse demandée avec l'évolution réelle des matières qui composent chaque produit. L'acheteur voit tout de suite, fournisseur par fournisseur, combien d'euros il peut renégocier.

**Question métier :** sur la campagne tarifaire N+1, quel montant de hausse n'est pas justifié par les matières, et chez quels fournisseurs ?

**Lien avec Buyvera :** c'est le module d'analyse préalable des hausses, sur données publiques et synthétiques uniquement. Aucun prix net, aucune remise, aucune donnée client.

---

## 2. Les données

### 2.1 Données publiques réelles (les indices matières)

| Matière | Source | Série | Unité |
|---|---|---|---|
| Cuivre | INSEE (BDM) | `010767327`, LME Grade A, comptant | € / tonne |
| Cuivre (indice) | INSEE (BDM) | `010002094` | indice base 2010, en € |
| Aluminium | INSEE (BDM) | `010002093` | indice base 2010, en € |
| Nickel (inox) | INSEE (BDM) | `010002096` | indice base 2010, en € |
| Zinc | INSEE (BDM) | `010002098` | indice base 2010, en € |
| Acier / métaux ferreux | INSEE (BDM) | `010002103`, métaux ferreux | indice base 2010, en € |
| Plastiques (approximation) | INSEE (BDM) | `010002090`, naphta | indice, en € |
| Contrôle / complément | Banque mondiale, « Pink Sheet » | fichier `CMO-Historical-Data-Monthly.xlsx` | USD, mensuel |

**Récupération :**

- INSEE : chaque série a une page `https://www.insee.fr/fr/statistiques/serie/<idbank>` avec un téléchargement CSV. Il existe aussi une API SDMX publique (`https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/<idbank>`). Laisse Claude Code tester l'URL et prendre la plus simple qui marche.
- Banque mondiale : le fichier Excel mensuel se trouve sur la page « Commodity Markets » du site de la Banque mondiale. Il sert de contrôle ou de complément (acier, plastiques).
- **À vérifier au démarrage :** que les séries sont bien mensuelles et à jour. La série acier `001743680` est arrêtée, ne pas l'utiliser.
- Option : un indice de prix de production de l'industrie (IPPI) par secteur, comme référence d'inflation pour la part non matière (main-d'œuvre, énergie). Si ce n'est pas trouvé vite, fixer 2 %/an en hypothèse affichée.

**Période :** janvier 2022 → dernier mois disponible.

### 2.2 Données synthétiques (générées par un script Python)

Tout est fictif, mais réaliste et conforme à ton expérience terrain. Pas de vraies marques, pour ne pas laisser croire à des tarifs réels.

| Table | Volume | Contenu |
|---|---|---|
| Fournisseurs | 12 | noms fictifs, pays, devise, profil de comportement (caché) |
| Familles | 8 | 4 en transmission mécanique (roulements, moteurs, réducteurs, courroies et chaînes) et 4 en CVC (pompes à chaleur, climatisation, tubes et raccords cuivre, ventilation) |
| Acheteurs | 3 | un acheteur Transmission, un acheteur CVC, un responsable achats (voit tout) |
| Articles | ~3 000 | référence fournisseur, référence ERP, désignation, famille, fournisseur, unité |
| Composition | ~3 000 × 2 à 4 matières | part de chaque matière dans le coût du produit (ex. moteur : 35 % acier, 20 % cuivre, 10 % alu, reste non matière) |
| Tarifs | 4 campagnes (janv. 2023 → janv. 2026) | prix brut public par article et par campagne |
| Achats | mensuels 2023–2026 | quantités achetées par article (Pareto 80/20 réaliste) |

**Comportements à injecter (sinon le tableau de bord ne raconte rien) :**

1. 4 fournisseurs « honnêtes » : hausse proche de la hausse justifiée (± 1 pt).
2. 4 fournisseurs « opportunistes » : hausse au-dessus de la justifiée, de 3 à 8 points.
3. 2 fournisseurs qui ne baissent pas leurs prix quand les matières baissent (effet cliquet).
4. 2 fournisseurs qui changent la référence d'une partie des articles (tirets, espaces, préfixes) : ça alimente la page rattachement.
5. Quelques articles qui disparaissent, d'autres qui apparaissent, à chaque campagne.

**Génération de la hausse :** hausse fournisseur = hausse justifiée (calculée à partir des vrais indices) + biais du profil + bruit. La hausse fournisseur est donc reliée aux vrais cours des matières.

### 2.3 Page rattachement (le morceau « intégration après acquisition »)

- Référence ERP ≠ référence tarif sur ~20 % des articles.
- Le script calcule un statut par article : `Automatique` (référence normalisée identique), `Proposé` (correspondance approchée sur la désignation, à valider), `Non rattaché`.
- Objectif affiché : 80 % de rattachement automatique, comme la règle Buyvera.

---

## 3. Modèle en étoile

```
                 dim_date
                    │
dim_fournisseur ── fact_tarif ── dim_article ── dim_famille ── dim_acheteur
                    │              │
               fact_achats   bridge_composition ── dim_matiere ── fact_indice ── dim_date
```

| Table | Type | Clés / colonnes clés |
|---|---|---|
| `fact_tarif` | faits | article_id, fournisseur_id, campagne, date_effet, prix_brut |
| `fact_achats` | faits | article_id, date (mois), quantite |
| `fact_indice` | faits | matiere_id, date (mois), valeur_eur |
| `bridge_composition` | pont | article_id, matiere_id, part (0–1) |
| `dim_article` | dimension | article_id, ref_fournisseur, ref_erp, designation, famille_id, statut_rattachement |
| `dim_fournisseur` | dimension | fournisseur_id, nom, pays |
| `dim_famille` | dimension | famille_id, libelle, univers (Transmission / CVC), acheteur_id |
| `dim_acheteur` | dimension | acheteur_id, nom, email (pour la RLS) |
| `dim_matiere` | dimension | matiere_id, libelle, source, idbank |
| `dim_date` | dimension | date, mois, année, campagne |

Relations simples, de 1 vers plusieurs, filtrage dans un seul sens. Le pont de composition est la seule subtilité : bien l'expliquer en entretien.

---

## 4. Mesures DAX clés

| Mesure | Logique |
|---|---|
| `Hausse demandée %` | (Σ prix N+1 × volume N) / (Σ prix N × volume N) − 1, pondérée par les volumes |
| `Variation matière %` | moyenne de l'indice sur les 6 mois avant la campagne N+1 / même moyenne avant la campagne N − 1 |
| `Hausse justifiée %` | Σ (part matière × variation matière) + part non matière × inflation de référence |
| `Écart pts` | hausse demandée − hausse justifiée |
| `€ renégociables` | Σ par article de MAX(0, écart) × prix N × volume annuel |
| `% articles rattachés auto` | articles « Automatique » / total |
| `Effet cliquet` | nb de campagnes avec matière en baisse et prix non baissé |

Règles : variables `VAR` partout, `DIVIDE` à la place de `/`, un dossier d'affichage par thème, une description sur chaque mesure (elles alimentent la doc TMDL).

---

## 5. Pages du rapport

1. **Synthèse campagne** : hausse demandée, hausse justifiée, € renégociables, top 5 des fournisseurs à renégocier.
2. **Fournisseurs** : nuage de points hausse demandée × hausse justifiée (diagonale = juste), taille de bulle = volume d'achat.
3. **Détail article** : composition matière, courbe des indices, historique des prix sur 4 campagnes.
4. **Matières** : évolution des indices, sélecteur de période de référence (3, 6 ou 12 mois).
5. **Rattachement** : taux automatique / proposé / non rattaché, par fournisseur, liste à valider.

**RLS (sécurité par ligne)** : rôle `Acheteur` filtré sur `dim_acheteur[email] = USERPRINCIPALNAME()`, propagé par famille. Rôle `Direction` sans filtre. À tester avec « Afficher en tant que » et à montrer en capture.

**Documentation** : description de chaque table, colonne et mesure dans le TMDL, en français et en anglais. Un script exporte un dictionnaire de données en markdown à partir du TMDL.

---

## 6. Organisation du travail avec Claude Code

**Format :** projet Power BI au format **PBIP**, avec le modèle en **TMDL** (fichiers texte). Claude Code lit et modifie directement les tables, mesures et rôles, et tout est versionné sous Git.

**Machine :** tout le projet se fait sur la machine Windows (Power BI Desktop + Claude Code + Python + Git), dans un seul dossier.

**Serveur MCP Microsoft (recommandé) :** le serveur Power BI Modeling MCP se connecte à Power BI Desktop, à Fabric ou à un dossier PBIP. Il peut créer des mesures, tester des requêtes DAX et configurer la RLS. Installation :

```bash
claude mcp add powerbi-modeling -- npx -y @microsoft/powerbi-modeling-mcp@latest --start
```

Faire une sauvegarde ou un commit Git avant chaque série de modifications.

**Arborescence :**

```
buyvera-bi/
├── CLAUDE.md                 ← règles du projet (données fictives, pas de vraie marque, DAX propre)
├── data/
│   ├── raw/                  ← indices INSEE / Banque mondiale bruts
│   └── processed/            ← CSV du modèle (une table = un fichier)
├── scripts/
│   ├── fetch_indices.py
│   ├── generate_synthetic.py ← graine aléatoire fixe : résultats reproductibles
│   └── export_dictionary.py
├── pbip/                     ← BuyveraBI.pbip, .SemanticModel (TMDL), .Report
├── claude-dashboard/         ← volet 2 : même analyse en tableau de bord Claude
├── docs/
│   ├── captures/
│   ├── comparatif.md         ← Power BI vs tableau de bord Claude
│   └── dictionnaire.md
└── README.md                 ← pitch, captures, choix de modélisation
```

---

## 6 bis. Volet 2 : la même analyse en tableau de bord Claude

**Objectif :** montrer que tu sais choisir l'outil selon le besoin. Ce n'est pas « l'IA remplace Power BI ». C'est « Power BI pour le pilotage gouverné, un tableau de bord Claude pour l'analyse rapide et partageable ».

**Ce qu'on construit :** à partir des mêmes CSV (`data/processed/`) et des mêmes définitions de mesures, Claude produit un tableau de bord de synthèse de campagne : les mêmes indicateurs clés, le classement des fournisseurs, le nuage hausse demandée × hausse justifiée et un commentaire écrit par fournisseur (« hausse de 7,2 % pour 2,1 % justifiée, levier de négociation : cuivre en baisse sur 6 mois »).

**Règle d'or :** les deux versions doivent donner **exactement les mêmes chiffres**. On contrôle 5 valeurs clés côte à côte, et c'est la preuve que les mesures sont bien définies.

**Comparatif à écrire (`docs/comparatif.md`), à présenter tel quel en entretien :**

| Critère | Power BI | Tableau de bord Claude |
|---|---|---|
| Temps de construction | ~4 jours (modèle, DAX, pages) | quelques heures à partir des mêmes données |
| Sécurité par utilisateur (RLS) | oui, native | non, il faut un fichier par public |
| Gouvernance / source unique | modèle sémantique partagé, rafraîchissement planifié | instantané des données, à republier |
| Volumétrie | des millions de lignes | données agrégées en amont |
| Commentaire et explication | à écrire à la main | rédigés par fournisseur, en langage clair |
| Partage | licences Power BI | lien, sans licence côté lecteur |
| Usage idéal | pilotage récurrent des achats | préparation d'une négociation, note à la direction, prototype avant industrialisation |

**Message à faire passer :** le tableau de bord Claude sert de **prototype et de support de négociation**, Power BI reste la **version industrialisée**. C'est le même cycle que Buyvera : analyser vite, puis outiller durablement.

**À ne pas promettre :** que Claude remplace le modèle sémantique ou la RLS. Les limites sont écrites dans le comparatif, c'est ce qui rend la démarche crédible.

---

## 7. Planning court (≈ 6 jours)

| Jour | Livrable |
|---|---|
| 1 | Indices récupérés et nettoyés, script de génération, CSV prêts, contrôles (sommes des parts = 1, pas de prix négatif) |
| 2 | Modèle en étoile dans Power BI Desktop, enregistré en PBIP, relations, table de dates |
| 3 | Mesures DAX + descriptions, validation des chiffres sur 3 articles calculés à la main |
| 4 | 5 pages, RLS, captures |
| 5 | Volet 2 : tableau de bord Claude sur les mêmes données, contrôle des 5 chiffres clés, `comparatif.md` |
| 6 | README GitHub, dictionnaire de données, publication (GitHub + portfolio pduclos.github.io + post LinkedIn « même analyse, deux outils ») |

---

## 8. Prompt de démarrage pour Claude Code (jour 1)

```
Lis PROJET_BUYVERA_BI.md. Crée l'arborescence de la section 6 et un CLAUDE.md
avec les règles du projet. Ensuite :
1. scripts/fetch_indices.py : récupère les séries INSEE de la section 2.1
   (teste l'export CSV et l'API SDMX, garde la méthode qui marche), mensuel
   depuis 2022-01, sortie data/raw/ puis fact_indice.csv + dim_matiere.csv.
2. scripts/generate_synthetic.py : génère les tables de la section 2.2 avec une
   graine fixe et les 5 comportements fournisseurs. La hausse fournisseur se
   calcule à partir des vrais indices + biais du profil + bruit.
3. Contrôles automatiques et petit rapport : nb de lignes par table, parts de
   composition = 1, hausse demandée vs justifiée par fournisseur.
Ne pas utiliser de vraies marques. Montre-moi le rapport de contrôle avant de continuer.
```

---

## 9. Ce que le projet prouve à un recruteur

| Attendu Data Analyst / BI | Preuve dans le projet |
|---|---|
| SQL / préparation de données | pipeline Python + Power Query, contrôles qualité |
| Power BI / DAX | modèle en étoile, table pont, mesures pondérées, intelligence temporelle |
| Sécurité / gouvernance | RLS, dictionnaire de données, TMDL documenté |
| Compréhension métier | logique achats réelle : campagne tarifaire, effet cliquet, rattachement de références |
| Méthode moderne | PBIP + Git, assistant IA via MCP |
| Recul sur l'IA | même analyse en Power BI et en tableau de bord Claude, chiffres identiques, limites écrites |

**À dire franchement en entretien :** les tarifs et les volumes sont synthétiques, les indices matières sont réels. La logique vient de 20 ans de distribution industrielle.
