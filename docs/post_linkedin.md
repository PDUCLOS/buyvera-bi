# Brouillon de post LinkedIn (à relire et publier soi-même)

Vidéo à joindre : `docs/video/buyvera_linkedin.mp4` (44 s, format 4:5, sous-titrée, lisible sans le son).
Miniature : `docs/video/miniature_linkedin.png`.

---

Chaque année, la même lettre : « Suite à l'évolution des matières premières, nos tarifs augmentent de 6,2 % au 1er janvier. »

Après 20 ans en distribution industrielle, j'ai voulu outiller la question que tout acheteur se pose : cette hausse est-elle justifiée ?

J'ai construit un outil Power BI qui confronte chaque tarif à l'évolution réelle des matières qui composent le produit (indices INSEE : cuivre, aluminium, nickel, acier, plastiques).

Sur l'exemple de la vidéo :
→ le fournisseur demande +6,2 %, ses matières n'en justifient que +0,5 %
→ appliqué à ses 108 références et aux volumes achetés : 120 k€ à renégocier
→ 35 références portent 80 % de l'enjeu : on commence par elles
→ pour 2027, les cours justifient déjà +11,2 % : l'acheteur connaît le plafond avant de recevoir le tarif

Et après la négociation :
→ 624 k€ payés au-dessus du meilleur prix du groupe, entre trois sites
→ 524 k€ obtenus en trois campagnes, 51 % du potentiel chiffré

Sous le capot :
• un modèle Power BI généré par script et versionné sous Git, 103 mesures DAX, sécurité par acheteur
• chaque chiffre recalculé en Python : écart nul avec le DAX
• du machine learning gardé seulement s'il bat un modèle naïf (sur les cours des métaux, le naïf gagne : l'outil le dit)

Les tarifs et les fournisseurs sont fictifs, les indices matières sont réels.
Le projet complet : github.com/PDUCLOS/buyvera-bi

#PowerBI #Achats #DataAnalyst #BusinessIntelligence #Négociation
