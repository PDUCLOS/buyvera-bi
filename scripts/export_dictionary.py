"""Exporte le dictionnaire de données (tables, colonnes, mesures, relations, rôles) depuis le TMDL.

Usage : python scripts/export_dictionary.py → docs/dictionnaire.md
Les descriptions viennent des commentaires `///` du TMDL, écrits par build_pbip.py.
"""
from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DEF = RACINE / "pbip" / "BuyveraBI.SemanticModel" / "definition"
SORTIE = RACINE / "docs" / "dictionnaire.md"


def nom(s: str) -> str:
    s = s.strip()
    return s[1:-1].replace("''", "'") if s.startswith("'") else s


def lire_table(chemin: Path) -> dict:
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    t = {"nom": "", "desc": "", "colonnes": [], "mesures": []}
    desc, courant = [], None
    for l in lignes:
        brut = l.strip()
        prof = len(l) - len(l.lstrip("\t"))
        if brut.startswith("///"):
            desc.append(brut[3:].strip())
            continue
        if prof == 0 and brut.startswith("table "):
            t["nom"], t["desc"], desc = nom(brut[6:]), " ".join(desc), []
        elif prof == 1 and brut.startswith("column "):
            m = re.match(r"column\s+('(?:[^']|'')+'|\S+)(\s*=.*)?", brut)
            courant = {"nom": nom(m.group(1)), "desc": " ".join(desc), "type": "", "cache": False,
                       "calc": bool(m.group(2)), "format": ""}
            t["colonnes"].append(courant)
            desc = []
        elif prof == 1 and brut.startswith("measure "):
            m = re.match(r"measure\s+('(?:[^']|'')+'|[^=\s]+)", brut)
            courant = {"nom": nom(m.group(1)), "desc": " ".join(desc), "dossier": "", "format": ""}
            t["mesures"].append(courant)
            desc = []
        elif prof == 1:
            courant, desc = None, []
        elif courant is not None and prof == 2:
            if brut.startswith("dataType:"):
                courant["type"] = brut.split(":", 1)[1].strip()
            elif brut == "isHidden":
                courant["cache"] = True
            elif brut.startswith("displayFolder:"):
                courant["dossier"] = brut.split(":", 1)[1].strip()
            elif brut.startswith("formatString:"):
                courant["format"] = brut.split(":", 1)[1].strip()
    return t


def cellule(s: str) -> str:
    return s.replace("|", "\\|") if s else ""


def main() -> None:
    tables = [lire_table(p) for p in sorted((DEF / "tables").glob("*.tmdl"))]
    rel = re.findall(r"fromColumn:\s*(\S+)\s+toColumn:\s*(\S+)", (DEF / "relationships.tmdl").read_text(encoding="utf-8"))
    roles = []
    for p in sorted((DEF / "roles").glob("*.tmdl")):
        txt = p.read_text(encoding="utf-8")
        d = re.search(r"^///\s*(.*)$", txt, re.M)
        f = re.findall(r"tablePermission\s+(\S+)\s*=\s*(.+)", txt)
        roles.append((p.stem, d.group(1) if d else "", "; ".join(f"`{a}` : `{b.strip()}`" for a, b in f) or "aucun"))

    out = ["# Dictionnaire de données — Buyvera BI", "",
           "Généré par `scripts/export_dictionary.py` depuis le modèle TMDL (`pbip/BuyveraBI.SemanticModel`). Ne pas modifier à la main.", "",
           f"{len(tables)} tables · {sum(len(t['colonnes']) for t in tables)} colonnes · "
           f"{sum(len(t['mesures']) for t in tables)} mesures · {len(rel)} relations · {len(roles)} rôles", "",
           "## Sommaire", ""]
    out += [f"- [{t['nom']}](#{t['nom'].lower().replace('_', '_')}) — {t['desc']}" for t in tables]
    out += ["", "## Relations", "", "Toutes de plusieurs vers un, filtrage dans un seul sens.", "",
            "| De (plusieurs) | Vers (un) |", "|---|---|"]
    out += [f"| `{a}` | `{b}` |" for a, b in rel]
    out += ["", "## Sécurité par ligne", "", "| Rôle | Description | Filtre |", "|---|---|---|"]
    out += [f"| {r} | {cellule(d)} | {f} |" for r, d, f in roles]

    mes = [m for t in tables for m in t["mesures"]]
    if mes:
        out += ["", "## Mesures", ""]
        for dossier in sorted({m["dossier"] for m in mes}):
            out += [f"### {dossier or 'Sans dossier'}", "", "| Mesure | Format | Description |", "|---|---|---|"]
            out += [f"| {cellule(m['nom'])} | `{cellule(m['format'])}` | {cellule(m['desc'])} |"
                    for m in mes if m["dossier"] == dossier]
            out.append("")

    out += ["## Tables et colonnes", ""]
    for t in tables:
        if not t["colonnes"] or t["nom"] == "_Mesures":
            continue
        out += [f"### {t['nom']}", "", t["desc"], "", "| Colonne | Type | Visible | Description |", "|---|---|---|---|"]
        for c in t["colonnes"]:
            typ = c["type"] + (" (calculée)" if c["calc"] else "")
            out.append(f"| `{c['nom']}` | {typ} | {'non' if c['cache'] else 'oui'} | {cellule(c['desc'])} |")
        out.append("")
    SORTIE.write_text("\n".join(out), encoding="utf-8")
    print(f"{SORTIE} : {len(tables)} tables, {len(mes)} mesures")


if __name__ == "__main__":
    main()
