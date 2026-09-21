# HRSG Fouling Advisor — 백엔드 (Django + Gunicorn / Celery)
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# psycopg(바이너리) 와 WeasyPrint/ReportLab 이 쓰는 런타임 라이브러리.
# 빌드 도구는 남기지 않는다(이미지 크기·공격면).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성만 먼저 복사해 레이어 캐시를 살린다.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# 한글 리포트용 동봉 폰트가 이미지에 들어갔는지 확인한다.
# 빠지면 PDF 의 한글이 전부 네모로 나가는데 런타임에야 발견된다.
RUN test -f reports/fonts/NanumGothic.ttf || (echo "나눔고딕 폰트 누락" && exit 1)

# root 로 돌리지 않는다.
RUN useradd --create-home --uid 10001 hrsg \
    && mkdir -p /app/var /app/staticfiles \
    && chown -R hrsg:hrsg /app
USER hrsg

EXPOSE 8000

CMD ["gunicorn", "-c", "gunicorn.conf.py", "config.wsgi:application"]
