"""Alias for PowerShell: python -m uvicorn backend.app:app --reload"""
from backend.main.main import app, create_app

__all__ = ["app", "create_app"]
