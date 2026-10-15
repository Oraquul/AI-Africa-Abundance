# AI Africa Abundance

Public record of the white paper *The Oracle and the Partner* (version 3.1, July 2026), by Benedict Itegbe, and a tracker for the oracles the paper proposes.

The site is built for GitHub Pages at <https://oraquul.github.io/AI-Africa-Abundance/>.

This is an independent personal initiative. The views are Benedict Itegbe’s own. They are not official positions of the Nigerian Export Promotion Council or any other institution.

Text and data are under [CC BY 4.0](LICENSE-CC-BY-4.0). Code is under the [MIT License](LICENSE).

## Run the site locally

Python 3.12 is enough. The PDF also needs Pango.

```bash
sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b shared-mime-info fonts-liberation fonts-dejavu-core
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/build.py
```

`scripts/build.py` validates `data/oracles/*.yml` and `data/progress/*.md`, then writes HTML, `feed.xml`, `oracles/oracles.json`, and the paper PDF into `dist/`.

Pages use the base path `/AI-Africa-Abundance`, because that is where GitHub Pages will serve this repository. Preview it on the same path:

```bash
mkdir -p /tmp/aaa-preview
rm -rf /tmp/aaa-preview/AI-Africa-Abundance
cp -a dist /tmp/aaa-preview/AI-Africa-Abundance
python3 -m http.server 8000 --directory /tmp/aaa-preview
```

Open <http://127.0.0.1:8000/AI-Africa-Abundance/>.

## Add an oracle

Add one file, `data/oracles/<id>.yml`. The filename must match `id`. Required fields:

| Field | Meaning |
|---|---|
| `id` | Stable lowercase identifier |
| `name` | Name of the task family or infrastructure item |
| `domain` | Subject domain, in the paper’s wording where it has one |
| `layer` | `benchmark`, `data`, `lab`, `field`, or `simulator` |
| `feedback_loop_speed` | How fast the paper says the loop can close. This is the feedback-loop speed. |
| `status` | `proposed`, `specified`, `data-sourcing`, `prototype`, `published`, `leaderboard-live`, or `retired` |
| `leads` | Names, only after each person opts in. Otherwise `[]` |
| `working_group` | A name, or `null` |
| `milestones` | List of `{date, item, done}`. Empty until a real date exists |
| `evidence` | List of `{label, url, date}`. Empty until there is a link |
| `dataset_licence` | `Unassigned`, or the licence of an attached dataset |
| `paper_section` | Chapter or annex |

The launch set is 46 Annex A families plus 6 infrastructure items from sections 22 and 31, all `proposed`, with no leads and no milestone dates. Further oracles are added the same way. The schema is `data/schema/oracle.schema.json`, and the build rejects a file that does not match it. A full example is in [CONTRIBUTING.md](CONTRIBUTING.md).

## Add a progress entry

Add `data/progress/YYYY-MM-DD-short-title.md` with this front matter:

```yaml
title: Project launched
date: 2026-10-14
summary: One or two sentences.
link: https://oraquul.github.io/AI-Africa-Abundance/
x: "Text for X. 280 characters or fewer."
linkedin: |
  Text for LinkedIn.
```

The `x` field is validated at 280 characters or fewer. The build publishes a [progress page](https://oraquul.github.io/AI-Africa-Abundance/progress/), a [share page](https://oraquul.github.io/AI-Africa-Abundance/share/) with copy buttons, and an RSS feed at `/feed.xml`. The site does not post to X or LinkedIn.

## Enable GitHub Pages

The workflow is `.github/workflows/pages.yml`. It runs the build on every push to `main` and deploys with `actions/deploy-pages`.

In the repository: **Settings → Pages → Build and deployment → Source: GitHub Actions**.

If Pages has never been switched to GitHub Actions, the workflow cannot deploy until that source is selected. The API equivalent is a Pages configuration with `build_type` set to `workflow`.

## Layout

| Path | Contents |
|---|---|
| `content/paper/white-paper-v3.1.md` | Verified master of the white paper |
| `content/paper/versions.md` | Version history and errata |
| `content/blog/` | Essays. `_template.md` is not published |
| `content/research/` | Research notes. `_template.md` is not published |
| `data/oracles/` | One YAML file per oracle |
| `data/progress/` | Dated progress entries |
| `data/schema/` | JSON Schema used by the build |
| `scripts/build.py` | Generator |
| `templates/` | Page templates |
| `.github/` | Pages workflow, issue forms, pull request template |

How to contribute, including the opt-in credit rule, is [CONTRIBUTING.md](CONTRIBUTING.md). The code of conduct is [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
