# Research corpus

A labelled corpus for measuring whether AI-authored technical prose is
distinguishable from human technical prose, and for calibrating detectors
against something other than intuition.

**Assembled 2026-08-16.**

## What is here, and what is not

| | Committed | Why |
| --- | --- | --- |
| Fetch and build scripts | yes | reproducibility is the point |
| Derived statistics and features | yes | facts about the text, not the text |
| Locally-authored messages and file lists | yes | this repository's owner authored them |
| `git/git` message bodies | **no** | fetched on demand, see below |

The human corpus is **not redistributed**. `git/git` is GPLv2 and its commit
messages are its contributors' expression. `fetch_human.py` pulls them from the
GitHub API into `derived/` at run time, and `derived/` is gitignored. What is
committed is the *measurement*, which is factual.

Run `python research/corpus/fetch_human.py` to materialise it. Roughly 2,400
messages and 166k words, ~40 seconds against the API.

## Classes

| Class | Source | Label evidence | Volume |
| --- | --- | --- | --- |
| `human` | `git/git`, 2018-01 to 2020-01 | predates LLM coding assistants | 2,400 msgs, 166k words |
| `claude_msg` | local repos | `Co-Authored-By: Claude` trailer | 261 msgs, 28k words |
| `claude_file` | local repos | every commit touching the file is trailered | 195 prose (221k w), 105 code (103k w) |
| `codex` | `DataWorkStation_Powershell` | `.specify/` + `.agents/`, no trailer | 19 msgs, 100 words |
| `human_local` | `WindowsHardeningScript` | third-party authors | 17 msgs, 74 words |

The last two are **too small to support any estimate** and are retained only to
document that they were checked.

## Why `git/git` is the right human control

Commit-message length tracks **process, not authorship**:

| Corpus | Median words | Driver |
| --- | --- | --- |
| `git/git` 2019 | 50 | no ticket system; the message *is* the documentation, reviewed on a mailing list |
| CPython, curl 2019 | 16 | messages reference `bpo-` / issue numbers |
| This owner, pre-AI | 3 | ticket-driven; context lived in the ticket |
| Claude, here | 91 | no ticket, and asked to explain reasoning |

A 2019 git contributor and Claude write long messages for the same structural
reason: the message is the only record. "Verbose implies AI" is false, and any
study that does not control for this is measuring workflow.

`git/git` is process-matched to the Claude corpus on exactly that axis, which
CPython and curl are not. That is why it was chosen.

## The confound this corpus does not solve

87k of the 221k `claude_file` prose words are **this repository's own kiro
specs**, and 59k more come from one other repo. A classifier fitted to that
learns a spec template and one developer's toolchain, not a model.

If a discrimination study is run, hold out **whole repositories**, never
individual files, and report per-repository performance. A single pooled
accuracy figure would be meaningless.

## What a result here would and would not mean

It would measure whether *this* Claude usage, in *this* register, is separable
from 2019 git contributors. That is a calibration exercise.

It would **not** be watermark detection. Claude's text watermark is
statistical and keyed; no publicly available method detects it. Style
discrimination is a different thing wearing similar clothes, and conflating
them is the error this whole project exists to avoid.

## First result, 2026-08-16

Claude commit messages (n=262) against `git/git` 2018-2019 (n=2400), then
length-matched into shared word-count buckets (n=262 each, median 92 vs 86
words).

| Feature | AUC raw | AUC matched | Reading |
| --- | --- | --- | --- |
| `word_count` | 0.731 | **0.521** | pure length confound |
| `mean_sentence_len` | 0.649 | 0.555 | mostly length |
| `comma_rate` | 0.697 | 0.587 | mostly length |
| `burstiness_cv` | 0.715 | 0.621 | partly length |
| `first_person_rate` | 0.370 | **0.244** | survives, strongest |
| `type_token_ratio` | 0.475 | **0.705** | survives |
| `bullet_line_rate` | 0.590 | 0.632 | survives |
| `colon_rate` | 0.410 | 0.619 | survives |
| `hedge_rate` | 0.458 | 0.398 | survives, weak |

AUC 0.5 is chance; below 0.5 means the feature runs the other way.

**Length explains most of the apparent difference but not all.** Word count
looked strong at 0.731 and collapsed to 0.521 once matched — exactly the
ticket-system artifact. What survives is a coherent picture: Claude writes
*less personally* (`first_person_rate` 0.244, the strongest single signal),
with higher lexical diversity, more bullets and more colons.

That reads as register, not model. git contributors write "I think this is
cleaner"; the Claude corpus writes impersonally and structurally, which is at
least partly an instruction artifact rather than a property of the weights.

**The ceiling this establishes.** The best single feature reaches an effective
AUC near 0.76. Given one Claude document and one human document, you would rank
them correctly about three times in four. That is a usable prior for triage and
nowhere near sufficient to attribute a single document, let alone accuse anyone.
No combination of these features turns a 0.76 into evidence.

## Reproducing

```bash
python research/corpus/fetch_human.py       # pulls git/git, writes derived/
python research/corpus/build_labelled.py    # scans local repos, writes derived/
python research/corpus/features.py          # computes and prints statistics
```

`build_labelled.py` takes a `--source-root` and defaults to the parent of this
repository. It reads only git metadata and file contents; it writes nothing
outside `derived/`.
