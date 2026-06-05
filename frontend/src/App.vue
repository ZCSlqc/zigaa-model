<template>
  <router-view v-slot="{ Component }">
    <keep-alive include="Project">
      <component :is="Component" />
    </keep-alive>
  </router-view>
</template>
