# DivePhoto — guide d'utilisation

Logiciel de retouche colorimétrique, tag d'espèces et renommage en masse pour photos de plongée sous-marine.

## Installation

Aucune installation requise : un seul fichier, `DivePhoto.exe`, à enregistrer où tu veux et à double-cliquer. Le premier lancement est un peu plus lent que les suivants (quelques secondes, le temps que l'exécutable se décompresse en mémoire).

Windows peut afficher un avertissement SmartScreen ("Windows a protégé votre ordinateur") au premier lancement, le temps que l'exécutable se fasse connaître : clique sur **Informations complémentaires** puis **Exécuter quand même**.

## Utilisation

1. **Nouvelle session** : indique le dossier contenant tes photos brutes (JPG ou RAW), un dossier de sortie (créé automatiquement s'il n'existe pas), le lieu et la date de la plongée, la zone de plongée (utilisée pour filtrer la liste d'espèces — la base ne couvre bien aujourd'hui que Méditerranée et Atlantique Nord-Est), et ton nom pour le crédit photo.
2. **Retouche** : pour chaque photo, choisis l'une des 3 propositions colorimétriques (ou l'original) en cliquant sur une vignette ou avec les touches `1`-`4`, ou règle un preset personnalisé (`5`, sliders). Valide avec Entrée ou en cliquant sur l'aperçu. `Suppr` écarte une photo ratée.
3. **Espèces** : recherche et ajoute les espèces visibles sur la photo (nom commun ou scientifique, avec leur embranchement — 562 espèces référencées). Une espèce absente de la base peut être ajoutée librement, ou recherchée via le bouton "Chercher avec Google Lens" (copie la photo dans le presse-papiers et ouvre Google Lens).
4. **Export** : une fois toutes les photos passées en revue, le logiciel traite les photos retenues en pleine résolution (couleur + incrustation du crédit en bas à droite), les renomme (`lieu_especes_date_numero.jpg`) et les enregistre dans le dossier de sortie, avec un fichier `inventaire_*.xlsx` récapitulant les espèces observées pendant la session.

## Remarques

- La base d'espèces est un point de départ (Méditerranée/Atlantique) et peut contenir des lacunes — les espèces ajoutées "librement" pendant une session ne sont pas mémorisées pour les sessions suivantes.
- Les photos écartées ne sont pas supprimées du dossier d'origine — seules les photos retenues sont copiées (retouchées) vers le dossier de sortie.
