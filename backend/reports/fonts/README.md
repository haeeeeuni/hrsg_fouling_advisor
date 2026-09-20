# 한글 폰트

`specs/12-reports.md` §3.1 — PDF 한글 깨짐 방지를 위해 오픈 라이선스 폰트를 저장소에 동봉한다.

| 파일 | 용도 | 라이선스 |
|------|------|----------|
| `NanumGothic-Regular.ttf` | 본문 | SIL Open Font License 1.1 (`OFL.txt`) |
| `NanumGothic-Bold.ttf` | 제목·강조 | 동일 |

출처: <https://github.com/google/fonts/tree/main/ofl/nanumgothic>

ReportLab 과 matplotlib 양쪽에 **명시적으로 등록**해야 한다(`reports/pdf/fonts.py`).
기본 Helvetica 를 쓰면 한글이 전부 깨진다.
