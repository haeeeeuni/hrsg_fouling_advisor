/**
 * Vitest 전역 설정.
 *
 * Node 26 부터 런타임이 자체 `localStorage` 전역을 갖는데, `--localstorage-file`
 * 없이 실행하면 값이 `undefined` 인 채로 jsdom 의 구현을 가린다.
 * (`ExperimentalWarning: localStorage is not available because --localstorage-file was not provided`)
 *
 * 호기 선택 보존(AC-16-3)처럼 localStorage 를 쓰는 동작을 검증해야 하므로,
 * 비어 있을 때만 최소 구현을 채워 넣는다. 정상 동작하는 런타임에서는 아무것도 하지 않는다.
 */
function createStorage() {
  let store = new Map()
  return {
    get length() {
      return store.size
    },
    key: (index) => [...store.keys()][index] ?? null,
    getItem: (key) => (store.has(String(key)) ? store.get(String(key)) : null),
    setItem: (key, value) => void store.set(String(key), String(value)),
    removeItem: (key) => void store.delete(String(key)),
    clear: () => void (store = new Map()),
  }
}

for (const name of ['localStorage', 'sessionStorage']) {
  if (globalThis[name]?.setItem) continue
  const storage = createStorage()
  Object.defineProperty(globalThis, name, { value: storage, configurable: true, writable: true })
  if (globalThis.window) {
    Object.defineProperty(globalThis.window, name, {
      value: storage,
      configurable: true,
      writable: true,
    })
  }
}
