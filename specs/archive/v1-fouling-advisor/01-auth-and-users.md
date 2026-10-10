# 01. 인증 및 사용자 관리

관련 요구사항: FR-U-01, FR-A-01, FR-A-02, TR-06

---

## 1. 목적
사내 담당자만 접근 가능한 폐쇄형 시스템을 구성한다. 성명·사번·비밀번호로 로그인하며, 일반 사용자와 관리자의 권한을 분리한다.

## 2. 사용자 모델

Django `AbstractUser`를 상속해 확장한다.

```
User(AbstractUser)
  - employee_no   : 사번 (로그인 식별자, USERNAME_FIELD, unique, 최대 20자)
  - full_name     : 성명 (최대 50자, 필수)
  - role          : 'USER' | 'ADMIN'  (기본 'USER')
  - department    : 부서 (선택, 최대 50자)
  - phone         : 연락처 (선택)
  - is_active     : 사용 여부 (비활성 시 로그인 불가)
  - must_change_password : bool (기본 False)
  - last_login_at : 최근 로그인 일시
  - created_at / updated_at
```

- `AbstractUser`의 `first_name`, `last_name`, `email`은 사용하지 않는다(`email`은 선택 입력 허용).
- **`username` 필드를 제거하고 `employee_no`를 `USERNAME_FIELD`로 사용한다.**
  (`AbstractUser`를 상속하되 `username = None`으로 두고 `employee_no`를 별도 정의, `REQUIRED_FIELDS = ['full_name']`)
  > **정정 근거(2026-09-20):** 기존 문서는 모델 정의에 `username`(사번 저장)을 두면서 바로 아래에서 "`username` 필드를 제거한다"는
  > 구현 결정을 내려 자기모순이었다. 구현 결정문을 정본으로 채택하고 모델 정의에서 `username`을 삭제했다.
  > 이 결정은 **첫 마이그레이션 이전에 확정**되어야 한다(`14-data-model.md` §7).
- 관리자 여부는 `role == 'ADMIN'` 으로 판단한다. Django 기본 `is_staff`/`is_superuser`는 Django Admin 접근용으로만 사용하며, 앱 권한 판정에 쓰지 않는다.

## 3. 로그인

### 3.1 입력
| 필드 | 필수 | 설명 |
|------|------|------|
| full_name | ✔ | 성명 |
| employee_no | ✔ | 사번 |
| password | ✔ | 비밀번호 |

### 3.2 인증 절차
1. `employee_no`로 사용자 조회. 없으면 실패.
2. `full_name`이 저장된 값과 정확히 일치하는지 확인(공백 제거 후 비교). 불일치 시 실패.
3. `is_active == False` 이면 실패(“비활성화된 계정입니다. 관리자에게 문의하세요.”).
4. 비밀번호 검증(Django 해셔).
5. 성공 시 세션/토큰 발급, `last_login_at` 갱신, 로그인 이력 기록.

- 실패 메시지는 원인을 구분하지 않고 **“성명, 사번 또는 비밀번호가 올바르지 않습니다.”** 로 통일한다(계정 존재 여부 노출 방지). 단 비활성 계정은 위 문구를 사용한다.
- 로그인 실패 5회 연속 시 5분간 해당 사번 로그인 차단(잠금 해제는 시간 경과 또는 관리자 수동 해제).

### 3.3 세션
- 인증 방식: **세션 쿠키(HttpOnly, SameSite=Lax) + CSRF 토큰** 을 기본으로 한다.
- 세션 만료: 8시간 무활동 시 자동 로그아웃.
- 프론트엔드는 앱 부팅 시 `GET /api/auth/me/` 로 세션 유효성을 확인한다.

### 3.4 접근 제어
- 로그인 페이지(`/login`)를 제외한 **모든 SPA 라우트**는 인증 가드로 보호한다.
- 모든 API는 `IsAuthenticated`가 기본 권한이며, 관리자 전용 API는 `IsAdminRole`을 추가한다.
- 비인증 API 접근 → `401`, 권한 부족 → `403`.

## 4. 기본 관리자 계정 자동 생성 (FR-A-01)

- 애플리케이션 시작 시(예: `AppConfig.ready()` 또는 마이그레이션 후 실행되는 `seed_defaults` 관리 명령) **관리자 역할(`role='ADMIN'`) 사용자가 하나도 없으면** 다음 계정을 생성한다.

| 항목 | 값 |
|------|-----|
| 성명 | 관리자 |
| 사번 | ADM01 |
| 비밀번호 | qwer |
| role | ADMIN |
| must_change_password | True |

- 이미 관리자 계정이 존재하면 **아무 것도 하지 않는다**(덮어쓰기 금지).
- `must_change_password=True` 인 사용자는 로그인 후 대시보드 상단에 비밀번호 변경 안내 배너를 표시한다(강제 리디렉션은 하지 않음).
- 생성 여부는 애플리케이션 로그에 남긴다(비밀번호는 로그에 남기지 않는다).

## 5. 사용자 관리 (관리자 전용, FR-A-02)

| 기능 | 설명 |
|------|------|
| 목록 | 성명·사번·부서·역할·사용여부·최근 로그인 표시, 검색(성명/사번), 역할·활성 필터 |
| 추가 | 성명, 사번, 부서, 역할, 초기 비밀번호 입력. 생성 시 `must_change_password=True` |
| 수정 | 성명, 부서, 연락처, 역할, 활성 여부 변경. 사번은 변경 불가 |
| 비밀번호 초기화 | 관리자가 새 비밀번호 지정 → `must_change_password=True` |
| 삭제 | 기본은 **비활성화(soft delete)**. 물리 삭제는 분석 이력이 없는 계정만 허용 |

### 제약
- 마지막 활성 관리자 계정은 삭제·비활성화·역할 변경이 불가하다.
- 자기 자신의 역할을 `USER`로 낮출 수 없다.
- 사번은 영문 대문자+숫자 2~20자, 중복 불가.

## 6. 비밀번호 정책
- 최소 4자(기본 관리자 계정 `qwer` 허용을 위한 완화). 권장 8자 이상.
- Django 기본 validator 중 `MinimumLengthValidator(4)`만 활성화하고 나머지는 비활성화한다.
- 본인 비밀번호 변경: 현재 비밀번호 확인 후 변경, 변경 시 `must_change_password=False`.

## 7. 감사 로그
`LoginHistory` 레코드를 남긴다: 사용자(실패 시 입력 사번 문자열), 일시, IP, User-Agent, 성공/실패, 실패 사유 코드.

## 8. 예외 처리
| 상황 | 응답 |
|------|------|
| 미인증 접근 | 401 `{"error":{"code":"NOT_AUTHENTICATED"}}` |
| 권한 부족 | 403 `{"error":{"code":"PERMISSION_DENIED"}}` |
| 사번 중복 | 400 `{"error":{"code":"DUPLICATE_EMPLOYEE_NO"}}` |
| 잠금 상태 | 429 `{"error":{"code":"LOGIN_LOCKED","details":{"retry_after_sec":300}}}` |

## 9. 수용 기준 (AC)
- [ ] AC-01-1: 계정이 없는 상태에서 앱을 처음 기동하면 `관리자/ADM01/qwer`로 로그인할 수 있다.
- [ ] AC-01-2: 이미 관리자 계정이 있는 상태로 재기동하면 새 계정이 생성되지 않는다.
- [ ] AC-01-3: 성명이 틀리면 사번·비밀번호가 맞아도 로그인에 실패한다.
- [ ] AC-01-4: 비로그인 상태로 `/dashboard` 직접 접근 시 `/login`으로 리디렉션된다.
- [ ] AC-01-5: 일반 사용자가 관리자 API를 호출하면 403을 받는다.
- [ ] AC-01-6: 마지막 관리자 계정을 비활성화하려 하면 거부된다.
