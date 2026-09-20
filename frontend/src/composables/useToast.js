/** 아주 작은 토스트 큐. 컴포넌트 밖(라우터 가드 등)에서도 쓸 수 있도록 모듈 스코프에 둔다. */
import { ref } from 'vue'

const toasts = ref([])
let seq = 0

export function useToast() {
  function push(message, variant = 'info', timeout = 4000) {
    const id = ++seq
    toasts.value.push({ id, message, variant })
    if (timeout > 0) {
      setTimeout(() => dismiss(id), timeout)
    }
    return id
  }

  function dismiss(id) {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  return { toasts, push, dismiss }
}
