# DivePhoto

Logiciel de retouche colorimétrique, renommage en masse et tag d'espèces pour photos de plongée sous-marine (Méditerranée / Atlantique), destiné à être distribué comme exécutable Windows autonome.

## Développement

```powershell
python -m venv .venv
.venv\Scripts\pip install -e .
.venv\Scripts\python -m divephoto.app
```

## Compilation de l'exécutable Windows

```powershell
.venv\Scripts\pip install pyinstaller
.venv\Scripts\pyinstaller DivePhoto.spec --noconfirm
```

Le résultat est généré dans `dist\DivePhoto\` (à distribuer en entier, voir `GUIDE_UTILISATION.md`).

## Tests

```powershell
.venv\Scripts\python -m unittest discover -s tests
```

## État du projet

Pipeline complet fonctionnel : accueil (dossiers, lieu, date, zone, crédit) → revue colorimétrique (3 presets + original) → tags d'espèces (base Méditerranée/Atlantique) → export (retouche pleine résolution, crédit incrusté, renommage, EXIF, inventaire Excel) → compilation en exécutable Windows autonome.
