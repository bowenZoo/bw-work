FROM python:3.12-slim

WORKDIR /app

# System deps for pymupdf, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir "crewai[anthropic]" "crewai[google-genai]" litellm langchain-anthropic

COPY . .

# Data dir (will be volume-mounted)
RUN mkdir -p data/projects data/chroma

EXPOSE 18000

CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "18000"]
