# Sacred Hearth Catholic Church Livestream Automation (Node.js 24)

This service runs on Google Cloud Run using Cloud Buildpacks.  
Push updates to GitHub and Cloud Run will automatically rebuild and redeploy.

## Endpoints

- GET `/` — health check  
- POST `/trigger` — automation trigger endpoint

## Requirements

- Node.js 24 runtime
- Express.js
- Cloud Run Services (HTTP)
- Cloud Buildpacks (no Docker needed)
