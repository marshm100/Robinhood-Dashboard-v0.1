#!/usr/bin/env python3
"""Local development server."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api.index:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["api", "templates", "static"],
        log_level="info",
    )
