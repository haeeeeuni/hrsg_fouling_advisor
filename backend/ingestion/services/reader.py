"""CSV 읽기 — 인코딩·구분자 자동 감지, 청크 스트리밍 (specs/03 §3, §7).

Django 모델을 import 하지 않는 순수 함수 모듈이다(AGENTS.md §3).
"""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterator
from pathlib import Path

import pandas as pd

# specs/03 §3 — UTF-8, UTF-8-BOM, CP949(EUC-KR) 자동 감지
CANDIDATE_ENCODINGS: tuple[str, ...] = ("utf-8-sig", "utf-8", "cp949")
CANDIDATE_DELIMITERS: tuple[str, ...] = (",", ";", "\t")

DEFAULT_CHUNK_SIZE = 50_000


class UnsupportedEncoding(Exception):
    """어떤 후보 인코딩으로도 해석되지 않음."""


def detect_encoding(path: str | Path, sample_bytes: int = 256_000) -> str:
    raw = Path(path).open("rb").read(sample_bytes)
    for encoding in CANDIDATE_ENCODINGS:
        try:
            raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        else:
            return encoding
    raise UnsupportedEncoding("지원하지 않는 파일 인코딩입니다. UTF-8 또는 CP949로 저장해 주세요.")


def detect_delimiter(path: str | Path, encoding: str) -> str:
    with Path(path).open("r", encoding=encoding, newline="") as fp:
        header = fp.readline()
    if not header:
        return ","

    try:
        return csv.Sniffer().sniff(header, delimiters="".join(CANDIDATE_DELIMITERS)).delimiter
    except csv.Error:
        # Sniffer 가 실패하면 출현 횟수가 가장 많은 후보를 쓴다.
        counts = {d: header.count(d) for d in CANDIDATE_DELIMITERS}
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ","


def read_header(path: str | Path, encoding: str, delimiter: str) -> list[str]:
    """헤더를 읽고 앞뒤 공백을 제거한다 (specs/03 §3)."""
    with Path(path).open("r", encoding=encoding, newline="") as fp:
        reader = csv.reader(fp, delimiter=delimiter)
        try:
            row = next(reader)
        except StopIteration:
            return []
    return [cell.strip() for cell in row]


def find_duplicate_headers(header: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for name in header:
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)
    return duplicates


def iter_chunks(
    path: str | Path,
    encoding: str,
    delimiter: str,
    usecols: list[str] | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Iterator[pd.DataFrame]:
    """청크 단위로 읽어 메모리 사용량을 2GB 이하로 유지한다(specs/03 §7).

    모든 컬럼을 문자열로 읽는다. 숫자 변환은 validator 가 오류를 집계하며 수행한다.
    """
    reader = pd.read_csv(
        path,
        encoding=encoding,
        sep=delimiter,
        usecols=usecols,
        dtype=str,
        keep_default_na=False,
        na_values=[""],
        chunksize=chunk_size,
        skipinitialspace=True,
    )
    for chunk in reader:
        chunk.columns = [str(c).strip() for c in chunk.columns]
        yield chunk


def file_checksum(path: str | Path, block_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fp:
        while block := fp.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def sanitize_for_spreadsheet(value: str) -> str:
    """CSV 수식 인젝션 방지 (AGENTS.md §7, specs/18 §2).

    엑셀·CSV로 내보낼 때 `=`, `+`, `-`, `@` 로 시작하는 셀 앞에 작은따옴표를 붙인다.
    """
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@"}:
        return f"'{value}"
    return value
