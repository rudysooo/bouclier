# Notes de version

## 3.1.0

### Corrigé
- **Important :** sans OCR (Tesseract), Bouclier annonçait « Aucune donnée sensible repérée » sur une image pleine de données. Il indique maintenant clairement que le texte n'a pas été lu. Si vous utilisez la version 1.0, mettez à jour.
- Documents Word, Excel, PowerPoint : les auteurs restaient dans le suivi des modifications et les commentaires, le texte supprimé était conservé, les images internes et la vignette gardaient leurs métadonnées (GPS compris).
- Images à plusieurs pages (TIFF, PNG et WebP animés) : le nettoyeur ne gardait que la première.
- Détection : IBAN et adresses en minuscules, noms en majuscules, numéros de carte suivis d'autres chiffres, style « étoiles » sur les adresses.
- Anti-arnaque : petits montants (« 1,99 € »), arnaques au compte formation et messages en anglais.
- Lien de secours pour installer l'OCR.
- Panneau de résultat de l'anti-arnaque qui débordait.

### Changé
- Le nettoyeur produit la version finale d'un document Office : modifications acceptées et commentaires supprimés.
- Les éléments qui ne peuvent pas être nettoyés sont signalés « À vérifier ».
- Le numéro de version publié rejoint celui de l'application (la version publiée précédente s'appelait 1.0).

## 1.0

Première version publiée.
