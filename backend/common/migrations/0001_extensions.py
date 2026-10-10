"""PostgreSQL 확장 (specs/03 §6, specs/13 §6).

vector  — 청크 임베딩 저장·검색(pgvector)
pg_trgm — 키워드(삼중자) 검색. 한국어 형태소 분석기 없이 제품명·모델명 같은 정확 단어를 잡는다.

확장 생성에는 DB 슈퍼유저 권한(또는 신뢰 확장 설정)이 필요하다. 관리형 DB 에서 실패하면
DB 콘솔에서 미리 CREATE EXTENSION 을 실행해 둔다 — IF NOT EXISTS 라 이후 마이그레이션은 통과한다.
"""

from django.contrib.postgres.operations import CreateExtension, TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies: list = []

    operations = [
        CreateExtension("vector"),
        TrigramExtension(),
    ]
