# TASP Delivery Platform – Alpha Release

## Overview
This Alpha Release demonstrates the core functionality of the TASP Placement & Matching Gateway. 
It includes multi-module integration, a functional AI matching component, and a working CI/CD pipeline.

## Features Included
- FastAPI backend service
- AI-driven sponsor matching algorithm (MOS, Rank Tier, Load weighting)
- PostgreSQL schema for personnel and inbound PCS tracking
- Automated CI/CD pipeline using GitHub Actions
- Pytest suite validating core matching logic

## How to Run Locally
pip install -r requirements.txt
uvicorn main:app --reload

## How to Run Tests
pytest -v backend/tests/

## CI/CD Pipeline
The pipeline runs automatically on pull requests to `develop` or `main`, executing:
- Dependency installation
- FastAPI environment setup
- Pytest validation

## Team Members
- (List names)
