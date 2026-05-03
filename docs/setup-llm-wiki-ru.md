# Как собрать свою LLM-вики

Рецепт персонального хранилища знаний, с которым LLM умеет работать напрямую. Каждая сессия Claude / Cursor / opencode превращается в поток атомарных заметок, которые можно грепать, линковать и возвращаться к ним через полгода.

## Что это такое

Плоская директория с markdown-заметками: имя файла с префиксом-категорией, YAML-frontmatter, Obsidian-стиль `[[wikilinks]]` и маленький Python-скрипт, который перегенерирует индексы по команде. В начале сессии LLM читает `CLAUDE.md` и «загружает» хранилище в контекст — поэтому он может ссылаться на твои прошлые заметки, а не изобретать всё заново.

## Происхождение

Этот рецепт — конкретная реализация паттерна, который Андрей Карпатый описывает в [*The agent-maintained LLM wiki*](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). Он формулирует базовую архитектуру: три слоя (**raw sources → agent-owned wiki → schema document**), воркфлоу ingest / query / lint, `index.md` + `log.md` с префиксом `## [YYYY-MM-DD] event | title`, и философию — *«LLM берёт на себя bookkeeping; человек курирует источники, задаёт хорошие вопросы и думает, что всё это значит».* Если не читал гист — начни с него, там короче и понятнее объяснено *зачем*.

Этот гайд добавляет opinionated-специфику, которую Карпатый намеренно оставляет открытой:

- Развёрнутая схема префиксов имён (`concept--`, `arch-decision--`, `bug-pattern--`, …), которая удобно ложится на процесс ингеста.
- Автогенерящийся `glossary.md` рядом с индексом — источник определений это строка `> **TL;DR:**` в каждой заметке.
- Разделение памяти на статичную и живую (`user.md` / `preferences.md` vs. `current.md` / `future.md` / `daily/`) — LLM получает и контекст идентичности, и состояние сессии.
- Готовые `CLAUDE.md` и `rebuild_index.py` — можно развернуть за 15 минут, ничего не придумывая с нуля.

## Зачем это нужно

- **История чатов испаряется.** Закрытые вкладки — всё, их нет. Атомарные заметки остаются.
- **grep — это твой RAG.** 300 атомарных заметок отлично ищутся `ls prefix--*` и `grep`. Векторная база не нужна.
- **LLM хорошо умеет резюмировать.** Двухчасовая отладка ужимается Claude'ом в одну заметку с TL;DR и выводами.
- **Форкается и приватно.** Это git-репозиторий из plain text. Ни сервера, ни SaaS, ни привязки к вендору.

## Архитектура в двух словах

```
~/my-knowledge/
├── CLAUDE.md                    ← инструкции, которые Claude читает при старте сессии
├── README.md                    ← необязательный вход «для людей»
├── log.md                       ← хронологическая лента только на append
├── memory/                      ← кто ты, что делаешь сейчас
│   ├── user.md                  ←   кто ты (статично)
│   ├── preferences.md           ←   как тебе удобно работать
│   ├── decisions.md             ←   архитектурные решения по проектам
│   ├── people.md                ←   коллеги, команды, имена
│   ├── current.md               ←   срез: активные проекты и приоритеты
│   ├── future.md                ←   предстоящие планы и идеи
│   └── daily/
│       └── YYYY-MM-DD.md        ←   рабочий лог за день
├── moc--master-index.md         ← корневой каталог (автогенерится)
├── moc--*.md                    ← оглавления по доменам (автогенерятся)
├── glossary.md                  ← алфавитный глоссарий (автогенерится)
├── concept--*.md                ← атомарные заметки-определения
├── arch-decision--*.md          ← ADR-записи
├── arch-pattern--*.md
├── arch-system--*.md
├── bug-issue--*.md              ← конкретные баги и их фиксы
├── bug-pattern--*.md            ← повторяющиеся паттерны багов
├── dev-snippet--*.md            ← сниппеты кода
├── dev-workflow--*.md           ← процессы и воркфлоу
├── dev-config--*.md             ← конфиги
├── tool--*.md                   ← документация к инструментам
├── synthesis--*.md              ← кросс-заметочные синтезы / запомненные ответы на вопросы
└── rebuild_index.py             ← перегенерирует MOC и глоссарий
```

**Всё плоско.** Папок-категорий нет — категоризацию делает префикс имени файла. Почему: `ls concept--ios*` работает из любой точки; «переложить заметку в другую категорию» — это переименование, а не перемещение между папками; граф в Obsidian сразу показывает всё хранилище одной сетью.

## Шаблон заметки

Каждая заметка устроена одинаково:

```markdown
---
title: Человекочитаемый заголовок
tags: [domain, type, maturity]
lang: ru
created: 2026-04-18
source: claude-session
session_file: original-export-filename.md
related: []
---

# Человекочитаемый заголовок

> **TL;DR:** Одно предложение — именно оно попадёт в глоссарий.

## Detail

Текст, код, что нужно по теме.
```

**Правила:**
- `title:` — то, что читает человек. Заверни в `"..."`, если внутри есть `:` или другие YAML-спецсимволы.
- `tags:` — один домен (ios, swift, backend, lifestyle…), один тип (concept, pattern, decision…), один уровень зрелости (`draft` или `mature`).
- `lang:` — `en` или `ru`. Определяй по телу заметки.
- `source:` — откуда приехала заметка (`claude-session`, `perplexity`, `manual`, …).
- `related:` — список stem-имён соседних заметок. LLM можно попросить заполнить это поле при ингесте.
- Строка `> **TL;DR:**` — **обязательная**, именно на ней строится автоглоссарий.

## Префиксы имён

| Префикс | Для чего |
|---|---|
| `concept--` | атомарное определение термина/идеи |
| `arch-decision--` | ADR — архитектурное решение с обоснованием |
| `arch-pattern--` | переиспользуемый архитектурный паттерн |
| `arch-system--` | обзор на уровне системы |
| `bug-issue--` | один конкретный баг + фикс |
| `bug-pattern--` | повторяющийся паттерн отказа |
| `dev-snippet--` | кусок кода |
| `dev-workflow--` | процесс / воркфлоу |
| `dev-config--` | конфиг / настройки |
| `tool--` | документация к инструменту |
| `synthesis--` | кросс-заметочный разбор, запомненный ответ |

Формат слага: `prefix--slugified-title.md` — нижний регистр, через дефис, максимум ~6 слов.

## Файлы памяти

Память делится на **статичную** (меняется редко) и **живую** (меняется каждую сессию).

**Статичная** (создаёшь один раз, правишь по мере изменений):
- `memory/user.md` — кто ты, чем занимаешься, где сильные стороны.
- `memory/preferences.md` — стиль кода, формат ответов, то, что ты уже просил LLM не делать.
- `memory/decisions.md` — архитектурные решения, на которых ты остановился.
- `memory/people.md` — коллеги, команды, повторяющиеся имена.

**Живая** (обновляется каждую сессию):
- `memory/current.md` — активные проекты, приоритеты, блокеры. Срез «прямо сейчас».
- `memory/future.md` — предстоящие события, планы, идеи для изучения.
- `memory/daily/YYYY-MM-DD.md` — append-only лог за день: секции `## HH:MM — <заголовок>`.

LLM читает всё это на старте сессии (это прописано в `CLAUDE.md`). Когда сессия заканчивается — обновляет `current.md` / `future.md`, если что-то сдвинулось, и дописывает в дневной лог.

## log.md — лента хранилища

Один append-only файл в корне, куда записываются значимые операции над хранилищем. По одной записи на ингест, синтез или проход по чистке:

```markdown
## [2026-04-18] ingest | 38 Claude-сессий → 28 новых заметок

Короткий контекст (1–3 строки).
```

События: `ingest`, `synthesis`, `query` (только если ответ сам стал заметкой), `lint`, `meta`. Тривиальные чаты пропускай.

Удобно грепать: `grep "^## \[" log.md | tail -20`.

## Bootstrap

```bash
mkdir -p ~/my-knowledge/memory/daily ~/my-knowledge/.manifests
cd ~/my-knowledge
git init
```

Создай `CLAUDE.md` (стартер ниже), создай `rebuild_index.py` (код ниже), напиши первую заметку руками, запусти `python3 rebuild_index.py`, закоммить.

### Стартовый `CLAUDE.md`

```markdown
# Claude Code Instructions — Knowledge Vault

## Memory: Read at Session Start

В начале каждой сессии в этой директории молча прочитай:

**Статично** (идентичность + предпочтения — меняются редко):
- `memory/user.md`
- `memory/preferences.md`
- `memory/decisions.md`
- `memory/people.md`

**Живое** (меняется часто — всегда читай):
- `memory/current.md`
- `memory/future.md`
- Самый свежий файл в `memory/daily/` (вчера-позавчера)

Пробеги по концу `log.md`:

    grep "^## \[" log.md | tail -20
    ls -t memory/daily/ | head -3

## Log.md — Append-Only Timeline

Добавляй одну запись на ингест, синтез или чистку:

    ## [YYYY-MM-DD] <event> | <title>

    <1–3 строки контекста>

События: `ingest`, `synthesis`, `query`, `lint`, `meta`. Тривиальные чаты пропускай.

## Обновления памяти

**Во время сессии — пиши в дневной лог:**

Любое значимое решение или сдвиг контекста идёт в `memory/daily/YYYY-MM-DD.md`:

    ## HH:MM — <заголовок>

    <1–3 строки тела>

Хронологически, новое снизу.

**В конце сессии:**
- Обнови `memory/current.md`, если проекты/приоритеты/блокеры сдвинулись.
- Обнови `memory/future.md`, если появились новые события/планы/идеи.
- Обновляй статичную память только под действительно долгоживущие новые факты (новый инструмент, новое предпочтение, новое решение).

## Правила заметок

- Хранилище плоское — все заметки в корне. Префикс имени файла = категория.
- Frontmatter: `title`, `tags`, `lang`, `created`, `source`, `related`.
- Каждая заметка начинается с `# Title`, потом `> **TL;DR:** <одно предложение>`.
- Wikilinks: `[[stem]]` — без `.md`.
- Префиксы: `concept--`, `arch-decision--`, `arch-pattern--`, `arch-system--`, `bug-issue--`, `bug-pattern--`, `dev-snippet--`, `dev-workflow--`, `dev-config--`, `tool--`, `synthesis--`.

## Ключевые скрипты

- `python3 rebuild_index.py` — перегенерирует все MOC и `glossary.md`. Запускай после каждого добавления / переименования / правки TL;DR.

## Сохранение ответов на чат-запросы

Если разговор породил содержательный синтезированный ответ (сравнение, анализ, связь между заметками), предложи сохранить его как `synthesis--<slug>.md`. Добавь запись в `log.md`.
```

### Стартовый `rebuild_index.py`

Drop-in, только stdlib, ~150 строк. Перегенерирует все MOC, мастер-индекс и глоссарий, плюс докладывает о битых wikilinks.

```python
#!/usr/bin/env python3
"""Rebuild MOC files, master index, and glossary from existing vault notes."""

import re
from pathlib import Path
from collections import defaultdict
from datetime import date as dt

VAULT = Path(__file__).parent

FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---', re.DOTALL)
TLDR_RE = re.compile(r'>\s*\*\*TL;DR:\*\*\s*(.+)')
WIKILINK_RE = re.compile(r'\[\[([^\]]+)\]\]')
FENCED_CODE_RE = re.compile(r'```.*?```', re.DOTALL)
INLINE_CODE_RE = re.compile(r'`[^`\n]+`')
LEADING_ARTICLE_RE = re.compile(r'^(the|a|an)\s+', re.IGNORECASE)


def parse_frontmatter(content):
    m = FRONTMATTER_RE.match(content)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        if ':' in line:
            key, _, val = line.partition(':')
            val = val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            result[key.strip()] = val
    return result


def scan_notes(vault):
    notes = []
    for path in sorted(vault.glob("*.md")):
        stem = path.stem
        if stem.startswith(("_template", "moc--")) or stem in ("log", "CLAUDE", "README", "glossary"):
            continue
        content = path.read_text()
        fm = parse_frontmatter(content)
        tldr_m = TLDR_RE.search(content)
        notes.append({
            "path": path, "stem": stem,
            "title": fm.get("title", stem),
            "tldr": tldr_m.group(1).strip() if tldr_m else "",
            "content": content,
        })
    return notes


def strip_code(content):
    return INLINE_CODE_RE.sub('', FENCED_CODE_RE.sub('', content))


def _link_target(link):
    return link.split("|", 1)[0].split("#", 1)[0].strip()


def count_wikilinks(notes):
    counts = defaultdict(int)
    for n in notes:
        for link in WIKILINK_RE.findall(strip_code(n["content"])):
            counts[_link_target(link)] += 1
    return counts


def find_broken(notes, vault):
    stems = {n["stem"] for n in notes}
    broken = []
    for n in notes:
        for link in WIKILINK_RE.findall(strip_code(n["content"])):
            target = _link_target(link)
            if target not in stems and not (vault / f"{target}.md").exists():
                broken.append(f"{n['stem']}: [[{link}]]")
    return broken


def _note_line(n):
    return f"- [[{n['stem']}]] — {n['tldr'] or n['title']}"


def build_moc(title, prefixes, notes):
    matching = [n for n in notes if any(n["stem"].startswith(p) for p in prefixes)]
    lines = ["---", f"title: {title}", "tags: [moc, index]", "---", "", f"# {title}", ""]
    lines += [_note_line(n) for n in matching] if matching else ["_No notes yet._"]
    return "\n".join(lines) + "\n"


MOC_SPECS = [
    ("moc--architecture.md", "Architecture", ["arch-decision--", "arch-pattern--", "arch-system--"]),
    ("moc--development.md",  "Development",  ["dev-snippet--", "dev-workflow--", "dev-config--"]),
    ("moc--debugging.md",    "Debugging",    ["bug-issue--", "bug-pattern--"]),
    ("moc--tools.md",        "Tools",        ["tool--"]),
    ("moc--concepts.md",     "Concepts",     ["concept--"]),
    ("moc--synthesis.md",    "Synthesis",    ["synthesis--"]),
]

GLOSSARY_PREFIXES = ("concept--", "arch-pattern--", "arch-system--",
                     "arch-decision--", "bug-pattern--", "tool--")


def _gkey(title):
    return LEADING_ARTICLE_RE.sub("", title).lower()


def _gletter(title):
    k = _gkey(title)
    if not k:
        return "#"
    c = k[0].upper()
    return c if c.isalpha() else "0-9"


def build_glossary(notes):
    entries = sorted(
        (n for n in notes if any(n["stem"].startswith(p) for p in GLOSSARY_PREFIXES)),
        key=lambda n: _gkey(n["title"]),
    )
    lines = ["---", "title: Glossary", "tags: [moc, index, glossary]", "---", "",
             "# Glossary", "",
             "> A–Z term index. Auto-generated by `rebuild_index.py` — do not edit.", ""]
    buckets = defaultdict(list)
    for n in entries:
        buckets[_gletter(n["title"])].append(n)
    for letter in sorted(buckets, key=lambda x: (0, "") if x == "0-9" else (1, x)):
        lines += [f"## {letter}", ""]
        for n in buckets[letter]:
            defn = n["tldr"] or "_No TL;DR yet._"
            lines += [f"**{n['title']}** — {defn} See [[{n['stem']}]].", ""]
    lines += ["---", "", f"_Total terms: {len(entries)}_", ""]
    return "\n".join(lines) + "\n"


def build_master(notes, link_counts):
    top = sorted(link_counts.items(), key=lambda x: -x[1])[:10]
    lines = ["---", "title: Master Index", "tags: [moc, index]", "---", "",
             "# Master Index", "", "## By Domain", "",
             "- [[moc--architecture]]", "- [[moc--development]]", "- [[moc--debugging]]",
             "- [[moc--tools]]", "- [[moc--concepts]]", "- [[moc--synthesis]]",
             "- [[glossary]]", "", "## Top Linked Concepts", ""]
    lines += [f"- [[{s}]] ({c} ref{'s' if c != 1 else ''})" for s, c in top] or ["_No links yet._"]
    lines += ["", f"_Total notes: {len(notes)}_", ""]
    return "\n".join(lines) + "\n"


def main():
    notes = scan_notes(VAULT)
    link_counts = count_wikilinks(notes)
    broken = find_broken(notes, VAULT)

    for filename, title, prefixes in MOC_SPECS:
        (VAULT / filename).write_text(build_moc(title, prefixes, notes))
    (VAULT / "moc--master-index.md").write_text(build_master(notes, link_counts))
    (VAULT / "glossary.md").write_text(build_glossary(notes))

    print(f"\n=== rebuild_index summary ({dt.today().isoformat()}) ===")
    print(f"Notes:          {len(notes)}")
    print(f"MOC files:      {len(MOC_SPECS) + 1}")
    print(f"Glossary terms: {sum(1 for n in notes if any(n['stem'].startswith(p) for p in GLOSSARY_PREFIXES))}")
    print(f"Broken links:   {len(broken)}")
    for b in broken:
        print(f"  WARNING: {b}")
    print()


if __name__ == "__main__":
    main()
```

## Пусть Claude развернёт всё сам

Не хочешь копипастить скрипты руками? В свежей сессии Claude Code / Cursor / opencode зайди в пустую директорию и отдай этот промпт вместе со всем документом:

> Прочитай прикреплённый гайд целиком. Потом создай свежую LLM-вики в `./` строго по нему:
>
> 1. Создай дерево директорий (`memory/daily/`, `.manifests/`).
> 2. Напиши `CLAUDE.md`, скопировав блок «Стартовый `CLAUDE.md`» дословно.
> 3. Напиши `rebuild_index.py`, скопировав блок «Стартовый `rebuild_index.py`» дословно.
> 4. Создай пустые заглушки для всех memory-файлов: `memory/user.md`, `memory/preferences.md`, `memory/decisions.md`, `memory/people.md`, `memory/current.md`, `memory/future.md`, `memory/daily/<сегодня>.md`. В каждом по одному заголовку H1, совпадающему с именем файла.
> 5. Создай `log.md` с заголовком и одной записью `## [<сегодня>] meta | vault bootstrapped`.
> 6. Сделай `git init` и первый коммит.
> 7. Запусти `python3 rebuild_index.py`, чтобы сгенерировать первичные MOC и глоссарий.
> 8. Потом интерактивно спроси меня, чтобы я заполнил `memory/user.md` (кто я, роль, экспертиза) и `memory/preferences.md` (как со мной работать). Только эти два нужно писать мне самому.

В этом документе есть всё, что Claude понадобится, чтобы сделать это без уточняющих вопросов.

## Ежедневный воркфлоу

### В обычной сессии

Claude читает `memory/` + `log.md` на старте (потому что так сказано в `CLAUDE.md`). У него есть контекст: кто ты и что делаешь. По ходу сессии решения и сдвиги контекста он дописывает в `memory/daily/YYYY-MM-DD.md`.

### Когда сессия породила долговечное знание

Превращай в заметку. Попроси Claude:

> «Сохрани это как concept-заметку в хранилище — `concept--<slug>.md`. С TL;DR, frontmatter и wikilink на `[[related-note]]`, если уместно. Добавь запись в log.»

Он пишет заметку; ты проверяешь; запускаешь `python3 rebuild_index.py`; коммитишь.

### Когда заканчивается контекст посреди темы

Попроси Claude сделать синтез. Если ответ содержательный (сравнение, связь между заметками, обоснование решения) — сохрани как `synthesis--<slug>.md`. Тот же пайплайн.

### Периодически

Прогоняй **lint-проход** — проси Claude проверить хранилище на сироты (заметки без входящих wikilinks), залежалые драфты (тег `draft`, давно создана, ≥3 входящих ссылок), противоречия, отсутствующие concept-страницы, битые ссылки. Чини или игнорируй по вкусу.

## Ингест внешних источников

Полезно для Perplexity-экспортов, расшаренных ChatGPT-чатов, исследовательских статей, старых заметок в других форматах.

Простой вариант: кладёшь raw-файл куда-нибудь (например, `~/raw-sources/perplexity/foo.md`), просишь Claude прочитать, выделить заметкоёмкие куски и написать одну или несколько vault-заметок. Используй шаблон. В frontmatter добавь `source: perplexity` и `session_file:` с оригинальным именем файла — это provenance.

Продвинутый вариант (необязательно): отслеживай ингестированные файлы по SHA-256-хэшам в `.manifests/`, чтобы повторные прогоны пропускали неизменившееся и отмечали отредактированное. Обернуть в shell-скрипт или Python-CLI.

## Необязательные дополнения

### Семантический кросс-линкер

Короткий Python-скрипт, который ходит в Anthropic API, скармливает ему пачки заметок и спрашивает: «какие заметки соседствуют с какими?» — потом дозаполняет `related:` в frontmatter. Нужен `ANTHROPIC_API_KEY`. Запускай после больших ингестов, не каждый раз — это стоит денег.

### Ingest-скилл

Если используешь Claude Code: оберни процесс ингеста в `~/.claude/skills/ingest-to-vault/SKILL.md`, чтобы `/ingest-to-vault` стал командой одной кнопкой. Экономит повторение одних и тех же инструкций.

### Граф

Поставь Obsidian и открой хранилище. Wikilinks превращаются в визуальный граф. Полезно находить заметки-хабы и изолированные кластеры.

### Два хранилища

Одно техническое, одно личное. Та же форма, разные директории. Личное не попадает в рабочие / GitHub-контексты. В `CLAUDE.md` прописывается правило: если в технической сессии всплывает личный контекст (здоровье, поездки, отношения) — его запись уходит в дневной лог личного хранилища.

## Подсказки и подводные камни

- **Заметки атомарны.** Одна заметка = одна идея. Заметка на три страницы — это четыре заметки, которые надо разделить.
- **Осмысленные заголовки.** Заголовок попадёт в глоссарий и мастер-индекс. «Баг на iOS» бесполезно; «UIViewController deinit race with CADisplayLink» полезно.
- **TL;DR обязателен.** Без него запись в глоссарии пустая. Одно предложение, по делу.
- **Не перекатегоризируй.** Четыре-пять префиксов покрывают 90% случаев. Не изобретай `concept-advanced--` или `arch-pattern-experimental--`.
- **Коммить часто.** Хранилище — это git-репозиторий, коммиты бесплатны и делают историю грепаемой.
- **Хранилище — прежде всего для тебя.** Не пиши заметки, представляя публичную аудиторию — заглохнешь. Приватно по умолчанию, делись когда полезно.
- **Obsidian не обязателен.** Хранилище — plain markdown. Obsidian добавляет только граф и backlinks-UI. VS Code + grep работают отлично.

## Когда это начинает окупаться

Где-то на 50–100-й заметке щёлкает. LLM начинает цитировать тебе же твои прошлые заметки. Понимаешь, что эту проблему ты уже решал полгода назад. Стоимость поддержки опускается ниже стоимости выведения всего с нуля.

До 50-й заметки это ощущается как overhead. Дожми.

## Образец

Рабочее хранилище в этой раскладке лежит в `~/knowledge` — плоский markdown, frontmatter, MOC и глоссарий перегенерируются по мере надобности. Структура ровно такая, как описано выше. Скрипты в этом репозитории можно тащить как есть.
