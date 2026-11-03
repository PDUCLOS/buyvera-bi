"""Pousse la table _Mesures (définie dans build_pbip.py) dans le modèle ouvert dans Power BI Desktop.

Usage : python scripts/push_mesures.py
Évite de relancer Desktop pour tester une mesure. Les fichiers TMDL restent la source :
relancer ensuite build_pbip.py (déjà fait si les mesures viennent de là) et rouvrir le projet
avant d'enregistrer depuis Desktop.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE))
import build_pbip as b  # noqa: E402


def main() -> int:
    mesures = [{"name": n, "expression": e, "displayFolder": f, "description": d,
                **({"formatString": fmt} if fmt else {})} for n, f, fmt, d, e in b.MESURES]
    table = {
        "name": "_Mesures",
        "columns": [{"name": "masque", "dataType": "int64", "isHidden": True, "type": "calculatedTableColumn",
                     "isNameInferred": True, "sourceColumn": "[masque]"}],
        "partitions": [{"name": "_Mesures", "source": {"type": "calculated", "expression": 'ROW ( "masque", 0 )'}}],
        "measures": mesures,
    }
    cmd = {"sequence": {"operations": [
        {"createOrReplace": {"object": {"database": "__DB__", "table": "_Mesures"}, "table": table}},
        {"refresh": {"type": "calculate", "objects": [{"database": "__DB__"}]}},
    ]}}
    fichier = RACINE.parent / "tests" / "dax" / "_push_mesures.json"
    fichier.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            str(RACINE / "dax_query.ps1"), "-Fichier", str(fichier)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(r.stdout.strip() or r.stderr.strip())
        return r.returncode
    finally:
        fichier.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
