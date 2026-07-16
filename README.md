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
