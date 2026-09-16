<p align="center"><img src="branding/logo-full.png" width="240" alt="Logo AquaBioScope"></p>

# AquaBioScope

Logiciel de retouche colorimétrique, renommage en masse et tag d'espèces pour photos de plongée sous-marine dans le monde entier, destiné à être distribué comme exécutable autonome (Windows, macOS, Linux).

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

## Publier une nouvelle version

1. Monter le numéro dans `src/aquabioscope/__init__.py` (`__version__ = "x.y.z"`) — c'est la seule
   source de vérité, `pyproject.toml` la lit dynamiquement.
2. Commiter, puis taguer et pousser le tag :
   ```powershell
   git tag vx.y.z
   git push origin vx.y.z
   ```
3. Le tag déclenche `.github/workflows/build.yml`, qui compile **Windows, macOS (Intel +
   Apple Silicon) et Linux**, et publie les 4 fichiers sur une **Release GitHub** correspondant au
   tag.
4. La page de téléchargement (`site/index.html`) va chercher toute seule (en JavaScript, au
   chargement) la dernière Release via l'API GitHub : version affichée et liens de téléchargement
   se mettent à jour automatiquement, sans ré-upload FTP des exécutables.

Le workflow peut aussi être lancé manuellement (onglet *Actions* du dépôt, bouton *Run workflow*) ;
dans ce cas il compile les 3 plateformes en artefacts téléchargeables, mais ne publie pas de
Release (seul un tag `v*` le fait).

## Compilation manuelle macOS / Linux

PyInstaller ne fait pas de cross-compilation : impossible de générer une app macOS ou Linux depuis
Windows, il faut un vrai Mac / une vraie machine Linux (ou passer par le workflow CI ci-dessus).

Pour compiler manuellement sur un vrai Mac :

```bash
python3 -m venv .venv
.venv/bin/pip install -e . pyinstaller
.venv/bin/pyinstaller AquaBioScope-macos.spec --noconfirm
```

Le résultat est `dist/AquaBioScope.app`. L'app n'étant pas signée par un compte développeur Apple
(payant), macOS affichera un avertissement « développeur non identifié » au premier lancement :
l'utilisateur doit faire clic droit → *Ouvrir* → *Ouvrir* (une seule fois).

Pour compiler manuellement sur Linux (voir `.github/workflows/build.yml` pour l'assemblage complet
en AppImage) :

```bash
python3 -m venv .venv
.venv/bin/pip install -e . pyinstaller
.venv/bin/pyinstaller AquaBioScope-linux.spec --noconfirm
```

Le résultat est le dossier `dist/AquaBioScope/` (à distribuer en entier), ou l'AppImage produite
par le workflow pour un fichier unique portable.

## Tests

```powershell
.venv\Scripts\python -m unittest discover -s tests
```

## État du projet

Pipeline complet fonctionnel : accueil (dossiers, lieu, date, zone, crédit) → revue colorimétrique (3 presets + original) → tags d'espèces (base mondiale, 5300+ espèces) → export (retouche pleine résolution, crédit incrusté, renommage, EXIF, inventaire Excel) → compilation en exécutable Windows/macOS/Linux.
