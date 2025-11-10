# Knowledge Base (KB) - CrisPRO.ai

## Overview
Durable, auditable knowledge base that our AI and UI rely on for entities, facts, cohorts, policies, and prompts.

## Structure
- `schemas/` - JSON Schema definitions for all entity types
- `entities/` - Core entities (genes, variants, pathways, drugs, diseases)
- `facts/` - Curated facts (mechanisms, policies, evidence)
- `cohorts/` - Study manifests and coverage summaries
- `prompts/` - RAG system prompts and templates
- `relationships/` - Subject-predicate-object edges
- `indexes/` - Vector search manifests and metadata
- `snapshots/` - Immutable releases with lockfiles

## Usage
- **Frontend**: Helper copy, pathway membership, cohort coverage chips
- **Backend**: Stable priors, pathway maps, policy thresholds
- **RAG/Agents**: Embedded entities with citations and run IDs

## Provenance
All items include provenance: `{ source, created_at, sha256?, curator?, license }`

## Updates
- Schema validation enforced in CI
- Snapshots created for immutable releases
- Git is primary source of truth

## API Endpoints
- `GET /api/kb/items?type={type}&limit={n}&offset={n}`
- `GET /api/kb/item/{id}`
- `GET /api/kb/search?q={query}&types={types}`
- `POST /api/kb/vector_search`
- `POST /api/kb/reload` (admin only)



