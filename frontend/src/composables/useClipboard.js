/**
 * 클립보드 복사 (specs/07 CHK-5).
 * 클립보드 API 는 보안 컨텍스트(HTTPS·localhost)에서만 동작하고, 권한이 막히면 실패한다.
 * 실패하면 false 를 돌려주고, 화면은 텍스트 상자를 펼쳐 손으로 복사하게 한다.
 */
export async function copyText(text) {
  try {
    if (!window.isSecureContext || !navigator.clipboard?.writeText) return false
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}
