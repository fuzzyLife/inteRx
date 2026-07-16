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


## prompt 2
Update this notebook to to replace the hardcoded interaction database with literature-derived interaction probabilities extracted from DrugBank, FDA labeling, PubMed studies, and pharmacovigilance datasets, then use Bayesian aggregation instead of fixed pairwise probabilities.

Updated [app.py](app.py).
Changes include:
Removed the embedded five-row interaction database.
Added loading from interaction_evidence.csv, configurable via INTERACTION_EVIDENCE.
Added support for evidence fields from DrugBank, FDA labels, PubMed, and pharmacovigilance sources.
Added source-specific evidence weights and normalized drug-pair ordering.
Replaced fixed probabilities with Beta–Bernoulli posterior probabilities.
Added posterior 95% credible intervals.
Combined pairwise posterior samples using uncertainty-propagating noisy-OR aggregation.
Added a clear message when the evidence file is missing.

## prompt 3
Create a demo video is which under 3 minutes which can be uploaded publicly on YouTube, ensure is correct in the format. Your voiceover explains what we built, how we used Codex and how we used GPT-5.6.

Created and validated the demo video:
[Download the inteRx demo video](demo/inteRx_demo.mp4)
Duration: 1:46
Format: MP4, H.264 video, AAC audio
Resolution: 1920×1080, 16:9
Suitable for public YouTube upload
Voiceover covers the Bayesian evidence model, Codex’s role, and GPT-5.6 Luna Light
Includes the required research/education disclaimer
The narration source and renderer are also available at [render_demo.ps1](demo/render_demo.ps1).

Uploaded to [YouTube](https://www.youtube.com/watch?v=a0pYnpxZgTw)