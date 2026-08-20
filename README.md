# rare-earth-intel

An agentic system that answers questions about rare earth supply chains and
pricing by reasoning over both policy and company documents and over trade
and production data — and flags where the two disagree.

**Status:** in development — started August 2026

## Problem

Rare earth supply data is fragmented and partly unreliable. Production and
export figures reported by producing countries often diverge from importing
countries' declared imports, and disclosed prices diverge from prices implied
by trade data. Answering a question like "what happened to NdPr supply in a
given year" means reading several documents and reconciling several datasets
that don't agree with each other.

## Approach

_(filled in as I build)_

## Results

| Configuration | Recall@5 | MRR | Cost/query |
|---|---|---|---|
| _baseline_ | — | — | — |

## Data

All sources are public and documented in `docs/sources.md`. No proprietary or
non-public data is used in this project.

## Running it

    uv sync
    uv run pytest

## Limitations

_(filled in honestly as I find them)_