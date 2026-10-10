/** 서버가 준 파일(blob)을 내려받게 한다. 인증 쿠키가 필요해 a[href] 대신 axios 로 받는다. */
export function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
