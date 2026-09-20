# 00. 요구사항 인덱스 및 추적 매트릭스

## 1. 문서 규약

- 요구사항 ID 체계
  - `FR-U-xx` : 기능 요구사항 – 사용자
  - `FR-A-xx` : 기능 요구사항 – 관리자
  - `FR-D-xx` : 기능 요구사항 – 데이터
  - `TR-xx`   : 기술 요구사항
  - `NFR-xx`  : 비기능 요구사항
- 우선순위: **P0**(필수), **P1**(중요), **P2**(옵션)
- 각 명세 문서는 다음 구조를 따른다: 목적 / 범위 / 상세 규칙 / 입출력 / 예외 처리 / 수용 기준(AC)

---

## 2. 사용자 기능 요구사항

| ID | 요구사항 | 우선순위 | 명세 문서 |
|----|----------|----------|-----------|
| FR-U-01 | 성명·사번·비밀번호 기반 로그인, 로그인 후에만 모든 화면 접근 | P0 | `01-auth-and-users.md` |
| FR-U-02 | 호기 선택 후 운전 데이터 CSV 업로드 | P0 | `03-data-ingestion.md` |
| FR-U-03 | 업로드 시 필수 컬럼 누락·형식 오류 검증 | P0 | `03-data-ingestion.md` |
| FR-U-04 | 결측치·이상치 자동 정제 | P0 | `04-preprocessing.md` |
| FR-U-05 | 분석 기간 선택 및 제외 구간(기동/정지/부하급변/덕트버너) 자동 배제 | P0 | `04-preprocessing.md` |
| FR-U-06 | 부하대/계절별 운전 구간 군집화 | P0 | `05-clustering.md` |
| FR-U-07 | 운전 조건별 기대 차압·기대 스택온도 예측 | P0 | `06-expected-value-model.md` |
| FR-U-08 | 예측 정확도(MAE, R²) 표시 | P0 | `06-expected-value-model.md` |
| FR-U-09 | 실측-기대 편차를 오염도 지수(0~100)로 환산 | P0 | `07-fouling-index.md` |
| FR-U-10 | 오염도 등급 표시(정상<30, 주의 30~60, 경고≥60) | P0 | `07-fouling-index.md` |
| FR-U-11 | 오염도 지수 추세 예측 및 임계치 도달 예상일 제시 | P0 | `08-trend-and-dday.md` |
| FR-U-12 | 세정 시 예상 회수 편익 산출, 분석별 임시 입력값 변경 | P0 | `09-benefit-model.md` |
| FR-U-13 | 대시보드 시각화(현재 지수·등급·D-day·예상 편익·시계열·세정 이벤트) | P0 | `11-dashboard.md` |
| FR-U-14 | 정비 이력 파일(CSV/엑셀) 업로드 및 오염 관련 이력 자동 추출 | P1 | `10-maintenance-history.md` |
| FR-U-15 | 세정 전후 비교 리포트(같은 운전 구간끼리 비교) | P1 | `12-reports.md` |
| FR-U-16 | 분석 결과 PDF·엑셀 다운로드(한글 깨짐 없음) | P0 | `12-reports.md` |
| FR-U-17 | 새 기간 데이터 추가 시 저장된 설정으로 자동 재계산 | P2 | `19-optional-features.md` |
| FR-U-18 | 과거 세정 시점 기준 예측 정확도 검증(백테스트) | P2 | `19-optional-features.md` |

---

## 3. 관리자 기능 요구사항

| ID | 요구사항 | 우선순위 | 명세 문서 |
|----|----------|----------|-----------|
| FR-A-01 | 앱 시작 시 기본 관리자 계정(관리자/ADM01/qwer) 자동 생성 | P0 | `01-auth-and-users.md` |
| FR-A-02 | 사용자 추가·삭제·수정 | P0 | `01-auth-and-users.md`, `13-admin.md` |
| FR-A-03 | 호기 추가·삭제·수정 및 호기별 컬럼 매핑 지정 | P0 | `02-unit-and-column-mapping.md` |
| FR-A-04 | 임계치(기본 60)·등급 경계·차압/스택온도 가중치 설정 | P0 | `13-admin.md`, `07-fouling-index.md` |
| FR-A-05 | 편익 계산 기본값 설정(전력단가, 연료비, 세정비용, 정지일수, 출력손실계수) | P0 | `09-benefit-model.md`, `13-admin.md` |
| FR-A-06 | 세정 이력 등록·삭제·수정(일자, 방법, 비용) | P0 | `10-maintenance-history.md` |
| FR-A-07 | 오염 관련 키워드 사전 추가·삭제·수정 | P1 | `10-maintenance-history.md` |
| FR-A-08 | 예측 모델 재학습 및 청정 기준 기간 지정 | P0 | `06-expected-value-model.md`, `13-admin.md` |
| FR-A-09 | 분석 실행 이력 조회(실행자, 일시, 데이터 기간, 적용 설정값) | P0 | `13-admin.md` |
| FR-A-10 | 호기 간 오염도 비교 및 세정 우선순위 조회 | P2 | `19-optional-features.md` |

---

## 4. 데이터 요구사항

| ID | 요구사항 | 우선순위 | 명세 문서 |
|----|----------|----------|-----------|
| FR-D-01 | 운전 데이터 필수 컬럼 정의 및 강제 | P0 | `03-data-ingestion.md` |
| FR-D-02 | 운전 데이터 선택 컬럼 정의 | P0 | `03-data-ingestion.md` |
| FR-D-03 | 호기별 컬럼 매핑으로 표준 항목 연결 | P0 | `02-unit-and-column-mapping.md` |
| FR-D-04 | 운전 데이터 호기별 누적 저장 | P0 | `03-data-ingestion.md`, `14-data-model.md` |
| FR-D-05 | 설정값은 코드 고정 금지, DB 저장 + 관리자 화면 변경 | P0 | `13-admin.md`, `14-data-model.md` |
| FR-D-06 | 분석 결과에 실행자·일시·데이터 기간·설정값·모델 버전 기록 | P0 | `14-data-model.md` |
| FR-D-07 | 가상 샘플 데이터 생성 스크립트(오염-회복 2~3회 반복) | P0 | `17-sample-data.md` |

---

## 5. 기술 요구사항

| ID | 요구사항 | 명세 문서 |
|----|----------|-----------|
| TR-01 | Vue.js 3 + Vite + Bootstrap 5 기반 SPA | `16-frontend.md` |
| TR-02 | Django + DRF, REST/JSON API | `15-api.md` |
| TR-03 | Django ORM + PostgreSQL | `14-data-model.md` |
| TR-04 | pandas, scikit-learn 기반 분석 | `06-expected-value-model.md` |
| TR-05 | openpyxl 엑셀, 한글 폰트 포함 PDF | `12-reports.md` |
| TR-06 | User/Admin은 Django AbstractUser 상속 확장 | `01-auth-and-users.md`, `14-data-model.md` |

---

## 6. 명세 간 의존 관계

```
02 컬럼매핑 ──> 03 업로드 ──> 04 정제 ──> 05 군집화 ──> 06 기대값모델
                                                          │
                                                          v
                                        07 오염도지수 ──> 08 추세/D-day
                                                │              │
                                                v              v
                          10 정비/세정이력 ──> 09 편익 ──> 11 대시보드 ──> 12 리포트
                                                                        │
01 인증  ─ 전 화면 전제                                                  v
13 관리자 ─ 설정값 공급                                            19 옵션기능
14 데이터모델 / 15 API / 16 프론트 / 17 샘플데이터 / 18 비기능 ─ 전 구간 공통
```
