from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from .api import calls, analytics
from .api.auth import authorized
from .api.appointments import router as appt_router
from .api.crm import router as crm_router
from .config import ROOT, LIVE
from .database import init
from .agents.graph import graph

@asynccontextmanager
async def lifespan(app):
    init()
    graph()
    yield

app = FastAPI(title="FlowCRM Voice Agent", lifespan=lifespan)

@app.get("/api/health")
def health():
    return {"status":"ok","live":LIVE}

app.include_router(calls.router,prefix="/api",dependencies=[Depends(authorized)])
app.include_router(analytics.router,prefix="/api",dependencies=[Depends(authorized)])
app.include_router(appt_router,prefix="/api",dependencies=[Depends(authorized)])
app.include_router(crm_router,prefix="/api",dependencies=[Depends(authorized)])
dist = ROOT / "frontend" / "dist"
if dist.is_dir():
    app.mount("/",StaticFiles(directory=dist,html=True),name="frontend")
