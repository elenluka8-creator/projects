from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.routers.admin import router as admin_router
from app.api.routers.auth import router as auth_router
from app.api.routers.config import router as config_router
from app.api.routers.credits import router as credits_router
from app.api.routers.jobs import router as jobs_router
from app.api.routers.precheck import router as precheck_router
from app.api.routers.security import router as security_router
from app.api.routers.storage import router as storage_router
from app.api.routers.upload import router as upload_router

app = FastAPI(title="Unfolda API")
app.include_router(auth_router)
app.include_router(config_router)
app.include_router(credits_router)
app.include_router(security_router)
app.include_router(storage_router)
app.include_router(upload_router)
app.include_router(precheck_router)
app.include_router(jobs_router)
app.include_router(admin_router)


@app.get("/health", include_in_schema=False)
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
