"""Local API; routes call shared business functions and never accept scrape URLs."""

from functools import lru_cache
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Query

from backend.models import (DealResponse, HealthResponse, ProductPage, SearchRequest,
                            SearchResponse, StatusResponse)
from backend.service import ShoppingService
from db.embeddings import DIMENSIONS, MODEL_NAME
from backend.settings import setting, configuration_status

app = FastAPI(title="Shoppie local backend", version="0.1.0")


@lru_cache(maxsize=1)
def get_service():
    source = setting("SHOPPIE_API_SOURCE", "demo")
    if source not in {"demo", "live", "supabase"}:
        raise ValueError("SHOPPIE_API_SOURCE must be demo, live, or supabase")
    return ShoppingService(mode="demo" if source == "demo" else "live",
                           storage="supabase" if source == "supabase" else "local")


def run(function):
    try:
        return function()
    except ValueError as error:
        raise HTTPException(400, str(error)) from None
    except Exception:
        raise HTTPException(503, "Local collection or embedding service is unavailable; inspect local setup.") from None


@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok", "source": setting("SHOPPIE_API_SOURCE", "demo"), "model_name": MODEL_NAME, "dimensions": DIMENSIONS}


@app.get("/storage/status")
def storage_status():
    # configuration booleans only; hosted reads require the explicit CLI/UI check
    return configuration_status()


@app.get("/products", response_model=ProductPage)
def products(service=Depends(get_service)):
    return run(lambda: {"source": service.mode, "products": service.products()})


@app.get("/search", response_model=SearchResponse)
def product_search(request: Annotated[SearchRequest, Query()], service=Depends(get_service)):
    return run(lambda: service.search(request))


@app.get("/deals", response_model=DealResponse)
def deals(request: Annotated[SearchRequest, Query()], service=Depends(get_service)):
    return run(lambda: service.deals(request))


@app.get("/scraper/status", response_model=StatusResponse)
def scraper_status(service=Depends(get_service)):
    return service.status


@app.post("/demo/collect", response_model=StatusResponse)
def demo_collect(service=Depends(get_service)):
    if service.mode != "demo":
        raise HTTPException(400, "Demo collection is available only in Demo mode")
    return run(lambda: service.collect("demo fixtures"))
