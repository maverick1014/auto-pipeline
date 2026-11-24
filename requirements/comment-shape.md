# comment-shape — requirements (level 3 rules gate)

Status: rules yes 2026-11-24 (owner: all 6 families of table B, D1-D7 defaults, est 100m). Base e90db3b.
Source: owner 4A 2026-11-20 (idea 145): a diff that only changes comments lands at L2 today; make "comment-only change" a fifth L0 shape next to text values, one colour value, style switch, move in the same container.
Files: bin/agent_level.py (the check), PRINCIPLES.md R8 level 0 line, tests/test_comment_shape.py (new).

## 0. Words

| Word | Meaning |
|---|---|
| plain comment | a comment that is not a directive (table C) |
| code view | the file text with every plain comment removed (an inline `/* */` or `<!-- -->` becomes one space), trailing white space dropped from each line, then the lines that are blank dropped. A line that starts inside a multi-line string, heredoc or block scalar is kept as it is (blank too). Directive comments stay in the code view |
| old / new | the file at the merge base (`git show <mb>:<path>`) / in the working tree |
| today's level | what agent-level.sh prints for that file now (the new check is skipped) |

## A. Rules table

How: a modified file (not new, not deleted, not binary, not a symlink) whose extension is in table B, after the path rules (L4/L3), style, asset and text file rules. Lex old and new. Same code view → L0; `comment only` when the plain comments differ, `whitespace only` when only blank lines or trailing white space differ. Not the same, or the lexer is unsure → today's level.

| # | Case | Example: old → new | Result |
|---|---|---|---|
| 1 | a whole-line comment changes | sh `# retry twice` → `# retry three times` | `L0 comment only` |
| 2 | a comment line added or removed, a comment block removed | py add `# keep the order: R5` above `run()` | `L0 comment only` |
| 3 | a trailing comment changes, the code before it stays | py `n = 3  # tries` → `n = 3  # max tries` | `L0 comment only` |
| 4 | blank lines only (no comment change) | py one blank line added between two functions | `L0 whitespace only` |
| 5 | a block comment over several lines | js `/* a⏎ b */` → `/* a⏎ c */` | `L0 comment only` |
| 6 | a JSX comment | tsx `{/* old */}` → `{/* new */}` | `L0 comment only` |
| 7 | an HTML or XML comment | html `<!-- old -->` → `<!-- new -->` | `L0 comment only` |
| 8 | a YAML comment, a conf comment line | yml `# ports` → `# open ports`; agent.conf-like `.conf` `# x` → `# y` | `L0 comment only` |
| 9 | comment and code change on the same line | py `n = 3  # tries` → `n = 4  # max tries` | today's level (L2 code change) |
| 10 | code commented out, or uncommented | py `run()` → `# run()` | today's level (L2 code change) |
| 11 | a comment change plus another shape elsewhere in the same file | py `# a` → `# b` and `flash("Hi")` → `flash("Hello")` | today's level (L2 code change) — no mixing in v1 (D2) |
| 12 | a comment-looking line inside a string | py line `# step 1` inside `"""…"""`; sh `# x` inside a heredoc body; yml `# x` under `run: |`; js `// x` inside a template literal; html `// x` inside `<script>` | today's level (L2 code change) |
| 13 | a comment marker inside a one-line string | py `s = "# a"` → `s = "# b"` | today's level (L0 text change, as now) |
| 14 | a docstring | py `"""Old."""` → `"""New."""` | today's level (a string, not a comment: L0 text change one-line, L2 multi-line) |
| 15 | a directive comment added, removed, edited or moved (table C) | py add `  # noqa: E501`; ts add `// @ts-ignore`; sh `#!/bin/sh` → `#!/bin/bash` | today's level (L2 code change) |
| 16 | a license or copyright comment | `# Copyright 2025 Acme` → `# Copyright 2026 Acme` | today's level (L2 code change) (D4) |
| 17 | a comment or blank line right after a code line that ends in `\` (old or new) | sh `docker run \` / add `  # -v a:b \` / `  img` | today's level: it ends the continued line |
| 18 | a comment that ends in `\` (old or new) | c `// see C:\` above `run();` | today's level: in C the next line becomes comment |
| 19 | the lexer is unsure: a quote not closed at the end of its line (where that string cannot span lines), or a string, heredoc or block comment still open at the end of the file | jsx `<p>Don't stop</p>` (the `'` looks like a string) | today's level |
| 20 | a Go file with `import "C"` | the comment above `import "C"` is C code (cgo) | today's level |
| 21 | built-in L4 path, level4_paths, level3_paths | `requirements.txt` `# pinned` → `# pinned for py3.9`; `.sql` `-- x`; a level3_paths file | path level stays (L4 / L3) (D1) |
| 22 | new file, deleted file, binary file | a new `.sh` holding only comments | today's level (L2 new / deleted / binary file) |
| 23 | a style file, a text file | `.css` `/* a */` → `/* b */`; `.md` | as now: L1 style file; L0 text file |
| 24 | an extension not in table B | `.rb`, `.rs`, `.php`, `.vue`, `.svelte`, `.toml`, `.ini`, `.cfg`, `Makefile`, `Dockerfile`, `bin/foo` with no extension | today's level |
| 25 | indentation or spacing of code changes too | py `x=1  # a` → `x = 1  # b` | today's level (L2 code change) |
| 26 | line endings or trailing white space only | `run()  ` → `run()` | `L0 whitespace only` (as now) |

REQUIRED LEVEL, RAISE, `--declared`, the file order: unchanged. The new line reads like the others: `bin/agent-start.sh: L0 comment only`.

## B. Languages (v1)

| Family | Extensions | Comment | Strings the lexer knows (their content is code) |
|---|---|---|---|
| py | `.py` | `#` (Python's own `tokenize`) | every Python string: quotes, triple quotes, docstrings, f-strings, prefixes |
| sh | `.sh` `.bash` `.zsh` | `#` at line start or after a space or tab | `'…'`, `"…"` and `` `…` `` (`\` escapes, not in `'…'`), `$'…'`, all may span lines; heredoc body after `<<WORD`, `<<-WORD`, `<<'WORD'`, `<<"WORD"`, `<<\WORD` until the line that is WORD (`<<-`: leading tabs dropped); `<<<` is no heredoc |
| yaml | `.yaml` `.yml` | `#` at line start or after a space or tab | `'…'` (`''` escape) and `"…"` (`\` escapes) only when they open a value (line start, after `: `, `- `, `? `, `[`, `{`, `,`), may span lines; block scalar: a line ending in `: \|`, `: >`, `- \|`, … (with `-` `+` digit indicators) → the next lines that are blank or indented deeper than that line are its body |
| conf | `.conf` | whole-line `#` only (after indentation) | none: a `#` after code on a line is code |
| slash | `.js` `.mjs` `.cjs` `.jsx` `.ts` `.mts` `.cts` `.tsx` `.dart` `.java` `.kt` `.kts` `.swift` `.go` `.c` `.h` `.cc` `.cpp` `.cxx` `.hpp` `.hh` | `//` at line start or after a space or tab; `/* … */` anywhere, not nested | `"…"` and `'…'` one line, `\` escapes; js/ts family `` `…` `` template, multi-line, `${…}` inside is code again (may hold strings and templates); go `` `…` `` raw, multi-line, no escapes; `"""…"""` in java, kt, kts, swift, dart (kt and kts: no escapes); `'''…'''` in dart |
| markup | `.html` `.htm` `.xml` | `<!-- … -->` outside tags | quoted attribute values inside a tag; the bodies of `<script>` and `<style>` and `<![CDATA[…]]>` are code |
| not in v1 | `.md` and other text files (already L0), `.sql` (built-in L4), `.css` and other style files (L1), everything else | - | today's level |

## C. Directives (the comment stays code)

Body = the text inside the marker: after `#` or `//`, between `/*` and `*/`, between `<!--` and `-->`. Head = the body with its leading `#`, `/`, `*`, `-` and white space removed. A comment is a directive when one of these holds (any case):

| # | Rule | Examples |
|---|---|---|
| C1 | tight: the body's first character is not white space, not the family's own marker (`#` in py sh yaml conf, `/` and `*` in slash, `-` in markup) and not `=` `-` `~` | `#!/bin/bash`, `#SBATCH --time=1`, `#compdef git`, `#cloud-config`, `#print(x)`, `//go:build linux`, `//nolint`, `/*#__PURE__*/`, `//# sourceMappingURL=a.map`, `<!--#include file="x"-->`, `<!--[if IE]>`, `<!--more-->`. Not tight: `# note`, `## Part 2`, `#----`, `/// doc`, `/** doc */`, `#` alone |
| C2 | the head starts with a tool word: `type:` `noqa` `nolint` `pylint:` `pyright:` `mypy:` `pragma` `isort:` `fmt:` `ruff:` `flake8:` `nosec` `cython:` `coding:` `coding=` `vim:` `vi:` `ex:` `shellcheck` `yamllint` `yaml-language-server` `renovate:` `eslint` `global ` `globals ` `exported ` `prettier-ignore` `istanbul` `c8 ` `v8 ` `biome-ignore` `deno-` `tslint:` `jshint` `jscs:` `swiftlint:` `ignore:` `ignore_for_file:` `go:` `+build` `<reference` `<amd-` `clang-format` `noinspection` `checkstyle:` `$` `webpack` `ko ` `/ko` `build:` `endbuild` `inject:` `endinject` `htmlmin:` `[if` `[endif` `<![endif` | `# type: ignore`, `# pylint: disable=x`, `# shellcheck disable=SC2086`, `// eslint-disable-next-line`, `/* global x */`, `// ignore: unused` (dart), `// +build linux`, `/// <reference types="node" />`, `// NOLINT`, `// CHECKSTYLE:OFF`, `// $NON-NLS-1$`, `<!-- ko if: x -->`, `<!-- build:js a.js -->` |
| C3 | the body holds anywhere: `noqa` `nolint` `pragma` `type: ignore` `eslint-` `@ts-` `-*-` `coding:` `coding=` `prettier-ignore` `fallthrough` `fall through` `falls through` `fallthru` | `n = f()  # long, noqa: E501`, `# -*- coding: utf-8 -*-`, `/* falls through */` |
| C4 | the body holds `@` plus a letter at its start or after white space or `*` | `// @ts-ignore`, `// @flow`, `/** @jsx h */`, `/** @type {Foo} */` and `* @param x` in a JSDoc block (types count as code), `// @dart=2.9`, `# @package _global_` |
| C5 | license: the body holds `licen` (license, licence, licensed), `copyright`, `©` or `spdx` | `# SPDX-License-Identifier: MIT`, `// Copyright 2026 Acme` |

## D. Decisions taken (defaults; owner may change)

| # | Question | Default taken | Why |
|---|---|---|---|
| D1 | Do level 3/4 paths drop to L0 for a comment-only change? | No: the path level stays; only the L2 code floor drops | the main manager's default; a level only goes up |
| D2 | A comment change plus another L0 shape in the same file? | Today's level (L2) in v1 | the brief's definition (every added and removed line is blank or a comment); simplest; an idea for later |
| D3 | Blank lines only? | `L0 whitespace only` (today L2) | blank lines are inside the brief's definition; the lexer keeps blank lines inside strings |
| D4 | License headers? | Directive: today's level | a legal text, not a wording change |
| D5 | Reason words | `comment only`, `whitespace only` | the brief's example; `whitespace only` already exists |
| D6 | sql, md, css, vue, svelte, toml, ini, rb …? | Not in v1 (sql L4 path, md already L0, css L1 style file, the rest today's level) | sql and md need nothing; mixed-language files (vue, svelte) need two lexers |
| D7 | jsx/tsx text with an apostrophe (`Don't`) | today's level (rule 19) | the lexer cannot tell JSX text from code; safe side |

## E. Real data (read-only, this repo at e90db3b)

| Count | Value | So |
|---|---|---|
| `.sh` files with a `#` line inside a heredoc body | 3 of 24 (22 lines: agent-city.sh, agent-cloud-pack.sh, agent-show-todo.sh) | a line-by-line check would call them comments: the lexer tracks heredocs |
| `.py` files with a `#` line inside a multi-line string | 9 of 151 | Python's `tokenize` gives the string spans |
| `.js`/`.mjs` files with a template literal | 9 of 10 | the slash lexer tracks templates and `${…}` |

## F. Time

Re-estimate on the record: est 28m assumed a line-by-line check; real files need a small lexer per family (E). New est 100m (rules 15, tests 30, two workers 35, review + suite + E2E 20).
