import os 
import httpx

from fastapi import FastAPI, HTTPException

app = FastAPI()

# Railway provides the GPU server address through an environment variable
# This points to the Railtail service, which forwards request through
# Tailscale to the RunPod GPU running llama.cpp - H
GPU_API_URL = os.getenv("GPU_API_URL","").rstrip("/")

@app.get("/")

def read_root():
    # Basic backend health/root route
    return {"message": "ZakLang"}

@app.get("/gpu-health")
async def gpu_health():
    # Make sure Railway has been configured with the GPU API address
    # Without this variable, the backend does not know where to send
    # request for the remote inference server -H
    if not GPU_API_URL:
        raise HTTPException(
            status_code=500,
            detail="GPU_API_URL is not configured",
        )

    try:
        # Create an asynchronous HTTP client so the FastAPI server can
        # contact the remote GPU without blocking other backend requests -H
        async with httpx.AsyncClient(timeout=15.0) as client:

            # Send a health request through:
            # FastAPI -> Railtail -> Tailscale -> RunPod -> llama.cpp  -H
            response = await client.get(f"{GPU_API_URL}/health")

            # Treat any HTTP error response as a failed GPU connection -H
            response.raise_for_status()

        # If llama.cpp reponds successfully, report that the backend
        # can communivate with the remote GPU inference server -H
        try:
            llama_server = response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=502,
                detail="GPU server returned invalid JSON",
            ) from exc

        return {
            "gpu":"connected",
            "llama_server": llama_server,
        }

    except httpx.HTTPError as exc:
        raise HTTPException(
            # Return a 502 error when the backend itself is running, 
            # but the remote GPU service cannot be reached successfully -H
            status_code=502,
            detail=f"Could not reach GPU server: {exc}"
        )
