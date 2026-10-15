# Rehab CDSS — Frontend

React + TypeScript + Vite frontend for the Rehabilitation Clinical Decision Support System.

## Overview

A Ukrainian-language web interface for uploading patient test files (PDFs, CSVs), configuring patient parameters, and generating structured biomechanical analysis reports.

## Getting started

```bash
npm install
npm run dev
```

The dev server starts at http://localhost:3000.

## Environment variables

Copy `.env.example` to `.env.local` and configure:

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE` | `http://localhost:8000` | Base URL of the backend API |
| `VITE_API_KEY` | _(empty)_ | Optional API key sent as `X-API-Key` header |

## Backend

The backend must be running on port 8000 before using the app:

```bash
uv run rehab-api
```

## Structure

- `src/api/` — typed API client and TypeScript types
- `src/store/` — Zustand global state
- `src/hooks/` — custom React hooks (file detection, job polling, config)
- `src/components/` — UI components organized by layout / files / params / ui
- `src/styles/` — design tokens, reset, and global CSS
