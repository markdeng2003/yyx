from fastapi import FastAPI

from app.api.profile import router as profile_router

app = FastAPI(title="ETF Volume Profile Backend")
app.include_router(profile_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
