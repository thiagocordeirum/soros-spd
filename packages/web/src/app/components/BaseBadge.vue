<script setup lang="ts">
import type { TomBadge } from '../../domains/types/tipos';

withDefaults(
  defineProps<{
    tom?: TomBadge
  }>(),
  {tom: 'cinza'}
)

const classes: Record<TomBadge, string> = {
  verde: 'bg-emerald-50 text-emerald-800',
  amarelo: 'bg-amber-50 text-amber-800',
  vermelho: 'bg-red-50 text-red-800',
  cinza: 'bg-slate-100 text-slate-700',
}
</script>

<template>
  <span 
    class="inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-xs font-medium whitespace-nowrap"
    :class="classes[tom]"
  >
    <span aria-hidden="true" class="size-1.5 rounded-full bg-current"></span>
    <slot/>
  </span>
</template>