# Brouillon de post LinkedIn (à relire et publier soi-même)

Chaque année, c'est la même lettre : « Suite à l'évolution des matières premières, nos tarifs augmentent de 6 % au 1er janvier. »

Après 20 ans en distribution industrielle, j'ai voulu outiller la question que tout acheteur se pose : cette hausse est-elle justifiée ?

J'ai construit un rapport Power BI qui confronte la hausse demandée à l'évolution réelle des matières qui composent chaque produit (indices INSEE : cuivre, aluminium, nickel, acier, plastiques).

Sur une campagne simulée de 16 M€ d'achats :
→ les fournisseurs demandent +1,2 % quand les matières justifient −0,6 %
→ 335 k€ sont renégociables, dont 120 k€ chez un seul fournisseur
→ et pour 2027, les cours actuels justifient déjà +11 % : l'acheteur le sait avant le fournisseur

Ce que j'ai mis dedans :
• un modèle en étoile avec table pont article × matière, généré en TMDL et versionné sous Git
• des alertes matières avec plan d'action : convoquer le fournisseur quand ça baisse, anticiper les achats quand ça monte
• une fiche de négociation avec argument rédigé et simulateur de contre-proposition
• la mesure du décalage : les hausses sont-elles répercutées plus vite que les baisses ?
• la sécurité par acheteur (RLS), testée

Puis j'ai refait la même analyse en tableau de bord Claude, sur les mêmes données. Les 5 chiffres clés sont identiques au centime. Power BI pour piloter, Claude pour préparer le rendez-vous : chaque outil a son usage, et les limites sont écrites.

Les tarifs sont fictifs, les indices sont réels.
Le projet complet : github.com/PDUCLOS/buyvera-bi

#PowerBI #Achats #DataAnalyst #BusinessIntelligence #Négociation
