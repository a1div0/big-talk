#!/usr/bin/env python3
"""big-talk lint — проверка инвариантов графа артефактов.

Использование:
  python tools/lint.py check [--strict]   # инварианты, exit 1 при ошибках
  python tools/lint.py matrix             # матрица прослеживаемости (markdown)
  python tools/lint.py graph              # граф связей в формате DOT
  python tools/lint.py budget             # текущее потребление бюджета сложности
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- модель типов

TYPES = {
    # type: (prefix, directory, allowed statuses)
    "axiom":       ("AX",     "axioms",        {"draft", "proposed", "accepted", "deprecated"}),
    "requirement": ("REQ",    "requirements",  {"draft", "proposed", "accepted", "deprecated"}),
    "element":     ("EL",     "spec",          {"draft", "proposed", "accepted", "deprecated"}),
    "adr":         ("ADR",    "adr",           {"proposed", "accepted", "rejected", "superseded"}),
    "precedent":   ("PREC",   "precedents",    {"draft", "accepted", "disputed"}),
    "actor":       ("ACT",    "actors",        {"draft", "accepted"}),
    "threat":      ("THR",    "actors/threats",{"open", "mitigated", "accepted"}),
    "dissent":     ("DIS",    "dissent",       {"open", "addressed", "accepted"}),
    "assumption":  ("ASM",    "assumptions",   {"draft", "accepted", "falsified"}),
    "test":        ("TEST",   "tests",         {"draft", "accepted", "deprecated"}),
    "test_run":    ("RUN",    "tests/runs",    {"done"}),
    "simulation":  ("SIM",    "sim/scenarios", {"draft", "accepted", "deprecated"}),
    "sim_run":     ("SIMRUN", "sim/runs",      {"done"}),
    "normative":   ("NORM",   "normative",     {"draft", "proposed", "accepted", "deprecated"}),
    "defect":      ("DEF",    "registry",      {"open", "resolved", "wontfix"}),
    "question":    ("OQ",     "registry",      {"open", "resolved"}),
    "risk":        ("RISK",   "registry",      {"accepted", "retired"}),
}
PREFIX_TO_TYPE = {v[0]: k for k, v in TYPES.items()}
ID_RE = re.compile(r"^(" + "|".join(PREFIX_TO_TYPE) + r")-\d{3,4}$")

# ключи frontmatter, значения которых — ссылки на другие артефакты
LINK_KEYS = [
    "derives_from", "satisfies", "applies_to", "decides", "decided_by", "depends_on",
    "precedents", "roles", "actor", "affected_by", "addressed_by", "mitigated_by",
    "accepted_as", "load_bearing_for", "verifies", "targets", "test", "scenario",
    "findings", "implements", "affects", "found_by", "resolved_by", "supersedes",
    "superseded_by", "dissent", "normative", "runs",
]

# обязательные секции в теле (по типу)
REQUIRED_SECTIONS = {
    "adr": ["## Контекст", "## Рассмотренные альтернативы",
            "## Стилмен отвергнутой альтернативы", "## Решение",
            "## Последствия", "## Принятые риски"],
    "test": ["## Назначение", "## Процедура", "## Рубрика", "## Формат результата"],
    "element": ["## Назначение", "## Правила", "## Поведение при неисполнении",
                "## Наблюдаемые индикаторы"],
    "precedent": ["## Что произошло", "## Какой механизм сработал или отказал",
                  "## Спор об интерпретации", "## Источники"],
    "requirement": ["## Формулировка", "## Критерий приёмки"],
    "axiom": ["## Формулировка", "## Почему это аксиома, а не требование"],
}

SKIP_DIRS = {"templates", "skills", "tools", "schemas", ".git", ".github", "node_modules"}

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)
TERM_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


class Artifact:
    def __init__(self, path: Path, fm: dict, body: str):
        self.path = path
        self.fm = fm
        self.body = body
        self.id = str(fm.get("id", ""))
        self.type = str(fm.get("type", ""))
        self.status = str(fm.get("status", ""))

    def links(self, key: str) -> list[str]:
        v = self.fm.get(key)
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            return [str(x) for x in v]
        return []

    def rel(self) -> str:
        return str(self.path.relative_to(ROOT))


class Report:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")


# ---------------------------------------------------------------- загрузка

def load_artifacts(rep: Report) -> dict[str, Artifact]:
    arts: dict[str, Artifact] = {}
    for path in sorted(ROOT.rglob("*.md")):
        parts = path.relative_to(ROOT).parts
        if parts[0] in SKIP_DIRS or path.name.upper() in {"README.MD", "GLOSSARY.MD", "CONSTITUTION.MD"}:
            continue
        if parts[0] == "deploy":
            continue
        text = path.read_text(encoding="utf-8")
        m = FM_RE.match(text)
        if not m:
            rep.err(path.relative_to(ROOT), "нет frontmatter (--- ... ---)")
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as e:
            rep.err(path.relative_to(ROOT), f"frontmatter не парсится: {e}")
            continue
        a = Artifact(path, fm, m.group(2))
        if not a.id:
            rep.err(a.rel(), "нет поля id")
            continue
        if a.id in arts:
            rep.err(a.rel(), f"дубликат id {a.id} (уже в {arts[a.id].rel()})")
            continue
        arts[a.id] = a
    return arts


def load_glossary() -> dict[str, str]:
    p = ROOT / "GLOSSARY.md"
    terms: dict[str, str] = {}
    if not p.exists():
        return terms
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            term = line[3:].strip()
            terms[term.lower()] = term
    return terms


def load_budget() -> dict:
    p = ROOT / "budget.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}


# ---------------------------------------------------------------- проверки

def check_structure(a: Artifact, rep: Report):
    if a.type not in TYPES:
        rep.err(a.rel(), f"неизвестный type '{a.type}'")
        return
    prefix, directory, statuses = TYPES[a.type]
    if not ID_RE.match(a.id):
        rep.err(a.rel(), f"id '{a.id}' не соответствует формату PREFIX-NNN")
    elif not a.id.startswith(prefix + "-"):
        rep.err(a.rel(), f"id '{a.id}' не соответствует type '{a.type}' (ожидался префикс {prefix})")
    if not a.path.name.startswith(a.id):
        rep.err(a.rel(), f"имя файла должно начинаться с id '{a.id}'")
    rel_dir = str(a.path.parent.relative_to(ROOT)).replace("\\", "/")
    if rel_dir != directory:
        rep.err(a.rel(), f"артефакт типа '{a.type}' должен лежать в {directory}/")
    if a.status not in statuses:
        rep.err(a.rel(), f"status '{a.status}' недопустим для {a.type}; допустимо: {sorted(statuses)}")
    if not a.fm.get("title"):
        rep.err(a.rel(), "нет поля title")
    for sec in REQUIRED_SECTIONS.get(a.type, []):
        if sec not in a.body:
            rep.err(a.rel(), f"нет обязательной секции '{sec}'")


def check_links(a: Artifact, arts: dict[str, Artifact], rep: Report):
    for key in LINK_KEYS:
        for ref in a.links(key):
            if ref == "all":
                continue
            if ref not in arts:
                rep.err(a.rel(), f"{key}: висячая ссылка на '{ref}'")


def check_rules(arts: dict[str, Artifact], rep: Report):
    by_type: dict[str, list[Artifact]] = defaultdict(list)
    for a in arts.values():
        by_type[a.type].append(a)

    # обратные индексы
    tests_for_req: dict[str, list[str]] = defaultdict(list)
    for t in by_type["test"]:
        for r in t.links("verifies"):
            tests_for_req[r].append(t.id)
    adrs_for_el: dict[str, list[Artifact]] = defaultdict(list)
    for d in by_type["adr"]:
        for e in d.links("decides"):
            adrs_for_el[e].append(d)
    runs_for_test: dict[str, list[Artifact]] = defaultdict(list)
    for r in by_type["test_run"]:
        for t in r.links("test"):
            runs_for_test[t].append(r)

    # AX
    for a in by_type["axiom"]:
        if "negotiable" not in a.fm:
            rep.err(a.rel(), "аксиома обязана иметь поле negotiable: true|false")
        if not a.fm.get("provenance"):
            rep.err(a.rel(), "аксиома обязана иметь provenance (кто и почему зафиксировал)")

    # REQ
    for a in by_type["requirement"]:
        if not a.links("derives_from"):
            rep.err(a.rel(), "требование должно выводиться из аксиомы или другого требования (derives_from)")
        if a.status == "accepted" and not tests_for_req.get(a.id):
            rep.err(a.rel(), "принятое требование не покрыто ни одним TEST (verifies)")
        elif not tests_for_req.get(a.id):
            rep.warn(a.rel(), "требование пока не покрыто тестом")

    # EL
    for a in by_type["element"]:
        decided = a.links("decided_by") or [d.id for d in adrs_for_el.get(a.id, [])]
        if not decided:
            (rep.err if a.status == "accepted" else rep.warn)(a.rel(), "элемент без ADR (decided_by)")
        else:
            acc = [arts[d].status for d in decided if d in arts]
            if a.status == "accepted" and "accepted" not in acc:
                rep.err(a.rel(), "принятый элемент должен опираться хотя бы на один принятый ADR")
        if not a.links("satisfies"):
            rep.err(a.rel(), "элемент не привязан ни к одному требованию (satisfies)")
        for dep in a.links("depends_on"):
            if dep in arts and a.status == "accepted" and arts[dep].status != "accepted":
                rep.warn(a.rel(), f"принятый элемент зависит от непринятого {dep}")
        if a.status == "accepted" and not a.links("normative"):
            rep.err(a.rel(), "принятый элемент должен иметь нормативный текст (normative)")

    # ADR
    for a in by_type["adr"]:
        if not a.links("decides"):
            rep.err(a.rel(), "ADR должен указывать, какие элементы он решает (decides)")
        if not a.links("satisfies"):
            rep.warn(a.rel(), "ADR не ссылается на требования (satisfies)")
        if not a.links("precedents"):
            rep.warn(a.rel(), "ADR без прецедентов — обоснование опирается только на рассуждение")
        alts = len(re.findall(r"^### ", a.body[a.body.find("## Рассмотренные альтернативы"):a.body.find("## Стилмен")], re.M)) \
            if "## Рассмотренные альтернативы" in a.body and "## Стилмен" in a.body else 0
        if alts < 2:
            rep.err(a.rel(), "ADR должен рассматривать минимум две альтернативы (подзаголовки ### в секции альтернатив)")
        if a.status == "superseded" and not a.links("superseded_by"):
            rep.err(a.rel(), "superseded ADR должен указывать superseded_by")

    # PREC
    for a in by_type["precedent"]:
        cc = a.fm.get("causal_confidence")
        if cc not in {"high", "medium", "low", "contested"}:
            rep.err(a.rel(), "прецедент обязан иметь causal_confidence: high|medium|low|contested")
        if not a.fm.get("sources"):
            rep.err(a.rel(), "прецедент без источников не принимается")

    # THR
    for a in by_type["threat"]:
        if not a.links("actor"):
            rep.err(a.rel(), "угроза должна иметь актора")
        if not a.links("mitigated_by") and not a.links("accepted_as"):
            (rep.err if a.status != "open" else rep.warn)(a.rel(), "угроза без митигации (mitigated_by) и без принятого риска (accepted_as)")
        if not a.fm.get("capability_required"):
            rep.err(a.rel(), "угроза должна описывать capability_required (что нужно атакующему)")

    # DIS
    for a in by_type["dissent"]:
        if not a.links("actor"):
            rep.err(a.rel(), "разногласие должно указывать актора")
        if not a.links("affected_by"):
            rep.err(a.rel(), "разногласие должно указывать, какой элемент/аксиома ущемляет интерес (affected_by)")
        if not a.fm.get("likely_response"):
            rep.err(a.rel(), "разногласие должно предсказывать likely_response (что актор будет делать)")
        if a.status == "addressed" and not a.links("addressed_by"):
            rep.err(a.rel(), "статус addressed требует addressed_by")

    # ASM
    for a in by_type["assumption"]:
        if not a.fm.get("if_false"):
            rep.err(a.rel(), "допущение обязано описывать if_false (что ломается)")
        if not a.links("load_bearing_for"):
            rep.warn(a.rel(), "допущение ничего не держит (load_bearing_for пуст) — зачем оно?")

    # TEST
    for a in by_type["test"]:
        if not a.links("verifies"):
            rep.err(a.rel(), "тест должен верифицировать хотя бы одно требование (verifies)")
        if a.fm.get("kind") not in {"thought", "simulation", "lint"}:
            rep.err(a.rel(), "тест обязан иметь kind: thought|simulation|lint")

    # RUN
    for a in by_type["test_run"]:
        if not a.links("test"):
            rep.err(a.rel(), "прогон должен указывать test")
        if a.fm.get("result") not in {"pass", "fail", "inconclusive"}:
            rep.err(a.rel(), "прогон обязан иметь result: pass|fail|inconclusive")
        if a.fm.get("result") == "fail" and not a.links("findings"):
            rep.err(a.rel(), "проваленный прогон обязан порождать findings (DEF/OQ)")
        if not a.fm.get("executor"):
            rep.err(a.rel(), "прогон обязан указывать executor (human:<кто> или agent:<модель>)")
        if not a.fm.get("date"):
            rep.err(a.rel(), "прогон обязан иметь date")

    # SIM
    for a in by_type["sim_run"]:
        if not a.links("scenario"):
            rep.err(a.rel(), "прогон симуляции должен указывать scenario")
        if not a.links("findings"):
            rep.warn(a.rel(), "прогон симуляции без findings — что мы из него вынесли?")

    # NORM
    for a in by_type["normative"]:
        if not a.links("implements"):
            rep.err(a.rel(), "нормативный текст должен реализовывать элемент (implements)")

    # registry
    for a in by_type["defect"] + by_type["question"]:
        if not a.links("affects"):
            rep.err(a.rel(), "запись реестра должна указывать affects")
        if a.status == "resolved" and not a.links("resolved_by"):
            rep.err(a.rel(), "статус resolved требует resolved_by (ADR или RUN)")
    for a in by_type["risk"]:
        if not a.links("affects"):
            rep.err(a.rel(), "принятый риск должен указывать affects")
        if not a.links("resolved_by"):
            rep.err(a.rel(), "принятый риск — это решение: нужен ADR в resolved_by")

    # прогоны для принятых элементов
    for a in by_type["element"]:
        if a.status != "accepted":
            continue
        applicable = [t for t in by_type["test"] if "all" in t.links("targets") or a.id in t.links("targets")]
        for t in applicable:
            runs = [r for r in runs_for_test.get(t.id, []) if a.id in r.links("targets") or "all" in r.links("targets")]
            if not runs:
                rep.err(a.rel(), f"принятый элемент не имеет прогона теста {t.id}")
            elif all(r.fm.get("result") == "fail" for r in runs):
                rep.err(a.rel(), f"все прогоны {t.id} провалены, элемент не может быть accepted")


def check_glossary(arts: dict[str, Artifact], rep: Report):
    terms = load_glossary()
    used: set[str] = set()
    for a in arts.values():
        if a.type not in {"element", "requirement", "axiom", "normative", "test"}:
            continue
        for m in TERM_RE.finditer(a.body):
            term = m.group(1).strip().lower()
            used.add(term)
            if term not in terms:
                rep.err(a.rel(), f"термин [[{m.group(1)}]] не определён в GLOSSARY.md")
    for t, orig in terms.items():
        if t not in used:
            rep.warn("GLOSSARY.md", f"термин «{orig}» определён, но нигде не используется как [[{orig}]]")


def words(text: str) -> int:
    return len(re.findall(r"\w+", text, re.U))


def compute_budget(arts: dict[str, Artifact]) -> dict:
    els = [a for a in arts.values() if a.type == "element"]
    norms = [a for a in arts.values() if a.type == "normative"]
    roles = [a for a in arts.values() if a.type == "actor" and a.fm.get("kind") == "role"]

    def depth(eid: str, seen=()) -> int:
        if eid in seen or eid not in arts:
            return 0
        deps = arts[eid].links("depends_on")
        return 0 if not deps else 1 + max(depth(d, seen + (eid,)) for d in deps)

    return {
        "spec_words": sum(words(a.body) for a in els),
        "normative_words": sum(words(a.body) for a in norms),
        "elements": len(els),
        "roles": len(roles),
        "max_depends_depth": max((depth(a.id) for a in els), default=0),
        "max_links_per_element": max((sum(len(a.links(k)) for k in LINK_KEYS) for a in els), default=0),
        "exceptions": sum(len(re.findall(r"^\s*(?:\d+\.|-)\s*Исключение", a.body, re.M | re.I)) for a in els),
    }


def check_budget(arts: dict[str, Artifact], rep: Report):
    budget = load_budget()
    if not budget:
        rep.warn("budget.yaml", "бюджет сложности не задан")
        return
    usage = compute_budget(arts)
    for key, limit in budget.items():
        if key in usage and usage[key] > limit:
            rep.err("budget.yaml", f"{key}: {usage[key]} > лимита {limit}")


# ---------------------------------------------------------------- команды

def cmd_check(strict: bool) -> int:
    rep = Report()
    arts = load_artifacts(rep)
    for a in arts.values():
        check_structure(a, rep)
        check_links(a, arts, rep)
    check_rules(arts, rep)
    check_glossary(arts, rep)
    check_budget(arts, rep)
    for w in rep.warnings:
        print(f"WARN  {w}")
    for e in rep.errors:
        print(f"ERROR {e}")
    print(f"\n{len(arts)} артефактов, {len(rep.errors)} ошибок, {len(rep.warnings)} предупреждений")
    return 1 if rep.errors or (strict and rep.warnings) else 0


def cmd_matrix() -> int:
    rep = Report()
    arts = load_artifacts(rep)
    reqs = sorted((a for a in arts.values() if a.type == "requirement"), key=lambda a: a.id)
    els = [a for a in arts.values() if a.type == "element"]
    tests = [a for a in arts.values() if a.type == "test"]
    runs = [a for a in arts.values() if a.type == "test_run"]
    print("| REQ | из | статус | элементы | ADR | тесты | последний результат |")
    print("|---|---|---|---|---|---|---|")
    for r in reqs:
        el_ids = [e.id for e in els if r.id in e.links("satisfies")]
        adr_ids = sorted({d for e in els if r.id in e.links("satisfies") for d in e.links("decided_by")})
        t_ids = [t.id for t in tests if r.id in t.links("verifies")]
        last = {}
        for run in sorted(runs, key=lambda x: str(x.fm.get("date"))):
            for t in run.links("test"):
                if t in t_ids:
                    last[t] = run.fm.get("result")
        res = ", ".join(f"{k}:{v}" for k, v in last.items()) or "—"
        print(f"| {r.id} | {', '.join(r.links('derives_from'))} | {r.status} | "
              f"{', '.join(el_ids) or '—'} | {', '.join(adr_ids) or '—'} | {', '.join(t_ids) or '—'} | {res} |")
    return 0


def cmd_graph() -> int:
    rep = Report()
    arts = load_artifacts(rep)
    print("digraph politeia {\n  rankdir=LR; node [shape=box, fontsize=10];")
    for a in arts.values():
        print(f'  "{a.id}" [label="{a.id}\\n{a.type}"];')
    for a in arts.values():
        for key in LINK_KEYS:
            for ref in a.links(key):
                if ref in arts:
                    print(f'  "{a.id}" -> "{ref}" [label="{key}", fontsize=8];')
    print("}")
    return 0


def cmd_budget() -> int:
    rep = Report()
    arts = load_artifacts(rep)
    usage = compute_budget(arts)
    budget = load_budget()
    print("| метрика | сейчас | лимит |")
    print("|---|---|---|")
    for k, v in usage.items():
        print(f"| {k} | {v} | {budget.get(k, '—')} |")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--strict", action="store_true", help="предупреждения считать ошибками")
    sub.add_parser("matrix")
    sub.add_parser("graph")
    sub.add_parser("budget")
    args = p.parse_args()
    if args.cmd == "check":
        return cmd_check(args.strict)
    return {"matrix": cmd_matrix, "graph": cmd_graph, "budget": cmd_budget}[args.cmd]()


if __name__ == "__main__":
    sys.exit(main())
