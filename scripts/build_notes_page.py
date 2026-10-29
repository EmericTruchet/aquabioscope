"""Génère la page « Nouveautés » du site (site/nouveautes.html) à partir de
NOUVEAUTES.md. Lancé par .github/workflows/site.yml à chaque mise en ligne :
la page n'est pas versionnée, NOUVEAUTES.md reste la seule source.

Usage : python scripts/build_notes_page.py   (aperçu local : ouvrir site/nouveautes.html)
"""
from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "NOUVEAUTES.md"
OUTPUT = ROOT / "site" / "nouveautes.html"

# Un emoji (avec ses variantes / drapeaux) en tete de puce, mis a part dans la page.
_EMOJI = re.compile(r"^((?:[\U0001F000-\U0001FAFF☀-➿⬀-⯿↩⏳]"
                    r"[️\U0001F3FB-\U0001F3FF]?‍?)+)\s*")


def parse(text: str) -> list[dict]:
    """[{version, date, title, items: [(emoji, texte)]}], dans l'ordre du fichier."""
    versions: list[dict] = []
    for line in text.splitlines():
        if line.startswith("## "):
            parts = [p.strip() for p in line[3:].split("·")]
            versions.append({
                "version": parts[0].lstrip("vV"),
                "date": parts[1] if len(parts) > 1 else "",
                "title": parts[2] if len(parts) > 2 else "",
                "items": [],
            })
        elif versions and line.startswith("- "):
            item = line[2:].strip()
            match = _EMOJI.match(item)
            emoji = match.group(1) if match else "•"
            versions[-1]["items"].append((emoji, item[match.end():] if match else item))
    return versions


def inline(text: str) -> str:
    """Échappe le HTML puis rend le **gras** du Markdown."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(text, quote=False))


def render(versions: list[dict]) -> str:
    cards = []
    for i, v in enumerate(versions):
        items = "\n".join(
            f'        <li><span class="emoji">{e}</span><span>{inline(t)}</span></li>' for e, t in v["items"]
        )
        badge = '<span class="badge">Dernière version</span>' if i == 0 else ""
        cards.append(f"""    <article class="release{' latest' if i == 0 else ''}" id="v{html.escape(v['version'])}">
      <div class="dot"></div>
      <div class="card">
        <div class="meta"><span class="version">v{html.escape(v['version'])}</span>{badge}<span class="date">{html.escape(v['date'])}</span></div>
        <h2>{inline(v['title'])}</h2>
        <ul>
{items}
        </ul>
      </div>
    </article>""")
    return TEMPLATE.replace("{{RELEASES}}", "\n".join(cards))


TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AquaBioScope — Nouveautés</title>
<meta name="description" content="Toutes les nouveautés d'AquaBioScope, version par version.">
<link rel="icon" type="image/png" href="favicon.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<!-- Page generee par scripts/build_notes_page.py a partir de NOUVEAUTES.md : ne pas modifier a la main. -->
<style>
  :root {
    --ink: #14262E; --navy: #0C232B; --navy-2: #123540;
    --teal: #1298A5; --teal-dark: #0E7C86; --teal-soft: #E4F3F2;
    --coral: #DD7A42; --coral-soft: #FBEADC;
    --sand: #F7F2E7; --card: #FFFFFF; --border: #E7DFCC; --text-secondary: #5C6A66;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--sand); color: var(--ink); line-height: 1.6;
         font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; }
  h1, h2 { font-family: 'Fraunces', Georgia, serif; font-weight: 700; letter-spacing: -0.01em; }
  a { color: var(--teal-dark); }
  .wrap { max-width: 820px; margin: 0 auto; padding: 0 24px; }

  header.hero {
    background: radial-gradient(circle at 18% 8%, rgba(18,152,165,0.35), transparent 46%),
                linear-gradient(165deg, var(--navy-2), var(--navy) 65%);
    color: white; text-align: center; padding: 40px 0 0;
  }
  header.hero .wrap { padding-bottom: 40px; }
  header.hero .back { display: inline-block; color: rgba(255,255,255,0.8); text-decoration: none;
                      font-size: 0.9rem; margin-bottom: 18px; }
  header.hero .back:hover { color: white; }
  header.hero img { width: 84px; height: 84px; margin: 0 auto 8px; display: block; }
  header.hero h1 { font-size: 2.4rem; margin: 0 0 6px; }
  header.hero p { margin: 0; color: rgba(255,255,255,0.78); }
  svg.wave { display: block; width: 100%; height: 40px; }

  main { padding: 28px 0 60px; }
  .timeline { position: relative; padding-left: 34px; }
  .timeline::before { content: ""; position: absolute; left: 11px; top: 8px; bottom: 8px; width: 2px;
                      background: linear-gradient(var(--teal), var(--border)); }
  .release { position: relative; margin-bottom: 26px; }
  .release .dot { position: absolute; left: -30px; top: 24px; width: 16px; height: 16px; border-radius: 50%;
                  background: var(--sand); border: 3px solid var(--teal); }
  .release.latest .dot { background: var(--teal); box-shadow: 0 0 0 6px rgba(18,152,165,0.18); }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 22px 26px;
          box-shadow: 0 1px 2px rgba(12,35,43,0.04); }
  .release.latest .card { border-color: var(--teal); box-shadow: 0 8px 28px rgba(14,124,134,0.12); }
  .meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 0.85rem; }
  .version { font-weight: 700; color: var(--teal-dark); background: var(--teal-soft);
             border-radius: 999px; padding: 2px 12px; }
  .badge { font-weight: 600; color: #8A4B22; background: var(--coral-soft); border-radius: 999px; padding: 2px 12px; }
  .date { color: var(--text-secondary); margin-left: auto; }
  .card h2 { font-size: 1.35rem; margin: 10px 0 12px; color: var(--navy); }
  .card ul { list-style: none; margin: 0; padding: 0; }
  .card li { display: flex; gap: 12px; padding: 7px 0; border-top: 1px solid #F3EEE0; }
  .card li:first-child { border-top: none; }
  .card li .emoji { flex: 0 0 1.6em; font-size: 1.15rem; line-height: 1.5; text-align: center; }
  .card li strong { color: var(--navy); }

  .cta { text-align: center; margin-top: 36px; }
  .cta a { display: inline-block; background: var(--teal-dark); color: white; text-decoration: none;
           font-weight: 600; padding: 12px 26px; border-radius: 10px; }
  .cta a:hover { background: var(--navy-2); }
  footer { text-align: center; color: var(--text-secondary); font-size: 0.85rem; padding: 0 24px 40px; }

  @media (max-width: 560px) {
    .timeline { padding-left: 24px; }
    .timeline::before { left: 6px; }
    .release .dot { left: -24px; }
    .card { padding: 18px; }
    .date { margin-left: 0; width: 100%; }
  }
</style>
</head>
<body>

<header class="hero">
  <div class="wrap">
    <a class="back" href="index.html">← Retour à l'accueil</a>
    <img src="logo.png" alt="Logo AquaBioScope" width="84" height="84">
    <h1>📰 Nouveautés</h1>
    <p>Tout ce qui a changé dans AquaBioScope, version par version.</p>
  </div>
  <svg class="wave" viewBox="0 0 1200 60" preserveAspectRatio="none">
    <path d="M0,32 C200,64 400,0 600,24 C800,48 1000,8 1200,32 L1200,60 L0,60 Z" fill="var(--sand)"/>
  </svg>
</header>

<main>
  <div class="wrap">
    <div class="timeline">
{{RELEASES}}
    </div>
    <div class="cta"><a href="index.html#telechargement">⬇️ Télécharger la dernière version</a></div>
  </div>
</main>

<footer>AquaBioScope — logiciel gratuit pour plongeurs. Les applications installées se mettent à jour toutes seules.</footer>

</body>
</html>
"""


def main() -> None:
    versions = parse(CHANGELOG.read_text(encoding="utf-8"))
    OUTPUT.write_text(render(versions), encoding="utf-8")
    print(f"{OUTPUT} : {len(versions)} versions")


if __name__ == "__main__":
    main()
