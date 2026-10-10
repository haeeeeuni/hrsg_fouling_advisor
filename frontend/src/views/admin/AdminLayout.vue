<script setup>
/**
 * 관리자 모드 셸 (specs/08 §2, specs/11 §4).
 * 데스크톱은 좌측 사이드바, 모바일(lg 미만)은 오프캔버스 메뉴. 메뉴 목록은 라우터의 ADMIN_MENU 가 정본이다.
 */
import Offcanvas from 'bootstrap/js/dist/offcanvas'
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ADMIN_MENU } from '@/router'

const route = useRoute()
const currentTitle = computed(() => route.meta?.title ?? '')
const menu = ref(null)

/*
 * 모바일 메뉴는 이동이 끝난 뒤 코드로 닫는다. 링크에 data-bs-dismiss 를 달면 Bootstrap 이
 * 링크의 기본 동작을 막아 RouterLink 이동이 취소된다 — 데스크톱에서도 메뉴가 먹통이 됐다.
 */
watch(
  () => route.fullPath,
  () => {
    if (menu.value) Offcanvas.getInstance(menu.value)?.hide()
  },
)
</script>

<template>
  <div class="ui-admin">
    <!-- 데스크톱: 고정 사이드바 / 모바일: 같은 메뉴를 오프캔버스로 -->
    <aside
      id="adminMenu"
      ref="menu"
      class="ui-sidebar offcanvas-lg offcanvas-start"
      tabindex="-1"
      aria-labelledby="adminMenuTitle"
    >
      <div class="offcanvas-header d-lg-none">
        <h2 id="adminMenuTitle" class="h6 mb-0 text-white">관리자 모드</h2>
        <button
          type="button"
          class="btn-close btn-close-white"
          data-bs-dismiss="offcanvas"
          data-bs-target="#adminMenu"
          aria-label="메뉴 닫기"
        ></button>
      </div>
      <nav class="offcanvas-body d-block" aria-label="관리자 메뉴">
        <p class="ui-menu-title d-none d-lg-block">관리자 모드</p>
        <ul class="list-unstyled m-0">
          <li v-for="item in ADMIN_MENU" :key="item.name">
            <RouterLink
              class="ui-menu-link"
              :to="{ name: item.name }"
              exact-active-class="active"
            >
              <i class="bi" :class="item.icon" aria-hidden="true"></i>
              <span>{{ item.title }}</span>
            </RouterLink>
          </li>
        </ul>
      </nav>
    </aside>

    <section class="ui-admin-content">
      <div class="d-flex align-items-center gap-2 mb-3">
        <button
          class="btn btn-sm ui-pill d-lg-none"
          type="button"
          data-bs-toggle="offcanvas"
          data-bs-target="#adminMenu"
          aria-controls="adminMenu"
        >
          <i class="bi bi-list me-1" aria-hidden="true"></i>관리 메뉴
        </button>
        <h1 class="h4 mb-0">{{ currentTitle }}</h1>
      </div>
      <RouterView />
    </section>
  </div>
</template>
