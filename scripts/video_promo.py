"""Vidéo promotionnelle Buyvera BI (vision métier achats) : 1920×1080, 30 i/s, sans voix off (VOIX = True pour l'ajouter).

Usage : python scripts/video_promo.py → docs/video/buyvera_promo.mp4
Prérequis : pip install imageio-ffmpeg ; voix Windows « Microsoft Hortense » (System.Speech).
Captures du rapport : docs/captures/*.png. Toutes les valeurs affichées sont celles du rapport (campagne 2026).
"""
from __future__ import annotations

import math
import subprocess
import tempfile
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

RACINE = Path(__file__).resolve().parents[1]
CAPT = RACINE / "docs" / "captures"
SORTIE = RACINE / "docs" / "video" / "buyvera_promo.mp4"
W, H, FPS = 1920, 1080, 30
FONTS = Path("C:/Windows/Fonts")

# Charte Buyvera (thème sombre) : encre, vert marque, menthe, ambre signal
NAVY, NAVY2, BLEU, AMBRE, ROUGE, VERT, BLANC, GRIS = (
    (14, 23, 20), (22, 33, 29), (15, 92, 74), (229, 154, 69), (229, 154, 69), (95, 196, 160), (238, 242, 239), (157, 176, 168))
MENTHE = (127, 209, 179)
CROP = (37, 204, 1222, 922)  # zone du canevas du rapport (bandeau compris) dans les captures 1728×1080
CROP_1920 = (50, 80, 1610, 1002)  # même zone dans les captures 1920×1080 (écran 4K)


def police(nom: str, taille: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / nom), taille)


F_TITRE = lambda t: police("segoeuib.ttf", t)  # noqa: E731
F_TEXTE = lambda t: police("segoeui.ttf", t)  # noqa: E731
F_LEGER = lambda t: police("segoeuil.ttf", t)  # noqa: E731
F_CHIFFRE = lambda t: police("bahnschrift.ttf", t)  # noqa: E731
F_SYMB = lambda t: police("seguisym.ttf", t)  # noqa: E731


def ease(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def apparition(t: float, debut: float, duree: float = 0.6) -> float:
    return ease((t - debut) / duree)


def fond() -> Image.Image:
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    for i in range(0, H, 4):  # léger dégradé vertical
        c = tuple(int(a + (b - a) * i / H) for a, b in zip(NAVY, NAVY2))
        d.rectangle([0, i, W, i + 4], fill=c)
    return img


FOND = fond()


def texte(img, xy, s, font, couleur, alpha=1.0, ancre="la", dy=0):
    if alpha <= 0:
        return
    calque = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(calque).text((xy[0], xy[1] + (1 - alpha) * 30 + dy), s, font=font,
                                fill=couleur + (int(255 * alpha),), anchor=ancre)
    img.alpha_composite(calque)


def pastille(img, xy, s, couleur, alpha=1.0, taille=34):
    if alpha <= 0:
        return
    f = F_TITRE(taille)
    calque = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(calque)
    l, t, r, b = d.textbbox((0, 0), s, font=f)
    x, y = xy[0], xy[1] + (1 - alpha) * 24
    d.rounded_rectangle([x, y, x + r - l + 56, y + b - t + 34], radius=(b - t + 34) // 2,
                        fill=couleur + (int(235 * alpha),))
    d.text((x + 28, y + 17 - t), s, font=f, fill=BLANC + (int(255 * alpha),))
    img.alpha_composite(calque)


def charger_capture(nom: str, largeur: int) -> Image.Image:
    im = Image.open(CAPT / nom).convert("RGB")
    im = im.crop(CROP_1920 if im.size == (1920, 1080) else CROP)
    h = int(im.height * largeur / im.width)
    im = im.resize((largeur, h), Image.LANCZOS)
    masque = Image.new("L", im.size, 0)
    ImageDraw.Draw(masque).rounded_rectangle([0, 0, im.width, im.height], radius=22, fill=255)
    out = Image.new("RGBA", im.size)
    out.paste(im, (0, 0), masque)
    return out


CACHE: dict = {}


def capture(img, nom, t, duree, x, y, largeur, focus=(0.5, 0.5), zoom=0.07):
    """Capture du rapport en zoom lent (Ken Burns) vers un point d'intérêt, ombre portée."""
    if nom not in CACHE:
        CACHE[nom] = charger_capture(nom, largeur)
    base = CACHE[nom]
    a = apparition(t, 0, 0.7)
    z = 1 + zoom * ease(t / duree)
    bw, bh = base.size
    cw, ch = int(bw / z), int(bh / z)
    cx = int((bw - cw) * focus[0])
    cy = int((bh - ch) * focus[1])
    vue = base.crop((cx, cy, cx + cw, cy + ch)).resize((bw, bh), Image.BILINEAR)
    ombre = Image.new("RGBA", (bw + 80, bh + 80), (0, 0, 0, 0))
    ImageDraw.Draw(ombre).rounded_rectangle([40, 52, bw + 40, bh + 52], radius=26, fill=(0, 0, 0, int(130 * a)))
    ombre = ombre.filter(ImageFilter.GaussianBlur(22))
    img.alpha_composite(ombre, (x - 40, int(y - 40 + (1 - a) * 40)))
    vue.putalpha(Image.eval(base.getchannel("A"), lambda v: int(v * a)))
    img.alpha_composite(vue, (x, int(y + (1 - a) * 40)))


def compteur(img, xy, valeur, fmt, t, debut, libelle, couleur):
    a = apparition(t, debut, 0.5)
    v = valeur * ease((t - debut) / 1.2)
    texte(img, xy, fmt(v), F_CHIFFRE(92), couleur, a)
    texte(img, (xy[0], xy[1] + 112), libelle, F_TEXTE(28), GRIS, a)


def pct(v):
    return f"{v:+.1f} %".replace(".", ",").replace("-", "–")


# --------------------------------------------------------------------------------------
# Scènes : (voix off, durée minimale, fonction de dessin(img, t, duree))
# --------------------------------------------------------------------------------------
def s_lettre(img, t, d):
    a = apparition(t, 0.1)
    calque = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(calque).rounded_rectangle([460, 170 + (1 - a) * 40, 1460, 910 + (1 - a) * 40], radius=10,
                                            fill=(250, 250, 247, int(255 * a)))
    img.alpha_composite(calque)
    noir = (30, 30, 30)
    texte(img, (540, 240), "Orlenza Thermique", F_TITRE(34), noir, a)
    texte(img, (540, 290), "Service commercial", F_TEXTE(24), (110, 110, 110), a)
    texte(img, (540, 380), "Objet : revalorisation tarifaire au 1er janvier", F_TITRE(30), noir, apparition(t, 0.6))
    corps = ["Madame, Monsieur,", "", "Suite à la forte évolution du coût des matières",
             "premières, nous sommes contraints d'appliquer",
             "une hausse de nos tarifs de"]
    for i, l in enumerate(corps):
        texte(img, (540, 460 + i * 44), l, F_TEXTE(28), noir, apparition(t, 1.0 + i * 0.25))
    texte(img, (540, 690), "+6,2 %", F_CHIFFRE(110), ROUGE, apparition(t, 2.4, 0.4))


def s_question(img, t, d):
    texte(img, (W // 2, 430), "Cette hausse est-elle", F_TITRE(96), BLANC, apparition(t, 0.1), "mm")
    texte(img, (W // 2, 560), "vraiment justifiée ?", F_TITRE(96), AMBRE, apparition(t, 0.5), "mm")


def s_probleme(img, t, d):
    texte(img, (200, 220), "Aujourd'hui, l'acheteur négocie à l'aveugle", F_TITRE(64), BLANC, apparition(t, 0.1))
    items = [("✕", "Aucun lien entre la hausse demandée et les cours réels"),
             ("✕", "Les baisses matières ne sont jamais répercutées"),
             ("✕", "Le fournisseur connaît les cours avant vous"),
             ("✕", "Le même article est payé plus cher d'un site à l'autre")]
    for i, (ic, s) in enumerate(items):
        a = apparition(t, 1.0 + i * 1.3)
        texte(img, (220, 380 + i * 120), ic, F_SYMB(56), ROUGE, a)
        texte(img, (310, 385 + i * 120), s, F_TEXTE(48), BLANC, a)


def s_logo(img, t, d):
    a = apparition(t, 0.1, 0.8)
    r = int(70 + 10 * math.sin(t * 2))
    calque = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(calque)
    for k in range(3):
        hb = 120 + 12 * math.sin(t * 3 + k)
        d.rounded_rectangle([W // 2 - 470 + k * 44, 390 - hb, W // 2 - 440 + k * 44, 390], radius=8,
                            fill=MENTHE + (int(255 * a),))
    img.alpha_composite(calque)
    f = F_TITRE(130)
    texte(img, (W // 2 - 310, 330), "buy", f, BLANC, a, "lm")
    texte(img, (W // 2 - 310 + int(f.getlength("buy")), 330), "vera", f, MENTHE, a, "lm")
    texte(img, (W // 2 - 310 + int(f.getlength("buyvera ")), 330), "BI", f, BLANC, a, "lm")
    texte(img, (W // 2, 560), "Chaque tarif fournisseur confronté", F_LEGER(58), BLANC, apparition(t, 0.8), "mm")
    texte(img, (W // 2, 640), "aux cours réels des matières premières", F_LEGER(58), AMBRE, apparition(t, 1.1), "mm")
    texte(img, (W // 2, 780), "Cuivre · Aluminium · Nickel · Acier · Zinc · Plastiques — indices INSEE",
          F_TEXTE(30), GRIS, apparition(t, 1.6), "mm")


def pareto_orlenza() -> list[float]:
    """€ renégociables 2026 d'Orlenza Thermique par référence (désignation), triés : données réelles du projet."""
    import pandas as pd
    p = RACINE / "data" / "processed"
    f = pd.read_csv(p / "fact_hausse_article.csv")
    f = f[(f.fenetre == 6) & (f.decalage == 0) & f.comparable & (f.campagne == 2026)]
    a = pd.read_csv(p / "dim_article.csv")[["article_id", "fournisseur_id", "designation"]]
    n = pd.read_csv(p / "dim_fournisseur.csv")[["fournisseur_id", "nom"]]
    f = f.merge(a, on="article_id").merge(n, on="fournisseur_id")
    f = f[f.nom == "Orlenza Thermique"]
    f["e"] = (f.prix_n1 / f.prix_n - 1 - f.hausse_justifiee).clip(lower=0) * f.prix_n * f.volume_n
    return f.groupby("designation").e.sum().sort_values(ascending=False).tolist()


PARETO = pareto_orlenza()


def s_synthese(img, t, d):
    """La hausse réelle : le pourcentage de la lettre appliqué aux références et aux volumes de l'acheteur."""
    texte(img, (90, 150), "Orlenza Thermique · campagne 2026", F_TITRE(46), BLANC, apparition(t, 0.1))
    etapes = [(0.6, "+6,2 %", "annoncés dans la lettre", AMBRE),
              (1.8, f"{len(PARETO)} références", "achetées chez lui en 2025", BLANC),
              (3.0, "+131 k€ / an", "la hausse réelle, sur tes volumes", ROUGE),
              (4.2, "+0,5 %", "seulement justifiés par ses matières", VERT)]
    for i, (deb, gros, petit, c) in enumerate(etapes):
        a = apparition(t, deb)
        x = 90 + i * 445
        calque = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(calque).rounded_rectangle([x, 300 + (1 - a) * 30, x + 410, 620 + (1 - a) * 30], radius=22,
                                                fill=NAVY2 + (int(255 * a),), outline=c + (int(200 * a),), width=3)
        img.alpha_composite(calque)
        texte(img, (x + 205, 430), gros, F_CHIFFRE(54), c, a, "mm")
        texte(img, (x + 205, 540), petit, F_TEXTE(25), GRIS, a, "mm")
        if i < 3:
            texte(img, (x + 427, 460), "→", F_SYMB(40), GRIS, apparition(t, deb + 0.6), "mm")
    compteur(img, (90, 700), 120, lambda v: f"{v:,.0f} k€".replace(",", " "), t, 4.9, "à renégocier chez Orlenza", ROUGE)
    texte(img, (1000, 760), "Sur toute la campagne : 335 k€", F_TEXTE(34), GRIS, apparition(t, 6.2))


def s_pareto(img, t, d):
    """80/20 : les quelques références qui portent l'enjeu, à négocier en premier."""
    texte(img, (90, 150), "80/20 : par où commencer", F_TITRE(56), BLANC, apparition(t, 0.1))
    tot = sum(PARETO)
    n80 = next(i + 1 for i in range(len(PARETO)) if sum(PARETO[:i + 1]) >= 0.8 * tot)
    x0, y0, larg, haut = 90, 900, 1100, 560
    bw = larg / len(PARETO)
    calque = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(calque)
    cum, pts = 0.0, []
    for i, e in enumerate(PARETO):
        a = apparition(t, 0.6 + i * 0.012, 0.4)
        h = haut * e / PARETO[0] * a
        c = (ROUGE if i < n80 else GRIS)
        dr.rectangle([x0 + i * bw, y0 - h, x0 + (i + 1) * bw - 1, y0], fill=c + (int(255 * a),))
        cum += e
        pts.append((x0 + (i + 0.5) * bw, y0 - haut * cum / tot))
    k = max(2, int(len(pts) * min(1.0, max(0.0, (t - 1.8) / 1.6))))
    dr.line(pts[:k], fill=MENTHE + (255,), width=5)
    xs = x0 + n80 * bw
    if t > 3.4:
        dr.line([(xs, y0 - haut - 20), (xs, y0)], fill=BLANC + (180,), width=2)
    img.alpha_composite(calque)
    texte(img, (x0 + larg - 10, y0 - haut - 30), "cumul de l'enjeu", F_TEXTE(26), MENTHE, apparition(t, 2.2), "rs")
    texte(img, (1290, 330), f"{n80} références", F_CHIFFRE(84), ROUGE, apparition(t, 3.4))
    texte(img, (1290, 440), f"sur {len(PARETO)} portent 80 %", F_TEXTE(38), BLANC, apparition(t, 3.6))
    texte(img, (1290, 490), "des 120 k€ à renégocier", F_TEXTE(38), BLANC, apparition(t, 3.7))
    texte(img, (1290, 620), "20 % des références", F_TITRE(40), AMBRE, apparition(t, 4.6))
    texte(img, (1290, 672), "= 68 % de l'enjeu", F_TEXTE(38), AMBRE, apparition(t, 4.7))
    pastille(img, (1290, 800), "Négocier ces références en premier", VERT, apparition(t, 5.6), 30)


def s_fournisseurs(img, t, d):
    capture(img, "02_fournisseurs.png", t, d, 90, 210, 1180, focus=(0.15, 0.6), zoom=0.12)
    texte(img, (1320, 260), "Qui demande plus", F_TITRE(54), BLANC, apparition(t, 0.4))
    texte(img, (1320, 330), "que ses matières ?", F_TITRE(54), AMBRE, apparition(t, 0.6))
    pastille(img, (1320, 480), "▲ À renégocier", ROUGE, apparition(t, 1.4))
    pastille(img, (1320, 580), "● À surveiller", (236, 131, 90), apparition(t, 1.8))
    pastille(img, (1320, 680), "● Conforme", VERT, apparition(t, 2.2))
    texte(img, (1320, 820), "Nuage animé 2024 → 2026", F_TEXTE(30), GRIS, apparition(t, 2.8))


def s_alertes(img, t, d):
    capture(img, "06_alertes_matieres.png", t, d, 760, 170, 1080, focus=(0.3, 0.25), zoom=0.1)
    texte(img, (90, 170), "Sachez avant", F_TITRE(60), BLANC, apparition(t, 0.2))
    texte(img, (90, 245), "le fournisseur", F_TITRE(60), AMBRE, apparition(t, 0.4))
    pastille(img, (90, 400), "▼ Baisse : convoquer le fournisseur", VERT, apparition(t, 1.4), 30)
    pastille(img, (90, 500), "▲ Hausse : anticiper les achats", ROUGE, apparition(t, 2.4), 30)
    compteur(img, (90, 650), 11.2, pct, t, 3.6, "déjà justifiés pour 2027", AMBRE)


def s_fiche(img, t, d):
    capture(img, "07_fiche_negociation.png", t, d, 90, 210, 1180, focus=(0.5, 0.35), zoom=0.1)
    texte(img, (1320, 250), "Prêt pour", F_TITRE(56), BLANC, apparition(t, 0.3))
    texte(img, (1320, 322), "le rendez-vous", F_TITRE(56), AMBRE, apparition(t, 0.5))
    for i, s in enumerate(["Argument rédigé", "Levier matière chiffré", "Contre-proposition simulée",
                           "Historique demandé / justifié"]):
        a = apparition(t, 1.3 + i * 0.6)
        texte(img, (1320, 470 + i * 90), "✓", F_SYMB(44), VERT, a)
        texte(img, (1380, 474 + i * 90), s, F_TEXTE(38), BLANC, a)


def s_groupe(img, t, d):
    capture(img, "10_prix_payes.png", t, d, 760, 190, 1080, focus=(0.2, 0.45), zoom=0.1)
    texte(img, (90, 170), "Un article,", F_TITRE(60), BLANC, apparition(t, 0.2))
    texte(img, (90, 245), "trois prix", F_TITRE(60), AMBRE, apparition(t, 0.4))
    compteur(img, (90, 400), 624, lambda v: f"{v:,.0f} k€".replace(",", " "), t, 1.0, "payés au-dessus du meilleur prix du groupe", ROUGE)
    compteur(img, (90, 640), 72, lambda v: f"{v:,.0f} k€".replace(",", " "), t, 2.2, "tarifs négociés mal appliqués dans les ERP", AMBRE)
    pastille(img, (90, 860), "Aligner les sites rachetés", VERT, apparition(t, 3.4), 30)


def s_gains(img, t, d):
    capture(img, "11_gains.png", t, d, 90, 200, 1180, focus=(0.25, 0.6), zoom=0.1)
    texte(img, (1320, 250), "Prouvez", F_TITRE(60), BLANC, apparition(t, 0.3))
    texte(img, (1320, 325), "ce que vous rapportez", F_TITRE(48), AMBRE, apparition(t, 0.5))
    compteur(img, (1320, 450), 524, lambda v: f"{v:,.0f} k€".replace(",", " "), t, 1.1, "économies obtenues en 3 campagnes", VERT)
    compteur(img, (1320, 690), 51, lambda v: f"{v:,.0f} %", t, 2.3, "du potentiel transformé en gains", MENTHE)


def s_rls(img, t, d):
    capture(img, "00_parcours.png", t, d, 760, 190, 1080, focus=(0.3, 0.5), zoom=0.06)
    texte(img, (90, 260), "Un parcours guidé,", F_TITRE(58), BLANC, apparition(t, 0.2))
    texte(img, (90, 335), "de l'alerte au rendez-vous", F_TITRE(46), AMBRE, apparition(t, 0.4))
    texte(img, (90, 480), "Chaque acheteur ne voit", F_TEXTE(38), GRIS, apparition(t, 1.2))
    texte(img, (90, 535), "que son périmètre.", F_TEXTE(38), GRIS, apparition(t, 1.4))


def s_benefices(img, t, d):
    texte(img, (W // 2, 200), "Ce que gagnent les achats", F_TITRE(66), BLANC, apparition(t, 0.1), "mm")
    cartes = [("Négocier", "les baisses aussi vite", "que les hausses", VERT),
              ("Anticiper", "la campagne suivante", "avant le tarif", AMBRE),
              ("Prouver", "les gains obtenus,", "campagne après campagne", MENTHE)]
    for i, (a1, a2, a3, c) in enumerate(cartes):
        a = apparition(t, 0.8 + i * 0.9)
        x = 180 + i * 540
        calque = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(calque).rounded_rectangle([x, 330 + (1 - a) * 40, x + 480, 780 + (1 - a) * 40], radius=24,
                                                fill=NAVY2 + (int(255 * a),), outline=c + (int(255 * a),), width=4)
        img.alpha_composite(calque)
        texte(img, (x + 240, 450), a1, F_TITRE(64), c, a, "mm")
        texte(img, (x + 240, 570), a2, F_TEXTE(36), BLANC, a, "mm")
        texte(img, (x + 240, 625), a3, F_TEXTE(36), BLANC, a, "mm")


def s_fin(img, t, d):
    a = apparition(t, 0.1, 0.8)
    f = F_TITRE(140)
    x0 = W // 2 - int(f.getlength("buyvera BI")) // 2
    texte(img, (x0, 360), "buy", f, BLANC, a, "lm")
    texte(img, (x0 + int(f.getlength("buy")), 360), "vera", f, MENTHE, a, "lm")
    texte(img, (x0 + int(f.getlength("buyvera ")), 360), "BI", f, BLANC, a, "lm")
    texte(img, (W // 2, 520), "Ne subissez plus les hausses. Argumentez. Prouvez.", F_LEGER(64), AMBRE, apparition(t, 0.7), "mm")
    texte(img, (W // 2, 700), "Power BI · DAX · TMDL · indices INSEE", F_TEXTE(34), GRIS, apparition(t, 1.3), "mm")
    texte(img, (W // 2, 770), "github.com/PDUCLOS/buyvera-bi", F_TITRE(40), BLANC, apparition(t, 1.6), "mm")
    texte(img, (W // 2, 950), "Indices matières réels · tarifs, volumes et fournisseurs fictifs",
          F_TEXTE(24), GRIS, apparition(t, 2.0), "mm")


SCENES = [
    ("Chaque année, la même lettre. Nos tarifs augmentent, à cause des matières premières.", 4.5, s_lettre),
    ("Mais cette hausse est-elle vraiment justifiée ?", 3.0, s_question),
    ("Sans outil, l'acheteur négocie à l'aveugle. Les baisses ne sont jamais répercutées. "
     "Et le fournisseur connaît les cours avant lui.", 5.5, s_probleme),
    ("Buyvera BI confronte chaque tarif fournisseur aux cours réels des matières premières.", 4.0, s_logo),
    ("La lettre annonce plus six virgule deux pour cent. Appliqués à tes références et à tes volumes, c'est cent trente et un mille "
     "euros de plus par an, quand ses matières ne justifient que zéro virgule cinq : cent vingt mille euros à renégocier.", 7.5, s_synthese),
    ("Et pas besoin de tout négocier : trente-cinq références portent quatre-vingts pour cent de l'enjeu. "
     "On commence par elles.", 6.5, s_pareto),
    ("En un coup d'œil, vous voyez qui demande plus que ses matières ne le justifient.", 4.5, s_fournisseurs),
    ("Les alertes matières vous préviennent avant le fournisseur. Une baisse ? On le convoque. "
     "Une hausse ? On anticipe les achats. Pour 2027, les cours justifient déjà plus onze pour cent.", 6.5, s_alertes),
    ("Pour le rendez-vous, la fiche négociation rédige l'argument et chiffre la contre-proposition.", 5.0, s_fiche),
    ("Dans le groupe, un même article se paie trois prix. Six cent vingt-quatre mille euros au-dessus du meilleur prix, "
     "et soixante-douze mille euros de tarifs négociés mal appliqués dans les ERP.", 6.0, s_groupe),
    ("Et la négociation se mesure : cinq cent vingt-quatre mille euros obtenus en trois campagnes, "
     "la moitié du potentiel transformée.", 5.5, s_gains),
    ("Un parcours guidé, de l'alerte au rendez-vous. Chaque acheteur ne voit que son périmètre.", 4.0, s_rls),
    ("Négocier les baisses aussi vite que les hausses. Anticiper la campagne suivante. "
     "Prouver les gains, campagne après campagne.", 5.5, s_benefices),
    ("Buyvera BI. Ne subissez plus les hausses : argumentez, prouvez.", 4.5, s_fin),
]
FONDU = 0.35  # fondu au noir entre scènes, en secondes
VOIX = False  # True : voix off Windows (Hortense) calée sur chaque scène
# Durée de lecture de chaque scène sans voix off (secondes)
DUREES_LECTURE = [4.5, 3.0, 6.5, 4.5, 7.5, 7.0, 5.0, 7.0, 5.5, 6.5, 6.0, 4.5, 5.5, 5.0]


def voix(dossier: Path) -> list[Path]:
    """Synthèse vocale Windows (Hortense, fr-FR), un WAV par scène."""
    fichiers = [dossier / f"s{i:02d}.wav" for i in range(len(SCENES))]
    lignes = ["Add-Type -AssemblyName System.Speech",
              "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer",
              "$s.SelectVoice('Microsoft Hortense Desktop')", "$s.Rate = 2"]
    for f, (txt, _, _) in zip(fichiers, SCENES):
        lignes += [f"$s.SetOutputToWaveFile('{f}')", f"$s.Speak('{txt.replace(chr(39), chr(39) * 2)}')"]
    lignes.append("$s.Dispose()")
    ps1 = dossier / "voix.ps1"
    ps1.write_text("\n".join(lignes), encoding="utf-8-sig")
    subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)], check=True)
    return fichiers


def lire_wav(p: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(p)) as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        if w.getnchannels() == 2:
            data = data.reshape(-1, 2).mean(axis=1).astype(np.int16)
        return data, w.getframerate()


def preparer_voix(tmp: Path) -> tuple[list[float], float, list[str]]:
    wavs = voix(tmp)
    pistes = [lire_wav(p) for p in wavs]
    sr = pistes[0][1]
    durees = [max(mini, len(a) / sr + 0.9) for (a, _), (_, mini, _) in zip(pistes, SCENES)]
    total = sum(durees)
    # Piste audio : chaque voix démarre 0,3 s après le début de sa scène
    audio = np.zeros(int((total + 0.5) * sr), dtype=np.int16)
    debut = 0.0
    for (a, _), d in zip(pistes, durees):
        i = int((debut + 0.3) * sr)
        audio[i:i + len(a)] = a[: len(audio) - i]
        debut += d
    wav_total = tmp / "voix.wav"
    with wave.open(str(wav_total), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(audio.tobytes())

    return durees, total, ["-i", str(wav_total)]


def main() -> None:
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="buyvera_video_"))
    if not VOIX:
        durees = DUREES_LECTURE
        total = sum(durees)
        entree_audio = []
    else:
        durees, total, entree_audio = preparer_voix(tmp)

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.Popen([ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", *entree_audio,
                             "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                             *(["-c:a", "aac", "-b:a", "160k", "-shortest"] if entree_audio else ["-an"]), "-movflags", "+faststart", str(SORTIE)],
                            stdin=subprocess.PIPE)
    vignettes = []
    for n, ((_, _, dessin), d) in enumerate(zip(SCENES, durees)):
        nb = int(d * FPS)
        for k in range(nb):
            t = k / FPS
            img = FOND.copy().convert("RGBA")
            dessin(img, t, d)
            fade = min(1.0, t / FONDU, (d - t) / FONDU)
            frame = img.convert("RGB")
            if fade < 1:
                frame = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), frame, max(fade, 0))
            if k == int(nb * 0.8):
                vignettes.append(frame.copy())
            proc.stdin.write(frame.tobytes())
        print(f"scène {n + 1}/{len(SCENES)} : {d:.1f} s")
    proc.stdin.close()
    proc.wait()
    planche = Image.new("RGB", (4 * 480, -(-len(vignettes) // 4) * 270), NAVY)
    for i, v in enumerate(vignettes):
        planche.paste(v.resize((480, 270)), ((i % 4) * 480, (i // 4) * 270))
    planche.save(SORTIE.with_name("planche_contact.png"))
    vignettes[4].save(SORTIE.with_name("miniature.png"))
    print(f"{SORTIE} : {total:.1f} s, {SORTIE.stat().st_size / 1e6:.1f} Mo")


if __name__ == "__main__":
    main()
