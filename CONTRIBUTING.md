# Contributing to AI Africa Abundance

This repository publishes the white paper *The Oracle and the Partner* (version 3.1) and tracks the oracles it proposes. Issues and pull requests are welcome. If you do not have a GitHub account, use the form at <https://oraquul.github.io/AI-Africa-Abundance/contribute/#contact>.

Please read the [code of conduct](CODE_OF_CONDUCT.md) first.

## Credit is opt-in

You are named only if you ask to be. On an issue form or a pull request, leave the credit box unchecked and the editor will not add your name to a byline, an oracle lead list, or a working group. Putting your name in a commit does not, by itself, count as opting in.

## Ways to contribute

| You want to | Do this |
|---|---|
| Propose an oracle | [Issue form](https://github.com/Oraquul/AI-Africa-Abundance/issues/new?template=propose-oracle.yml), or a pull request that adds `data/oracles/<id>.yml` |
| Update a status, lead, milestone, or evidence link | [Issue form](https://github.com/Oraquul/AI-Africa-Abundance/issues/new?template=update-oracle.yml), or edit the YAML file |
| Correct the paper | Use “Suggest a correction” on the section, or the [issue form](https://github.com/Oraquul/AI-Africa-Abundance/issues/new?template=correct-paper.yml) |
| Submit a concept note, preprint, or dataset record | [Issue form](https://github.com/Oraquul/AI-Africa-Abundance/issues/new?template=submit-research.yml), or add `content/research/<slug>.md` |
| Pitch an essay | [Issue form](https://github.com/Oraquul/AI-Africa-Abundance/issues/new?template=pitch-blog.yml), or add `content/blog/YYYY-MM-DD-title.md` |
| Add a progress note | Add `data/progress/YYYY-MM-DD-title.md` |

Open issues labelled [good first issue](https://github.com/Oraquul/AI-Africa-Abundance/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) are a reasonable place to start, when any exist.

## Add an oracle

Create `data/oracles/<id>.yml`. The filename must match `id`. The build validates every file against `data/schema/oracle.schema.json`.

```yaml
id: example-task-family
name: A short name, taken from the task rather than invented as a slogan
domain: Agriculture
layer: benchmark
feedback_loop_speed: Days (section 20.1)
status: proposed
leads: []
working_group: null
milestones: []
evidence: []
dataset_licence: Unassigned
paper_section: Annex A
```

Rules:

- `id` is lowercase letters, digits, and hyphens.
- `layer` is `benchmark`, `data`, `lab`, `field`, or `simulator`. A simulator is a digital twin, the form named in section 17. It is not agent scaffolding.
- `status` is one of `proposed`, `specified`, `data-sourcing`, `prototype`, `published`, `leaderboard-live`, `retired`.
- `feedback_loop_speed` states the loop time the paper gives. If the paper gives none, say that. Do not invent a latency.
- `leads` stays empty until each person has opted in to being named. `working_group` stays `null` until a group exists.
- `milestones` is a list of `{date, item, done}`. `date` is `YYYY-MM-DD`. Add a date only when you can point to it. The example below is a format sample, not a project date:

```yaml
milestones:
  - date: 2026-11-01
    item: Protocol posted at the evidence URL
    done: false
evidence:
  - label: Task specification
    url: https://example.org/spec
    date: 2026-11-01
```

- `dataset_licence` is `Unassigned` until a dataset is attached. The project spells the field `licence`. When a dataset exists, name its licence (for example `CC BY 4.0`).
- `paper_section` points at the chapter or annex. An optional `note` may quote a flag already in the paper. It may not add a new claim.
- Do not present a proposed oracle as specified, published, or live.

## Add a progress entry

Create `data/progress/YYYY-MM-DD-short-title.md`. The date in the filename must match the `date` field. The build checks the front matter against `data/schema/progress.schema.json`.

```yaml
---
title: Short title
date: 2026-10-14
summary: One or two sentences.
link: https://oraquul.github.io/AI-Africa-Abundance/
x: "Text for X, at most 280 characters, including spaces and the URL."
linkedin: |
  Text for LinkedIn.
  A second paragraph is fine.
---

Optional longer note in Markdown.
```

The `x` field is counted in characters. The build fails if it is longer than 280. The share page lists the `x` and `linkedin` text with copy buttons. Nothing is posted to X or LinkedIn by the site.

## Add an essay or a research note

Copy `content/blog/_template.md` or `content/research/_template.md`. Files whose names start with `_` are not published.

- A blog file is `content/blog/YYYY-MM-DD-short-title.md`, with `title`, `date`, `summary`, `author`, and `byline_opt_in`.
- A research file is `content/research/short-title.md`, with `status` of `planned`, `note`, `preprint`, or `dataset`.
- Set `byline_opt_in` to `true` only when the named person has agreed. Otherwise the name is not shown.
- Do not add a quantitative claim the paper does not already source, unless the note links the primary source.
- Do not include confidential material.

## Paper corrections

The reading text is `content/paper/white-paper-v3.1.md`. Do not silently rewrite a published version. Propose the change in an issue. If a new version is issued, it is added beside the old one. The version table is `content/paper/versions.md`.

## Run the checks

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/build.py
```

The PDF step needs Pango and related libraries. On Debian or Ubuntu:

```bash
sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b shared-mime-info fonts-liberation fonts-dejavu-core
```

The script validates every oracle and every progress entry, writes `dist/`, and stops if the schema fails, if an `x` field is too long, or if the PDF does not render.

## Licences

Text and data you contribute are published under [CC BY 4.0](LICENSE-CC-BY-4.0) unless you say otherwise before they are merged and the editor agrees. Code is under the [MIT License](LICENSE).
