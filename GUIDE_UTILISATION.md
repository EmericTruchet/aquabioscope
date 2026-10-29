# AquaBioScope — guide d'utilisation

Logiciel de retouche colorimétrique, tag d'espèces et renommage en masse pour photos de plongée sous-marine.

## Installation

Sous Windows, deux possibilités :

- **`AquaBioScope-Setup.exe` (recommandé)** : installe l'application pour ton compte (pas besoin d'être administrateur), avec un raccourci dans le menu Démarrer. Elle se **met à jour toute seule** : au démarrage, un bandeau signale une nouvelle version, un clic sur « Mettre à jour maintenant » la télécharge, l'installe et relance l'application.
- **`AquaBioScope.exe` (portable)** : un seul fichier, à enregistrer où tu veux et à double-cliquer, sans installation. Le bandeau signale aussi les nouvelles versions, mais le téléchargement se fait à la main.

Windows peut afficher un avertissement SmartScreen ("Windows a protégé votre ordinateur") au premier lancement : clique sur **Informations complémentaires** puis **Exécuter quand même**. (Pas d'avertissement avec la version Microsoft Store, quand elle sera publiée.)

## Utilisation

1. **Nouvelle session** : indique le dossier contenant tes photos brutes (JPG ou RAW), un dossier de sortie (créé automatiquement s'il n'existe pas), le lieu et la date de la plongée, la zone de plongée (utilisée pour pré-filtrer la liste d'espèces quand la base a une couverture suffisante pour cette zone — sinon la base complète est proposée), et ton nom pour le crédit photo. Coche **Suggérer les espèces par IA** pour que le logiciel propose les espèces de chaque photo (voir l'étape 3) : la première fois, il télécharge un module d'environ 450 Mo, qui fonctionne ensuite sans connexion.
2. **Retouche** : pour chaque photo, choisis une correction en cliquant sur une vignette ou avec les touches `1`-`5` :
   - `1` **Original** ;
   - `2` **Naturel** : correction équilibrée, à essayer en premier ;
   - `3` **Corrigé profondeur** : photos en lumière naturelle très bleues (rouge restauré, voile de l'eau retiré) ;
   - `4` **Macro / flash** : photos au flash (contraste, couleurs, netteté) ;
   - `5` **Eau verte** : Atlantique, Manche, lacs.

   Les corrections s'adaptent à chaque photo (une photo au flash n'est pas « recolorée » comme une photo à 20 m sans flash). La tuile **+** crée un preset personnalisé (curseurs), mémorisé pour les sessions suivantes. Le preset choisi est repris automatiquement pour la photo suivante.
   **Recadrer** (bouton ou touche `C`) : trace le cadre, choisis des proportions (libre, 3:2, 4:3, 16:9, carré…) ; le bouton « Comme la photo précédente » reprend le même cadrage.
   Valide avec Entrée ou en cliquant sur l'aperçu. `Suppr` écarte une photo ratée.
   **Photo précédente** (bouton ou `Retour arrière`) : rouvre la photo d'avant avec tout ce qui avait été choisi (correction, recadrage, espèces), pour la corriger ou récupérer une photo écartée par erreur. Une fois revalidée, tu reprends là où tu en étais.
   **Séries** : quand plusieurs photos ont été prises à quelques secondes d'intervalle (rafale sur un même sujet), le bouton **Valider pour la série** (ou `S`) apparaît. Il montre les photos de la série avec la correction choisie : décoche celles qui ne vont pas avec les autres. Les photos cochées reçoivent la même correction, le même recadrage et les mêmes espèces ; les décochées restent à traiter normalement.
3. **Espèces** : recherche et ajoute les espèces visibles sur la photo, par nom commun, nom usuel de plongeur ou de pêcheur (« chapon », « mostelle », « planaire », « dormeur »…) ou nom scientifique, avec leur embranchement — plus de 9600 espèces référencées, filtrées par zone de plongée. Une espèce absente de la base peut être ajoutée librement (son nom est alors proposé anonymement, sans la photo, à l'équipe AquaBioScope pour enrichir la base), ou recherchée via le bouton "Chercher avec Google Lens" : il copie la photo (ou la zone encadrée pour l'IA) dans le presse-papiers et ouvre Google Lens, où il suffit de la coller (`Ctrl+V`). Copie ensuite le nom trouvé (`Ctrl+C`) : en revenant dans AquaBioScope, il est directement recherché dans la base.
   **Suggestions IA** (si l'option est cochée) : les 5 espèces les plus probables parmi celles de la zone de plongée s'affichent au-dessus de la recherche, avec un pourcentage de confiance ; un clic (ou `Ctrl+1` à `Ctrl+5`) ajoute l'espèce. Quand l'IA hésite (1ʳᵉ suggestion sous 50 %), elle le signale : c'est le moment d'essayer Google Lens. Ce sont des suggestions, à vérifier : sur nos photos de test, la bonne espèce est la première suggestion 7 fois sur 10 et figure parmi les cinq 9 fois sur 10. **Identifier une zone** (`Ctrl+I`) : encadre un sujet précis (deuxième espèce, animal petit dans le cadre) pour que l'IA ne regarde que lui.
   **Mêmes espèces que la photo précédente** (`Ctrl+R`) : pratique pour une série sur le même sujet. **Retour au filtre** (`Échap`) : revient au choix de la correction de cette photo, sans perdre les espèces déjà taguées.
4. **Export** : une fois toutes les photos passées en revue, un récapitulatif s'affiche (photos retenues, écartées, nombre d'espèces, photos sans espèce) : « ← Revenir aux photos » permet encore de corriger, « Exporter » lance l'export. Le logiciel traite alors les photos retenues en pleine résolution (couleur + incrustation du crédit en bas à droite), les renomme (`lieu_especes_date_numero.jpg`) et les enregistre dans le dossier de sortie, avec un fichier `inventaire_*.xlsx` récapitulant les espèces observées pendant la session.

## Remarques

- La base d'espèces couvre le monde entier mais reste un point de départ et peut contenir des lacunes — les espèces ajoutées "librement" pendant une session ne sont pas mémorisées pour les sessions suivantes.
- Les photos RAW reprennent le rendu de ton appareil et ses corrections d'objectif (distorsion, vignetage, bruit — indispensables sur les compacts comme les Olympus TG), complétés à l'export par le fin détail du RAW, en pleine résolution.
- Les photos écartées ne sont pas supprimées du dossier d'origine — seules les photos retenues sont copiées (retouchées) vers le dossier de sortie.
