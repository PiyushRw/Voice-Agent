FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ backend/
COPY knowledge_base/ knowledge_base/
ARG DOWNLOAD_MODELS=false
RUN if [ "$DOWNLOAD_MODELS" = "true" ]; then python -m backend.voice.agent download-files; fi
COPY --from=frontend /build/dist frontend/dist/
CMD ["uvicorn","backend.main:app","--host","0.0.0.0","--port","8000"]
