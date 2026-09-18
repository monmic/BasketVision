# BasketVision

BasketVision automatically analyzes basketball game videos.

## Architecture
- backend: ASP.NET Core .NET 8 + EF Core + PostgreSQL
- frontend: React + TypeScript
- vision: Python + OpenCV + Ultralytics
- orchestration: Docker Compose

## Current milestone
CV-02.

## Current priority
Improve basketball ball detection before implementing shot detection.

CV-01 results on a 10m22s sample:
- Person detections: 32564
- Ball detections: 8
- Frames with ball: 7
- Person tracks: 987
- Ball tracks: 0

## Existing features
- Local video upload only
- Background analysis
- Analysis range DA → A
- Pause / resume / delete analysis
- Team A / Team B
- Persistent AnalysisJob
- Vision debug report

## Rules
- Do not remove existing features.
- Keep frontend/backend/worker contracts synchronized.
- Keep Docker Compose working.
- Do not identify individual players yet.
- Game events should support team attribution.
- Prefer incremental changes.
- Ball detection is currently the main CV bottleneck.