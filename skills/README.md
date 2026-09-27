# Скиллы для агентов

Формат совместим с Claude Code / Agent Skills: `skills/<name>/SKILL.md` с frontmatter
`name`, `description`. Чтобы Claude Code видел их, сделайте `ln -s ../skills .claude/skills`
или скопируйте.

Общие правила для всех скиллов:
1. Агент не мержит и не переводит артефакты в accepted. Всё, что он создаёт, — proposed/draft/done.
2. Каждый созданный артефакт проходит `python tools/lint.py check` до открытия PR.
3. `executor: agent:<модель>` в каждом RUN и SIMRUN.
4. Агент, написавший EL, не прогоняет тесты на этот EL в той же сессии.
5. Ссылки только на существующие id. Нет id — сначала создать артефакт через `tools/new.py`.
