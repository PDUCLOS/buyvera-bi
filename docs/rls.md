# Sécurité par ligne (RLS) : test du 2026-11-03

## Rôles

| Rôle | Filtre | Effet |
|---|---|---|
| `Acheteur` | `dim_acheteur[email] = USERPRINCIPALNAME()` | propagé acheteur → famille → article → tarifs, achats, hausses précalculées, impacts |
| `Direction` | aucun | voit tout |

`dim_fournisseur` et `dim_matiere` ne sont pas filtrées : un acheteur voit les noms de tous les fournisseurs et
toutes les matières dans les segments, mais seuls ses articles portent des chiffres.

## Résultats

Requêtes : `tests/dax/08_rls.dax` (rôle réel) et `tests/dax/09_rls_propagation.dax` (filtre du rôle simulé par email),
lancées avec `scripts/dax_query.ps1 -Role Acheteur`. Capture : `docs/captures/08_rls_acheteur_cvc.png`
(Modélisation → Voir comme → Autre utilisateur + Acheteur).

| Utilisateur | Familles visibles | Articles | € renégociables 2026 | Plafond 2027 |
|---|---|---|---|---|
| acheteur.transmission@buyvera.example | Roulements, Moteurs, Réducteurs, Courroies et chaînes | 1 500 | 124 094 € | +7,6 % |
| acheteur.cvc@buyvera.example | Pompes à chaleur, Climatisation, Tubes et raccords cuivre, Ventilation | 1 500 | 211 083 € | +14,3 % |
| utilisateur absent de `dim_acheteur` | aucune | 0 | — | — |
| rôle Direction | les 8 familles | 3 000 | 335 178 € | +11,2 % |

Contrôles : 124 094 + 211 083 = 335 178 € (total Direction) et identique au calcul Python par acheteur
(`data/controle/hausses_articles.csv`). Le responsable achats n'a aucune famille : il doit être dans le rôle `Direction`.

Limite : le moteur local de Desktop refuse `EffectiveUserName` (il faut un annuaire Active Directory). Le test par
utilisateur passe donc par « Voir comme » dans Desktop, ou par la simulation du filtre en DAX.
