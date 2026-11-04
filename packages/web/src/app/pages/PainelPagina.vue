<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

import BaseBadge from '../components/BaseBadge.vue'
import BasePanel from '../components/BasePanel.vue'

import { useAutenticacao } from '../hooks/useAuthentication'
import { usePainel } from '../hooks/usePainel'

const router = useRouter()
const { usuario } = useAutenticacao()

const {
  dadosDisponiveis,
  carregando,
  erro,
  statusErro,
  consultadoEm,
  busca,
  filtro,
  unidades,
  unidadesConhecidas,
  unidadesSemContato,
  unidadesFiltradas,
  totalAmpolas,
  ampolasEmTransito,
  vencimentos,
  alertas,
  remessasPendentes,
  usoDiario,
  maiorUso,
  totalUso,
  estoqueDisponivel,
  ocupacaoReservada,
  nomeUnidade,
  nomeSoro,
  formatarIdade,
  formatarData,
  limparFiltros,
  carregar,
} = usePainel()

async function atualizar() {
  await carregar()

  if (statusErro.value === 401) {
    await router.replace({
      name: 'entrada',
      query: { motivo: 'sessao' },
    })
  }
}

onMounted(() => {
  if (usuario.value?.tipo === 'gestor') {
    void atualizar()
  }
})
</script>

<template>
  <section v-if="usuario?.tipo !== 'gestor'" class="panel p-6">
    <h1 class="page-title">Painel estadual</h1>

    <p class="mt-4 text-sm leading-7 text-muted">
      Esta visão é destinada à gestão estadual.
    </p>
  </section>

  <div v-else class="space-y-6">
    <header class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 class="page-title">Visão geral da rede</h1>

        <p class="page-description">
          Estoques e movimentações conhecidos pela sua unidade.
        </p>
      </div>

      <button
        type="button"
        class="button-secondary disabled:opacity-60"
        :disabled="carregando"
        @click="atualizar"
      >
        {{ carregando ? 'Consultando…' : 'Atualizar dados' }}
      </button>
    </header>

    <section
      v-if="carregando || (!dadosDisponiveis && !erro)"
      role="status"
      aria-live="polite"
      class="panel p-8"
    >
      <p class="font-semibold">Consultando a rede</p>
      <p class="mt-2 text-sm text-muted">
        Aguarde enquanto os dados do nó são carregados.
      </p>
    </section>

    <section
      v-else-if="erro"
      class="rounded-xl border border-red-200 bg-red-50 p-6"
    >
      <h2 class="font-semibold text-red-900">
        Não foi possível carregar o painel
      </h2>

      <p role="alert" class="mt-3 text-sm leading-6 text-red-800">
        {{ erro }}
      </p>

      <button
        type="button"
        class="button-secondary mt-5"
        @click="atualizar"
      >
        Tentar novamente
      </button>
    </section>

    <template v-else-if="dadosDisponiveis">
      <section
        class="rounded-xl bg-forest p-6 text-white sm:p-8"
      >
        <h2 class="text-xl font-semibold tracking-tight">
          Dados consultados no nó da sua unidade
        </h2>

        <p class="mt-3 max-w-2xl text-sm leading-7 text-emerald-50/85">
          As informações das outras unidades podem estar atrasadas.
          Confira a idade dos dados antes de planejar uma movimentação.
        </p>

        <p v-if="consultadoEm" class="mt-4 text-xs text-emerald-100">
          Consulta realizada às
          {{
            consultadoEm.toLocaleTimeString('pt-BR', {
              hour: '2-digit',
              minute: '2-digit',
            })
          }}
        </p>
      </section>

      <section
        aria-label="Indicadores da rede"
        class="grid gap-6 sm:grid-cols-3"
      >
        <article class="border-t-2 border-river py-4">
          <h2 class="text-sm text-muted">Ampolas disponíveis conhecidas</h2>

          <p class="mt-3 text-4xl font-semibold tabular-nums">
            {{ totalAmpolas.toLocaleString('pt-BR') }}
          </p>

          <p class="mt-2 text-xs leading-6 text-muted">
            Em {{ unidadesConhecidas.length }} unidades com informação.
            Exclui lotes vencidos.
          </p>
        </article>

        <article class="border-t-2 border-river py-4">
          <h2 class="text-sm text-muted">Ampolas a caminho na rede</h2>

          <p class="mt-3 text-4xl font-semibold tabular-nums">
            {{ ampolasEmTransito.toLocaleString('pt-BR') }}
          </p>

          <p class="mt-2 text-xs leading-6 text-muted">
            Remessas conhecidas pelo nó, ainda sem recebimento confirmado.
          </p>
        </article>

        <article class="border-t-2 border-amber-600 py-4">
          <h2 class="text-sm text-muted">Lotes próximos do vencimento</h2>

          <p class="mt-3 text-4xl font-semibold tabular-nums">
            {{ vencimentos.length }}
          </p>

          <p class="mt-2 text-xs leading-6 text-muted">
            Lotes incluídos no aviso de validade da rede.
          </p>
        </article>
      </section>

      <p
        v-if="unidadesSemContato.length"
        role="status"
        class="rounded-lg border border-amber-200
               bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900"
      >
        {{ unidadesSemContato.length }} unidades ainda não possuem contato
        conhecido. Seus saldos não foram incluídos no total disponível.
      </p>

      <BasePanel
        titulo="Estoque por unidade"
        descricao="Últimas informações conhecidas pelo nó."
      >
        <template #acoes>
          <span class="text-xs text-muted">
            {{ unidadesFiltradas.length }} de {{ unidades.length }} unidades
          </span>
        </template>

        <div
          class="grid gap-3 px-5 pb-5
                 sm:grid-cols-[1fr_180px_auto] sm:items-end sm:px-6"
        >
          <label>
            <span class="field-label">Buscar unidade</span>
            <input
              v-model="busca"
              type="search"
              class="field"
              placeholder="Nome ou região"
            />
          </label>

          <label>
            <span class="field-label">Exibir</span>
            <select v-model="filtro" class="field">
              <option value="todas">Todas as unidades</option>
              <option value="sem-contato">Sem contato</option>
            </select>
          </label>

          <button
            type="button"
            class="button-secondary"
            @click="limparFiltros"
          >
            Limpar
          </button>
        </div>

        <div class="table-container">
          <table class="data-table">
            <caption class="sr-only">
              Estoque e capacidade por unidade, com idade das informações
              no momento da consulta
            </caption>

            <thead>
              <tr>
                <th scope="col">Unidade</th>
                <th scope="col">Disponíveis</th>
                <th scope="col">A caminho</th>
                <th scope="col">Ocupação reservada</th>
                <th scope="col">Idade na consulta</th>
              </tr>
            </thead>

            <tbody>
              <tr v-for="unidade in unidadesFiltradas" :key="unidade.unidade">
                <th scope="row">
                  <span class="block font-semibold">{{ unidade.nome }}</span>
                  <span class="mt-1 block text-xs font-normal text-muted">
                    {{ unidade.regiao ?? 'Secretaria estadual' }}
                  </span>
                </th>

                <td class="font-semibold tabular-nums">
                  {{
                    unidade.atualizado_ha_s === null
                      ? '—'
                      : estoqueDisponivel(unidade).toLocaleString('pt-BR')
                  }}
                </td>

                <td class="tabular-nums">
                  {{ unidade.a_caminho }}
                </td>

                <td class="tabular-nums">
                  {{ ocupacaoReservada(unidade) }}
                </td>

                <td>
                  <BaseBadge
                    :tom="unidade.atualizado_ha_s === null ? 'cinza' : 'verde'"
                  >
                    {{ formatarIdade(unidade.atualizado_ha_s) }}
                  </BaseBadge>
                </td>
              </tr>

              <tr v-if="unidadesFiltradas.length === 0">
                <td colspan="5" class="empty-state">
                  Nenhuma unidade encontrada.
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p class="border-t border-line px-5 py-4 text-xs leading-6 text-muted">
          Ocupação reservada considera o estoque físico, incluindo lotes
          vencidos, mais as remessas a caminho. A idade indica tempo,
          não uma classificação de qualidade dos dados.
        </p>
      </BasePanel>

      <div class="grid items-start gap-6 xl:grid-cols-2">
        <BasePanel titulo="Lotes próximos do vencimento">
          <ul class="divide-y divide-line">
            <li
              v-for="lote in vencimentos"
              :key="`${lote.unidade}-${lote.lote}`"
              class="p-5"
            >
              <div class="flex flex-wrap justify-between gap-3">
                <h3 class="text-sm font-semibold">{{ lote.lote }}</h3>
                <BaseBadge tom="amarelo">
                  {{ lote.vence_em_dias }} dias para vencer
                </BaseBadge>
              </div>

              <p class="mt-2 text-sm text-river">{{ nomeSoro(lote.soro) }}</p>
              <p class="mt-1 text-xs text-muted">{{ lote.nome }}</p>

              <p class="mt-3 text-xs text-muted">
                {{ lote.qtd }} ampolas · Validade
                {{ formatarData(lote.validade) }}
              </p>
            </li>
          </ul>

          <p v-if="vencimentos.length === 0" class="empty-state">
            Nenhum lote próximo do vencimento nos dados conhecidos.
          </p>
        </BasePanel>

        <BasePanel titulo="Alertas de surto">
          <ul class="divide-y divide-line">
            <li v-for="alerta in alertas" :key="alerta.id" class="p-5">
              <BaseBadge tom="amarelo">Alerta ativo</BaseBadge>

              <h3 class="mt-3 text-sm font-semibold">{{ alerta.regiao }}</h3>

              <p class="mt-2 text-sm leading-7 text-muted">
                {{ alerta.observado }} casos observados.
                Limiar de referência:
                {{ alerta.limiar.toLocaleString('pt-BR', {
                  maximumFractionDigits: 1,
                }) }}.
              </p>

              <p class="mt-3 text-xs text-muted">
                Dia avaliado: {{ formatarData(alerta.dia) }}
              </p>
            </li>
          </ul>

          <p v-if="alertas.length === 0" class="empty-state">
            Nenhum alerta ativo nos dados conhecidos.
          </p>
        </BasePanel>
      </div>

      <BasePanel
        titulo="Uso diário de ampolas"
        descricao="Consumo registrado nos últimos sete dias."
      >
        <template #acoes>
          <span class="text-sm text-muted">
            <strong class="text-ink">{{ totalUso }}</strong> no período
          </span>
        </template>

        <p v-if="totalUso === 0" class="px-5 pb-5 text-sm text-muted">
          Não há consumo registrado no período.
        </p>

        <dl class="grid grid-cols-7 gap-2 px-5 pb-6 sm:gap-5">
          <div
            v-for="item in usoDiario"
            :key="item.data"
            class="flex flex-col text-center"
          >
            <dt class="order-2 mt-3 text-xs text-muted">
              {{ item.data.slice(5).split('-').reverse().join('/') }}
            </dt>

            <dd class="order-1">
              <span class="text-xs font-semibold tabular-nums">
                {{ item.ampolas }}
                <span class="sr-only">ampolas</span>
              </span>

              <div
                aria-hidden="true"
                class="mt-3 flex h-28 items-end rounded-t bg-mist"
              >
                <div
                  class="w-full rounded-t bg-river"
                  :style="{ height: `${(item.ampolas / maiorUso) * 100}%` }"
                ></div>
              </div>
            </dd>
          </div>
        </dl>
      </BasePanel>

      <BasePanel
        titulo="Remessas pendentes do nó"
        descricao="Remessas enviadas ou destinadas à sua unidade."
      >
        <ul class="divide-y divide-line">
          <li
            v-for="remessa in remessasPendentes"
            :key="remessa.id"
            class="p-5"
          >
            <div class="flex flex-wrap justify-between gap-3">
              <h3 class="text-sm font-semibold">
                {{ nomeUnidade(remessa.origem) }}
                → {{ nomeUnidade(remessa.destino) }}
              </h3>

              <span class="text-sm font-semibold text-river">
                {{ remessa.qtd }} ampolas
              </span>
            </div>

            <p class="mt-2 text-sm text-muted">
              {{ nomeSoro(remessa.soro) }}
            </p>

            <p class="mt-2 text-xs text-muted">
              {{ remessa.id }} · Enviada em {{ formatarData(remessa.data) }}
            </p>
          </li>
        </ul>

        <p v-if="remessasPendentes.length === 0" class="empty-state">
          Nenhuma remessa pendente envolvendo sua unidade.
        </p>
      </BasePanel>
    </template>
  </div>
</template>