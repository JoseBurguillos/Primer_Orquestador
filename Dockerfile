# 1. Imagen base: Python 3.13 en versión ligera
FROM python:3.13-slim

# 2. Carpeta de trabajo dentro del contenedor
WORKDIR /app

# 3. Primero solo las dependencias (Docker las guarda en caché y no las reinstala si no cambian)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Después, el código del orquestador y de la API
COPY app.py api.py ./

# 5. El puerto en el que escucha la API
EXPOSE 8000

# 6. Arrancar la API escuchando en todas las direcciones (0.0.0.0), no solo dentro del contenedor
CMD ["uvicorn", "api:api", "--host", "0.0.0.0", "--port", "8000"]