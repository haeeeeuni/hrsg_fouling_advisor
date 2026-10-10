<script setup>
/** 첫 화면 — 앱 소개와 사용 방법 (specs/11 §2, UI-7). 로그인 없이 볼 수 있다. */
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { FEATURES } from '@/utils/constants'

const auth = useAuthStore()
const ui = useUiStore()

const STEPS = [
  { title: '회원가입', text: 'ID·비밀번호·성명·소속을 입력해 가입을 신청합니다.' },
  { title: '관리자 승인', text: '외부인 접근을 막기 위해 관리자가 승인한 계정만 로그인할 수 있습니다.' },
  { title: '로그인 후 사용', text: '화면 오른쪽 위에서 로그인하면 세 기능을 바로 쓸 수 있습니다.' },
]

const TIPS = [
  { feature: '질의응답', text: '가스터빈 모델과 운전값을 함께 적으면 계산 결과 카드까지 받아 볼 수 있습니다.' },
  { feature: '계산기', text: '값을 바꾸면 결과가 바로 다시 계산됩니다. 상태는 색과 문구로 함께 표시됩니다.' },
  { feature: '체크리스트', text: '요청 건마다 받은 항목을 체크하고, 남은 항목을 이메일 본문으로 복사해 보내세요.' },
]

const NOTICES = [
  '모든 수치는 앱의 계산기로만 산출합니다. AI 가 임의로 숫자를 만들지 않습니다.',
  '일부 참조값은 현재 임시값입니다. 임시값을 쓴 결과에는 "참고용" 안내가 함께 표시됩니다.',
  '질문에 고객사·발전소 이름이나 개인 정보를 입력하지 마세요.',
]
</script>

<template>
  <div class="ui-container">
    <section class="ui-hero">
      <p class="ui-eyebrow">HRSG 세정·성능 레퍼런스</p>
      <h1 class="ui-hero-title">HRSG 레퍼런스 앱</h1>
      <p class="ui-hero-lead">
        HRSG(배열회수보일러) 세정과 성능에 관한 질문에 답하고, 손실과 세정 효과를 계산하고,
        정확한 평가에 필요한 플랜트 데이터를 빠짐없이 받도록 돕습니다.
      </p>
      <div class="d-flex flex-wrap gap-2">
        <RouterLink v-if="auth.isAuthenticated" class="btn btn-primary" :to="{ name: 'home' }">
          홈으로 <i class="bi bi-arrow-right ms-1" aria-hidden="true"></i>
        </RouterLink>
        <template v-else>
          <button type="button" class="btn btn-primary" @click.stop="ui.openLogin()">로그인</button>
          <RouterLink class="btn btn-outline-secondary" :to="{ name: 'signup' }">회원가입</RouterLink>
        </template>
      </div>
    </section>

    <section class="mb-5" aria-labelledby="featuresTitle">
      <h2 id="featuresTitle" class="ui-section-title">주요 기능</h2>
      <div class="row g-3">
        <div v-for="feature in FEATURES" :key="feature.key" class="col-12 col-md-4">
          <article class="card h-100">
            <div class="card-body">
              <i class="bi ui-feature-icon" :class="feature.icon" aria-hidden="true"></i>
              <h3 class="h5 mt-3">{{ feature.title }}</h3>
              <p class="mb-2">{{ feature.summary }}</p>
              <p class="text-secondary small mb-0">{{ feature.detail }}</p>
            </div>
          </article>
        </div>
      </div>
    </section>

    <section class="mb-5" aria-labelledby="stepsTitle">
      <h2 id="stepsTitle" class="ui-section-title">사용 방법</h2>
      <ol class="row g-3 list-unstyled mb-0">
        <li v-for="(step, index) in STEPS" :key="step.title" class="col-12 col-md-4">
          <div class="d-flex gap-3">
            <span class="ui-step ui-step--ready" aria-hidden="true">{{ index + 1 }}</span>
            <div>
              <p class="fw-semibold mb-1">{{ step.title }}</p>
              <p class="text-secondary small mb-0">{{ step.text }}</p>
            </div>
          </div>
        </li>
      </ol>
    </section>

    <section class="row g-3 mb-4">
      <div class="col-12 col-lg-6">
        <div class="card h-100">
          <div class="card-body">
            <h2 class="h6">기능별 사용 팁</h2>
            <dl class="mb-0">
              <template v-for="tip in TIPS" :key="tip.feature">
                <dt class="small">{{ tip.feature }}</dt>
                <dd class="small text-secondary">{{ tip.text }}</dd>
              </template>
            </dl>
          </div>
        </div>
      </div>
      <div class="col-12 col-lg-6">
        <div class="card h-100">
          <div class="card-body">
            <h2 class="h6">이용 안내</h2>
            <ul class="small text-secondary ps-3 mb-0">
              <li v-for="notice in NOTICES" :key="notice" class="mb-1">{{ notice }}</li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
