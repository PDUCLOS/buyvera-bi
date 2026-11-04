# Machine learning : ce que l'historique permet de prédire

Généré par `scripts/ml_predictions.py`. Chaque modèle est comparé à une référence naïve sur un backtest chronologique (le modèle ne voit jamais le futur) et n'est retenu que s'il la bat.

## 1. Indices matières (INSEE, réel)

Backtest chronologique : 32 dates de départ (janvier 2024 → août 2026), 6 matières, chaque modèle réentraîné à chaque date sur le seul passé. Erreur = écart relatif à l'indice réellement publié ensuite (MAPE). « Sens » = part des cas où le modèle a vu juste sur hausse / baisse.

| horizon | modèle | erreur moyenne | sens juste | prévisions |  |
|---|---|---|---|---|---|
| 1 mois | lightgbm | 4,7 % | 49 % | 192 |  |
| 1 mois | naif | 4,2 % | — | 192 | **retenu** |
| 1 mois | tendance_amortie | 4,4 % | 42 % | 192 |  |
| 3 mois | lightgbm | 9,0 % | 51 % | 180 |  |
| 3 mois | naif | 8,5 % | — | 180 | **retenu** |
| 3 mois | tendance_amortie | 9,0 % | 41 % | 180 |  |
| 6 mois | lightgbm | 14,2 % | 38 % | 162 |  |
| 6 mois | naif | 11,4 % | — | 162 | **retenu** |
| 6 mois | tendance_amortie | 12,4 % | 40 % | 162 |  |

Pourquoi le naïf gagne : 6 séries mensuelles sur moins de 5 ans, soit quelques centaines de points, c'est trop peu pour qu'un modèle à arbres (LightGBM) apprenne autre chose que du bruit. Un « sens juste » proche de 50 % le confirme : sur des cours de métaux, le mois prochain ressemble surtout au dernier. La valeur utile est donc la **fourchette**, tirée des erreurs passées, qui sert de budget de hausse.

Prévision depuis septembre 2026 et variation attendue pour la campagne 2027 (moyenne juillet-décembre 2026, dont juillet à septembre connus, vs même période 2025). Intervalle à 80 % tiré des erreurs du backtest.

| matière | variation 2027 attendue | fourchette 80 % |
|---|---|---|
| Cuivre | +38,7 % | +35,6 % à +47,8 % |
| Aluminium | +20,9 % | +15,9 % à +28,3 % |
| Nickel (inox) | +11,3 % | +6,8 % à +17,4 % |
| Zinc | +32,7 % | +27,4 % à +40,3 % |
| Acier / métaux ferreux | −0,5 % | −6,3 % à +2,6 % |
| Plastiques (naphta) | +49,4 % | +39,1 % à +60,5 % |

**Plafond de hausse justifiable 2027 projeté, tous fournisseurs : +11,3 %** (fourchette +8,3 % à +14,8 %), contre +11,2 % avec les seuls indices déjà publiés.

## 2. Volumes mensuels par famille (fictifs)

Backtest à 1 mois sur octobre 2025 → septembre 2026 (12 mois × 8 familles). Le naïf saisonnier reprend le même mois de l'an dernier, corrigé de la tendance sur 12 mois.

| modèle | erreur moyenne |  |
|---|---|---|
| naif_saisonnier | 9,0 % |  |
| holt_winters | 7,3 % | **retenu** |

Prévision octobre 2026 → mars 2027 par famille, comparée à la même période un an plus tôt :

| famille | quantités prévues | vs N-1 |
|---|---|---|
| Climatisation | 478 | +5,3 % |
| Courroies et chaînes | 14 356 | +3,1 % |
| Moteurs électriques | 3 175 | −4,1 % |
| Pompes à chaleur | 442 | −1,8 % |
| Réducteurs | 2 485 | +5,2 % |
| Roulements | 74 455 | −0,1 % |
| Tubes et raccords cuivre | 90 491 | −4,6 % |
| Ventilation | 1 801 | +3,9 % |

## 3. Segmentation des fournisseurs (KMeans, non supervisé)

4 variables par fournisseur sur 3 campagnes : écart moyen, régularité de l'écart, part des campagnes en effet cliquet, taux de rattachement automatique. Nombre de segments choisi par la silhouette : **4** (k=2 : 0,40 ; k=3 : 0,44 ; k=4 : 0,61 ; k=5 : 0,54).

Contrôle : accord avec le profil caché du générateur (indice de Rand ajusté) **1,0** (1 = identique, 0 = hasard). Cet accord parfait vient du générateur, qui sépare nettement les profils. Test de robustesse, en ajoutant du bruit aux variables standardisées (30 tirages) : accord 0,75 avec un bruit d'écart-type 0,5 et 0,36 avec un bruit de 1. Sur données réelles, ce profil n'existe pas : le segment devient l'information, à valider avec l'acheteur.

| fournisseur | segment trouvé | profil caché | écart moyen | campagnes en cliquet |
|---|---|---|---|---|
| Rotavel | Aligné sur les matières | honnete | -0,1 pts | 0% |
| Mekandra | Aligné sur les matières | honnete | +0,2 pts | 0% |
| Tressile | Aligné sur les matières | honnete | +0,3 pts | 0% |
| Brunelle Aéraulique | Aligné sur les matières | honnete | +0,1 pts | 0% |
| Zentrix Technik | Cliquet | cliquet | +1,5 pts | 67% |
| Aerivo Klima | Cliquet | cliquet | +0,6 pts | 33% |
| Kelmaro Antriebe | Opportuniste | opportuniste | +4,4 pts | 33% |
| Vandrelo | Opportuniste | opportuniste | +4,7 pts | 33% |
| Orlenza Thermique | Opportuniste | opportuniste | +5,5 pts | 0% |
| Cuprana | Opportuniste | opportuniste | +6,3 pts | 33% |
| Halderis | Références instables | refs_modifiees | +1,2 pts | 0% |
| Sorvane | Références instables | refs_modifiees | +1,3 pts | 0% |

## 4. Lignes tarifaires anormales (Isolation Forest, campagne 2026)

2 096 lignes comparées sur 4 variables (écart à la hausse justifiée, écart à la médiane de la famille, hausse demandée, poids de la ligne). 63 lignes isolées, dont **42 en écart non justifié** (hausse excessive ou baisse non répercutée), pour 61 874 € d'écart.

Contrôle : 90% des lignes signalées viennent des fournisseurs opportunistes, contre 33% de toutes les lignes. Précision : 93% des lignes signalées dépassent vraiment la hausse justifiée de plus de 3 points ; elles ne couvrent que 6% de ces lignes (le modèle cible les cas les plus atypiques, pas tous les écarts).

| article | fournisseur | demandée | justifiée | écart en € |
|---|---|---|---|---|
| Roulement à rouleaux 6336 E | Kelmaro Antriebe | −0,7 % | −4,2 % | 10 858 € |
| Pompe à chaleur hybride 18 kW monobloc R290 | Orlenza Thermique | +7,0 % | +1,0 % | 10 142 € |
| Pompe à chaleur hybride 17 kW split R410A | Orlenza Thermique | +7,4 % | +0,9 % | 8 050 € |
| Pompe à chaleur eau/eau 20 kW bi-bloc R290 | Orlenza Thermique | +5,2 % | −0,2 % | 6 627 € |
| Pompe à chaleur air/air 12 kW bi-bloc R410A | Orlenza Thermique | +5,2 % | −0,2 % | 5 686 € |
| Climatiseur mural 5 kW réversible R32 blanc | Orlenza Thermique | +5,8 % | +0,2 % | 5 527 € |
| Climatiseur console 7 kW réversible R410A unité int. | Orlenza Thermique | +7,0 % | +0,6 % | 4 292 € |
| Pompe à chaleur eau/eau 19 kW monobloc R410A | Orlenza Thermique | +7,4 % | +1,1 % | 1 788 € |
| Tube cuivre pré-isolé Ø22x1 couronne 50 m | Cuprana | +11,9 % | +4,1 % | 1 700 € |
| Tube cuivre écroui Ø14x1 couronne 50 m | Cuprana | +12,8 % | +4,1 % | 1 236 € |
