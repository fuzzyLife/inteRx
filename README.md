# inteRx
probabilistic drug-interaction, specifically, interpret if any combination of drugs prescribed poses risk?

## app.py: marimo notebook script 

hosted at [molab-wasm-page](https://molab.marimo.io/github//fuzzyLife/inteRx/blob/master/app.py/wasm), for serving locally try
```
uv run marimo run app.py 

        Running app.py ⚡

        ➜  URL: http://localhost:2718
```         

## Inspiration
reduce iatrogenic  issues
## What it does
it will provide a probabilistic score of harm from a combination of drugs
## How we built it
go through drug interaction literature and extract relevant information, give probability scores for a given combination
## Challenges we ran into
hard to find good resource
## Accomplishments that we're proud of
got quite close to predicting effects
## What we learned
what sounds easy to implement gets complicated as we progress...
## What's next for fuzzyLife
probabilistic diagnosis, specifically, interpret lab tests and imaging results coming from suspected infectious disease and risk assessment of other conditions e.g. cancer


# GPT-5.6 Luna Codex Copilot Chat
create marimo notebook inteRx for probabilistic drug-interaction, specifically, interpret if any combination of drugs prescribed poses risk?

What it does
it will provide a probabilistic score of harm from a combination of drugs

How to built it
go through drug interaction literature and extract relevant information, give probability scores for a given combination


**Svar**
Created the marimo notebook prototype:

Features:

* Drug combination input
* Example interaction knowledge base
* Detection of interacting drug pairs
* Probabilistic harm aggregation
* Risk score output
* Marimo UI components

Current scoring is a demonstration. For a hackathon or production version, the next step would be to replace the hardcoded interaction database with literature-derived interaction probabilities extracted from DrugBank, FDA labeling, PubMed studies, and pharmacovigilance datasets, then use Bayesian aggregation instead of fixed pairwise probabilities.
