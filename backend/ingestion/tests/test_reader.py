"""CSV 인코딩·구분자 감지 (specs/03 §3). DB 불필요."""

import pytest

from ingestion.services import reader

HEADER_KR = ["시각", "GT출력(MW)", "스택온도(℃)"]


def write(tmp_path, name, text, encoding):
    path = tmp_path / name
    path.write_text(text, encoding=encoding)
    return path


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp949"])
def test_ac_03_4_korean_headers_in_each_supported_encoding(tmp_path, encoding):
    """AC-03-4: CP949 인코딩 한글 헤더 파일이 정상 처리된다."""
    path = write(tmp_path, "s.csv", "시각,GT출력(MW)\n2024-01-01 00:00:00,150\n", encoding)

    detected = reader.detect_encoding(path)
    header = reader.read_header(path, detected, ",")

    assert header == ["시각", "GT출력(MW)"]


def test_unsupported_encoding_raises(tmp_path):
    path = tmp_path / "bad.csv"
    # UTF-8 로도 CP949 로도 해석되지 않는 바이트열
    path.write_bytes(b"\xff\xfe\x00\x81\x82hello\xed\xa0\x80")

    with pytest.raises(reader.UnsupportedEncoding):
        reader.detect_encoding(path)


@pytest.mark.parametrize(("delimiter", "line"), [(",", "a,b,c"), (";", "a;b;c"), ("\t", "a\tb\tc")])
def test_delimiter_is_detected(tmp_path, delimiter, line):
    path = write(tmp_path, "s.csv", f"{line}\n1{delimiter}2{delimiter}3\n", "utf-8")

    assert reader.detect_delimiter(path, "utf-8") == delimiter


def test_single_column_file_defaults_to_comma(tmp_path):
    path = write(tmp_path, "s.csv", "onlycol\n1\n", "utf-8")

    assert reader.detect_delimiter(path, "utf-8") == ","


def test_header_whitespace_is_trimmed(tmp_path):
    path = write(tmp_path, "s.csv", "  시각 , GT출력  \n1,2\n", "utf-8")

    assert reader.read_header(path, "utf-8", ",") == ["시각", "GT출력"]


def test_duplicate_headers_are_found():
    assert reader.find_duplicate_headers(["a", "b", "a", "c", "b"]) == ["a", "b"]


def test_no_duplicate_headers():
    assert reader.find_duplicate_headers(["a", "b", "c"]) == []


def test_chunks_cover_all_rows(tmp_path):
    rows = "\n".join(f"2024-01-01 00:{i:02d}:00,{i}" for i in range(50))
    path = write(tmp_path, "s.csv", f"시각,값\n{rows}\n", "utf-8")

    chunks = list(reader.iter_chunks(path, "utf-8", ",", chunk_size=20))

    assert len(chunks) == 3
    assert sum(len(c) for c in chunks) == 50


def test_checksum_is_stable_and_content_sensitive(tmp_path):
    a = write(tmp_path, "a.csv", "x,y\n1,2\n", "utf-8")
    b = write(tmp_path, "b.csv", "x,y\n1,2\n", "utf-8")
    c = write(tmp_path, "c.csv", "x,y\n1,3\n", "utf-8")

    assert reader.file_checksum(a) == reader.file_checksum(b)
    assert reader.file_checksum(a) != reader.file_checksum(c)


@pytest.mark.parametrize("cell", ["=1+1", "+CMD", "-2", "@SUM"])
def test_csv_injection_is_neutralized(cell):
    """AC-18-5 / specs/18 §2 — 수식 인젝션 방지."""
    assert reader.sanitize_for_spreadsheet(cell).startswith("'")


def test_ordinary_cells_are_untouched():
    assert reader.sanitize_for_spreadsheet("150.5") == "150.5"
    assert reader.sanitize_for_spreadsheet("정상") == "정상"
