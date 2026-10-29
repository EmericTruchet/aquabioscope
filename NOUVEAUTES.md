# Nouveautés d'AquaBioScope

Chaque section `## x.y.z` devient la note de la Release GitHub correspondante
(voir scripts/release_notes.py), affichée aussi dans l'application au moment
de proposer la mise à jour. À compléter AVANT de taguer une version, en
langage utilisateur.

## 0.5.1

- **Mises à jour plus claires** : l'application affiche maintenant les nouveautés de chaque version avant de l'installer.
- Pendant une mise à jour, l'application explique qu'il suffit de patienter : elle se ferme, s'installe et redémarre toute seule.

## 0.5.0

- **Suggestions d'espèces par IA** : coche « Suggérer les espèces par IA » à l'accueil, et les 5 espèces les plus probables de ta zone de plongée s'affichent pour chaque photo, à ajouter d'un clic (ou Ctrl+1 à 5). Sur nos photos de test, la bonne espèce est la première suggestion 7 fois sur 10, et parmi les cinq 9 fois sur 10. L'IA tourne sur ton ordinateur, sans connexion : le module (environ 450 Mo) est téléchargé une seule fois.
- **Identifier une zone** (Ctrl+I) : encadre un sujet précis (deuxième espèce, animal petit dans le cadre) pour que l'IA ne regarde que lui.
- **Google Lens en renfort** : quand l'IA hésite, elle le signale ; Lens reçoit la zone encadrée, et le nom que tu y copies est directement recherché à ton retour dans AquaBioScope.
- L'écran des espèces montre la photo corrigée et recadrée.
- Base d'espèces : corrections (Salmacine, Dentelle de Neptune).

## 0.4.1

- Récapitulatif avant l'export (photos retenues, écartées, espèces, photos sans espèce), avec retour possible aux photos.

## 0.4.0

- **Photo précédente** (Retour arrière) : rouvre la photo d'avant avec tout ce qui avait été choisi, y compris une photo écartée par erreur.
- **Séries** : les photos prises à quelques secondes d'intervalle sont repérées ; un clic leur applique la même correction, le même recadrage et les mêmes espèces.
