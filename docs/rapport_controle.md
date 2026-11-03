# Rapport de contrôle des données

Généré par `scripts/controles.py`. Tarifs et volumes synthétiques, indices matières réels (INSEE).

## 1. Volumétrie

| table | lignes |
|---|---|
| dim_date | 1826 |
| dim_fournisseur | 12 |
| dim_famille | 8 |
| dim_acheteur | 3 |
| dim_matiere | 8 |
| dim_article | 3000 |
| bridge_composition | 11697 |
| fact_tarif | 10142 |
| fact_achats | 62095 |
| fact_indice | 456 |

## 2. Contrôles bloquants

| contrôle | anomalies | statut |
|---|---|---|
| Σ parts composition = 1 (±0,0001) | 0 | OK |
| Parts de composition hors ]0 ; 1] | 0 | OK |
| Articles hors 2 à 4 matières | 0 | OK |
| Prix négatifs ou nuls | 0 | OK |
| Quantités négatives ou nulles | 0 | OK |
| Clés article orphelines dans fact_tarif | 0 | OK |
| Clés article orphelines dans fact_achats | 0 | OK |
| Clés article orphelines dans bridge_composition | 0 | OK |
| Clés matière orphelines (composition) | 0 | OK |
| Dates absentes de dim_date dans fact_achats | 0 | OK |
| Dates absentes de dim_date dans fact_indice | 0 | OK |
| Doublons article × campagne (fact_tarif) | 0 | OK |
| Fournisseur tarif ≠ fournisseur article | 0 | OK |

## 3. Réalisme et anomalies volontaires

- Lignes tarif sans prix (volontaire, ~0,3 %) : **33**
- Articles sans aucun achat : **208**
- Articles entrés après 2023 : **608**, sortis avant 2026 : **344**
- Pareto : 20 % des articles = **82 %** de la dépense (cible ≈ 80 %)

Dépense valorisée au prix brut par an (2026 : janvier à septembre) :

| année | dépense |
|---|---|
| 2023 | 15 613 176 € |
| 2024 | 16 821 679 € |
| 2025 | 17 748 232 € |
| 2026 | 13 176 405 € |

## 4. Variation matière par campagne (moyenne 6 mois avant N+1 / avant N)

| matière | 2024 | 2025 | 2026 |
|---|---|---|---|
| Aluminium | -13,0 % | +14,1 % | +2,0 % |
| Cuivre | -1,7 % | +11,2 % | +5,6 % |
| Acier / métaux ferreux | +10,6 % | -16,8 % | -5,7 % |
| Nickel (inox) | -25,6 % | -14,1 % | -13,9 % |
| Non matière (main-d'œuvre, énergie, frais) | +2,0 % | +2,0 % | +2,0 % |
| Plastiques (naphta) | -11,4 % | +1,5 % | -21,9 % |
| Zinc | -26,4 % | +18,3 % | -4,6 % |

## 5. Hausse demandée / justifiée par fournisseur (écart en pts)

Pondérée par la valeur N (prix N × volume N). Le profil est caché dans le rapport Power BI.

| id | fournisseur | profil | 2024 | 2025 | 2026 | € renégociables (3 campagnes) |
|---|---|---|---|---|---|---|
| F01 | Rotavel | honnete | +3,7 % / +3,9 % (-0,2) | -7,1 % / -7,0 % (-0,1) | -3,2 % / -3,1 % (-0,1) | 7 980 € |
| F02 | Mekandra | honnete | +3,5 % / +3,0 % (+0,4) | -1,8 % / -1,7 % (-0,1) | +0,3 % / +0,1 % (+0,2) | 9 994 € |
| F03 | Tressile | honnete | +1,7 % / +1,2 % (+0,5) | -3,2 % / -3,9 % (+0,7) | -7,0 % / -6,8 % (-0,2) | 7 518 € |
| F04 | Brunelle Aéraulique | honnete | +1,1 % / +0,5 % (+0,6) | +0,5 % / +0,8 % (-0,4) | -0,3 % / -0,3 % (-0,0) | 22 119 € |
| F05 | Kelmaro Antriebe | opportuniste | +9,3 % / +4,3 % (+5,0) | -3,3 % / -7,6 % (+4,3) | +0,7 % / -3,3 % (+4,0) | 152 111 € |
| F06 | Vandrelo | opportuniste | +9,0 % / +3,5 % (+5,5) | +2,6 % / -2,2 % (+4,7) | +3,8 % / +0,1 % (+3,8) | 97 308 € |
| F07 | Orlenza Thermique | opportuniste | +5,1 % / +0,2 % (+4,9) | +8,2 % / +2,1 % (+6,0) | +6,2 % / +0,5 % (+5,7) | 346 855 € |
| F08 | Cuprana | opportuniste | +3,4 % / -2,6 % (+6,0) | +14,5 % / +8,8 % (+5,7) | +10,5 % / +3,3 % (+7,2) | 157 616 € |
| F09 | Zentrix Technik | cliquet | +3,9 % / +3,6 % (+0,4) | +0,3 % / -3,3 % (+3,6) | +0,1 % / -0,5 % (+0,6) | 56 887 € |
| F10 | Aerivo Klima | cliquet | +0,4 % / -1,5 % (+1,9) | +5,3 % / +5,4 % (-0,0) | +1,7 % / +1,6 % (+0,0) | 67 716 € |
| F11 | Halderis | refs_modifiees | +5,3 % / +4,7 % (+0,6) | -4,4 % / -5,8 % (+1,4) | -0,2 % / -1,6 % (+1,4) | 58 385 € |
| F12 | Sorvane | refs_modifiees | +2,2 % / +0,7 % (+1,5) | -1,1 % / -2,0 % (+0,9) | -2,3 % / -3,7 % (+1,4) | 42 108 € |

Comportements attendus : **tous vérifiés**

## 6. Synthèse par campagne (chiffres de référence)

| campagne | articles | valeur N | hausse demandée | hausse justifiée | écart pts | € renégociables |
|---|---|---|---|---|---|---|
| 2024 | 1926 | 14 700 245 € | +3,61 % | +1,39 % | +2,22 | 337 974 € |
| 2025 | 2026 | 15 948 133 € | +1,47 % | -0,59 % | +2,05 | 353 445 € |
| 2026 | 2096 | 16 530 304 € | +1,22 % | -0,64 % | +1,86 | 335 178 € |

Top 5 à renégocier, campagne 2026 :

| fournisseur | écart pts | € renégociables |
|---|---|---|
| Orlenza Thermique | +5,7 | 120 408 € |
| Cuprana | +7,2 | 65 199 € |
| Kelmaro Antriebe | +4,0 | 47 321 € |
| Vandrelo | +3,8 | 28 806 € |
| Halderis | +1,4 | 22 215 € |

## 7. Rattachement des références

- Référence tarif ≠ référence ERP (brute) : **21,0 %** des articles (cible ~20 %)
- Automatique **95,4 %** (objectif ≥ 80 %), Proposé **3,3 %**, Non rattaché **1,2 %**
- Précision des propositions (bon article proposé) : **93,0 %**

| fournisseur_id | Automatique | Proposé | Non rattaché |
|---|---|---|---|
| F01 Rotavel | 100,0 | 0,0 | 0,0 |
| F02 Mekandra | 100,0 | 0,0 | 0,0 |
| F03 Tressile | 100,0 | 0,0 | 0,0 |
| F04 Brunelle Aéraulique | 100,0 | 0,0 | 0,0 |
| F05 Kelmaro Antriebe | 100,0 | 0,0 | 0,0 |
| F06 Vandrelo | 100,0 | 0,0 | 0,0 |
| F07 Orlenza Thermique | 100,0 | 0,0 | 0,0 |
| F08 Cuprana | 100,0 | 0,0 | 0,0 |
| F09 Zentrix Technik | 100,0 | 0,0 | 0,0 |
| F10 Aerivo Klima | 100,0 | 0,0 | 0,0 |
| F11 Halderis | 67,4 | 24,0 | 8,5 |
| F12 Sorvane | 69,8 | 21,9 | 8,3 |

## Verdict

**Contrôles bloquants OK.**
