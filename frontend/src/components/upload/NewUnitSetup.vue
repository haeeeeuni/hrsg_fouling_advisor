<script setup>
import { computed } from 'vue'

import { useAuthStore } from '@/stores/auth'

/**
 * 새 호기 데이터를 넣으려면 호기 등록 → 컬럼 매핑이 먼저다 (specs/03 §2).
 *
 * 업로드 화면의 호기 목록은 "활성 + 매핑 완료" 만 보여주므로, 방금 등록한 호기는
 * 목록에 없고 화면이 막다른 길이 된다. 여기서 남은 단계와 이동 경로를 보여준다.
 *
 * 호기 등록·매핑은 관리자 전용(IsAdminRole)이라 일반 사용자에게는 링크 대신
 * 요청 안내를 보여준다.
 */
const props = defineProps({
  units: { type: Array, default: () => [] },
})
const emit = defineEmits(['select-ready'])

const auth = useAuthStore()

const active = computed(() => props.units.filter((u) => u.is_active))
const pending = computed(() => active.value.filter((u) => !u.is_mapping_complete))
const ready = computed(() => active.value.filter((u) => u.is_mapping_complete))
</script>

<template>
  <div class="card mb-3">
    <div class="card-body">
      <h2 class="h6 mb-1">새 호기 데이터를 올리는 순서</h2>
      <p class="small text-secondary mb-3">
        분석 코드는 원본 컬럼명을 알지 못합니다. 호기를 등록하고 컬럼 매핑을 마쳐야
        업로드가 열립니다.
      </p>

      <ol class="list-unstyled mb-0">
        <!-- 1단계 : 호기 등록 -->
        <li class="d-flex gap-3 pb-3 border-bottom">
          <span class="badge text-bg-secondary rounded-circle flex-shrink-0 mt-1">1</span>
          <div class="flex-grow-1">
            <p class="fw-semibold mb-1">호기 등록</p>
            <p class="small text-secondary mb-2">
              호기 코드·정격 출력·샘플링 간격을 입력합니다. 정격 출력은 물리적 범위 검증의
              기준이라 실제 값과 맞춰야 합니다.
            </p>
            <RouterLink
              v-if="auth.isAdmin"
              class="btn btn-sm btn-outline-primary"
              :to="{ name: 'admin-units' }"
            >
              호기 관리로 이동
            </RouterLink>
            <p v-else class="small text-secondary mb-0">
              <i class="bi bi-info-circle me-1" aria-hidden="true"></i>
              관리자에게 호기 등록을 요청하세요.
            </p>
          </div>
        </li>

        <!-- 2단계 : 컬럼 매핑 -->
        <li class="d-flex gap-3 py-3 border-bottom">
          <span class="badge text-bg-secondary rounded-circle flex-shrink-0 mt-1">2</span>
          <div class="flex-grow-1">
            <p class="fw-semibold mb-1">컬럼 매핑</p>
            <p class="small text-secondary mb-2">
              원본 CSV 의 컬럼을 표준 항목으로 연결합니다. 필수 8개 항목이 모두 연결돼야
              업로드가 열립니다.
            </p>

            <div v-if="pending.length" class="alert alert-warning py-2 px-3 small mb-2">
              <p class="fw-semibold mb-2">매핑이 끝나지 않은 호기</p>
              <div v-for="unit in pending" :key="unit.id" class="mb-2">
                <p class="fw-semibold mb-1">{{ unit.code }} — {{ unit.name }}</p>
                <ul v-if="unit.mapping_problems?.length" class="mb-0 ps-3">
                  <li v-for="problem in unit.mapping_problems" :key="problem.code">
                    {{ problem.message }}
                    <code v-if="problem.fields?.length" class="ms-1">
                      {{ problem.fields.join(', ') }}
                    </code>
                  </li>
                </ul>
              </div>
            </div>
            <p v-else class="small text-secondary mb-2">
              매핑이 남은 호기가 없습니다.
            </p>

            <RouterLink
              v-if="auth.isAdmin"
              class="btn btn-sm btn-outline-primary"
              :to="{ name: 'admin-column-mapping' }"
            >
              컬럼 매핑으로 이동
            </RouterLink>
            <p v-else class="small text-secondary mb-0">
              <i class="bi bi-info-circle me-1" aria-hidden="true"></i>
              관리자에게 컬럼 매핑을 요청하세요.
            </p>
          </div>
        </li>

        <!-- 3단계 : 업로드 -->
        <li class="d-flex gap-3 pt-3">
          <span
            class="badge rounded-circle flex-shrink-0 mt-1"
            :class="ready.length ? 'text-bg-success' : 'text-bg-secondary'"
          >3</span>
          <div class="flex-grow-1">
            <p class="fw-semibold mb-1">운전 데이터 업로드</p>
            <template v-if="ready.length">
              <p class="small text-secondary mb-2">
                아래 호기는 준비가 끝났습니다. 선택하면 업로드로 넘어갑니다.
              </p>
              <div class="d-flex flex-wrap gap-2">
                <button
                  v-for="unit in ready"
                  :key="unit.id"
                  type="button"
                  class="btn btn-sm btn-primary"
                  @click="emit('select-ready', unit.id)"
                >
                  {{ unit.code }} — {{ unit.name }} 업로드
                </button>
              </div>
            </template>
            <p v-else class="small text-secondary mb-0">
              1·2단계를 마치면 여기에서 업로드할 수 있습니다.
            </p>
          </div>
        </li>
      </ol>
    </div>
  </div>
</template>
