# Схемы frontmatter

Каждый артефакт — markdown-файл с YAML-frontmatter. Ключи ниже — единственный
способ провязать артефакты; линтер (`tools/lint.py`) проверяет их существование
и направление. Свободный текст живёт в теле файла.

## Общие поля

| поле | обяз. | значение |
|---|---|---|
| `id` | да | `PREFIX-NNN`, совпадает с началом имени файла |
| `type` | да | см. таблицу типов |
| `title` | да | одна строка |
| `status` | да | зависит от типа |
| `created` | да | дата |
| `owners` | нет | люди или агенты, отвечающие за артефакт |

## Типы

| type | префикс | каталог | статусы | обязательные поля/секции |
|---|---|---|---|---|
| axiom | AX | axioms/ | draft, proposed, accepted, deprecated | `negotiable`, `provenance`; секции Формулировка, Почему это аксиома |
| requirement | REQ | requirements/ | draft, proposed, accepted, deprecated | `derives_from`; секции Формулировка, Критерий приёмки; accepted ⇒ есть TEST |
| element | EL | spec/ | draft, proposed, accepted, deprecated | `satisfies`, `decided_by`; секции Назначение, Правила, Поведение при неисполнении, Наблюдаемые индикаторы; accepted ⇒ принятый ADR, `normative`, прогоны всех применимых тестов |
| adr | ADR | adr/ | proposed, accepted, rejected, superseded | `decides`; секции Контекст, Рассмотренные альтернативы (≥2 `###`), Стилмен отвергнутой альтернативы, Решение, Последствия, Принятые риски |
| precedent | PREC | precedents/ | draft, accepted, disputed | `causal_confidence`, `sources`; секции Что произошло, Какой механизм сработал или отказал, Спор об интерпретации, Источники |
| actor | ACT | actors/ | draft, accepted | `kind: role\|group\|external` |
| threat | THR | actors/threats/ | open, mitigated, accepted | `actor`, `capability_required`, и `mitigated_by` или `accepted_as` |
| dissent | DIS | dissent/ | open, addressed, accepted | `actor`, `affected_by`, `likely_response` |
| assumption | ASM | assumptions/ | draft, accepted, falsified | `if_false`, `load_bearing_for` |
| test | TEST | tests/ | draft, accepted, deprecated | `kind`, `verifies`, `targets`; секции Назначение, Процедура, Рубрика, Формат результата |
| test_run | RUN | tests/runs/ | done | `test`, `targets`, `executor`, `date`, `result`; fail ⇒ `findings` |
| simulation | SIM | sim/scenarios/ | draft, accepted, deprecated | `targets` |
| sim_run | SIMRUN | sim/runs/ | done | `scenario`, `findings` |
| normative | NORM | normative/ | draft, proposed, accepted, deprecated | `implements` |
| defect / question | DEF / OQ | registry/ | open, resolved, wontfix | `affects`; resolved ⇒ `resolved_by` |
| risk | RISK | registry/ | accepted, retired | `affects`, `resolved_by` (ADR, принявший риск) |

## Ключи-ссылки

`derives_from, satisfies, applies_to, decides, decided_by, depends_on, precedents,
roles, actor, affected_by, addressed_by, mitigated_by, accepted_as, load_bearing_for,
verifies, targets, test, scenario, findings, implements, affects, found_by,
resolved_by, supersedes, superseded_by, dissent, normative, runs`

Значение — список id. Особое значение `all` допустимо в `targets` и `applies_to`.

## Инварианты, которые проверяет линтер

1. Уникальность id; соответствие id ↔ type ↔ каталог ↔ имя файла.
2. Нет висячих ссылок.
3. EL: ≥1 REQ; accepted ⇒ ≥1 accepted ADR, ≥1 NORM, прогон каждого применимого TEST, ни один не «все прогоны провалены».
4. REQ: выводится из AX/REQ; accepted ⇒ покрыт TEST.
5. ADR: решает ≥1 EL; ≥2 альтернативы; стилмен отвергнутой; принятые риски.
6. PREC: источники и уверенность в причинной интерпретации.
7. THR: актор, требуемая способность, митигация или принятый риск.
8. DIS: актор, ущемляющий элемент, прогноз поведения.
9. ASM: что ломается, если ложно.
10. RUN: fail ⇒ findings; executor и date.
11. RISK: принят через ADR.
12. Глоссарий: каждый `[[термин]]` в AX/REQ/EL/NORM/TEST определён в GLOSSARY.md.
13. Бюджет сложности (budget.yaml) не превышен.
