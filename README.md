# 📱 Smart Guided Troubleshooting Engine
### Samsung PRISM · Theme 2: Smart Guided Troubleshooting Engine

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 16](https://img.shields.io/badge/frontend-Next.js%2016%20%7C%20React%2019-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI%20%7C%20Uvicorn-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📖 Executive Summary

The **Smart Guided Troubleshooting Engine** transforms vague customer complaints regarding Samsung Galaxy devices (e.g., *"My S22 screen is laggy and touch response is delayed"*) into **schema-valid, safety-ordered, one-tap actionable Settings repair plans**.

Instead of requiring support agents to manually read through technical documentation (Samsung SIIS articles) for 15 minutes per ticket, this engine delivers sub-second automated diagnostics, attaches **direct Bixby deeplink shortcuts** to open the exact Settings menu on the user's phone, and introduces **Closed-Loop Verification** to actively confirm that the proposed setting was applied and resolved the issue.

---

## 🎯 The Problem & Gaps Solved

| Traditional Customer Support Challenge | Our Smart Troubleshooting Engine Solution |
| :--- | :--- |
| **High Latency:** ~15 minutes spent by agents reading through long manuals. | **Sub-Second Response:** Instant triage in under 1 second (1 ms on cache hits). |
| **Confusing Navigation:** Users get lost in nested menus (*Settings → Display → Advanced → Touch sensitivity*). | **1-Tap Deeplinks:** Direct button shortcuts open the exact target switch. |
| **Accidental Data Loss:** Customers jump straight to a factory reset. | **3-Tier Safety Gating:** Safe auto fixes run first; destructive resets are strictly locked. |
| **No Verification:** Chatbots provide advice with no feedback loop on whether it worked. | **Closed-Loop Verification:** Checks `validationDeeplink` state to verify setting changes. |
| **AI Hallucinations:** Generic LLMs invent non-existent phone settings. | **100% Grounded Provenance:** Every step links directly to a verified sentence in Samsung's manual. |

---

## 🔄 End-to-End System Architecture

```
                                  Customer Complaint
                         ("s22 touch input delay laggy screen")
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │   1. Query Enrichment  │ (Extracts device, symptom signature,
                             └───────────┬───────────┘  handles compound multi-intents)
                                         │
                         ┌───────────────┴───────────────┐
                         ▼                               ▼
                 [ Semantic Cache ]             [ Knowledge Base ]
               (Exact & Cosine Hit)          (SIIS Article Retrieval)
                 ~1 ms Latency               Relevance Gate Floor > 0.12
                         │                               │
                         └───────────────┬───────────────┘
                                         ▼
                             ┌───────────────────────┐
                             │  2. Action Extraction │ (Deterministic NLP or Llama 3.3 LLM,
                             └───────────┬───────────┘  enforcing sentence provenance)
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │  3. Deeplink Mapping  │ (Exact setting match + TF-IDF,
                             └───────────┬───────────┘  resolves ON/OFF twin directions)
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │  4. Safety Validation │ (Order: 🟢 Auto ➔ 🟡 Manual ➔ 🔴 Critical)
                             └───────────┬───────────┘
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │  5. Closed-Loop Check │ (Reads validationDeeplink state
                             └───────────────────────┘  e.g. onURL -> boolean = True)
```

---

## 🌟 Key Innovations

1. **⭐ Closed-Loop Verification (`validationDeeplink`):**
   * Unlike static bots, each automated step is paired with a verification probe (`val/` URI).
   * The on-device agent flips the switch and reads back the device state (e.g. confirming `touch_sensitivity == true`). Disruptive steps are only unlocked if the safe fix is confirmed but the symptom persists.
2. **🛡️ 3-Tier Safety Hierarchy:**
   * **🟢 Safe Auto Steps:** Settings toggles with 1-tap shortcuts.
   * **🟡 Manual Steps:** Physical actions (cleaning ports, removing screen protectors).
   * **🔴 Critical Disruption:** Restarts, safe mode, and factory resets (locked behind safe failure confirmation).
3. **🔍 Sentence-Level Provenance & Auditability:**
   * Every instruction retains the exact text span from the source Samsung SIIS article, answering the enterprise compliance requirement: *"Did the system invent this step?"*
4. **⚡ Hybrid AI Architecture:**
   * **Default Mode (Deterministic NLP):** 100% offline, zero API costs, zero hallucinations, millisecond execution.
   * **Boosted Mode (Llama 3.3 70B via Groq):** LLM drafts complex multi-intent structures, strictly fenced by 60%+ token grounding validation.

---

## 📊 Benchmark Results (v1 vs v2 Engine)

Evaluated against hand-labeled gold standards and 60 unseen natural paraphrases:

| Metric | Baseline (v1) | Engine (v2) | Improvement |
| :--- | :---: | :---: | :---: |
| **Rule Compliance** (Goal, Title, Descriptions, Category) | 5.0% | **100.0%** | +95.0% |
| **Deeplink Relevance** (Exact Target Screen, Scale 0–2) | 0.03 | **2.00** | Perfect match |
| **Step Accuracy** (vs. Hand-Labeled Gold Standard, Scale 0–3) | 2.74 | **2.99** | Near ceiling |
| **Cache Hit Rate** (on 60 unseen natural paraphrases) | 0.0% | **90.0%** | Instant hits |
| **Closed-Loop Verifiability** (Validation Deeplink coverage) | 0.0% | **68.0%** | High coverage |
| **Schema Validity & Catalog Safety** | 100% / 0 leaks | **100% / 0 leaks** | Zero leaks |
| **Average Cold Execution Latency** | ~45 ms | **< 20 ms** | 2.2x faster |

---

## 🖥️ Interactive Web Console Overview

The web dashboard (`/web`) includes four dedicated interfaces:

1. **🛠️ Troubleshoot (Home):**
   * Live query input with pre-loaded real customer scenarios.
   * **Plan View:** Structured actions separated into colored safety tiers.
   * **Trace View:** Interactive audit tool highlighting exact source sentences on hover.
   * **Virtual Phone Simulator:** An animated Samsung Galaxy device simulator demonstrating 1-tap deep links, switch toggles, and live **"Fix Confirmed"** status.
2. **📦 Batch Run (`/batch`):**
   * Executes batch evaluation on all 20 official benchmark test queries simultaneously.
   * Exports full JSONL test runs.
3. **📈 Metrics (`/metrics`):**
   * Live visual charts comparing compliance, accuracy, and latency distributions.
4. **💡 Gaps & Innovation (`/about`):**
   * Presentation-ready slide decks and architectural deep-dives for stakeholder review.

---

## 📁 Repository Structure

```
prism_project/
├── app.py                     # Main FastAPI server entry point (port 8765)
├── schema.py                  # Standard Pydantic output contracts
├── requirements.txt           # Python dependencies
├── metrics.md                 # Detailed benchmark evaluation report
├── CollegeName_...pptx        # Presentation slide deck for Samsung PRISM
│
├── engine/                    # 🧠 The Core Intelligence Engine
│   ├── api.py                 # REST API endpoints & route handlers
│   ├── catalog.py             # Deeplink hygiene, twin resolution & mapping
│   ├── extract.py             # SIIS text to atomic Goal extraction
│   ├── enrichment.py          # Query normalization, symptom & entity parsing
│   ├── cache.py               # Semantic cache with cosine similarity & symptom gate
│   ├── llm.py                 # Optional Groq Llama 3.3 LLM integration
│   ├── pipeline.py            # End-to-end diagnostic orchestrator
│   ├── validate.py            # Safety constraints, field rules & URL scrubbers
│   └── verify.py              # Closed-loop validation & device state simulation
│
├── data/                      # 📚 Knowledge Base & Official Theme 2 Kit
│   ├── deeplinks.json         # 578 masked Samsung Settings deeplinks
│   ├── siis_responses.json    # 20 official Samsung troubleshooting articles
│   ├── input.txt              # Official test evaluation complaints
│   └── samples/               # Golden reference test samples
│
├── eval/                      # 🧪 Testing Lab & Metrics Scorer
│   ├── gold.json              # Hand-labeled ground truth
│   ├── paraphrases.json       # 60 unseen test paraphrases
│   ├── run_metrics.py         # Independent benchmark scoring runner
│   └── test_engine.py         # Pytest test suite
│
├── web/                       # 💻 Interactive Next.js Dashboard
│   ├── app/                   # Next.js App Router pages (Troubleshoot, Batch, Metrics, About)
│   ├── components/            # UI components, Phone Simulator, Trace & Plan viewers
│   └── lib/                   # API client bindings and state types
│
└── docs/                      # 📑 Diagrams, Research & Slide Content
    ├── GAPS_AND_INNOVATION.md # Detailed gap analysis and research findings
    ├── diagrams/              # Architecture and closed-loop visual diagrams
    └── images/                # Screenshots and UI previews
```

---

## 🚀 Quickstart Guide

### Prerequisites
* **Python 3.11+**
* **Node.js 20+ & npm**

### 1. Start the Backend Engine
```bash
# Install Python dependencies
python -m pip install -r requirements.txt

# Launch FastAPI server (runs on http://127.0.0.1:8765)
python -m uvicorn app:app --host 127.0.0.1 --port 8765
```

### 2. Start the Frontend Web Console
In a second terminal window:
```bash
cd web
npm install
npm run dev
```

Open your browser and navigate to: **`http://localhost:3000`** (or `http://127.0.0.1:43123`).

---

### ⚙️ Optional: Enable Cloud AI (Llama 3.3 70B via Groq)

To enable LLM-assisted drafting alongside deterministic validation:

Copy `.env.example` to `.env` and set `GROQ_API_KEY`. The engine loads that file automatically.

```bash
# Windows PowerShell
$env:GROQ_API_KEY="your_groq_api_key_here"
$env:GROQ_MODEL="llama-3.3-70b-versatile"

# Linux / macOS
export GROQ_API_KEY="your_groq_api_key_here"
export GROQ_MODEL="llama-3.3-70b-versatile"
```

---

## 📡 API Reference

### `POST /v1/troubleshoot`
Generates a structured troubleshooting plan.

**Request Body:**
```json
{
  "query": "phone swipe gestures wrong direction after app install",
  "siis_response": null
}
```

**Response Body:**
```json
{
  "query": "phone swipe gestures wrong direction after app install",
  "query_variations": [ ... ],
  "response": {
    "contexts": [
      {
        "goal": "Troubleshoot navigation swipe gestures",
        "title": "Swipe Gestures",
        "score": 0.95,
        "actions": [
          {
            "actionName": "Configure Navigation Bar Gestures",
            "description": "Adjust gesture sensitivity and navigation preferences.",
            "category": "auto",
            "stepGroups": [
              {
                "steps": ["Go to Settings > Display > Navigation bar."],
                "actionableDeeplink": {
                  "deeplink": "bixby://settings/navigation_bar",
                  "description": "Opens Navigation bar settings"
                },
                "validationDeeplink": {
                  "deeplink": "bixby://settings/val/navigation_bar",
                  "key": "navigation_mode",
                  "resultType": "str",
                  "condition": "equal",
                  "value": "gestures"
                }
              }
            ]
          }
        ]
      }
    ]
  },
  "meta": {
    "latency_ms": 14.2,
    "cache_hit": false,
    "model": "deterministic-hybrid-v2",
    "cost_usd": 0.0
  }
}
```

---

## 🧪 Running Tests & Reproducing Metrics

```bash
# Run complete test suite (unit tests, validation, contracts, cache)
python -m pytest -q

# Run batch evaluation across all input queries
python scripts/run_batch.py --samples

# Recompute benchmarks and generate metrics.md
python eval/run_metrics.py
```

---

## 📄 License
This project is developed under the **Samsung PRISM** program. All rights reserved.
