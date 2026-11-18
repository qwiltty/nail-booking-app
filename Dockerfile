FROM python:3.11-slim

# Создаем пользователя user (требование Hugging Face Spaces)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Установка зависимостей
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Копирование исходного кода проекта
COPY --chown=user:user . .

# Создаем папку для загрузок фото клиентов
RUN mkdir -p uploads

# Hugging Face слушает порт 7860
EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
