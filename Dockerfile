FROM python:3.10-slim

WORKDIR /app

# تثبيت التبعيات الأساسية للنظام و ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# تثبيت مكتبات بايثون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# تشغيل البوت
CMD ["python", "bot.py"]
