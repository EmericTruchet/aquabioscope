# Publier AquaBioScope sur le Microsoft Store

Les utilisateurs qui installent l'application depuis le Store n'ont **aucune
alerte SmartScreen/Defender** : Microsoft signe lui-même le paquet après
certification. Le Store gère aussi les **mises à jour automatiques** (la
vérification intégrée à l'application est désactivée dans ce cas, voir
`src/aquabioscope/updater.py`).

## Étapes à faire une seule fois (compte Microsoft)

1. Créer un compte développeur **particulier** (gratuit) :
   <https://storedeveloper.microsoft.com> → « Get started » → compte
   individuel. Vérification d'identité (pièce d'identité + selfie), quelques
   jours au plus.
2. Dans l'espace partenaires (<https://partner.microsoft.com/dashboard>) :
   **Applications et jeux → Nouveau produit → Application MSIX ou PWA**,
   réserver le nom **AquaBioScope**.
3. Ouvrir **Gestion des produits → Identité du produit** et noter les 3
   valeurs :
   - `Package/Identity/Name` (ex. `12345EmericTruchet.AquaBioScope`)
   - `Package/Identity/Publisher` (ex. `CN=XXXXXXXX-XXXX-...`)
   - `Package/Properties/PublisherDisplayName` (ex. `Emeric Truchet`)

## À chaque version

1. Compiler en mode dossier puis construire le paquet :
   ```powershell
   .venv\Scripts\pyinstaller AquaBioScope-installer.spec --noconfirm
   .\store\build_msix.ps1 -IdentityName "<Name>" -Publisher "<Publisher>" -PublisherDisplayName "<PublisherDisplayName>"
   ```
   → `dist\AquaBioScope.msix`
2. Dans l'espace partenaires : **Nouvelle soumission → Packages**, téléverser
   le `.msix`, remplir la fiche (description, captures d'écran : voir
   `site/screenshots`, catégorie « Photo et vidéo », âge : tout public,
   politique de confidentialité : l'application ne collecte aucune donnée —
   une page simple sur le site suffit), puis soumettre. Certification : de
   quelques heures à 3 jours ouvrés.

Le numéro de version du paquet doit augmenter à chaque soumission (il est
tiré de `src/aquabioscope/__init__.py`).

## Points d'attention

- La capacité `runFullTrust` (application de bureau classique) est
  normale pour une appli PyInstaller ; la certification peut demander de la
  justifier : « application de bureau Win32 empaquetée, accès aux dossiers
  de photos choisis par l'utilisateur ».
- Les presets personnalisés sont enregistrés dans `%APPDATA%\AquaBioScope` ;
  dans une appli Store, Windows redirige ce dossier vers l'espace privé du
  paquet (transparent pour l'utilisateur, mais ils ne sont pas partagés avec
  une éventuelle version installée hors Store).
