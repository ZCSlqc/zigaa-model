<template>
  <div class="app-layout">
    <NavBar />
    <main class="app-main">
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts">
import NavBar from './NavBar.vue'
</script>

<style scoped lang="scss">
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-page);
}

.app-main {
  flex: 1;
  overflow: auto;
  padding: var(--spacing-lg);
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}
</style>
