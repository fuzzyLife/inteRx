import marimo

app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    return mo, pd


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
def _(drugs, pd):
    interaction_db = pd.DataFrame(
        [
            ["warfarin", "aspirin", 0.85, "Bleeding risk"],
            ["warfarin", "ibuprofen", 0.80, "Bleeding risk"],
            ["sertraline", "tramadol", 0.75, "Serotonin syndrome"],
            ["simvastatin", "clarithromycin", 0.70, "Myopathy"],
            ["opioid", "benzodiazepine", 0.90, "Respiratory depression"],
        ],
        columns=["drug_a", "drug_b", "probability", "harm"],
    )

    entered = [
        drug.strip().lower()
        for drug in drugs.value.split(",")
        if drug.strip()
    ]

    findings = []
    for _, row in interaction_db.iterrows():
        if row.drug_a in entered and row.drug_b in entered:
            findings.append(row.to_dict())

    results = pd.DataFrame(findings)

    return interaction_db, entered, results


@app.cell
def _(mo, results):
    if len(results) == 0:
        mo.md("### No known interactions found in demo dataset")
    else:
        mo.vstack(
            [
                mo.md("### Potential interactions"),
                results,
            ]
        )
    return


@app.cell
def _(mo, results):
    if len(results) == 0:
        score = 0.0
    else:
        score = 1 - (1 - results["probability"]).prod()

    mo.md(
        f"## Combined estimated harm probability: **{score:.1%}**"
    )

    return score


if __name__ == "__main__":
    app.run()