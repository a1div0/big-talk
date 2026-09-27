#!/usr/bin/env python3
"""Создать новый артефакт из шаблона со следующим свободным номером.
python tools/new.py adr  ->  adr/ADR-0002-slug.md
"""
import re, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP = {  # type -> (prefix, dir, template, digits)
    "axiom": ("AX", "axioms", "AX.md", 3), "requirement": ("REQ", "requirements", "REQ.md", 3),
    "element": ("EL", "spec", "EL.md", 3), "adr": ("ADR", "adr", "ADR.md", 4),
    "precedent": ("PREC", "precedents", "PREC.md", 4), "actor": ("ACT", "actors", "ACT.md", 3),
    "threat": ("THR", "actors/threats", "THR.md", 3), "dissent": ("DIS", "dissent", "DIS.md", 3),
    "assumption": ("ASM", "assumptions", "ASM.md", 3), "test": ("TEST", "tests", "TEST.md", 3),
    "test_run": ("RUN", "tests/runs", "RUN.md", 4), "simulation": ("SIM", "sim/scenarios", "SIM.md", 3),
    "sim_run": ("SIMRUN", "sim/runs", "SIMRUN.md", 4), "normative": ("NORM", "normative", "NORM.md", 3),
    "defect": ("DEF", "registry", "DEF.md", 3), "question": ("OQ", "registry", "OQ.md", 3),
    "risk": ("RISK", "registry", "RISK.md", 3),
}

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in MAP:
        print("тип:", ", ".join(MAP)); return 1
    t = sys.argv[1]; slug = sys.argv[2] if len(sys.argv) > 2 else "untitled"
    prefix, d, tpl, digits = MAP[t]
    nums = [int(m.group(1)) for p in (ROOT / d).glob(f"{prefix}-*.md")
            if (m := re.match(rf"{prefix}-(\d+)", p.name))]
    nid = f"{prefix}-{(max(nums) + 1 if nums else 1):0{digits}d}"
    text = (ROOT / "templates" / tpl).read_text(encoding="utf-8")
    text = text.replace(f"{prefix}-000", nid).replace("YYYY-MM-DD", date.today().isoformat())
    out = ROOT / d / f"{nid}-{slug}.md"
    out.write_text(text, encoding="utf-8"); print(out.relative_to(ROOT)); return 0

if __name__ == "__main__":
    sys.exit(main())
