// Funções comuns às telas. Cada página fala só com o nó que a serviu (mesma origem).
const App = {
  info: null,
  sessao: null,

  async api(caminho, corpo) {
    const opcoes = corpo === undefined ? {} :
      {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(corpo)};
    const r = await fetch(caminho, opcoes);
    const dados = await r.json().catch(() => ({}));
    // Sessão vencida ou ausente: volta para o login e, depois dele, para esta tela.
    if (r.status === 401 && !location.pathname.endsWith("/login.html")) App.irParaLogin();
    if (!r.ok) throw new Error(dados.erro || `Erro ${r.status}`);
    return dados;
  },

  esc(s) {
    return String(s ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
  },

  idade(seg) {
    if (seg === null || seg === undefined) return "sem dados";
    if (seg < 60) return "agora";
    if (seg < 3600) return `há ${Math.round(seg / 60)} min`;
    if (seg < 172800) return `há ${Math.round(seg / 3600)} h`;
    return `há ${Math.round(seg / 86400)} dias`;
  },

  etiquetaIdade(seg) {
    const velho = seg === null || seg === undefined || seg > 6 * 3600;
    return `<span class="etq ${velho ? "aviso" : "ok"}">${App.idade(seg)}</span>`;
  },

  data(iso) {
    const [a, m, d] = iso.split("-");
    return `${d}/${m}/${a}`;
  },

  aviso(msg, erro = false) {
    let el = document.getElementById("aviso");
    if (!el) {
      el = document.createElement("div");
      el.id = "aviso";
      el.setAttribute("role", "status");
      document.body.appendChild(el);
    }
    el.className = "aviso-msg" + (erro ? " erro" : "");
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(App._t);
    App._t = setTimeout(() => (el.hidden = true), 4000);
  },

  irParaLogin() {
    location.href = "login.html?volta=" + encodeURIComponent(location.pathname.split("/").pop() + location.hash);
  },
  pode(acao) { return !!App.sessao?.pode.includes(acao); },
  iniciais(nome) {
    return nome.replace(/[^A-Za-zÀ-ú ]/g, " ").split(/\s+/).filter(w => w.length > 2).slice(0, 2).map(w => w[0]).join("").toUpperCase();
  },

  // Força da senha, para orientar quem digita. O servidor exige só os 8 caracteres.
  forcaSenha(s) {
    if (s.length < 8) return {nivel: 0, rotulo: "Curta demais", dica: `faltam ${8 - s.length} caracteres`};
    const faltam = [];
    let pontos = 0;
    if (s.length >= 12) pontos++; else faltam.push("use 12 ou mais caracteres");
    if (s.length >= 16) pontos++;
    if (/[a-z]/.test(s) && /[A-Z]/.test(s)) pontos++; else faltam.push("misture maiúsculas e minúsculas");
    if (/\d/.test(s)) pontos++; else faltam.push("ponha números");
    if (/[^A-Za-z0-9]/.test(s)) pontos++; else faltam.push("ponha um símbolo");
    // Sequências e palavras óbvias derrubam qualquer senha para fraca.
    const obvia = /^(.)\1+$|0123|1234|2345|3456|4567|5678|6789|abcd|qwer|asdf|senha|password|admin|soro|amazonas/i.test(s);
    if (obvia) pontos = Math.min(pontos, 1);
    const nivel = pontos <= 1 ? 1 : Math.min(pontos, 4);
    const rotulo = ["", "Fraca", "Razoável", "Boa", "Forte"][nivel];
    const dica = obvia ? "evite sequências e palavras óbvias" : nivel < 4 ? faltam[0] || "" : "";
    return {nivel, rotulo, dica};
  },
  medidorSenha(input) {
    const el = document.createElement("div");
    el.className = "forca";
    el.setAttribute("aria-live", "polite");
    el.innerHTML = '<span class="forca-barras" aria-hidden="true"><i></i><i></i><i></i><i></i></span><span></span>';
    input.insertAdjacentElement("afterend", el);
    const atualizar = () => {
      const f = App.forcaSenha(input.value);
      el.hidden = !input.value;
      el.dataset.nivel = f.nivel;
      el.lastChild.textContent = f.dica ? `${f.rotulo}: ${f.dica}` : f.rotulo;
    };
    input.addEventListener("input", atualizar);
    input.form?.addEventListener("reset", () => setTimeout(atualizar));
    atualizar();
  },

  novoId() {
    return (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random()).replace(/-/g, "");
  },

  // Ícones de traço (24x24), desenhados aqui para não depender de biblioteca externa.
  ICONES: {
    inicio: '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/>',
    estoque: '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
    painel: '<path d="M3 21h18"/><path d="M7 17v-6M12 17V5M17 17v-9"/>',
    pin: '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    rede: '<circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="m8.2 10.8 7.6-3.6M8.2 13.2l7.6 3.6"/>',
    caminhao: '<path d="M3 6h11v10H3zM14 9h4l3 3v4h-7"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>',
    frasco: '<path d="M9 3h6M10 3v4l-4 9a3 3 0 0 0 2.7 4.3h6.6A3 3 0 0 0 18 16l-4-9V3"/><path d="M7.5 13h9"/>',
    alerta: '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17h.01"/>',
    sino: '<path d="M6 9a6 6 0 0 1 12 0c0 6 2.5 7.5 2.5 7.5h-17S6 15 6 9z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
    relogio: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    calendario: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    busca: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    telefone: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/>',
    mapa: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>',
    hospital: '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M12 8v8M8 12h8"/>',
    sincronizar: '<path d="M20 11a8 8 0 0 0-14.9-3M4 13a8 8 0 0 0 14.9 3"/><path d="M4 4v4h4M20 20v-4h-4"/>',
    pedido: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1M9 11h6M9 15h4"/>',
    lista: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    cobra: '<path d="M3 17c2.5 0 2.5-4 5-4s2.5 4 5 4 2.5-4 5-4c1.4 0 2.2.6 3 1.4"/><circle cx="18.5" cy="8" r="2.2"/><path d="M18.5 10.2V13"/>',
    escorpiao: '<rect x="8" y="8" width="8" height="11" rx="4"/><path d="M12 8V5a3 3 0 0 1 5-2M4 11h4M16 11h4M4 16h4M16 16h4"/>',
    duvida: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14M12 17h.01"/>',
    socorro: '<path d="M12 21s-8-4.5-8-11a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 10c0 6.5-8 11-8 11z"/>',
    ok: '<path d="m5 12 5 5 9-10"/>',
    pessoa: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    equipe: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6.5 6.5 0 0 1 3.5 6"/>',
    sair: '<path d="M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4"/><path d="M10 17l5-5-5-5M15 12H3"/>',
    cadeado: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  },
  icone(nome) {
    return `<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${App.ICONES[nome] || ""}</svg>`;
  },

  // Cabeçalho: nome da unidade, conexão com os vizinhos e navegação entre as telas
  // (pílulas no computador, barra flutuante no celular).
  async cabecalho(atual) {
    [App.info, App.sessao] = await Promise.all([App.api("/api/info"), App.api("/api/sessao")]);
    if (!App.sessao.usuario) { App.irParaLogin(); return new Promise(() => {}); }
    const i = App.info, eu = App.sessao.usuario;
    const telas = [["index.html", "Início", "inicio"]];
    if (i.nivel === "posto" || i.nivel === "polo") telas.push(["posto.html", "Estoque", "estoque"]);
    if (i.nivel === "polo" && App.pode("paineis")) telas.push(["polo.html", "Painel", "painel"]);
    if (i.nivel === "estado") telas.push(["estado.html", "Painel", "painel"]);
    // No celular cabem quatro telas e o botão central; com cinco, "Onde tem soro" fica só nos atalhos.
    telas.push(["usuario.html", "Onde tem soro", "pin", telas.length > 2 ? "so-largo" : ""], ["rede.html", "Rede", "rede"]);
    const nivel = {estado: "Secretaria estadual", polo: "Polo", posto: "Ponto de soro"}[i.nivel];
    document.querySelector("header").outerHTML = `<header class="topo">
      <div class="quem"><h1>${App.esc(i.nome)}</h1><small>${nivel}${i.regiao ? " · " + App.esc(i.regiao) : ""} · ${App.esc(i.estado)}</small></div>
      <div class="dir"><a class="sinc" id="sinc" href="rede.html" title="Conexão com os vizinhos">${App.icone("rede")}<span class="ponto"></span><span class="txt">sincronização</span></a>
        <a class="avatar" href="equipe.html" title="${App.esc(eu.nome)} · ${App.esc(eu.tipo_nome)}" ${atual === "equipe.html" ? 'aria-current="page"' : ""}>${App.iniciais(eu.nome) || App.icone("pessoa")}</a></div></header>
      <nav class="nav" aria-label="Telas">${telas.map(([h, n, ic, cl]) =>
        `<a href="${h}" class="${cl || ""}" ${h === atual ? 'aria-current="page"' : ""}>${App.icone(ic)}<span>${n}</span></a>`).join("")}</nav>`;
    App.atualizarSinc();
    setInterval(App.atualizarSinc, 5000);
    App.ligarDicas();
    return i;
  },

  // Cartão de destaque com a ação principal; as outras ações viram ladrilhos no topo da folha.
  // A ação principal também vai para o botão redondo da barra do celular.
  // acoes: [{icone, rotulo, curto, cor, href | id, valor}]
  hero({rotulo, titulo, texto, acoes = []}) {
    const [principal, ...resto] = acoes;
    const alvo = a => a.href ? `a href="${a.href}"` : `button type="button" id="${a.id}"`;
    const fim = a => a.href ? "a" : "button";
    const ladrilho = a => `<${alvo(a)} class="atalho"><span class="ic ${a.cor || ""}">${App.icone(a.icone)}</span>`
      + `${a.valor !== undefined ? `<b class="valor num" id="${a.id}-v">${a.valor}</b>` : ""}<span>${App.esc(a.rotulo)}</span></${fim(a)}>`;
    const main = document.querySelector("main");
    main.insertAdjacentHTML("beforebegin", `<section class="hero"><div class="hero-card">
      <small id="hero-rot">${App.esc(rotulo)}</small><h2 id="hero-tit">${App.esc(titulo)}</h2>
      ${principal ? `<div class="hero-botoes"><${alvo(principal)} class="hero-botao">${App.icone(principal.icone)}<span>${App.esc(principal.rotulo)}</span></${fim(principal)}></div>` : ""}
      </div></section>`);
    main.insertAdjacentHTML("afterbegin", `<section class="abertura"><p class="frase" id="hero-txt">${App.negrito(texto)}</p>
      ${resto.length ? `<div class="atalhos">${resto.map(ladrilho).join("")}</div>` : ""}</section>`);
    const nav = document.querySelector(".nav");
    if (principal && nav) {
      const fab = principal.href ? document.createElement("a") : document.createElement("button");
      fab.className = "fab";
      if (principal.href) fab.href = principal.href;
      else { fab.type = "button"; fab.addEventListener("click", () => document.getElementById(principal.id).click()); }
      fab.innerHTML = `${App.icone(principal.icone)}<span>${App.esc(principal.curto || principal.rotulo)}</span>`;
      const visiveis = [...nav.querySelectorAll("a:not(.so-largo)")];
      visiveis[Math.floor(visiveis.length / 2)].before(fab);
    }
  },
  heroTexto(titulo, texto) {
    if (titulo !== undefined) document.getElementById("hero-tit").textContent = titulo;
    if (texto !== undefined) document.getElementById("hero-txt").innerHTML = App.negrito(texto);
  },
  // Texto da frase de abertura: *assim* vira negrito; o resto é escapado.
  negrito(s) { return App.esc(s).replace(/\*(.+?)\*/g, "<b>$1</b>"); },
  milhar(n) { return Number(n).toLocaleString("pt-BR"); },

  // Cabeçalho simples da tela do cidadão: sem o menu da equipe.
  async cabecalhoCidadao() {
    App.info = await App.api("/api/info");
    document.querySelector("header").outerHTML = `<header class="topo cidadao">
      <div class="quem"><h1>Olá! Precisa de soro?</h1><small>Soro antiveneno · ${App.esc(App.info.estado)}</small></div>
      <div class="dir"><a class="avatar" href="perfil.html" title="Seu perfil">${App.icone("pessoa")}</a></div></header>`;
    return App.info;
  },

  async atualizarSinc() {
    const el = document.getElementById("sinc");
    let txt, ok = 0;
    try {
      const s = await App.api("/api/sincronizacao");
      ok = s.vizinhos.filter(v => v.ultimo_ok_ha_s !== null && v.ultimo_ok_ha_s < 30).length;
      txt = `${ok} de ${s.vizinhos.length} vizinhos · ${App.milhar(s.eventos)} registros`;
    } catch (e) {
      txt = "nó sem resposta";
    }
    el.querySelector(".ponto").className = "ponto" + (ok ? "" : " off");
    el.querySelector(".txt").textContent = txt;
    el.title = `Conexão com os vizinhos: ${txt}`;
  },

  soro(cod) {
    return App.info?.soros?.[cod] || cod;
  },

  // Gráfico de casos por dia com o limite do método C2.
  grafico(serie) {
    const W = 640, H = 200, pl = 34, pb = 26, pt = 10, n = serie.length;
    const max = Math.max(4, ...serie.map(s => Math.max(s.observado, Math.ceil(s.limiar))));
    const y = v => pt + (H - pt - pb) * (1 - v / max), bw = (W - pl - 8) / n;
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Casos por dia e limite de alerta">`;
    for (let t = 0; t <= max; t += Math.max(1, Math.round(max / 4)))
      s += `<line x1="${pl}" x2="${W - 4}" y1="${y(t)}" y2="${y(t)}" stroke="var(--linha)"/><text x="${pl - 6}" y="${y(t) + 4}" text-anchor="end" font-size="11" fill="var(--tinta3)">${t}</text>`;
    let linha = "";
    serie.forEach((p, i) => {
      const x = pl + i * bw;
      s += `<rect x="${x + bw * 0.18}" y="${y(p.observado)}" width="${bw * 0.64}" height="${Math.max(0, y(0) - y(p.observado))}" rx="3" fill="${p.alarme ? "var(--ferrugem)" : "var(--verde2)"}"/>`;
      s += `<text x="${x + bw / 2}" y="${H - 8}" text-anchor="middle" font-size="10" fill="var(--tinta3)">${p.dia.slice(8)}</text>`;
      linha += `${i ? "L" : "M"}${x + bw / 2},${y(p.limiar)}`;
    });
    s += `<path d="${linha}" fill="none" stroke="var(--laranja)" stroke-width="2.5" stroke-dasharray="7 5"/></svg>`;
    return s;
  },

  // --- gráficos -------------------------------------------------------------
  // Cores por categoria em ordem fixa (--s1 a --s4, ver app.css). Cada soro tem sua cor e
  // cada tipo de acidente usa a cor do soro principal dele, então a cor segue a coisa e
  // não a posição no gráfico.
  corSoro(cod) {
    const i = Object.keys(App.info.soros).indexOf(cod);
    return `var(--s${(i < 0 ? 0 : i) % 4 + 1})`;
  },
  ordemSoro(cod) { return Object.keys(App.info.soros).indexOf(cod); },
  corAgravo(a) { return App.corSoro(App.info.agravos[a]?.soros[0]); },
  ordemAgravo(a) { return App.ordemSoro(App.info.agravos[a]?.soros[0]); },

  num(v) { return String(v).replace(".", ","); },
  passo(max) {
    const bruto = Math.max(1, max) / 4, e = 10 ** Math.floor(Math.log10(bruto)), f = bruto / e;
    return Math.max(1, (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * e);
  },
  curto(t, n = 22) { return t.length > n ? t.slice(0, n - 1) + "…" : t; },

  // O conteúdo da dica vai no próprio elemento, em data-dica.
  dica(titulo, linhas) { return App.esc(JSON.stringify({titulo, linhas})); },

  legenda(itens, forma = "bloco") {
    return `<div class="legenda">${itens.map(i => `<span><i class="leg-${i.forma || forma}" style="background:${i.cor}"></i>${App.esc(i.nome)}</span>`).join("")}</div>`;
  },

  tabelaDados(cab, linhas) {
    return `<details class="ver-tabela"><summary>Ver os números</summary><div class="tabela"><table>
      <tr>${cab.map((c, i) => `<th class="${i ? "d" : ""}">${App.esc(c)}</th>`).join("")}</tr>
      ${linhas.map(l => `<tr>${l.map((c, i) => `<td class="${i ? "d num" : ""}">${App.esc(c)}</td>`).join("")}</tr>`).join("")}
      </table></div></details>`;
  },

  // Barras horizontais, simples ou empilhadas. linhas: [{rotulo, segs: [{nome, valor, cor}], vazio, marca}]
  // ref: linha vertical de referência {valor, rotulo}; marca: risco do alvo de cada linha.
  // teto: corta a escala nesse valor; a barra que passa dele termina em seta e mostra o valor real.
  barras({linhas, unidade = "", ref = null, rotuloMarca = "alvo", teto = null, W = 640}) {
    const esq = Math.min(170, Math.round(W * 0.34)), dir = 56, alt = 30, topo = ref ? 20 : 6, H = topo + linhas.length * alt + 6;
    const total = l => l.segs.reduce((a, g) => a + g.valor, 0);
    const maior = Math.max(1, ref?.valor || 0, ...linhas.map(l => Math.max(total(l), l.marca || 0)));
    const max = teto ? Math.min(teto, maior) : maior;
    const nomeMax = Math.max(10, Math.floor((esq - 14) / 6.6));
    const x = v => esq + (W - esq - dir) * v / max;
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Gráfico de barras">`;
    linhas.forEach((l, i) => {
      const y = topo + i * alt, meio = y + alt / 2, h = 16;
      s += `<text x="${esq - 10}" y="${meio + 4}" text-anchor="end" font-size="12" fill="var(--tinta2)">${App.esc(App.curto(l.rotulo, nomeMax))}<title>${App.esc(l.rotulo)}</title></text>`;
      if (l.vazio) {
        s += `<text x="${esq}" y="${meio + 4}" font-size="12" fill="var(--tinta3)">${App.esc(l.vazio)}</text>`;
        return;
      }
      let x0 = esq;
      const vis = l.segs.filter(g => g.valor > 0);
      vis.forEach((g, k) => {
        const resto = W - dir - x0, cortada = x(g.valor) - esq > resto;
        const w = Math.max(1, Math.min(resto, x(g.valor) - esq) - (k < vis.length - 1 ? 2 : 0));
        const ultimo = k === vis.length - 1, r = Math.min(4, w / 2);
        // Cantos arredondados só na ponta da barra; a base fica reta.
        const d = ultimo
          ? `M${x0},${meio - h / 2}h${w - r}a${r},${r} 0 0 1 ${r},${r}v${h - 2 * r}a${r},${r} 0 0 1 -${r},${r}h-${w - r}z`
          : `M${x0},${meio - h / 2}h${w}v${h}h-${w}z`;
        const id = App.dica(l.rotulo, [{cor: g.cor, rotulo: g.nome, valor: `${App.num(g.valor)} ${unidade}`}]);
        s += `<path class="marca" d="${d}" fill="${g.cor}" data-dica="${id}" tabindex="0"/>`;
        if (cortada) s += `<path d="M${x0 + w - 10},${meio - h / 2 - 1}l6,${h / 2 + 1}l-6,${h / 2 + 1}" fill="none" stroke="var(--cartao)" stroke-width="2"/>`;
        x0 += w + 2;
      });
      if (l.marca) s += `<line x1="${x(l.marca)}" x2="${x(l.marca)}" y1="${meio - 12}" y2="${meio + 12}" stroke="var(--tinta)" stroke-width="2"><title>${rotuloMarca}: ${l.marca}</title></line>`;
      s += `<text x="${Math.min(W - dir, Math.max(x0, l.marca ? x(l.marca) + 4 : 0)) + 4}" y="${meio + 4}" font-size="12" font-weight="600" fill="var(--tinta)">${App.esc(l.texto || App.num(total(l)))}</text>`;
    });
    if (ref) {
      s += `<line x1="${x(ref.valor)}" x2="${x(ref.valor)}" y1="${topo - 4}" y2="${H - 4}" stroke="var(--ferrugem)" stroke-width="1.5" stroke-dasharray="4 4"/>`;
      s += `<text x="${x(ref.valor)}" y="12" text-anchor="middle" font-size="11" fill="var(--tinta2)">${App.esc(ref.rotulo)}</text>`;
    }
    return s + "</svg>";
  },

  // Linhas por dia com mira vertical. series: [{nome, cor, valores}]
  linhas({x, series, unidade = "", W = 640}) {
    const H = 220, esq = 34, dir = 10, topo = 10, base = 26, n = x.length;
    const max = Math.max(1, ...series.flatMap(sr => sr.valores)), p = App.passo(max), teto = Math.ceil(max / p) * p;
    const px = i => esq + (W - esq - dir) * (n === 1 ? 0.5 : i / (n - 1)), py = v => topo + (H - topo - base) * (1 - v / teto);
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Gráfico de linhas por dia">`;
    for (let t = 0; t <= teto; t += p)
      s += `<line x1="${esq}" x2="${W - dir}" y1="${py(t)}" y2="${py(t)}" stroke="var(--linha)"/><text x="${esq - 6}" y="${py(t) + 4}" text-anchor="end" font-size="11" fill="var(--tinta3)">${t}</text>`;
    const cada = W < 420 ? 14 : 7;
    x.forEach((d, i) => { if ((n - 1 - i) % cada === 0) s += `<text x="${px(i)}" y="${H - 8}" text-anchor="middle" font-size="11" fill="var(--tinta3)">${d.slice(8)}/${d.slice(5, 7)}</text>`; });
    series.forEach(sr => {
      s += `<path d="${sr.valores.map((v, i) => `${i ? "L" : "M"}${px(i)},${py(v)}`).join("")}" fill="none" stroke="${sr.cor}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;
      s += `<circle cx="${px(n - 1)}" cy="${py(sr.valores[n - 1])}" r="4" fill="${sr.cor}" stroke="var(--cartao)" stroke-width="2"/>`;
    });
    s += `<line class="mira" x1="0" x2="0" y1="${topo}" y2="${H - base}" stroke="var(--tinta3)" stroke-width="1" visibility="hidden"/>`;
    const larg = (W - esq - dir) / Math.max(1, n - 1);
    x.forEach((d, i) => {
      const id = App.dica(App.data(d), series.map(sr => ({cor: sr.cor, rotulo: sr.nome, valor: `${sr.valores[i]} ${unidade}`, linha: true})));
      s += `<rect x="${px(i) - larg / 2}" y="${topo}" width="${larg}" height="${H - topo - base}" fill="transparent" data-dica="${id}" data-mira="${px(i)}"/>`;
    });
    return s + "</svg>";
  },

  // Colunas empilhadas. colunas: [{rotulo, titulo, segs: [{nome, valor, cor}]}]
  colunas({colunas, unidade = "", W = 640}) {
    const H = 220, esq = 34, dir = 10, topo = 18, base = 26, n = colunas.length;
    const tot = c => c.segs.reduce((a, g) => a + g.valor, 0);
    const max = Math.max(1, ...colunas.map(tot)), p = App.passo(max), teto = Math.ceil(max / p) * p;
    const py = v => topo + (H - topo - base) * (1 - v / teto), faixa = (W - esq - dir) / n, w = Math.min(24, faixa * 0.6);
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Gráfico de colunas">`;
    for (let t = 0; t <= teto; t += p)
      s += `<line x1="${esq}" x2="${W - dir}" y1="${py(t)}" y2="${py(t)}" stroke="var(--linha)"/><text x="${esq - 6}" y="${py(t) + 4}" text-anchor="end" font-size="11" fill="var(--tinta3)">${t}</text>`;
    colunas.forEach((c, i) => {
      const cx = esq + faixa * (i + 0.5), x0 = cx - w / 2;
      if (faixa > 34 || i % 2 === 0) s += `<text x="${cx}" y="${H - 8}" text-anchor="middle" font-size="11" fill="var(--tinta3)">${App.esc(c.rotulo)}</text>`;
      let y0 = py(0);
      const vis = c.segs.filter(g => g.valor > 0);
      vis.forEach((g, k) => {
        const h = Math.max(1, py(0) - py(g.valor) - (k < vis.length - 1 ? 2 : 0));
        const ultimo = k === vis.length - 1, r = Math.min(4, h / 2), y = y0 - h;
        const d = ultimo
          ? `M${x0},${y0}v${-(h - r)}a${r},${r} 0 0 1 ${r},${-r}h${w - 2 * r}a${r},${r} 0 0 1 ${r},${r}v${h - r}z`
          : `M${x0},${y0}v${-h}h${w}v${h}z`;
        const id = App.dica(c.titulo || c.rotulo, [{cor: g.cor, rotulo: g.nome, valor: `${g.valor} ${unidade}`}]);
        s += `<path class="marca" d="${d}" fill="${g.cor}" data-dica="${id}" tabindex="0"/>`;
        y0 = y - 2;
      });
      if (tot(c)) s += `<text x="${cx}" y="${y0 - 2}" text-anchor="middle" font-size="11" font-weight="600" fill="var(--tinta)">${tot(c)}</text>`;
    });
    return s + "</svg>";
  },

  // Largura do conteúdo de um bloco dentro de uma .grade (colunas de no mínimo 320px),
  // para o SVG ser desenhado no tamanho em que aparece e o texto não encolher.
  larguraBloco(el, grade = true) {
    const total = el.clientWidth || 640;
    if (!grade) return Math.max(280, total - 38);
    const cols = Math.max(1, Math.floor((total + 20) / 340));
    return Math.max(280, Math.floor((total - 20 * (cols - 1)) / cols) - 38);
  },

  // Redesenha ao mudar o tamanho da janela (os gráficos são medidos na hora de desenhar).
  aoRedimensionar(fn) {
    let t;
    addEventListener("resize", () => { clearTimeout(t); t = setTimeout(fn, 200); });
  },

  // Os três gráficos que se repetem nos painéis, a partir de /api/graficos.
  graficosGerais(g, {casos = true, W = 640} = {}) {
    const soros = Object.keys(App.info.soros);
    const usados = soros.filter(sr => g.uso_diario[sr].some(v => v));
    const series = usados.map(sr => ({nome: App.soro(sr), cor: App.corSoro(sr), valores: g.uso_diario[sr]}));
    const blocos = [];
    blocos.push(`<div class="bloco"><div class="cab"><h2>Ampolas usadas por dia</h2><span class="leve">últimos ${g.dias.length} dias</span></div>
      ${series.length ? App.legenda(series, "linha") + `<div class="grafico">${App.linhas({x: g.dias, series, unidade: "amp.", W})}</div>`
        + App.tabelaDados(["Dia", ...series.map(x => x.nome)], g.dias.map((d, i) => [App.data(d), ...series.map(x => x.valores[i])]).reverse())
        : '<p class="vazio">Nenhuma ampola usada no período.</p>'}</div>`);
    if (casos) {
      const agravos = Object.keys(App.info.agravos).sort((a, b) => App.ordemAgravo(a) - App.ordemAgravo(b));
      const itens = agravos.map(a => ({nome: App.info.agravos[a].nome, cor: App.corAgravo(a)}));
      blocos.push(`<div class="bloco"><div class="cab"><h2>Atendimentos por tipo de acidente</h2><span class="leve">últimos ${g.dias.length} dias</span></div>
        ${g.casos_por_regiao.length ? App.legenda(itens) + `<div class="grafico">${App.barras({unidade: "casos", W,
          linhas: g.casos_por_regiao.map(r => ({rotulo: r.regiao, segs: agravos.map(a => ({nome: App.info.agravos[a].nome, valor: r.agravos[a] || 0, cor: App.corAgravo(a)}))}))})}</div>`
          + App.tabelaDados(["Região", ...itens.map(i => i.nome)], g.casos_por_regiao.map(r => [r.regiao, ...agravos.map(a => r.agravos[a] || 0)]))
          : '<p class="vazio">Nenhum atendimento no período.</p>'}</div>`);
    }
    const meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
    const nomeMes = m => `${meses[+m.slice(5) - 1]}/${m.slice(2, 4)}`;
    const comLote = soros.filter(sr => g.vencimento_mensal.some(m => m.soros[sr]));
    blocos.push(`<div class="bloco"><div class="cab"><h2>Ampolas que vencem por mês</h2><span class="leve">próximos 18 meses</span></div>
      ${comLote.length ? App.legenda(comLote.map(sr => ({nome: App.soro(sr), cor: App.corSoro(sr)}))) + `<div class="grafico">${App.colunas({unidade: "amp.", W,
        colunas: g.vencimento_mensal.map(m => ({rotulo: nomeMes(m.mes), titulo: "Vencem em " + nomeMes(m.mes),
          segs: comLote.map(sr => ({nome: App.soro(sr), valor: m.soros[sr], cor: App.corSoro(sr)}))}))})}</div>`
        + App.tabelaDados(["Mês", ...comLote.map(App.soro)], g.vencimento_mensal.map(m => [nomeMes(m.mes), ...comLote.map(sr => m.soros[sr])]))
        : '<p class="vazio">Nenhum lote vence nos próximos 18 meses.</p>'}</div>`);
    return blocos.join("");
  },

  // Uma dica para a página toda: segue o ponteiro e o foco do teclado.
  ligarDicas() {
    const el = document.createElement("div");
    el.className = "dica";
    el.hidden = true;
    document.body.appendChild(el);
    const mostrar = (alvo, cx, cy) => {
      const d = JSON.parse(alvo.dataset.dica);
      el.replaceChildren();
      const t = document.createElement("div");
      t.className = "dica-titulo";
      t.textContent = d.titulo;
      el.appendChild(t);
      d.linhas.forEach(l => {
        const r = document.createElement("div"), k = document.createElement("i"), v = document.createElement("b"), n = document.createElement("span");
        k.className = "chave";
        k.style.background = l.cor;
        v.textContent = l.valor;
        n.textContent = l.rotulo;
        r.append(k, v, n);
        el.appendChild(r);
      });
      el.hidden = false;
      const w = el.offsetWidth, h = el.offsetHeight;
      el.style.left = Math.min(innerWidth - w - 8, Math.max(8, cx + 14)) + "px";
      el.style.top = Math.max(8, cy - h - 12) + "px";
      const svg = alvo.ownerSVGElement, mira = svg?.querySelector(".mira");
      if (mira && alvo.dataset.mira) { mira.setAttribute("x1", alvo.dataset.mira); mira.setAttribute("x2", alvo.dataset.mira); mira.setAttribute("visibility", "visible"); }
    };
    const esconder = () => {
      el.hidden = true;
      document.querySelectorAll(".mira").forEach(m => m.setAttribute("visibility", "hidden"));
    };
    document.addEventListener("pointermove", e => {
      const a = e.target.closest?.("[data-dica]");
      a ? mostrar(a, e.clientX, e.clientY) : (!el.hidden && esconder());
    });
    document.addEventListener("focusin", e => {
      const a = e.target.closest?.("[data-dica]");
      if (a) { const r = a.getBoundingClientRect(); mostrar(a, r.right, r.top); }
    });
    document.addEventListener("focusout", e => { if (e.target.closest?.("[data-dica]")) esconder(); });
  },
};
