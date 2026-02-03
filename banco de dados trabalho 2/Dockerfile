# Usa uma imagem Python leve e oficial
FROM python:3.9-slim

# Define pasta de trabalho dentro do container
WORKDIR /app

# Instala bibliotecas do sistema necessárias para o MySQL
RUN apt-get update && apt-get install -y default-libmysqlclient-dev build-essential && rm -rf /var/lib/apt/lists/*

# Instala a biblioteca Python do MySQL
RUN pip install mysql-connector-python

# Copia os arquivos da pasta atual para dentro do container
COPY . .

# Comando para rodar o app (se cair, o Docker reinicia)
CMD ["python", "-u", "middleware.py"]