# Cataloging practice study

The scripts that produced
[Cataloging practice: a study](../../docs/practice-study/index.md).

## What you need before running anything

Every script expects to be run **from the repository root**, and every
path inside them is written relative to it:

```bash
uv run --with httpx python studies/cataloging-practice/draw_corpus.py
```

They read and write `tmp/vagf/`, named directly in each script as
`HERE`. That constant is the only thing changed from the scripts as
they ran: six of them resolved it relative to their own file, which
broke when they moved out of the directory they were written in. That directory is not in the repository. The corpus and the
derived feature vector are distributed as a separate archive; unpack it
to `tmp/vagf/` before running anything downstream of the draw.

The analysis scripts need `numpy`, `scipy` and `scikit-learn`, and the
figures need `matplotlib`. None is a project dependency, so they are
pulled in per run:

```bash
uv run --with numpy --with scipy --with scikit-learn \
    python studies/cataloging-practice/final_stats.py
```

## Order

**1. What the servers support.** Run before anything else against a new
catalog. Each sends one small query per candidate index and reports
whether it answers.

| Script | Established |
|---|---|
| `probe_indexes.py` | Which indexes NLI, LC and DNB honour |
| `probe2.py` | Boolean `AND` and `startRecord` paging on those three |
| `probe_new.py` | K10plus and Library Hub reachability and record format |
| `probe_isbn.py` | The ISBN index name for each catalog |

**2. Drawing the corpus.**

| Script | Produces |
|---|---|
| `sru_fetch.py` | Not run directly. The paced, disk-cached fetcher the others import. Four seconds minimum between requests to any one host, responses cached under `tmp/vagf/cache/` so a re-run costs no requests |
| `draw_corpus.py` | `tmp/vagf/corpus.jsonl` — 5,252 records with their stratum labels. Holds the query list that defines the sample |

**3. Representing a record.**

| Script | Produces |
|---|---|
| `featurize.py` | `tmp/vagf/features.json` — the 725-feature binary vector and the held-out labels |

**4. Clustering and its confidence.**

| Script | Produces |
|---|---|
| `analyze.py` | The adjusted mutual information tables, corpus-wide and per catalog, with and without local fields |
| `confidence.py` | `tmp/vagf/confidence.json` — bootstrap intervals on AMI and cluster stability under subsampling. Slow: several minutes |

**5. Markers.**

| Script | Produces |
|---|---|
| `final_stats.py` | `tmp/vagf/final_stats.json` — every marker table in the study: by catalog, by material type, by era, restricted to language material |
| `leader19.py` | The leader/19 tables and the precision and recall of the two-field test |
| `l19_score.py` | Adjusted mutual information against leader/19, on fresh partitions of each subset |
| `verify_ami19.py` | The same against the corpus-wide partitions, which is the figure the study reports. Also counts how many dependent-part records fall in the largest cluster |

**6. Matched items.**

| Script | Produces |
|---|---|
| `overlap.py` | How many ISBNs and titles appear in more than one catalog |
| `cases.py` | `tmp/vagf/cases.txt` — the field-by-field dumps behind the case chapter. Fetches each case ISBN from all five catalogs |

**7. Output.**

| Script | Produces |
|---|---|
| `charts.py` | The nine SVG figures in `docs/practice-study/figures/`. Reads `final_stats.json`, `set_summary.json`, `confidence.json` and the corpus |
| `set_cases.py` | `tmp/vagf/set_cases.json` — the set survey: 22 multi-volume works asked of all five catalogs by title |
| `set_report.py` | `tmp/vagf/set_summary.json` and the published `set-survey.csv`, filtering each response to records whose `245` names the work |
| `tradition.py` | Whether the clusters track a cataloging tradition rather than an institution |
| `era_stability.py` | Whether the leader/19 divide changed over time, on both the publication and record-creation axes |
| `build_data.py` | The three published files in `docs/practice-study/data/` |

## Reading them

They are as they ran, so they carry the marks of that. Several were
written to answer one question and print an answer, not to be reused.
Arguments are positional where they exist at all — `analyze.py` takes
`--drop-local`, and that is the extent of it. Percentages are computed
with floor division in `leader19.py` and rounding everywhere else, which
is why one table in the study reads 81% where the CSV rounds to 82%.

## Re-running the draw does not reproduce the corpus

SRU returns results in a server-determined order, and the catalogs
revise their records continuously. Running `draw_corpus.py` again draws
a comparable sample along the same axes, not the same records. The
frozen corpus is what the published numbers were computed from; the
[data page](../../docs/practice-study/data.md) says what is published
and what is not.
