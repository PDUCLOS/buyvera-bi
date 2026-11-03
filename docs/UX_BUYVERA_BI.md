# Buyvera BI : l'expérience utilisateur

Topo de ce qui a été mis en place dans le rapport Power BI `pbip/BuyveraBI.pbip`, état au 03/11/2026.
Charte appliquée : `buyvera-brand/BRAND.md` du dépôt Purchasingsolution.
Tout est généré par `scripts/build_pbip.py` : une modification de l'interface se fait dans le script, jamais à la main dans Power BI.

## Le principe

Le rapport suit le même principe que l'outil Tarifs fournisseurs : **l'outil prépare, l'acheteur décide**.
Il ne montre pas « des chiffres sur les achats ». Il répond, dans l'ordre, aux questions qu'un acheteur se pose avant un rendez-vous fournisseur :

| Étape | Question de l'acheteur | Page | Chiffre affiché sur le parcours |
|---|---|---|---|
| 1 Détecter | Quelles matières montent ou baissent ? | Alertes | 3 ▲ · 2 ▼ |
| 2 Chiffrer | Combien renégocier sur la campagne ? | Synthèse | 335 k€ |
| 3 Cibler | Qui demande plus que ses matières ? | Fournisseurs | 4 fournisseurs |
| 4 Comprendre | Prix et volumes, année sur année | Prix & volumes | +1,3 % d'effet prix |
| 5 Négocier | Argument et contre-proposition | Fiche négociation | 2027 : +11,2 % |

Chiffres de la démonstration (tarifs et volumes fictifs, indices matières INSEE réels).

## Architecture de navigation

- **Page d'accueil « Parcours »** : les 5 étapes, chacune avec son chiffre clé et un bouton « Ouvrir → ». Au-dessus, 4 tuiles (la tuile clé en vert marque) ; à droite, l'encart sombre « À retenir » et la courbe de décalage prix / matière.
- **Bandeau horizontal** en haut de chaque page : logo et 8 onglets dans l'ordre du parcours. L'onglet actif est sur fond encre clair, en menthe.
- **Du général au détail sans friction** :
  - clic droit sur un fournisseur, partout dans le rapport → *Extraire* → **Fiche négociation** filtrée sur lui ;
  - clic droit sur un article → *Extraire* → **Détail article** (page masquée de la navigation, on n'y arrive que par là) ;
  - bouton **← Retour** sur ces deux pages ;
  - un clic sur une matière dans les Alertes filtre la liste des articles exposés.
- **Segments synchronisés** : la campagne, l'univers ou le fournisseur choisis suivent l'acheteur d'une page à l'autre.

## Ce que voit l'acheteur à chaque page

| Page | Contenu | Interaction |
|---|---|---|
| Synthèse | 5 tuiles (€ renégociables en tête), € par fournisseur, écart par famille coloré par seuil | segments campagne / univers |
| Alertes | Signaux 3 et 12 mois par matière, plan d'action par fournisseur (négociation et appro), articles exposés | clic sur une matière |
| Fournisseurs | Nuage demandé × justifié **animé 2024 → 2026**, classement avec statut | ▶ lecture, extraction vers la fiche |
| Prix & volumes | N vs N-1 à date : montant, volumes, effet prix à volumes constants, surcoût € par fournisseur, une courbe de volumes par année | segments univers / fournisseur |
| Fiche négociation | Statut, demandé / justifié, € renégociables, **gain de la contre-proposition**, synthèse rédigée, argument 2027, action et conseil appro, **courbe prix vs coût matière**, matières de son panier | simulateur « hausse acceptée » |
| Matières | Indices INSEE, variation sur fenêtre 3 / 6 / 12 mois, **décalage d'application** 0 à 12 mois, délais hausses vs baisses | segments fenêtre / décalage |
| Rattachement | Taux automatique / proposé / non rattaché vs objectif 80 %, liste à valider | segment fournisseur |

## Le langage visuel

| Élément | Choix | Raison |
|---|---|---|
| Fond | grès `#ECEAE3`, cartes `surface` blanches | même rendu que la présentation Buyvera |
| Cartes | filet `line` `#DCD8CE`, rayon 12, **sans ombre** | charte : « bordures fines plutôt qu'ombres » |
| Tuile clé | pleine en `brand` `#0F5C4A`, texte blanc | un seul chiffre héros par page |
| Signal | ambre `#C9781C` réservé aux hausses et écarts | charte : « hausses / écarts uniquement » |
| Favorable | vert `brand` : conforme, baisse = levier | le vert = économie |
| Encart « À retenir » | fond `ink`, titre menthe | met l'argument au premier plan |
| Séries de graphiques | 8 couleurs dérivées de la charte | ordre testé pour les daltoniens (skill dataviz) |
| Statuts | icône + mot + couleur (▲ À renégocier, ◆ À surveiller, ● Conforme) | jamais la couleur seule |
| Fraîcheur | pastille ambre « Indices INSEE à fin septembre 2026 » | l'acheteur sait de quand date l'argument |

## Les mots

- Vouvoiement implicite, verbes d'action : « Préparer la défense », « Convoquer le fournisseur », « Limiter les achats, attendre la baisse », « Anticiper les achats ».
- **« Fournisseur » et non « commercial »** : le commercial est aussi un interlocuteur interne (appros, commerciaux de l'entreprise).
- Phrases générées courtes, sur une ligne : « Demande +1,7 % pour +1,6 % justifiés · à renégocier 9 076 € · levier Plastiques −21,9 % ».
- Les données fictives sont signalées sur chaque page (« tarifs, volumes et fournisseurs fictifs »).

## Fluidité

- Les hausses sont **précalculées** par article × campagne × fenêtre × décalage (`scripts/precalcul_hausses.py`) : chaque clic répond en une seconde environ au lieu d'une minute, avec les mêmes chiffres au centime.
- Pas plus de 6 à 8 visuels par page (hors navigation), KPI en haut, détail en dessous.

## Écarts à la charte, assumés ou à corriger

| Écart | Pourquoi | Suite |
|---|---|---|
| Police Segoe UI au lieu de Manrope | Manrope n'est pas installée sur le poste ; Power BI Desktop ne charge pas de police web | installer Manrope sur les postes, puis la déclarer dans le thème |
| Logotype tapé en texte « Buy**vera** BI » | Power BI ne place pas de SVG dans un bouton de navigation | remplacer par `buyvera-logo-reversed.svg` en image |
| Pages Matières, Rattachement, Détail article moins travaillées | priorité au parcours de négociation | appliquer la même grille |
| RLS : les courbes de décalage ne sont pas filtrées par acheteur | table fournisseur, hors chaîne famille → article | relier `fact_indice_fournisseur` au périmètre acheteur |

## Lien avec l'outil Tarifs fournisseurs

Les deux se complètent :
- **Tarifs fournisseurs** (Shiny) est l'outil de travail : il lit le tarif reçu, le rattache à l'ERP, l'acheteur y décide ligne par ligne.
- **Buyvera BI** (Power BI) est la vue de pilotage et de préparation : alertes matières avant la campagne, ciblage des fournisseurs, fiche de rendez-vous.

Les mêmes principes s'appliquent aux deux : hausse pondérée par les volumes, valeur vide plutôt que devinée, l'outil ne décide pas à la place de l'acheteur.
