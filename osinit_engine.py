#!/usr/bin/env python3
"""
OSINT Deep Briefing Engine — Autonomous Research & Discovery Edition
=====================================================================
Accepts a raw keyword or investigative question, discovers the links,
scrapes the text content, and compiles a comprehensive editorial briefing.

Usage:
  python osint_writer_engine.py --query "Who funds the NGO SaveThePlanet?" --provider groq
  python osint_writer_engine.py --query "XYZ Corporation controversies" --max-results 8 --mode article
"""

import os
import sys
import re
import json
import time
import argparse
import textwrap
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

console = Console()

# Ensure you install the free search package: pip install duckduckgo-search
try:
    from duckduckgo_search import DDGS
except ImportError:
    console.print("[bold red]Missing Core Search Dependency![/bold red]")
    console.print("Please run: [cyan]pip install duckduckgo-search[/cyan] to unlock autonomous search features.")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATIONS & CORE SETTINGS
# ─────────────────────────────────────────────────────────────────────────────

PROVIDERS = {
    "groq": {"name": "Groq", "env_key": "GROQ_API_KEY", "model": "llama-3.3-70b-versatile"},
    "gemini": {"name": "Google Gemini", "env_key": "GEMINI_API_KEY", "model": "gemini-2.5-flash"},
    "claude": {"name": "Anthropic Claude", "env_key": "ANTHROPIC_API_KEY", "model": "claude-opus-4-5"}
}

BRIEFING_SYSTEM = """You are an elite Investigative Journalist. Dissect the raw data provided and build an objective pre-writing brief. 
Output ONLY a valid JSON object matching this exact key structure:
{
  "context": ["bullet 1 [Source N]", "bullet 2 [Source N]"],
  "network": ["key connections and institutional ties [Source N]"],
  "trail": ["funding lines, parent groups, or operational infra [Source N]"],
  "guns": ["narrative shifts, direct contradictions, or red flags [Source N]"],
  "named_persons": ["Full Name 1", "Full Name 2"],
  "headline_variants": {"seo": "...", "clickable": "...", "thread_hook": "..."}
}
If data is completely missing for a section, write 'NO DIRECT DATA FOUND IN SOURCES'. Never hallucinate."""

# ─────────────────────────────────────────────────────────────────────────────
# MODULE 1: AUTONOMOUS LINK DISCOVERY
# ─────────────────────────────────────────────────────────────────────────────

def discover_relevant_urls(query: str, max_results: int = 5) -> list[str]:
    """Queries public search indexes autonomously to gather background reference URLs."""
    urls = []
    console.print(f"[bold red]◌[/bold red] Deploying autonomous crawler for query: [italic]{query}[/italic]...")
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
            for r in results:
                if 'href' in r or 'link' in r:
                    url = r.get('href') or r.get('link')
                    urls.append(url)
    except Exception as e:
        console.print(f"[bold yellow]⚠ Search fetch warning:[/bold yellow] {str(e)}. Falling back to direct mode.")
    return urls

# ─────────────────────────────────────────────────────────────────────────────
# MODULE 2: LIVE TEXT SCRAPER CORE
# ─────────────────────────────────────────────────────────────────────────────

def scrape_single_url(url: str, index: int) -> dict:
    """Scrapes raw web pages, cleaning out noise to preserve high-signal context."""
    res = {"index": index, "url": url, "domain": urlparse(url).netloc, "title": "", "text": "", "status": "ok"}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        r = requests.get(url, headers=headers, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Strip script, head, and junk visual elements
        for element in soup(["script", "style", "nav", "footer", "header", "form"]):
            element.decompose()
            
        res["title"] = soup.title.string.strip() if soup.title else url
        main_text = soup.get_text(separator="\n", strip=True)
        res["text"] = "\n".join([line for line in main_text.splitlines() if len(line.strip()) > 40])[:12000]
    except Exception as e:
        res["status"] = "failed"
        res["text"] = f"Scraping link error tracking marker: {str(e)}"
        
    return res

# ─────────────────────────────────────────────────────────────────────────────
# MODULE 3: LLM ROUTING ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def dispatch_ai_analysis(system: str, user: str, provider: str) -> dict:
    """Handles core routing logic across multi-provider endpoints."""
    p_info = PROVIDERS[provider]
    api_key = os.environ.get(p_info["env_key"], "")
    
    if not api_key:
        raise ValueError(f"Missing API Key for {p_info['name']}. Please set environmental variable: {p_info['env_key']}")

    if provider == "groq":
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
        resp = client.chat.completions.create(
            model=p_info["model"], response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}]
        )
        return json.loads(resp.choices[0].message.content)
        
    elif provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name=p_info["model"], system_instruction=system)
        resp = model.generate_content(user, generation_config={"response_mime_type": "application/json"})
        return json.loads(resp.text)
        
    else:
        raise NotImplementedError("Requested provider interface not mapped in engine core.")

# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE COORDINATION & EXECUTION
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Autonomous Investigative Pre-Writing Pipeline")
    parser.add_argument("--query", required=True, help="Investigative topic phrase, keyword, or core question")
    parser.add_argument("--provider", choices=["groq", "gemini"], default="groq", help="AI Model Provider")
    parser.add_argument("--max-results", type=int, default=5, help="Number of discoverable sources to parse")
    args = parser.parse_args()

    console.print(Panel(
        "[bold red]AUTONOMOUS PRE-WRITING RESEARCH ENGINE[/bold red]\n"
        "[dim]Converts raw investigative questions directly into verified research briefs[/dim]",
        border_style="red"
    ))

    # Phase 1: Search Discovery
    discovered_links = discover_relevant_urls(args.query, max_results=args.max_results)
    if not discovered_links:
        console.print("[bold red]Failure:[/bold red] Web search returned zero links to evaluate.")
        sys.exit(1)

    console.print(f"[green]✓[/green] Identified {len(discovered_links)} candidate search listings.\n")

    # Phase 2: Targeted Scraping Pass
    scraped_data_stack = []
    with Progress(SpinnerColumn(), TextColumn("[bold red]Extracting[/bold red] {task.description}"), BarColumn(), console=console) as progress:
        task = progress.add_task("scraping sources...", total=len(discovered_links))
        for idx, url in enumerate(discovered_links):
            progress.update(task, description=f"[dim]{urlparse(url).netloc}[/dim]")
            scraped_data_stack.append(scrape_single_url(url, idx))
            time.sleep(0.4)
            progress.advance(task)

    # Phase 3: AI Structuring Pack
    prompt_builder = [f"PRIMARY SYSTEM INVESTIGATIVE QUESTION: {args.query}\n", "RAW DISCOVERED DATA:"]
    for s in scraped_data_stack:
        if s["status"] == "ok":
            prompt_builder.append(f"\n[Source {s['index']}] URL: {s['url']}\nContent:\n{s['text']}\n{'─'*40}")

    try:
        briefing_payload = dispatch_ai_analysis(BRIEFING_SYSTEM, "\n".join(prompt_builder), args.provider)
    except Exception as e:
        console.print(f"\n[bold red]Pipeline Evaluation Fault:[/bold red] {str(e)}")
        sys.exit(1)

    # Phase 4: Output Rendering Framework
    console.print("\n")
    console.rule("[bold red]FINAL PRE-WRITING BRIEFING RECORD[/bold red]", style="red")
    
    for key in ["context", "network", "trail", "guns"]:
        console.print(f"\n[bold cyan]### {key.upper()}[/bold cyan]")
        for item in briefing_payload.get(key, ["No data found."]):
            console.print(f"  [red]▸[/red] {item}")

    console.print("\n[bold yellow]RIGHT-OF-REPLY CHECKLIST[/bold yellow]")
    for person in briefing_payload.get("named_persons", []):
        console.print(f"  [dim]☐[/dim] {person}")

    console.print("\n[bold green]AUTONOMOUS SOURCE AUDIT TRAILS[/bold green]")
    t = Table(box=None, header_style="bold dim")
    t.add_column("ID", style="cyan")
    t.add_column("Domain")
    t.add_column("Status")
    for s in scraped_data_stack:
        status_lbl = "[green]OK[/green]" if s["status"] == "ok" else "[red]Failed[/red]"
        t.add_row(f"[{s['index']}]", s["domain"], status_lbl)
    console.print(t)
    console.print()

if __name__ == "__main__":
    main()
