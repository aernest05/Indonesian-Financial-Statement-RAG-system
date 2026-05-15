# Use official Python image
FROM python:3.12-slim

# Set working directory inside container
WORKDIR /app

# Copy and install dependencies first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./backend/
COPY financial_statements_db/ /app/financial_statements_db/

# Expose port
EXPOSE 8080

# Run FastAPI
CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8080"]