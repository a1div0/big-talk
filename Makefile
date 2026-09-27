.PHONY: lint strict matrix graph budget new

lint:            ## проверить инварианты графа
	python3 tools/lint.py check

strict:          ## то же, предупреждения = ошибки
	python3 tools/lint.py check --strict

matrix:          ## матрица прослеживаемости REQ → EL → ADR → TEST
	python3 tools/lint.py matrix

graph:           ## граф связей (нужен graphviz для картинки)
	python3 tools/lint.py graph > graph.dot && dot -Tsvg graph.dot -o graph.svg || true

budget:          ## потребление бюджета сложности
	python3 tools/lint.py budget

new:             ## make new TYPE=adr — создать артефакт из шаблона со следующим номером
	python3 tools/new.py $(TYPE)
