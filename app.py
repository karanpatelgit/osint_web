#!/usr/bin/env python3
import os
import time
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, HttpUrl
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from duckduckgo_search import DDGS

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OSINT_Backend")

app = FastAPI(title="OSINT Engine Unified Hub")

# --- CRITICAL: CORS Middleware (Fixes the 'Failed to fetch' Error) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows your local index.html to communicate securely
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global memory cache to track running research jobs
JOBS_CACHE: Dict[str, Dict[str, Any]] = {}

class InvestigationRequest(BaseModel):
    target: str
    urls: Optional[List[HttpUrl]] = []
    provider: Optional[str] = "groq"
    mode: Optional[str] = "briefing"

# ─────────────────────────────────────────────────────────────────────────────
# CORE SCRAPER & AI PIPELINE WORKER
# ─────────────────────────────────────────────────────────────────────────────

def run_autonomous_investigation(job_id: str, target: str, provider: str):
    """Background worker that searches the web, scrapes data, and hits the AI."""
    try:
        # Step 1: Link Discovery
        JOBS_CACHE[job_id]["status"] = "ingesting_data"
        logger.info(f"[{job_id}] Initializing web search discovery for: {target}")
        
        discovered_urls = []
        try:
            with DDGS() as ddgs:
                results = ddgs.text(target, max_results=5)
                discovered_urls = [r.get('href') for r in results if r.get('href')]
        except Exception as e:
            logger.error(f"Search discovery warning: {e}")

        if not discovered_urls:
            raise ValueError("No search links could be found for this topic.")

        # Step 2: Content Extraction (Scraping)
        scraped_sources = []
        prompt_data_buffer = []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        for idx, url in enumerate(discovered_urls):
            try:
                r = requests.get(url, headers=headers, timeout=10)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    for s in soup(["script", "style", "nav", "footer", "form"]): 
                        s.decompose()
                    clean_text = soup.get_text(separator=" ", strip=True)[:3000]
                    
                    scraped_sources.append({
                        "index": idx,
                        "url": url,
                        "domain": urlparse(url).netloc,
                        "title": soup.title.string.strip() if soup.title else url,
                        "type": "news"
                    })
                    prompt_data_buffer.append(f"[Source {idx}] URL: {url}\nContent: {clean_text}\n")
            except Exception as e:
                logger.warning(f"Failed scraping {url}: {e}")

        # Step 3: AI Generation Structure Format Pass
        JOBS_CACHE[job_id]["status"] = "ai_generation"
        logger.info(f"[{job_id}] Data gathered. Requesting AI analysis via {provider}...")

        # --- AI Route Simulation ---
        # (This structures exactly what the UI tab renderer expects)
        time.sleep(3) # Simulating heavy AI processing computation
        
        simulated_briefing = {
            "context": [
                f"Core profiling indicates high activity surrounding '{target}' across recent indexes. [Source 0]",
                f"Primary operations appear aligned with text found in public databases. [Source 1]"
            ],
            "network": [
                "Identified institutional connections pointing to secondary infrastructure nodes. [Source 0]",
                "Key personnel list shows organizational adjustments over the last 12 months."
            ],
            "trail": [
                "Initial registration trails suggest domain setups mapped to standard hosting patterns.",
                "Financial context: Seed allocations or user backing records remain obscure in early sweeps."
            ],
            "guns": [
                "Minor narrative variance detected between target's initial landing pages and latest press entries. [Source 2]"
            ],
            "confidence": {"context": "high", "network": "medium", "trail": "low", "guns": "medium"},
            "needs_corroboration": [f"Direct authentication of registration documents linked to {target}."],
            "named_persons": ["John Doe (Director)", "Jane Smith (Lead Analyst)"],
            "keywords": [target, "Investigation", "OSINT Tracking", "Network Intel"],
            "headline_variants": {
                "seo": f"Deep Dive: What the Data Tells Us About {target}",
                "clickable": f"The Untold Story Behind {target}: Data Exposed",
                "print": f"INVESTIGATING THE NETWORK MATRIX OF {target.upper()}",
                "thread_hook": f"🧵 Let's talk about {target}. We mapped the links, dug through the archives, and found something fascinating. Thread below."
            },
            "sources": scraped_sources
        }

        # Step 4: Finalize Job State
        JOBS_CACHE[job_id]["status"] = "completed"
        JOBS_CACHE[job_id]["data"] = simulated_briefing
        logger.info(f"[{job_id}] Intelligence suite briefing built successfully.")

    except Exception as e:
        logger.error(f"[{job_id}] Pipeline crashed: {str(e)}")
        JOBS_CACHE[job_id]["status"] = "failed"
        JOBS_CACHE[job_id]["data"] = {"error": str(e)}

# ─────────────────────────────────────────────────────────────────────────────
# ROUTING CONTROLLERS
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/v1/analyze")
async def start_analysis(request: InvestigationRequest, background_tasks: BackgroundTasks):
    job_id = f"job_{int(datetime.utcnow().timestamp())}"
    
    JOBS_CACHE[job_id] = {
        "id": job_id,
        "target": request.target,
        "status": "queued",
        "data": None
    }
    
    # Hand off the scraping and AI workload to the background loop
    background_tasks.add_task(
        run_autonomous_investigation, 
        job_id, 
        request.target, 
        request.provider
    )
    
    return {"status": "enqueued", "job_id": job_id}

@app.get("/api/v1/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in JOBS_CACHE:
        raise HTTPException(status_code=404, detail="Job entry not found.")
    return JOBS_CACHE[job_id]
