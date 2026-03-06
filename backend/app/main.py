from fastapi import FastAPI

app = FastAPI(title="ETF Volume Profile Backend")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
