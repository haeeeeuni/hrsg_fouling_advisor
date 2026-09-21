"""Gunicorn 설정 (specs/18 §7).

동시 사용자 20명 규모다(PROJECT.md §1.6). 오래 걸리는 작업은 전부 Celery 워커가
맡으므로(업로드 적재·분석·재학습·리포트) 웹 워커는 짧은 요청만 처리한다.
"""

import multiprocessing
import os

bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")

# (2 × CPU) + 1 이 관례지만 컨테이너에서는 상한을 둔다.
# 워커마다 Django·pandas·sklearn 를 적재해 메모리를 꽤 쓴다.
workers = int(os.environ.get("GUNICORN_WORKERS", min(multiprocessing.cpu_count() * 2 + 1, 9)))
worker_class = "sync"
threads = int(os.environ.get("GUNICORN_THREADS", 2))

# 분석은 Celery 가 맡지만 리포트 다운로드처럼 큰 응답이 있다.
# Nginx 의 proxy_read_timeout 보다 짧게 둔다(먼저 끊겨야 502 대신 504 가 잡힌다).
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 120))
graceful_timeout = 30
keepalive = 5

# 장시간 구동 시 누적되는 메모리를 주기적으로 정리한다.
max_requests = 1000
max_requests_jitter = 100

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
# 비밀번호·사번이 쿼리스트링에 실리지 않도록 POST 본문은 애초에 기록하지 않는다.
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(M)sms'

# 요청 헤더 크기 제한 — 비정상적으로 큰 헤더 차단
limit_request_line = 8190
limit_request_fields = 100

preload_app = True
