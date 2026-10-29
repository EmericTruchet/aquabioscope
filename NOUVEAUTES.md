# Nouveautés d'AquaBioScope

Une section par version, en langage utilisateur, à compléter AVANT de taguer :
`## x.y.z · date · titre court`, puis une liste à puces.
Elle devient la note de la Release GitHub et s'affiche dans l'application
avant la mise à jour (scripts/release_notes.py) ; le fichier entier génère
aussi la page « Nouveautés » du site (scripts/build_notes_page.py).

## 0.5.2 · 29 octobre 2026 · 📬 Vos espèces manquantes nous arrivent

- 📬 **Espèces manquantes remontées** : quand tu ajoutes une espèce absente de la base (« Ajouter comme espèce non répertoriée »), son nom nous est proposé, anonymement et sans la photo, pour qu'on l'ajoute dans une prochaine version. Hors connexion, la demande partira au prochain lancement.
- 📰 **Page Nouveautés** sur le site : l'historique de toutes les versions.

## 0.5.1 · 29 octobre 2026 · 🔔 Des mises à jour plus claires

- 📝 **Les nouveautés s'affichent avant d'installer** une mise à jour.
- ⏳ **Consignes pendant la mise à jour** : l'application explique qu'il suffit de patienter ; elle se ferme, s'installe et redémarre toute seule.

## 0.5.0 · 29 octobre 2026 · ✨ L'IA t'aide à identifier tes espèces

- ✨ **Suggestions d'espèces par IA** : coche « Suggérer les espèces par IA » à l'accueil, et les 5 espèces les plus probables de ta zone de plongée s'affichent pour chaque photo, à ajouter d'un clic (ou Ctrl+1 à 5). Sur nos photos de test, la bonne espèce est la première suggestion 7 fois sur 10, et parmi les cinq 9 fois sur 10.
- 🔒 **Sur ton ordinateur, sans connexion** : le module IA (environ 450 Mo) est téléchargé une seule fois ; tes photos ne quittent jamais ton PC.
- 🎯 **Identifier une zone** (Ctrl+I) : encadre un sujet précis (deuxième espèce, animal petit dans le cadre) pour que l'IA ne regarde que lui.
- 🔍 **Google Lens en renfort** : quand l'IA hésite, elle le signale ; Lens reçoit la zone encadrée, et le nom que tu y copies est directement recherché à ton retour dans AquaBioScope.
- 🖼️ L'écran des espèces montre la photo corrigée et recadrée.
- 🐚 Base d'espèces : corrections (Salmacine, Dentelle de Neptune).

## 0.4.1 · 20 octobre 2026 · 📋 Un récapitulatif avant l'export

- 📋 **Récapitulatif avant l'export** : photos retenues, écartées, nombre d'espèces, photos sans espèce, avec retour possible aux photos pour corriger.

## 0.4.0 · 20 octobre 2026 · 📸 Séries et retour arrière

- ↩️ **Photo précédente** (Retour arrière) : rouvre la photo d'avant avec tout ce qui avait été choisi, y compris une photo écartée par erreur.
- 📸 **Séries** : les photos prises à quelques secondes d'intervalle sont repérées ; un clic leur applique la même correction, le même recadrage et les mêmes espèces.

## 0.3.1 · 20 octobre 2026 · 🇫🇷 9600 espèces avec TAXREF

- 🐠 **Base portée à plus de 9600 espèces** grâce à TAXREF (Muséum national d'Histoire naturelle) : noms français officiels et espèces des outre-mer.

## 0.3.0 · 19 octobre 2026 · 🎨 RAW, recadrage et mise à jour automatique

- 📷 **RAW** : les photos RAW gardent le rendu et les corrections d'objectif de l'appareil, avec le fin détail du RAW en pleine résolution.
- 🎨 **Corrections couleur repensées**, dosées selon la dominante de l'eau.
- ✂️ **Recadrage**, retour au choix du filtre, reprise des espèces de la photo précédente.
- 🐟 **8600 espèces** filtrées par zone de plongée, trouvables par leurs noms de plongeurs (« chapon », « mostelle »…).
- 🔄 **Installateur Windows et mise à jour automatique.**

## 0.2.0 · 16 septembre 2026 · 🌊 Naissance d'AquaBioScope

- 🌊 **Première version publique** pour Windows, macOS et Linux : retouche couleur des photos sous-marines, tag d'espèces, renommage et export avec crédit photo et inventaire Excel.
