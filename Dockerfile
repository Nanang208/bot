# Gunakan base image Python yang sudah lengkap dengan tools dasar
FROM python:3.11-bullseye

# Install Chromium Browser resmi langsung dari repositori Debian (Anti-Gagal)
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set folder kerja di dalam server
WORKDIR /app

# Copy requirements dan install library Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua file project kamu
COPY . .

# Jalankan bot utama
CMD ["python", "main.py"]
