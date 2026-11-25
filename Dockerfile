FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements*.txt ./
ARG REQUIREMENTS=requirements.txt
RUN pip install --no-cache-dir -r "$REQUIREMENTS"
COPY backend/ backend/
COPY knowledge_base/ knowledge_base/
RUN if [ "$REQUIREMENTS" = "requirements-live.txt" ]; then python -m backend.voice.agent download-files; fi
COPY --from=frontend /build/dist frontend/dist/
CMD ["uvicorn","backend.main:app","--host","0.0.0.0","--port","8000"]
