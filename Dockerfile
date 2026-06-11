# Gunakan base image Python resmi yang stabil
FROM python:3.11-slim

# Install Google Chrome asli dan dependencies pendukungnya
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    unzip \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -ch 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory di dalam container server
WORKDIR /app

# Copy daftar requirements dan install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh kode bot kita
COPY . .

# Jalankan bot utama
CMD ["python", "main.py"]
