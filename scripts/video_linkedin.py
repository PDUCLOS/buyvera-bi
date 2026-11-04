"""Vidéo LinkedIn Buyvera BI : 4:5 (1080×1350), ~45 s, sous-titres incrustés (le fil LinkedIn joue sans le son).

Usage : python scripts/video_linkedin.py → docs/video/buyvera_linkedin.mp4
Un seul exemple du début à la fin (Orlenza Thermique, campagne 2026), chiffres identiques au rapport.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw

import video_promo as vp

RACINE = Path(__file__).resolve().parents[1]
SORTIE = RACINE / "docs" / "video" / "buyvera_linkedin.mp4"
W, H, FPS = 1080, 1350, 30
CX = W // 2
A = vp.apparition


def fond() -> Image.Image:
    img = Image.new("RGB", (W, H), vp.NAVY)
    d = ImageDraw.Draw(img)
    for i in range(0, H, 6):
        c = tuple(int(a + (b - a) * i / H) for a, b in zip(vp.NAVY, vp.NAVY2))
        d.rectangle([0, i, W, i + 6], fill=c)
    return img


FOND = fond()


def t_(img, y, s, police, couleur, t, debut=0.0, ancre="mm", x=CX):
    vp.texte(img, (x, y), s, police, couleur, A(t, debut, 0.35), ancre)


def sous_titre(img, s, t):
    """Bandeau de sous-titre en bas : lisible sans le son."""
    a = A(t, 0.1, 0.3)
    if a <= 0:
        return
    f = vp.F_TEXTE(36)
    lignes, cur = [], ""
    for mot in s.split():
        if f.getlength(cur + " " + mot) > W - 160:
            lignes.append(cur)
            cur = mot
        else:
            cur = (cur + " " + mot).strip()
    lignes.append(cur)
    h = 56 * len(lignes) + 36
    calque = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(calque).rounded_rectangle([50, H - 70 - h, W - 50, H - 70], radius=20, fill=(0, 0, 0, int(170 * a)))
    img.alpha_composite(calque)
    for i, l in enumerate(lignes):
        vp.texte(img, (CX, H - 70 - h + 46 + i * 56), l, f, vp.BLANC, a, "mm")


def capture(img, nom, t, d, y, zone, larg=W - 80):
    im = Image.open(vp.CAPT / nom).convert("RGB").crop(zone)
    im = im.resize((larg, int(im.height * larg / im.width)), Image.LANCZOS)
    z = 1 + 0.05 * vp.ease(t / d)
    cw, ch = int(im.width / z), int(im.height / z)
    im = im.crop(((im.width - cw) // 2, (im.height - ch) // 2, (im.width + cw) // 2, (im.height + ch) // 2)).resize((larg, im.height))
    a = A(t, 0, 0.4)
    masque = Image.new("L", im.size, 0)
    ImageDraw.Draw(masque).rounded_rectangle([0, 0, im.width, im.height], radius=22, fill=int(255 * a))
    img.paste(im, ((W - larg) // 2, int(y + (1 - a) * 30)), masque)


def s_lettre(img, t, d):
    a = A(t, 0.05, 0.4)
    calque = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(calque).rounded_rectangle([110, 180, W - 110, 820], radius=12, fill=(250, 250, 247, int(255 * a)))
    img.alpha_composite(calque)
    noir = (30, 30, 30)
    t_(img, 250, "Orlenza Thermique", vp.F_TITRE(40), noir, t, 0.1, "la", 170)
    t_(img, 330, "Objet : revalorisation tarifaire au 1er janvier", vp.F_TITRE(30), noir, t, 0.4, "la", 170)
    for i, l in enumerate(["Suite à la forte évolution du coût", "des matières premières, nos tarifs", "augmenteront de"]):
        t_(img, 420 + i * 48, l, vp.F_TEXTE(32), noir, t, 0.7 + i * 0.2, "la", 170)
    t_(img, 680, "+6,2 %", vp.F_CHIFFRE(150), vp.AMBRE, t, 1.6, "la", 170)
    sous_titre(img, "Chaque année, la même lettre. Mais cette hausse est-elle justifiée ?", t)


def s_methode(img, t, d):
    t_(img, 220, "J'ai construit l'outil", vp.F_TITRE(64), vp.BLANC, t)
    t_(img, 300, "qui répond en euros", vp.F_TITRE(64), vp.MENTHE, t, 0.2)
    etapes = [("1", "Les tarifs du fournisseur", vp.BLANC), ("2", "La composition de chaque produit", vp.BLANC),
              ("3", "Les cours réels des matières (INSEE)", vp.VERT), ("=", "La hausse justifiée, article par article", vp.AMBRE)]
    for i, (n, s, c) in enumerate(etapes):
        a0 = 0.6 + i * 0.5
        t_(img, 470 + i * 110, n, vp.F_CHIFFRE(64), c, t, a0, "mm", 160)
        t_(img, 470 + i * 110, s, vp.F_TEXTE(40), vp.BLANC, t, a0, "lm", 230)
    sous_titre(img, "Power BI confronte chaque tarif fournisseur aux cours réels des matières qui composent le produit.", t)


def s_resultat(img, t, d):
    t_(img, 190, "Orlenza Thermique · 2026", vp.F_TITRE(48), vp.BLANC, t)
    cartes = [("+6,2 %", "demandés", vp.AMBRE, 0.3), ("+0,5 %", "justifiés par ses matières", vp.VERT, 1.0)]
    for i, (g, p, c, a0) in enumerate(cartes):
        y = 300 + i * 230
        a = A(t, a0, 0.35)
        calque = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(calque).rounded_rectangle([110, y, W - 110, y + 190], radius=22, fill=vp.NAVY2 + (int(255 * a),),
                                                outline=c + (int(220 * a),), width=3)
        img.alpha_composite(calque)
        t_(img, y + 80, g, vp.F_CHIFFRE(100), c, t, a0)
        t_(img, y + 155, p, vp.F_TEXTE(32), vp.GRIS, t, a0)
    v = 120 * vp.ease((t - 1.8) / 1.2)
    t_(img, 880, f"{v:,.0f} k€".replace(",", " "), vp.F_CHIFFRE(140), vp.ROUGE, t, 1.8)
    t_(img, 980, "à renégocier chez lui, sur ses 108 références", vp.F_TEXTE(36), vp.BLANC, t, 2.2)
    sous_titre(img, "Appliquée à ses références et aux volumes achetés : 120 000 € de hausse non justifiée.", t)


def s_pareto(img, t, d):
    t_(img, 200, "Par où commencer ?", vp.F_TITRE(60), vp.BLANC, t)
    tot, n = sum(vp.PARETO), len(vp.PARETO)
    n80 = next(i + 1 for i in range(n) if sum(vp.PARETO[:i + 1]) >= 0.8 * tot)
    x0, y0, larg, haut = 110, 760, W - 220, 420
    calque = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(calque)
    cum, pts = 0.0, []
    for i, e in enumerate(vp.PARETO):
        a = A(t, 0.3 + i * 0.008, 0.25)
        dr.rectangle([x0 + i * larg / n, y0 - haut * e / vp.PARETO[0] * a, x0 + (i + 1) * larg / n - 1, y0],
                     fill=(vp.ROUGE if i < n80 else vp.GRIS) + (int(255 * a),))
        cum += e
        pts.append((x0 + (i + 0.5) * larg / n, y0 - haut * cum / tot))
    k = max(2, int(n * min(1.0, max(0.0, (t - 1.3) / 1.2))))
    dr.line(pts[:k], fill=vp.MENTHE + (255,), width=5)
    img.alpha_composite(calque)
    t_(img, 880, f"{n80} références sur {n}", vp.F_CHIFFRE(90), vp.ROUGE, t, 2.4)
    t_(img, 975, "portent 80 % de l'enjeu", vp.F_TEXTE(40), vp.BLANC, t, 2.6)
    sous_titre(img, "Le 80/20 : 35 références portent 80 % de l'enjeu. On les met sur la table en premier.", t)


def s_fiche(img, t, d):
    t_(img, 170, "Prêt pour le rendez-vous", vp.F_TITRE(56), vp.BLANC, t)
    capture(img, "07_fiche_negociation.png", t, d, 250, (70, 330, 1590, 560))
    capture(img, "07_fiche_negociation.png", t, d, 600, (70, 640, 1590, 1000))
    sous_titre(img, "La fiche négociation : l'argument rédigé, le levier matière, la contre-proposition chiffrée.", t)


def s_alertes(img, t, d):
    t_(img, 170, "Savoir avant le fournisseur", vp.F_TITRE(56), vp.BLANC, t)
    capture(img, "06_alertes_matieres.png", t, d, 250, (70, 330, 990, 700))
    t_(img, 800, "+11,2 %", vp.F_CHIFFRE(120), vp.AMBRE, t, 0.8)
    t_(img, 890, "déjà justifiés pour 2027 · au-delà : à contester", vp.F_TEXTE(34), vp.BLANC, t, 1.0)
    sous_titre(img, "Les alertes matières préviennent avant la campagne : on connaît le plafond de hausse avant de recevoir le tarif.", t)


def s_groupe_gains(img, t, d):
    t_(img, 200, "Et après la négociation", vp.F_TITRE(56), vp.BLANC, t)
    for i, (g, p, c, a0) in enumerate([("624 k€", "payés au-dessus du meilleur prix du groupe", vp.ROUGE, 0.4),
                                         ("524 k€", "obtenus en 3 campagnes · 51 % du potentiel", vp.VERT, 1.4)]):
        t_(img, 400 + i * 300, g, vp.F_CHIFFRE(150), c, t, a0)
        t_(img, 505 + i * 300, p, vp.F_TEXTE(36), vp.BLANC, t, a0 + 0.2)
    sous_titre(img, "L'outil vérifie que chaque site paie le meilleur prix du groupe, et mesure ce que la négociation a rapporté.", t)


def s_credible(img, t, d):
    t_(img, 200, "Sous le capot", vp.F_TITRE(60), vp.BLANC, t)
    items = ["Indices matières réels (INSEE), tarifs fictifs", "Modèle Power BI généré par script, versionné sous Git",
             "103 mesures DAX, sécurité par acheteur", "Machine learning testé contre un modèle naïf",
             "Recalcul Python = DAX : écart nul sur 7 chiffres"]
    for i, s in enumerate(items):
        a0 = 0.4 + i * 0.45
        t_(img, 360 + i * 105, "✓", vp.F_SYMB(44), vp.VERT, t, a0, "mm", 130)
        t_(img, 360 + i * 105, s, vp.F_TEXTE(36), vp.BLANC, t, a0, "lm", 180)
    sous_titre(img, "Chaque chiffre est contrôlé deux fois, en Python et en DAX. Le machine learning n'est gardé que s'il bat un modèle naïf.", t)


def s_fin(img, t, d):
    a = A(t, 0, 0.4)
    f = vp.F_TITRE(130)
    x0 = CX - int(f.getlength("buyvera BI")) // 2
    vp.texte(img, (x0, 380), "buy", f, vp.BLANC, a, "lm")
    vp.texte(img, (x0 + int(f.getlength("buy")), 380), "vera", f, vp.MENTHE, a, "lm")
    vp.texte(img, (x0 + int(f.getlength("buyvera ")), 380), "BI", f, vp.BLANC, a, "lm")
    t_(img, 540, "Ne subissez plus les hausses.", vp.F_LEGER(56), vp.AMBRE, t, 0.3)
    t_(img, 620, "Argumentez. Prouvez.", vp.F_LEGER(56), vp.AMBRE, t, 0.5)
    t_(img, 790, "Patrice Duclos", vp.F_TITRE(52), vp.BLANC, t, 0.9)
    t_(img, 860, "Data Analyst / BI · Lyon · 20 ans d'achats industriels", vp.F_TEXTE(34), vp.GRIS, t, 1.1)
    t_(img, 960, "github.com/PDUCLOS/buyvera-bi", vp.F_TITRE(40), vp.BLANC, t, 1.3)
    sous_titre(img, "Le projet complet est en lien dans le post.", t)


SCENES = [(s_lettre, 4.5), (s_methode, 5.0), (s_resultat, 5.5), (s_pareto, 5.0), (s_fiche, 4.5), (s_alertes, 4.5),
          (s_groupe_gains, 5.0), (s_credible, 5.5), (s_fin, 4.5)]
FONDU = 0.2


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
            if k == int(nb * 0.8):
                vignettes.append(frame.copy())
            proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    planche = Image.new("RGB", (5 * 216, 2 * 270), vp.NAVY)
    for i, v in enumerate(vignettes):
        planche.paste(v.resize((216, 270)), ((i % 5) * 216, (i // 5) * 270))
    planche.save(SORTIE.with_name("planche_linkedin.png"))
    vignettes[2].save(SORTIE.with_name("miniature_linkedin.png"))
    print(f"{SORTIE} : {sum(d for _, d in SCENES):.1f} s, {SORTIE.stat().st_size / 1e6:.1f} Mo")


if __name__ == "__main__":
    main()
