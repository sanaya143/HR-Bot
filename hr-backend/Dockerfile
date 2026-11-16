FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# bake the Hugging Face models into the image so startup never depends on a download
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5')" \
 && python -c "from fastembed.rerank.cross_encoder import TextCrossEncoder; TextCrossEncoder(model_name='BAAI/bge-reranker-base')"
COPY . .
CMD exec uvicorn hr_assistant.api:create_app --factory --host 0.0.0.0 --port ${PORT:-8080}
