# 🌟 PubMed LLM Agent: Natural Language to Ranked Evidence (Powered by Google Gemini)

> **Ask in plain English. Get back ranked, relevant studies.**  
> A smart agent that turns your natural language questions into precise PubMed searches, retrieves full-text eligible studies, and uses AI to rank them by relevance — all in one seamless workflow.

---

## 📖 Overview

The **PubMed LLM Agent** is a powerful research tool that bridges the gap between **natural language questions** and **high-quality biomedical literature**.

Instead of requiring complex Boolean queries or MeSH terms, you can ask:

> _"Show me recent clinical trials on GLP-1 agonists for weight loss in adolescents."_

And the agent will:
1. **Understand your intent**
2. **Build an optimized PubMed search query**
3. **Retrieve relevant studies** (optionally limited to free full-text PMC articles)
4. **Use a large language model (LLM)** to re-rank results by clinical relevance (1–100)
5. **Return structured JSON** with titles, abstracts, PMCID, license info, and explanations

This tool is ideal for researchers, clinicians, students, and anyone who wants **fast, accurate access to medical evidence** — without needing to be a PubMed expert.

---

## 💡 Why This Exists

Searching PubMed effectively requires expertise:
- Knowing field tags like `[mh]`, `[pt]`, `[tiab]`
- Understanding MeSH terminology
- Constructing Boolean logic with `AND`, `OR`, `NOT`
- Filtering by study type, language, date

Most people just want answers — not a search syntax tutorial.

That’s where this agent comes in.

It **uses AI to do the hard work** so you don’t have to.

---

## 🔍 How It Works (Step-by-Step)

### 1. **Natural Language Input**
You provide a query in everyday English:
```text
"Which antidepressants are effective for anxiety in older adults since 2020?"
```

No special syntax needed.

### 2. **Query Understanding & Date Extraction**
The agent parses your query to:
- Extract **date ranges** (e.g., "since 2020")
- Identify **key concepts**: population, intervention, outcome
- Clean the query for searching

This allows flexible phrasing like:
- `"from 2018 to 2023"`
- `"in the last 5 years"`
- `"recent studies on..."`

### 3. **LLM-Powered Query Generation**
Using **Google Gemini**, the agent converts your natural language into a **precise, optimized PubMed search string**, such as:
```text
(antidepressants[tiab] OR SSRIs[mh]) AND (anxiety disorder[mh] OR generalized anxiety[tiab]) AND (elderly[mh] OR older adults[tiab]) AND ("2020"[pdat] : "2023"[pdat]) AND english[lang]
```
It also adds filters like:
- `clinical trial[pt]` if you want trials
- `pubmed pmc[sb]` if you want free full-text (PMC) articles

### 4. **PubMed Search & Retrieval**
Using NCBI’s E-utilities API, it:
- Fetches up to **10,000 matching PMIDs**
- Gets summaries (titles, journals, dates)
- Optionally downloads **abstracts and metadata**

With support for:
- NCBI API keys (faster rate limits)
- Email registration (recommended by NCBI)

### 5. **LLM Relevance Scoring (1–100)**
Each retrieved study is scored by the LLM for **relevance to your original question**.

For example:
| Score | Meaning |
|------|--------|
| 90–100 | Direct match: correct population, intervention, outcome, design |
| 70–89 | Highly relevant, minor mismatch |
| 50–69 | Partial match |
| <50 | Tangential or irrelevant |

Each score comes with a **human-readable explanation**:
> _"This study evaluates sertraline for anxiety in patients over 65 — directly matches all criteria."_  

Results are sorted by relevance, not just publication date.

### 6. **Rich Metadata Extraction**
For every paper, the agent extracts:
- ✅ **PMCID** (PubMed Central ID) — `PMC1234567`
- ✅ **License** (if available): `"cc by"`, `"public domain"`, etc.
- ✅ **DOI**, journal, year, abstract
- ✅ Publication types (e.g., "Randomized Controlled Trial")

All included in the output for reuse and compliance.

### 7. **Output: Structured, Usable Results**
Final output is clean **JSON**, perfect for:
- Saving to disk
- Feeding into downstream tools
- Integration with literature review software

Example snippet:
```json
{
  "results": [
    {
      "pmid": "12345678",
      "title": "A Randomized Trial of Sertraline in Older Adults with GAD",
      "journal": "JAMA Psychiatry",
      "year": 2022,
      "pmcid": "PMC9876543",
      "license": "cc by",
      "relevance": 96,
      "relevance_reason": "Direct RCT on sertraline for anxiety in older adults",
      "abstract": "Background: Generalized anxiety disorder affects..."
    }
  ]
}
```

---

## 🧩 Modular Architecture

The project is cleanly split into components:

```
core/
├── pubmed_client.py     → Talks to PubMed E-utilities (ESearch, ESummary, EFetch)
├── llm_client.py        → Interfaces with Google Gemini API
├── query_builder.py     → Uses LLM to convert natural language → PubMed query
├── llm_rerank.py        → Scores and ranks studies by relevance using LLM
├── utils.py             → Shared helpers: date parsing, JSON safety, record assembly
└── assemble_records.py  → Combines data into final structured format

pubmed_llm_agent.py      → Main logic and CLI interface
```

This makes it easy to extend, test, or integrate into other systems.

---

## ⚙️ Features & Capabilities

| Feature | Description |
|-------|-------------|
| **Natural Language First** | No need to know PubMed syntax — just ask your question |
| **Smart Date Parsing** | Understands "from 2020", "last 3 years", "since 2018" |
| **LLM Query Builder** | Converts your words into optimized, field-tagged PubMed queries |
| **Full-Text Ready** | Option to limit to **PubMed Central (PMC)** open-access articles |
| **Clinical Trial Filter** | Focus on RCTs and clinical trials only |
| **AI Relevance Ranking** | LLM scores each paper 1–100 with justification |
| **Batch Processing** | Efficiently scores dozens of papers at once using Gemini 1.5’s 1M context |
| **Metadata Rich** | Includes PMCID, license, DOI, MeSH, abstracts |
| **Configurable** | Set defaults via `config.json` — no code changes needed |
| **CLI & Scriptable** | Run from terminal, automate reviews, integrate into pipelines |

---

## 🛠️ Requirements

### APIs & Keys
- 🔑 **Gemini API Key** – Get it at [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) (requires Google account)
- 📧 **NCBI Email** – Recommended; set `NCBI_EMAIL` environment variable
- 🔐 **NCBI API Key** – Increases speed (up to 10 requests/sec)


## 🚀 Quick Start

## Install requirements
```bash

pip install -r requirements.txt

```

## 📄 Configuration via `config.json`

You can avoid repeating CLI arguments by creating a `config.json`:

```json
{
  "general": {
    "max_results": 500,
    "top_k": 30,
    "llm_rerank": true,
    "pmc_only": true,
    "only_trials": true,
    "batch_size": 50
  },
  "llm": {
    "model": "gemini-2.5-flash",
    "api_key": "your-gemini-api-key"
  },
  "pubmed": {
    "email": "you@example.com",
    "api_key": "your-ncbi-api-key"
  }
}
```

### 2. Run a Search
```bash
python pubmed_llm_agent.py \
  --query "I want to find studies on the use of mmega-3 supplements for depression in adults" \
  --llm-rerank \
  --only-trials \
  --top-k 10 \
  --config config.json

```

### 3. Save Results
Results are saved automatically to a timestamped JSON file, or use `--out results.json`.


## 📂 Project Structure

```
.
├── pubmed_llm_agent.py         # Main script (CLI entry point)
├── config.json                 # User configuration (API keys, defaults)
├── requirements.txt            # Python dependencies
├── core/
│   ├── pubmed_client.py        # PubMed API interface
│   ├── llm_client.py           # Gemini LLM interface
│   ├── query_builder.py        # Natural language → PubMed query
│   ├── llm_rerank.py           # AI-powered relevance scoring
│   ├── utils.py                # Helpers: date parsing, JSON safety
│   └── assemble_records.py     # Builds final result objects
└── README.md                   # This file
```

---

## 🎯 Use Cases

| Who | How They Use It |
|-----|-----------------|
| **Researchers** | Rapid scoping for systematic reviews, grant writing |
| **Clinicians** | Find latest evidence for patient care decisions |
| **Students** | Learn about topics with curated, ranked literature |
| **Bioinformaticians** | Automate evidence retrieval pipelines |
| **Journalists** | Back up health stories with peer-reviewed sources |

---

## 📢 Future Ideas

- Web interface (Streamlit, FastAPI)
- Export to CSV/BibTeX
- Citation summaries ("What do these papers conclude?")
- Alerts for new studies on a topic
- Integration with Zotero or Mendeley

---

## 🙌 Acknowledgements

- **Google AI Studio** – For hosting Gemini and providing the LLM backbone
- **NCBI** – For maintaining PubMed and providing free E-utilities API
---

## 📎 License

MIT License – feel free to use, modify, and share.

---

> ✨ **Stop searching. Start understanding.**  
> The PubMed LLM Agent turns your questions into answers — naturally.
