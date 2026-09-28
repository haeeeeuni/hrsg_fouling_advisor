<script setup>
/**
 * 관리자 콘솔 셸.
 *
 * 화면 목록(specs/13 §3)은 좌측 사이드바의 '관리자 콘솔' 하위에 펼쳐진다
 * (`AppSidebar`). 여기에 가로 탭을 또 두면 같은 메뉴가 두 벌이 되고, 12개가
 * 줄바꿈되며 빽빽해진다. 현재 화면 이름은 상단 네비가 route.meta.title 로 띄운다.
 */
</script>

<template>
  <RouterView />
</template>
