import { createRouter, createWebHashHistory } from 'vue-router'

import { useAutenticacao } from '../hooks/useAuthentication'

export const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),

  scrollBehavior() {
    return { top: 0 }
  },

  routes: [
    {
      path: '/entrada',
      name: 'entrada',
      component: () => import('../pages/EntradaPagina.vue'),
      meta: {
        titulo: 'Entrar',
      },
    },
    {
      path: '/',
      component: () => import('../layout/GestaoLayout.vue'),
      meta: {
        exigeAutenticacao: true,
      },
      children: [
        {
          path: '',
          redirect: '/painel',
        },
        {
          path: 'painel',
          name: 'painel',
          component: () => import('../pages/PainelPagina.vue'),
          meta: {
            titulo: 'Visão geral',
          },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/entrada',
    },
  ],
})

router.beforeEach(async (to) => {
  if (!to.meta.exigeAutenticacao) {
    return true
  }

  const { atualizarSessao } = useAutenticacao()

  try {
    const sessao = await atualizarSessao()

    if (!sessao.usuario) {
      return {
        name: 'entrada',
        query: {
          motivo: 'sessao',
        },
      }
    }

    return true
  } catch {
    return {
      name: 'entrada',
      query: {
        motivo: 'conexao',
      },
    }
  }
})

router.afterEach((to) => {
  document.title = `${String(to.meta.titulo ?? 'Gestão')} | AMpolo`
})