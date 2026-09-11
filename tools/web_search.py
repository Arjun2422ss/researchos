import os

def web_search(query, max_results=6):
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return [{
            "title": "Web search unavailable",
            "url": "",
            "snippet": "TAVILY_API_KEY is not configured. Enable private-document RAG or add a Tavily API key."
        }]
    from tavily import TavilyClient
    client = TavilyClient(api_key=api_key)
    response = client.search(
        query=query,
        search_depth="advanced",
        max_results=max_results,
        include_answer=False,
    )
    return [
        {
            "title": item.get("title", "Untitled"),
            "url": item.get("url", ""),
            "snippet": item.get("content", ""),
        }
        for item in response.get("results", [])
    ]
