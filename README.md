<p align="center"><img src="branding/logo-full.png" width="240" alt="Logo AquaBioScope"></p>

# AquaBioScope

Logiciel de retouche colorimétrique, renommage en masse et tag d'espèces pour photos de plongée sous-marine (Méditerranée / Atlantique), destiné à être distribué comme exécutable Windows autonome.

## Développement

```powershell
python -m venv .venv
.venv\Scripts\pip install -e .
.venv\Scripts\python -m aquabioscope.app
```

## Compilation de l'exécutable Windows

```powershell
.venv\Scripts\pip install pyinstaller
.venv\Scripts\pyinstaller AquaBioScope.spec --noconfirm
```

Le résultat est généré dans `dist\AquaBioScope\` (à distribuer en entier, voir `GUIDE_UTILISATION.md`).

## Compilation de l'application macOS

PyInstaller ne fait pas de cross-compilation : impossible de générer une app macOS depuis Windows.
La compilation se fait automatiquement sur des machines macOS via GitHub Actions
(`.github/workflows/build-macos.yml`), déclenchée manuellement (onglet *Actions* du dépôt,
bouton *Run workflow*) ou à la création d'un tag `v*`. Elle produit deux archives
(`AquaBioScope-macos-intel.zip` et `AquaBioScope-macos-apple-silicon.zip`) téléchargeables comme
artefacts du run, ou attachées automatiquement à la Release si déclenchée par un tag.

Pour compiler manuellement sur un vrai Mac :

```bash
python3 -m venv .venv
.venv/bin/pip install -e . pyinstaller
.venv/bin/pyinstaller AquaBioScope-macos.spec --noconfirm
```

Le résultat est `dist/AquaBioScope.app`. L'app n'étant pas signée par un compte développeur Apple
(payant), macOS affichera un avertissement « développeur non identifié » au premier lancement :
l'utilisateur doit faire clic droit → *Ouvrir* → *Ouvrir* (une seule fois).

## Tests

```powershell
.venv\Scripts\python -m unittest discover -s tests
```

## État du projet

Pipeline complet fonctionnel : accueil (dossiers, lieu, date, zone, crédit) → revue colorimétrique (3 presets + original) → tags d'espèces (base Méditerranée/Atlantique) → export (retouche pleine résolution, crédit incrusté, renommage, EXIF, inventaire Excel) → compilation en exécutable Windows autonome.
