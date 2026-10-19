# AquaBioScope — guide d'utilisation

Logiciel de retouche colorimétrique, tag d'espèces et renommage en masse pour photos de plongée sous-marine.

## Installation

Sous Windows, deux possibilités :

- **`AquaBioScope-Setup.exe` (recommandé)** : installe l'application pour ton compte (pas besoin d'être administrateur), avec un raccourci dans le menu Démarrer. Elle se **met à jour toute seule** : au démarrage, un bandeau signale une nouvelle version, un clic sur « Mettre à jour maintenant » la télécharge, l'installe et relance l'application.
- **`AquaBioScope.exe` (portable)** : un seul fichier, à enregistrer où tu veux et à double-cliquer, sans installation. Le bandeau signale aussi les nouvelles versions, mais le téléchargement se fait à la main.

Windows peut afficher un avertissement SmartScreen ("Windows a protégé votre ordinateur") au premier lancement : clique sur **Informations complémentaires** puis **Exécuter quand même**. (Pas d'avertissement avec la version Microsoft Store, quand elle sera publiée.)

## Utilisation

1. **Nouvelle session** : indique le dossier contenant tes photos brutes (JPG ou RAW), un dossier de sortie (créé automatiquement s'il n'existe pas), le lieu et la date de la plongée, la zone de plongée (utilisée pour pré-filtrer la liste d'espèces quand la base a une couverture suffisante pour cette zone — sinon la base complète est proposée), et ton nom pour le crédit photo.
2. **Retouche** : pour chaque photo, choisis une correction en cliquant sur une vignette ou avec les touches `1`-`5` :
   - `1` **Original** ;
   - `2` **Naturel** : correction équilibrée, à essayer en premier ;
   - `3` **Corrigé profondeur** : photos en lumière naturelle très bleues (rouge restauré, voile de l'eau retiré) ;
   - `4` **Macro / flash** : photos au flash (contraste, couleurs, netteté) ;
   - `5` **Eau verte** : Atlantique, Manche, lacs.

   Les corrections s'adaptent à chaque photo (une photo au flash n'est pas « recolorée » comme une photo à 20 m sans flash). La tuile **+** crée un preset personnalisé (curseurs), mémorisé pour les sessions suivantes. Le preset choisi est repris automatiquement pour la photo suivante.
   **Recadrer** (bouton ou touche `C`) : trace le cadre, choisis des proportions (libre, 3:2, 4:3, 16:9, carré…) ; le bouton « Comme la photo précédente » reprend le même cadrage.
   Valide avec Entrée ou en cliquant sur l'aperçu. `Suppr` écarte une photo ratée.
3. **Espèces** : recherche et ajoute les espèces visibles sur la photo, par nom commun, nom usuel de plongeur (« chapon », « mostelle », « planaire »…) ou nom scientifique, avec leur embranchement — plus de 8600 espèces référencées, filtrées par zone de plongée. Une espèce absente de la base peut être ajoutée librement, ou recherchée via le bouton "Chercher avec Google Lens" (copie la photo dans le presse-papiers et ouvre Google Lens).
   **Mêmes espèces que la photo précédente** (`Ctrl+R`) : pratique pour une série sur le même sujet. **Retour au filtre** (`Échap`) : revient au choix de la correction de cette photo, sans perdre les espèces déjà taguées.
4. **Export** : une fois toutes les photos passées en revue, le logiciel traite les photos retenues en pleine résolution (couleur + incrustation du crédit en bas à droite), les renomme (`lieu_especes_date_numero.jpg`) et les enregistre dans le dossier de sortie, avec un fichier `inventaire_*.xlsx` récapitulant les espèces observées pendant la session.

## Remarques

- La base d'espèces couvre le monde entier mais reste un point de départ et peut contenir des lacunes — les espèces ajoutées "librement" pendant une session ne sont pas mémorisées pour les sessions suivantes.
- Les photos RAW reprennent le rendu de ton appareil et ses corrections d'objectif (distorsion, vignetage, bruit — indispensables sur les compacts comme les Olympus TG), complétés à l'export par le fin détail du RAW, en pleine résolution.
- Les photos écartées ne sont pas supprimées du dossier d'origine — seules les photos retenues sont copiées (retouchées) vers le dossier de sortie.
