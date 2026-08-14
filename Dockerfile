# Imagem base enxuta com Python 3.12 (mesma versão usada no desenvolvimento).
FROM python:3.12-slim

# Evita gerar .pyc e faz os logs aparecerem na hora (bom para Cloud Run/servidor).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Instala as dependências primeiro (aproveita o cache: só reinstala se req.txt mudar).
COPY req.txt .
RUN pip install --no-cache-dir -r req.txt

# Copia o restante da aplicação.
COPY . .

# Porta que o servidor escuta. O Cloud Run injeta a variável PORT automaticamente.
EXPOSE 8080

# "Fogão industrial": gunicorn servindo o app Flask (objeto `app` dentro de app.py).
# 2 processos + 4 threads dão folga de sobra para um painel de leitura.
CMD exec gunicorn --bind :$PORT --workers 2 --threads 4 --timeout 120 app:app
