import marimo

app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import os
    from pathlib import Path
    import numpy as np
    import pandas as pd
    return Path, mo, np, os, pd


@app.cell
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


@app.cell
def _(mo):
    drugs = mo.ui.text_area(
        label="Enter drugs (comma-separated)",
        value="warfarin, aspirin",
    )
    drugs
    return (drugs,)


@app.cell
def _(Path, drugs, mo, np, os, pd):
    """Load normalized evidence exported from approved source datasets.

    The app deliberately does not embed clinical probabilities. Prepare a CSV
    from licensed DrugBank data, FDA labels, PubMed reviews/studies, and
    pharmacovigilance data with the columns documented below.
    """
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
    matched = evidence[
        evidence.apply(
            lambda r: r.drug_a in entered and r.drug_b in entered
            or r.drug_b in entered and r.drug_a in entered,
            axis=1,
        )
    ].copy()

    prior_alpha, prior_beta = 1.0, 9.0
    _rng = np.random.default_rng(42)
    findings = []
    for (drug_a, drug_b, harm), group in matched.groupby(["drug_a", "drug_b", "harm"]):
        alpha = prior_alpha + (group["positive"] * group["effective_weight"]).sum()
        beta = prior_beta + (group["negative"] * group["effective_weight"]).sum()
        samples = _rng.beta(alpha, beta, 20_000)
        findings.append({
            "drug_a": drug_a,
            "drug_b": drug_b,
            "harm": harm,
            "posterior_probability": alpha / (alpha + beta),
            "credible_low": np.quantile(samples, 0.025),
            "credible_high": np.quantile(samples, 0.975),
            "evidence_count": len(group),
            "sources": ", ".join(sorted(group["source"].unique())),
            "evidence_ids": ", ".join(group["evidence_id"].astype(str)),
        })
    results = pd.DataFrame(findings)

    return evidence_path, entered, results


@app.cell
def _(evidence_path, mo, results):
    if len(results) == 0:
        mo.md(
            f"### No matching evidence found\n"
            f"Expected a normalized evidence file at `{evidence_path}`."
        )
    else:
        mo.vstack(
            [
                mo.md("### Potential interactions"),
                results,
            ]
        )
    return


@app.cell
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
