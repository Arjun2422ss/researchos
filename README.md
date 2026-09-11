# 🔬 ResearchOS — Multi-Agent GenAI Research Assistant

ResearchOS is an end-to-end portfolio project demonstrating:

- Multi-agent orchestration with LangGraph
- LLM reasoning with the OpenAI Responses API
- Web research with Tavily
- Retrieval-Augmented Generation (RAG) with ChromaDB
- PDF/TXT/Markdown ingestion
- A dedicated fact-checking agent
- Source-aware report synthesis
- Interactive Streamlit UI
- Local testing and Streamlit Community Cloud deployment

## Architecture

```text
                         ┌─────────────────────┐
                         │     Streamlit UI    │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │    Planner Agent    │
                         └──────────┬──────────┘
                                    │
                     ┌──────────────┴──────────────┐
                     ▼                             ▼
             ┌───────────────┐             ┌───────────────┐
             │ Web Research  │             │   RAG Agent   │
             │    Agent      │             │  ChromaDB     │
             └───────┬───────┘             └───────┬───────┘
                     │                             │
                     └──────────────┬──────────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ Fact Check Agent    │
                         └──────────┬──────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ Synthesizer Agent   │
                         └──────────┬──────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ Report + Sources    │
                         └─────────────────────┘
```

## 1. Run locally

Use Python 3.12 or another currently supported Python version.

```bash
python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\activate        # Windows

pip install -r requirements.txt
cp .env.example .env
```

Put your API keys in `.env`, then export them:

```bash
export OPENAI_API_KEY="..."
export TAVILY_API_KEY="..."
```

On Windows PowerShell:

```powershell
$env:OPENAI_API_KEY="..."
$env:TAVILY_API_KEY="..."
```

Run:

```bash
streamlit run app.py
```

## 2. Use RAG

1. Start the app.
2. Upload PDFs/TXT/Markdown files in the sidebar.
3. Click **Index documents**.
4. Enable **Private-document RAG**.
5. Ask a question about the uploaded material.

ChromaDB stores the indexed collection under `data/chroma/`.

## 3. Use web research

Add `TAVILY_API_KEY` and enable **Web research**.

Without a Tavily key, the app still works for private-document RAG.

## 4. Deploy to Streamlit Community Cloud

Push this repository to GitHub.

Then open Streamlit Community Cloud and create an app using:

```text
Repository: your-user/researchos
Branch: main
Main file: app.py
```

Add secrets in the Streamlit app settings:

```toml
OPENAI_API_KEY = "..."
OPENAI_MODEL = "gpt-5.6-mini"
TAVILY_API_KEY = "..."
```

Streamlit Community Cloud supports GitHub-based deployment and secrets management. See:
https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy

## Important deployment note

The local Chroma database is stored on the app filesystem. Streamlit Community Cloud is best treated as a demo environment here; uploaded knowledge-base data can disappear when the app is rebuilt/restarted. For a production version, replace local Chroma with a managed vector database such as Qdrant Cloud, Pinecone, or another persistent service.

## 5. Tests

```bash
pytest
```

## 6. Suggested demo question

Try:

> Compare the EU AI Act and the US AI regulatory approach for startups. Explain the main differences, cite evidence, and identify practical compliance implications.

Then upload an official EU AI Act document and ask a follow-up question. This demonstrates both web research and private-document RAG.

## Portfolio extensions

After the MVP works, the strongest next additions are:

1. Parallel agent execution rather than sequential execution.
2. Reranking for RAG retrieval.
3. Explicit citation verification.
4. RAGAS evaluation dataset.
5. Cost/latency tracking per agent.
6. Streaming agent events in the UI.
7. Persistent managed vector database.
8. Authentication and per-user document collections.
9. Export reports to PDF/Markdown.
10. A benchmark comparing single-agent RAG vs multi-agent RAG.

## Security

Never commit `.env` or API keys to GitHub. Use Streamlit Secrets for deployment.
