FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY tum_project_study_chairs.json .
COPY compliance /app/compliance
COPY backend /app/backend
RUN pip install --no-cache-dir .
ENV PYTHONPATH=/app/backend
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
