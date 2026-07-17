# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo>=0.23.3",
#     "numpy>=2.5.1",
#     "pandas>=3.0.3",
#     "scipy>=1.18.0",
#     "requests>=2.31.0",
#     "matplotlib>=3.10.0",
# ]
# ///
#uv run marimo run inteRx/app.py 
import marimo

app = marimo.App()


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import os
    import re
    from itertools import combinations
    from pathlib import Path
    from urllib.parse import quote
    import numpy as np
    import pandas as pd
    import requests
    return Path, combinations, mo, np, os, pd, quote, re, requests


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
# inteRx

Probabilistic drug interaction explorer.

Goal: estimate a harm probability for a prescribed drug combination using
literature-derived interaction scores.

This prototype is for research/education and not clinical decision making.
"""
    )
    return


@app.cell(hide_code=True)
def _(mo):
    drugs = mo.ui.text_area(
        label="Enter drugs (comma-separated)",
        value="Xanax, Itraconazole, Warfarin",
    )
    drugs
    return (drugs,)


@app.cell(hide_code=True)
def _(Path, combinations, drugs, mo, np, os, pd, quote, re, requests):
    """Collect normalized evidence from openFDA plus optional local exports."""
    evidence_path = Path(os.getenv("INTERACTION_EVIDENCE", "interaction_evidence.csv"))
    columns = [
        "drug_a", "drug_b", "harm", "source", "evidence_id",
        "positive", "negative", "weight", "url",
    ]
    if evidence_path.exists():
        evidence = pd.read_csv(evidence_path)
        missing = set(columns) - set(evidence.columns)
        if missing:
            raise ValueError(f"Evidence file is missing columns: {sorted(missing)}")
        evidence = evidence.copy()
        for col in ["positive", "negative", "weight"]:
            evidence[col] = pd.to_numeric(evidence[col], errors="raise")
        evidence["source"] = evidence["source"].str.lower().str.strip()
        evidence["drug_a"] = evidence["drug_a"].str.lower().str.strip()
        evidence["drug_b"] = evidence["drug_b"].str.lower().str.strip()
    else:
        evidence = pd.DataFrame(columns=columns)

    def check_openfda_interactions(drug_list):
        """Turn explicit openFDA label mentions into evidence rows.

        openFDA supplies label text, not pairwise clinical probabilities. A
        missing drug name is deliberately not encoded as negative evidence.
        """
        base_url = "https://api.fda.gov/drug/label.json"
        rows = []
        errors = []

        def label_url(query):
            return f"{base_url}?search={quote(query, safe='')}&limit=1"

        def interaction_excerpt(section, other):
            """Return the label sentence that explicitly names the other drug."""
            text = " ".join(section.split())
            sentences = re.split(r"(?<=[.!?])\s+", text)
            for sentence in sentences:
                if re.search(rf"\b{re.escape(other)}\b", sentence, re.IGNORECASE):
                    return sentence[:500].rstrip()
            return None

        seen = set()
        for drug in drug_list:
            try:
                # `fields` is not a response-projection parameter for this
                # endpoint. Use its documented `search` and `limit` options.
                labels = []
                for field in ("openfda.brand_name", "openfda.generic_name"):
                    response = requests.get(
                        base_url,
                        params={"search": f'{field}:"{drug}"', "limit": 5},
                        timeout=15,
                    )
                    if response.status_code == 404:
                        continue
                    response.raise_for_status()
                    labels.extend(response.json().get("results", []))

                if not labels:
                    continue
                for other in drug_list:
                    if other == drug:
                        continue
                    for label in labels:
                        evidence_ids = (
                            label.get("openfda", {}).get("spl_id", [])
                            or label.get("openfda", {}).get("application_number", [])
                        )
                        evidence_id = str(evidence_ids[0]) if evidence_ids else f"openfda:{drug}"
                        source_url = label_url(
                            f'openfda.spl_id:"{evidence_id}"'
                            if evidence_ids
                            else f'openfda.generic_name:"{drug}"'
                        )
                        for section in label.get("drug_interactions", []):
                            harm = interaction_excerpt(section, other)
                            if harm is None:
                                continue
                            row_key = (drug, other, evidence_id, harm)
                            if row_key in seen:
                                continue
                            seen.add(row_key)
                            rows.append({
                                "drug_a": drug,
                                "drug_b": other,
                                "harm": harm,
                                "source": "fda_label",
                                "evidence_id": evidence_id,
                                "positive": 1,
                                "negative": 0,
                                "weight": 1.0,
                                "url": source_url,
                            })
            except requests.RequestException as exc:
                status = exc.response.status_code if exc.response is not None else "connection failed"
                errors.append(f"{drug}: openFDA HTTP {status}")
            except ValueError:
                errors.append(f"{drug}: invalid JSON response from openFDA")
        return pd.DataFrame(rows, columns=columns), errors

    fda_evidence, fda_errors = check_openfda_interactions(
        sorted({drug.strip().lower() for drug in drugs.value.split(",") if drug.strip()})
    )
    evidence = pd.concat([evidence, fda_evidence], ignore_index=True)

    # Source weights are conservative defaults and should be calibrated against
    # a reviewed validation set, not treated as clinical truth.
    source_weights = {
        "drugbank": 1.0,
        "fda_label": 1.25,
        "pubmed": 0.9,
        "pharmacovigilance": 0.75,
    }
    evidence["source_weight"] = evidence["source"].map(source_weights).fillna(0.5)
    evidence["effective_weight"] = evidence["weight"] * evidence["source_weight"]
    evidence[["drug_a", "drug_b"]] = evidence[["drug_a", "drug_b"]].apply(
        lambda row: sorted(row), axis=1, result_type="expand"
    )

    entered = sorted({drug.strip().lower() for drug in drugs.value.split(",") if drug.strip()})
    # `.loc` preserves the evidence schema when no rows are available; direct
    # bracket indexing with an empty `apply` result can instead select columns.
    matched = evidence.loc[
        evidence["drug_a"].isin(entered) & evidence["drug_b"].isin(entered)
    ].copy()

    prior_alpha, prior_beta = 1.0, 9.0
    _rng = np.random.default_rng(42)
    findings = []
    for (drug_a, drug_b), group in matched.groupby(["drug_a", "drug_b"]):
        alpha = prior_alpha + (group["positive"] * group["effective_weight"]).sum()
        beta = prior_beta + (group["negative"] * group["effective_weight"]).sum()
        samples = _rng.beta(alpha, beta, 20_000)
        source_urls = sorted(set(group["url"].dropna().astype(str)))
        harms = list(dict.fromkeys(group["harm"].dropna().astype(str)))
        findings.append({
            "drug_a": drug_a,
            "drug_b": drug_b,
            "harm": "\n\n".join(harms),
            "posterior_probability": alpha / (alpha + beta),
            "credible_low": np.quantile(samples, 0.025),
            "credible_high": np.quantile(samples, 0.975),
            "evidence_count": len(group),
            "sources": ", ".join(sorted(group["source"].unique())),
            "evidence_ids": ", ".join(group["evidence_id"].astype(str)),
            "source_url": source_urls[0] if source_urls else "",
        })
    results = pd.DataFrame(
        findings,
        columns=[
            "drug_a", "drug_b", "harm", "posterior_probability",
            "credible_low", "credible_high", "evidence_count", "sources",
            "evidence_ids", "source_url",
        ],
    )

    candidate_pairs = pd.DataFrame(
        combinations(entered, 2), columns=["drug_a", "drug_b"]
    )
    pair_results = candidate_pairs.merge(
        results, on=["drug_a", "drug_b"], how="left"
    )
    pair_results["status"] = np.where(
        pair_results["posterior_probability"].notna()
        if "posterior_probability" in pair_results
        else False,
        "Explicit label evidence found",
        "No explicit label co-mention found",
    )

    return evidence_path, entered, fda_errors, pair_results, results


@app.cell(hide_code=True)
def _(entered, evidence_path, fda_errors, mo, pair_results, results):
    notices = []
    if fda_errors:
        notices.append("FDA lookup warnings: " + "; ".join(fda_errors))
    if len(pair_results) == 0:
        notices.append(
            "### Enter at least two distinct drug names"
        )
    else:
        notices.append(
            f"### Pairwise evidence check ({len(entered)} drugs, {len(pair_results)} pairs)"
        )
        notices.append(pair_results)
        notices.append(f"Optional non-FDA evidence file: `{evidence_path}`.")
    mo.vstack([mo.md(item) if isinstance(item, str) else item for item in notices])
    return


@app.cell(hide_code=True)
def _(mo, np, results):
    if len(results) == 0:
        score = 0.0
        low, high = 0.0, 0.0
    else:
        # Draw from each pair's posterior and combine draws with a noisy-OR.
        # This propagates uncertainty instead of multiplying fixed point values.
        _rng = np.random.default_rng(123)
        draws = np.column_stack([
            _rng.beta(
                1 + row.posterior_probability * 100,
                1 + (1 - row.posterior_probability) * 100,
                20_000,
            )
            for row in results.itertuples()
        ])
        combined = 1 - np.prod(1 - draws, axis=1)
        score = float(np.mean(combined))
        low, high = np.quantile(combined, [0.025, 0.975])

    mo.md(
        f"## Bayesian combined harm probability: **{score:.1%}** "
        f"(95% credible interval: {low:.1%}–{high:.1%})"
    )

    return score


if __name__ == "__main__":
    app.run()
