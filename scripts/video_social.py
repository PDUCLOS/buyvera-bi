"""Vidéo réseaux sociaux Buyvera BI : verticale 1080×1920, ~24 s, rythmée, sans voix off.

Usage : python scripts/video_social.py → docs/video/buyvera_social.mp4
Même exemple que la vidéo longue (Orlenza Thermique, campagne 2026), mêmes chiffres que le rapport.
Les réseaux ajoutent souvent leur propre musique : la vidéo est muette et lisible sans le son.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw

import video_promo as vp  # polices, couleurs, helpers de texte, courbe 80/20 sur les vraies données

RACINE = Path(__file__).resolve().parents[1]
SORTIE = RACINE / "docs" / "video" / "buyvera_social.mp4"
W, H, FPS = 1080, 1920, 30
CX = W // 2


def fond() -> Image.Image:
    img = Image.new("RGB", (W, H), vp.NAVY)
    d = ImageDraw.Draw(img)
    for i in range(0, H, 6):
        c = tuple(int(a + (b - a) * i / H) for a, b in zip(vp.NAVY, vp.NAVY2))
        d.rectangle([0, i, W, i + 6], fill=c)
    return img


FOND = fond()
A = vp.apparition


def punch(t: float, debut: float) -> float:
    """Entrée rapide (0,25 s) : opacité de 0 à 1."""
    return A(t, debut, 0.25)


def gros(img, y, s, taille, couleur, t, debut=0.0, police=None):
    vp.texte(img, (CX, y), s, (police or vp.F_CHIFFRE)(taille), couleur, punch(t, debut), "mm")


def ligne(img, y, s, taille, couleur, t, debut=0.0):
    vp.texte(img, (CX, y), s, vp.F_TEXTE(taille), couleur, punch(t, debut), "mm")


def capture(img, nom, t, d, y, zone):
    """Morceau d'une capture du rapport, en pleine largeur, zoom lent."""
    im = Image.open(vp.CAPT / nom).convert("RGB").crop(zone)
    larg = W - 80
    im = im.resize((larg, int(im.height * larg / im.width)), Image.LANCZOS)
    z = 1 + 0.06 * vp.ease(t / d)
    cw, ch = int(im.width / z), int(im.height / z)
    im = im.crop(((im.width - cw) // 2, (im.height - ch) // 2, (im.width + cw) // 2, (im.height + ch) // 2)).resize((larg, im.height))
    a = punch(t, 0)
    masque = Image.new("L", im.size, 0)
    ImageDraw.Draw(masque).rounded_rectangle([0, 0, im.width, im.height], radius=26, fill=int(255 * a))
    img.paste(im, (40, int(y + (1 - a) * 40)), masque)


def s_hausse(img, t, d):
    ligne(img, 700, "Votre fournisseur annonce", 52, vp.BLANC, t)
    gros(img, 900, "+6,2 %", 260, vp.AMBRE, t, 0.15)
    ligne(img, 1110, "« à cause des matières premières »", 44, vp.GRIS, t, 0.5)


def s_justifie(img, t, d):
    gros(img, 900, "Vraiment ?", 170, vp.BLANC, t, 0, vp.F_TITRE)


def s_matieres(img, t, d):
    ligne(img, 700, "Ses matières, d'après l'INSEE :", 52, vp.BLANC, t)
    gros(img, 900, "+0,5 %", 260, vp.VERT, t, 0.15)
    ligne(img, 1110, "cuivre, aluminium, plastiques… indices réels", 40, vp.GRIS, t, 0.5)


def s_euros(img, t, d):
    v = 120 * vp.ease((t - 0.1) / 1.0)
    ligne(img, 700, "Sur vos volumes réels", 52, vp.BLANC, t)
    gros(img, 900, f"{v:,.0f} k€".replace(",", " "), 250, vp.ROUGE, t, 0.1)
    ligne(img, 1110, "à renégocier chez lui", 52, vp.BLANC, t, 0.4)


def s_pareto(img, t, d):
    ligne(img, 420, "Pas besoin de tout négocier", 54, vp.BLANC, t)
    tot, n = sum(vp.PARETO), len(vp.PARETO)
    n80 = next(i + 1 for i in range(n) if sum(vp.PARETO[:i + 1]) >= 0.8 * tot)
    x0, y0, larg, haut = 90, 1150, W - 180, 520
    calque = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(calque)
    for i, e in enumerate(vp.PARETO):
        a = A(t, 0.1 + i * 0.006, 0.2)
        h = haut * e / vp.PARETO[0] * a
        dr.rectangle([x0 + i * larg / n, y0 - h, x0 + (i + 1) * larg / n - 1, y0],
                     fill=(vp.ROUGE if i < n80 else vp.GRIS) + (int(255 * a),))
    img.alpha_composite(calque)
    gros(img, 1330, f"{n80} références", 130, vp.ROUGE, t, 0.9)
    ligne(img, 1460, "= 80 % de l'enjeu. On commence par elles.", 46, vp.BLANC, t, 1.1)


def s_fiche(img, t, d):
    ligne(img, 360, "L'argument est prêt", 64, vp.BLANC, t)
    capture(img, "07_fiche_negociation.png", t, d, 560, (70, 330, 1590, 560))
    capture(img, "07_fiche_negociation.png", t, d, 980, (70, 640, 1590, 1000))
    ligne(img, 1480, "Fiche négociation · contre-proposition chiffrée", 40, vp.GRIS, t, 0.4)


def s_alertes(img, t, d):
    ligne(img, 360, "Alerté avant lui", 64, vp.BLANC, t)
    capture(img, "06_alertes_matieres.png", t, d, 520, (70, 330, 990, 1000))
    gros(img, 1560, "+11,2 %", 120, vp.AMBRE, t, 0.5)
    ligne(img, 1660, "déjà justifiés pour 2027 · au-delà : à contester", 40, vp.BLANC, t, 0.7)


def s_groupe(img, t, d):
    ligne(img, 700, "Entre vos sites, même article :", 52, vp.BLANC, t)
    gros(img, 900, "624 k€", 230, vp.ROUGE, t, 0.15)
    ligne(img, 1110, "payés au-dessus du meilleur prix du groupe", 46, vp.BLANC, t, 0.45)


def s_gains(img, t, d):
    ligne(img, 700, "Et vous prouvez ce que vous rapportez", 50, vp.BLANC, t)
    gros(img, 900, "524 k€", 230, vp.VERT, t, 0.15)
    ligne(img, 1110, "obtenus en 3 campagnes · 51 % du potentiel", 46, vp.BLANC, t, 0.45)


def s_fin(img, t, d):
    a = punch(t, 0)
    f = vp.F_TITRE(150)
    x0 = CX - int(f.getlength("buyvera BI")) // 2
    vp.texte(img, (x0, 800), "buy", f, vp.BLANC, a, "lm")
    vp.texte(img, (x0 + int(f.getlength("buy")), 800), "vera", f, vp.MENTHE, a, "lm")
    vp.texte(img, (x0 + int(f.getlength("buyvera ")), 800), "BI", f, vp.BLANC, a, "lm")
    ligne(img, 1000, "Argumentez. Prouvez.", 72, vp.AMBRE, t, 0.3)
    ligne(img, 1180, "Power BI · DAX · Python · machine learning", 38, vp.GRIS, t, 0.6)
    ligne(img, 1260, "github.com/PDUCLOS/buyvera-bi", 44, vp.BLANC, t, 0.8)
    ligne(img, 1750, "Indices matières réels · tarifs et fournisseurs fictifs", 30, vp.GRIS, t, 1.0)


SCENES = [(s_hausse, 2.0), (s_justifie, 1.3), (s_matieres, 2.2), (s_euros, 2.3), (s_pareto, 3.0),
          (s_fiche, 2.6), (s_alertes, 2.8), (s_groupe, 2.3), (s_gains, 2.3), (s_fin, 3.2)]
FONDU = 0.12  # coupes franches : fondu très court


def main() -> None:
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                             "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", str(SORTIE)], stdin=subprocess.PIPE)
    vignettes = []
    for dessin, d in SCENES:
        nb = int(d * FPS)
        for k in range(nb):
            t = k / FPS
            img = FOND.copy().convert("RGBA")
            dessin(img, t, d)
            frame = img.convert("RGB")
            fade = min(1.0, t / FONDU, (d - t) / FONDU)
            if fade < 1:
                frame = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), frame, max(fade, 0))
            if k == int(nb * 0.75):
                vignettes.append(frame.copy())
            proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    planche = Image.new("RGB", (5 * 216, 2 * 384), vp.NAVY)
    for i, v in enumerate(vignettes):
        planche.paste(v.resize((216, 384)), ((i % 5) * 216, (i // 5) * 384))
    planche.save(SORTIE.with_name("planche_social.png"))
    print(f"{SORTIE} : {sum(d for _, d in SCENES):.1f} s, {SORTIE.stat().st_size / 1e6:.1f} Mo")


if __name__ == "__main__":
    main()
