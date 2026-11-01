# Perfil OTIMIZADO — The Sims 2 (PS2) em Mali-G52

Alvos típicos: **Helio G85 / G80 / G70 / G88, Exynos 850, Tiger T610/T618**
(2× Cortex-A75 + 6× A55, Mali-G52 MC1/MC2).

> Regra de ouro: em emulação de PS2 nesse hardware **quem manda é a CPU**. Baixar
> resolução ajuda a GPU e o aquecimento, mas o teto de fps vem do Emotion Engine.
> Por isso as duas alavancas que mais rendem são *Speedhack* e *Frame Skip*.

Todos os nomes abaixo estão em **Português (Configurações do ARMSX2)** e em
negrito como aparecem no app.

---

## 0. Primeiro: deixe o app se ajustar sozinho

1. Feche o jogo e abra **Configurações › Desempenho**.
2. Ligue **Ajuste automático de desempenho** — ele testa configurações mais leves
   por jogo quando os quadros caem e mantém o que ajudou.
3. Ligue **Desempenho Sustentado** — segura o clock em nível térmico estável
   (menos throttling no meio da sessão, menos calor e bateria).
4. Em **Configurações › Gráficos**, deixe **Perfil de GPU** em **Automático**.

Só depois disso mexa no resto: se o auto-ajuste já resolveu, não invente.

---

## 1. Gráficos (aba **Renderizador**)

| Opção | Valor para Mali-G52 | Por quê |
|---|---|---|
| **Renderizador** | **Vulkan** (1ª tentativa). Se piscar, travar ou der artefato: **OpenGL** | O ARMSX2 tem caminho otimizado para Mali; Vulkan costuma ser mais rápido, GL mais "seguro" |
| **OpenGL via ANGLE** | Desligado | Traduz GL→Vulkan por cima; camada extra de custo |
| **Upscale** (resolução interna) | **Nativo** | Acima de nativo é o maior gasto de GPU e de banda |
| **Resolução de Exibição (escalador HW)** | **Tela** (ou **1x PS2** se esquentar) | Reduz a saída final sem mexer na emulação |
| **Aglutinar passagens de renderização** | **Ligado** | GPUs tiling (toda Mali) lucram muito agrupando passes |
| **FXAA** | **Desligado** | Pós-processamento por pixel em tela cheia |
| **Afiação CAS** / **Ampliação FSR 1** | Desligados | Filtros caros; nada a ganhar em 1x |
| **Shader CRT / TV** | Desligado | Pós-processamento pesado |
| **Anisotrópico** | **1x** (ou off) | Custa banda de textura |
| **Trilinear** | **Automático** | Forçar custa mais |
| **HW Mipmapping** | Desligado (ligue só se tremular textura) | |
| **Filtragem de Texturas** | **PS2** | Mais seguro e mais barato |
| **Precisão de Blending** | **Básico** | Mais alto = mais correto e bem mais caro |
| **Desentrelaçamento** | **Automático** | O jogo é PAL 50 Hz |
| **Ritmo de Frames Ideal** | **Desligado** | Descrição oficial: "Desligue se um aparelho mais fraco ficar mais suave com uma pequena fila de frames" |
| **Forçar busca de framebuffer (MediaTek Mali)** | Deixe **desligado**; ligue só se houver artefato no Vulkan | Opção de teste para Mali MediaTek |
| **Driver de GPU** | **Não use** | É para Adreno/Mesa Turnip; em Mali não se aplica |

---

## 2. Desempenho (aba **Desempenho**)

| Opção | Valor | Comentário |
|---|---|---|
| **Perfil de Speedhack** | **Low-End** (se faltar fps) ou **Rápido** | Presets: *Ideal* = seguro, *Rápido* = agressivo + resolução nativa |
| **Frame Skip** | **1** (tente **2** se ainda cair) | Desenha 1 a cada (N+1) quadros; a emulação continua em velocidade cheia |
| **Speedhacks Avançados › MTVU** | **Ligado** | Roda o VU1 em outra thread — o A75/A55 agradece |
| **Núcleos de Desempenho** | Automático | |

Ordem exata para **ganhar fps**, do mais barato ao mais agressivo:

1. **Frame Skip = 1** (visual mais picotado, mas o jogo anda).
2. **Perfil de Speedhack = Low-End**.
3. **Resolução de Exibição = 1x PS2**.
4. **FXAA/CAS/FSR/CRT** desligados (se ainda estiverem ligados).
5. **Precisão de Blending** em Básico.
6. **Frame Skip = 2** (último recurso).

---

## 3. Áudio (aba **Áudio**)

| Opção | Valor |
|---|---|
| **Buffer de Áudio** | Aumente (ex.: 3–4) se estalar/engasgar em aparelho fraco |
| **Latência de Saída** | Padrão; menor = mais responsivo, maior = mais seguro |
| **Sincronização de Áudio** | **Time Stretch** ligado (tom estável quando o fps oscila) |
| **Áudio SPU2 SIMD (experimental)** | **Ligado** — caminho NEON do reverb, libera CPU (reinicie o jogo) |
| **Áudio compatível com gravação** | Desligado (só para gravar tela) |

---

## 4. Fora do emulador (isso rende mais que qualquer menu)

- **Modo desempenho do fabricante**: Game Turbo (MIUI), Game Launcher (Samsung),
  "Modo jogo" (Realme/ColorOS). Sem isso o governador de CPU segura clock.
- **Bateria**: tire o app da otimização de bateria/segundo plano.
- **Tela**: 60 Hz (não 90/120). Taxa maior só aumenta trabalho e calor.
- **Armazenamento**: mantenha ≥ 10 GB livres (shader cache e caches do jogo).
- **Temperatura**: acima de ~35 °C na bateria a Mali-G52 throttla forte. Jogue sem
  capa, sem carregar, ou com cooler. O próprio ARMSX2 avisa quando passa disso.
- **BIOS**: use um dump `scphXXXXX.bin` real; BIOS falsa/patcheada causa lentidão
  e telas pretas.
- **Formato do jogo**: o `.iso` em armazenamento interno é mais rápido que no
  cartão SD. Se quiser economizar espaço, o ARMSX2 lê formatos comprimidos
  (CHD/ZSO/CSO) — o CSO do bundle fica em 990 MB contra 3,31 GB do ISO. Adesão
  de CPU na leitura existe, mas é pequena: o gargalo aqui é o Emotion Engine.
- **Como abrir**: adicione a pasta do jogo em **Biblioteca › ⋮ › Adicionar pasta
  de jogos** (ex.: `Download/Sims2`) e toque na capa. Não use **Iniciar BIOS**:
  ele abre o menu do console **sem disco** e mostra “Inserir um disco com o
  formato para PlayStation ou PlayStation 2”. O app `Sims2Mobile-ABRIR-JOGO.apk`
  faz esse passo por você (entrega o disco ao emulador por intent).

---

## 5. Melhor combinação para este jogo (resumo de 30 segundos)

```
Renderizador ...... Vulkan (senão OpenGL)
Upscale ........... Nativo
Res. de Exibição .. Tela  (1x PS2 se esquentar)
Aglutinar passes .. Ligado
FXAA / CAS / FSR .. Desligados
Blending .......... Básico
Speedhack ......... Low-End
Frame Skip ........ 1
MTVU .............. Ligado
Desemp. Sustentado  Ligado
Ajuste automático . Ligado
SPU2 SIMD ......... Ligado
```

Com isso, num Helio G85 o esperado é **~20–30 fps** nas áreas abertas e picos
maiores em interiores. Não é 60 fps — e nenhum ajuste muda isso, porque o gargalo
é o Emotion Engine, não a Mali-G52.

---

## 6. Se ficar pior depois de mexer

Use **Redefinir o ajuste automático deste jogo** (Configurações › Desempenho) para
voltar ao que o auto-tune tinha aprendido, e **Limpar Cache de Shaders**
(Configurações › Gráficos) se a imagem ficar corrompida — sempre com o jogo
fechado. As configurações são **por jogo**, então testar aqui não estraga outros
jogos.
