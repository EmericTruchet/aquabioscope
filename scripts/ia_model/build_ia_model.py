"""Fabrique les deux parties de l'IA (voir src/aquabioscope/identify.py).

Outil de développement uniquement (l'application n'embarque ni PyTorch ni
OpenCLIP) :

    pip install torch --index-url https://download.pytorch.org/whl/cpu
    pip install open_clip_torch onnx onnxruntime onnxscript
    python scripts/ia_model/build_ia_model.py                        # tout
    python scripts/ia_model/build_ia_model.py --empreintes-seulement  # base d'especes modifiee

1. src/aquabioscope/data/especes_ia.npz : empreintes des noms scientifiques
   de data/species.csv, livrées DANS l'application (à commiter). À
   regénérer (--empreintes-seulement) quand la base d'espèces change : une
   espèce sans empreinte n'est jamais suggérée (le tag manuel reste
   possible). Seuls les noms nouveaux sont calculés, les autres sont repris
   du fichier existant (le calcul complet prend ~30 min sur CPU).
2. scripts/ia_model/dist/aquabioscope-ia-<nom>.zip : le module téléchargé à
   part (visual.onnx, modele.json, LICENCE-MODELE.txt), à publier sur la
   Release GitHub `modele-ia` (pré-version : elle ne doit pas devenir la
   "dernière version" vue par le contrôle de mise à jour). À refaire
   seulement quand on change de modèle : changer alors MODEL_NAME dans
   identify.py, regénérer les deux parties et publier une nouvelle version
   de l'application, qui proposera le nouveau module au lancement.

Le modèle et la précision par défaut sont ceux attendus par l'application
(MODEL_NAME) ; les autres choix servent aux essais.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import open_clip
import torch
from onnxruntime.quantization import QuantType, quantize_dynamic

# modele -> (depot Hugging Face, nom affiche)
MODELS = {
    "bioclip-2": ("hf-hub:imageomics/bioclip-2", "BioCLIP 2"),
    "bioclip-2.5": ("hf-hub:imageomics/bioclip-2.5-vith14", "BioCLIP 2.5 Huge"),
}
PRECISIONS = ("fp16", "int8")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from aquabioscope.identify import EMBEDDINGS_FILE, MODEL_NAME  # noqa: E402
from aquabioscope.species import load_species  # noqa: E402

EMBEDDINGS_PATH = ROOT / "src" / "aquabioscope" / "data" / EMBEDDINGS_FILE

LICENCE = """\
Modèle : {label} (Imageomics Institute) — https://huggingface.co/{repo}
Licence déclarée par les auteurs : MIT.
Seule la partie "image" est fournie ici, convertie au format ONNX (poids en {precision})
par AquaBioScope ; les empreintes des noms d'espèces ont été calculées avec la partie "texte".

Les auteurs demandent de citer l'article BioCLIP 2 (NeurIPS 2025) : référence complète
sur la fiche du modèle ci-dessus.

MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy of this software
and associated documentation files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""


def scientific_names() -> list[str]:
    """Binômes (Genre espèce) de la base ; les entrées sans nom latin ou au
    seul rang du genre ne sont pas suggérables."""
    return sorted({e.nom_scientifique.strip() for e in load_species() if len(e.nom_scientifique.split()) >= 2})


def write_embeddings(model, tokenizer, model_name: str) -> None:
    """Écrit data/especes_ia.npz, en reprenant du fichier existant les
    empreintes déjà calculées pour ce modèle."""
    names = scientific_names()
    known: dict[str, np.ndarray] = {}
    if EMBEDDINGS_PATH.exists():
        previous = np.load(EMBEDDINGS_PATH)
        if str(previous["modele"]) == model_name:
            known = dict(zip((str(n) for n in previous["noms"]), previous["empreintes"]))
    missing = [n for n in names if n not in known]
    print(f"{len(names)} noms scientifiques, {len(missing)} empreintes à calculer")
    with torch.no_grad():
        for i in range(0, len(missing), 256):
            batch = missing[i:i + 256]
            feats = model.encode_text(tokenizer([f"a photo of {n}." for n in batch]))
            feats = (feats / feats.norm(dim=-1, keepdim=True)).numpy().astype(np.float16)
            known.update(zip(batch, feats))
            print(f"  {min(i + 256, len(missing))}/{len(missing)}", flush=True)
    np.savez_compressed(
        EMBEDDINGS_PATH, modele=np.array(model_name), noms=np.array(names),
        empreintes=np.stack([known[n] for n in names]),
    )
    print(f"-> {EMBEDDINGS_PATH} ({EMBEDDINGS_PATH.stat().st_size / 1e6:.0f} Mo)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    default_model, default_precision = MODEL_NAME.rsplit("-", 1)
    parser.add_argument("--modele", choices=sorted(MODELS), default=default_model)
    parser.add_argument("--precision", choices=PRECISIONS, default=default_precision)
    parser.add_argument("--empreintes-seulement", action="store_true",
                        help="regénère seulement data/especes_ia.npz (base d'espèces modifiée)")
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("dist"))
    args = parser.parse_args()
    hf_model, label = MODELS[args.modele]
    name = f"{args.modele}-{args.precision}"

    model, _, preprocess = open_clip.create_model_and_transforms(hf_model)
    tokenizer = open_clip.get_tokenizer(hf_model)
    model.eval()
    image_size = model.visual.image_size
    image_size = image_size[0] if isinstance(image_size, (tuple, list)) else image_size
    norm = next(t for t in preprocess.transforms if type(t).__name__ == "Normalize")

    write_embeddings(model, tokenizer, name)
    if args.empreintes_seulement:
        return

    config = {
        "nom": name,
        "source": hf_model,
        "image_size": int(image_size),
        "mean": [float(v) for v in norm.mean],
        "std": [float(v) for v in norm.std],
        "logit_scale": float(model.logit_scale.exp()),
        "gabarit_texte": "a photo of {}.",
    }

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        fp32 = tmp / "fp32" / "visual.onnx"
        fp32.parent.mkdir()
        torch.onnx.export(
            model.visual, torch.zeros(1, 3, image_size, image_size), str(fp32),
            input_names=["image"], output_names=["embedding"], opset_version=17, dynamo=False,
        )
        if args.precision == "int8":
            # BioCLIP 2.5 en 8 bits : 71 % / 91 % (1re suggestion / top 5) contre 72 % / 90 % en
            # 32 bits sur nos photos de reference ; la quantification par canal n'apporte rien
            quantize_dynamic(str(fp32), str(tmp / "visual.onnx"), weight_type=QuantType.QInt8)
        else:
            import onnx
            from onnxruntime.transformers.float16 import convert_float_to_float16

            onnx.save(convert_float_to_float16(onnx.load(str(fp32)), keep_io_types=True, disable_shape_infer=True), str(tmp / "visual.onnx"))
        (tmp / "modele.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        (tmp / "LICENCE-MODELE.txt").write_text(
            LICENCE.format(label=label, repo=hf_model.removeprefix("hf-hub:"), precision=args.precision[2:] + " bits"),
            encoding="utf-8",
        )

        args.out.mkdir(parents=True, exist_ok=True)
        archive = args.out / f"aquabioscope-ia-{name}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_name in ("visual.onnx", "modele.json", "LICENCE-MODELE.txt"):
                zf.write(tmp / file_name, file_name)
    print(f"-> {archive} ({archive.stat().st_size / 1e6:.0f} Mo)")


if __name__ == "__main__":
    main()
