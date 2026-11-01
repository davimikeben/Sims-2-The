# Sims 2 Mobile — The Sims 2 (PS2) no Android, com teclado virtual bonito

![preview](docs/preview.png)

## Três arquivos — escolha o seu caminho

| Arquivo | Tamanho | Para quem |
|---|---|---|
| `Sims2Mobile-BUNDLE.apk` | **990 MB** | **O jogo vem dentro** (comprimido em CSO). O app extrai na 1ª execução e **abre o disco no emulador** |
| `Sims2Mobile-ABRIR-JOGO.apk` | **17 KB** | Já tem o `sims2.cso` em `Download/Sims2` (extraído por uma versão antiga): instala só o app corrigido, sem baixar 1 GB de novo |
| `Sims2Mobile-ARMSX2.apk` | **73 MB** | Só o emulador com a skin; você aponta a pasta onde está o seu jogo |

Em **nenhum** deles a BIOS vem embutida: você escolhe e coloca o seu dump
(`scphXXXXX.bin`) na tela *"Selecione sua BIOS"* do emulador.

> Se o emulador mostra **“Inserir um disco com o formato para PlayStation ou
> PlayStation 2”**, leia a seção **[2.1](#21-por-que-a-tela-inserir-um-disco-aparece)**:
> quase sempre é o botão *Iniciar BIOS*, não o arquivo do jogo.

### Por que o BUNDLE usa CSO (e não o ISO cru)

| Arquivo | Tamanho |
|---|---|
| ISO original (do seu zip) | 3.550.085.120 B = **3,31 GB** |
| CSO gerado (`tools/iso_to_cso.py`) | 1.038.445.087 B = **990 MB** |

Comprime **3,42x sem perder nada**: o `tools/iso_to_cso.py` decodifica o CSO de
volta e compara o SHA-256 com o ISO original. O formato segue o
`pcsx2/CDVD/CsoFileReader.cpp` do emulador (CISOV1, deflate raw por bloco,
índice `u32` **absoluto** com bit31 = bloco cru).

O script também **audita o disco** do jeito que o emulador e o BIOS fazem, e é
isso que decide entre "abrir o jogo" e "Inserir um disco":

```bash
python3 tools/iso_to_cso.py --check sims2.cso
#   cabecalho + indice ...... ok   1733440 frames de 2048 B (105178 crus), align 0
#   trilha 16 (PVD) ......... ok   PLAYSTATION, volume SIMS2_PS2_9_19_SKU2
#   SYSTEM.CNF / BOOT2 ...... ok   cdrom0:\SLES_537.18;1  (PAL)
#   todos os 1733440 frames .. ok   em 13s
# OK: o emulador reconhece este disco (frame 16 + SYSTEM.CNF)
```

Resultado no celular: **990 MB** em `Download/Sims2/sims2.cso` em vez de 3,31 GB.
Depois de extrair, o app pode ser desinstalado (o jogo fica no arquivo).

Pacote completo para jogar **The Sims 2 (PlayStation 2)** no celular, com um
teclado virtual (controle na tela) redesenhado do zero e um perfil de desempenho
pensado para GPUs fracas como a **Mali-G52**.

---

## 0. Baixar os arquivos (GitHub)

**Release (recomendado):**
<https://github.com/davimikeben/Sims-2-The/releases/tag/v1.4-bundle>

Links diretos:

| Arquivo | Link |
|---|---|
| **APK BUNDLE (990 MB, com o jogo)** | [Sims2Mobile-BUNDLE.apk](https://github.com/davimikeben/Sims-2-The/releases/download/v1.4-bundle/Sims2Mobile-BUNDLE.apk) |
| **APK 17 KB (só o app, jogo já extraído)** | [Sims2Mobile-ABRIR-JOGO.apk](https://github.com/davimikeben/Sims-2-The/releases/download/v1.4-bundle/Sims2Mobile-ABRIR-JOGO.apk) |
| **Jogo solto (990 MB, `.cso`)** | [sims2-2048.cso](https://github.com/davimikeben/Sims-2-The/releases/download/v1.3-bundle/sims2-2048.cso) — copie para `Download/Sims2/sims2.cso` e use o APK de 17 KB |
| APK do emulador (73 MB, sem o jogo) | [Sims2Mobile-ARMSX2.apk](https://github.com/davimikeben/Sims-2-The/releases/download/v1.0-sims2-mobile/Sims2Mobile-ARMSX2.apk) |
| Skin (2,1 MB) | [sims2-controller-skin.zip](https://github.com/davimikeben/Sims-2-The/releases/download/v1.0-sims2-mobile/sims2-controller-skin.zip) |
| Mockup | [preview.png](https://github.com/davimikeben/Sims-2-The/releases/download/v1.0-sims2-mobile/preview.png) |
| Guia Mali-G52 | [PERFIL-MALI-G52.md](https://github.com/davimikeben/Sims-2-The/releases/download/v1.0-sims2-mobile/PERFIL-MALI-G52.md) |
| Checksums | [SHA256.txt](https://github.com/davimikeben/Sims-2-The/releases/download/v1.0-sims2-mobile/SHA256.txt) |

O APK também está versionado no repositório, em
[`dist/Sims2Mobile-ARMSX2.apk`](https://github.com/davimikeben/Sims-2-The/blob/cline/qj7c5kzj/dist/Sims2Mobile-ARMSX2.apk)
(caso a página de Releases não abra para você).

---

## 1. Antes de tudo: a verdade tecnica sobre "transformar ROM em APK"

O arquivo que voce mandou e:

```
Sims 2 The (Europe) (EnFrDeEsItNlSvNoDaFi).zip     932 MB
└── Sims 2, The (Europe) (En,Fr,De,Es,It,Nl,Sv,No,Da,Fi).iso   3.385 MB
     └── ISO de DVD = PlayStation 2 (PAL, multi-idioma)
```

Um jogo de PS2 **nao pode** ser convertido em APK: o APK e um app Android (ARM64)
e o jogo e codigo MIPS R5900 + Emotion Engine + Graphics Synthesizer. Quem
traduz uma coisa na outra e um **emulador**. Entao o que existe de verdade — e e
o que este repositorio entrega — e:

```
APK (emulador ARMSX2 + skin do teclado virtual embutida) + ISO do jogo + BIOS do PS2
```

Tambem nao coloquei o ISO dentro do APK de proposito: 3,3 GB em `assets/`
obrigaria o Android a extrair tudo na instalacao (precisaria de ~7 GB livres) e o
app leria o jogo bem mais devagar. O ISO fica no armazenamento do aparelho, que e
mais rapido e permite trocar de jogo sem reinstalar nada.

---

## 2. O que esta pronto neste repositorio

| Arquivo | O que e |
|---|---|
| `dist/Sims2Mobile-ARMSX2.apk` | **O APK**: ARMSX2 2.9.1 (emulador PS2 ARM64, GPL-3) reempacotado, com a skin **Plumbob Glass** embutida e assinado. Android 8.0+ (arm64). |
| `dist/sims2-controller-skin.zip` | So a skin, para importar em qualquer ARMSX2 compativel. |
| `skin/src/*.png` | As 22 imagens do teclado virtual (fonte da arte). |
| `tools/gen_skin.py` | Gerador da arte (Pillow): muda cor/tema e re-renderiza tudo. |
| `tools/build_release.sh` | Empacota o ZIP e re-assina o APK com a skin embutida. |
| `dist/Sims2Mobile-ABRIR-JOGO.apk` | **O app (17 KB)**: extrai o jogo (quando ele vem no APK) e **abre o disco no emulador** via intent de frontend. |
| `app/src/com/sims2/bundle/MainActivity.java` | O app: extração + `openGame()` (entrega o disco ao ARMSX2). |
| `app/src/com/sims2/bundle/GameProvider.java` | `content://com.sims2.bundle.games/sims2.cso` — o `ContentProvider` que entrega o arquivo ao emulador. |
| `tools/iso_to_cso.py` | Gera o CSO **e audita o disco** (estrutura CSO + PVD + `SYSTEM.CNF`/`BOOT2`). `--check arquivo.cso` audita um CSO pronto. |
| `tools/test_iso_to_cso.py` | Testes do conversor (round-trip frame 2048/32768) e dos defeitos que o emulador recusa. |
| `tools/build_bundle_apk.sh` | Empacota o app (+ o jogo) e assina: `bash tools/build_bundle_apk.sh build/sims2.cso` ou `--no-asset`. |
| `docs/PERFIL-MALI-G52.md` | Ajustes exatos para rodar bem em Mali-G52 / celular fraco. |
| `docs/preview.png` | Mockup do teclado virtual. |

---

## 2.1 Por que a tela “Inserir um disco” aparece

O texto **“Inserir um disco com o formato para PlayStation® ou PlayStation®2”** é
do **BIOS do PS2**, não do emulador: é o menu do console **sem disco no drive**.
Ele aparece quando o emulador foi aberto em **Iniciar BIOS** — e isso acontece
porque o jogo extraído em `Download/Sims2` **não entra sozinho na biblioteca**
do ARMSX2 (ele não varre essa pasta), então o único botão óbvio na tela é
*Iniciar BIOS*.

Só extrair o arquivo, portanto, nunca foi suficiente. O que o disco precisa é ser
**entregue** ao emulador. O ARMSX2 aceita um *launch intent* de frontend
(`MainActivityRuntime.handleExternalLaunchIntent`) e `.cso` está na lista
`VMManager::IsDiscFileName`; então o app agora faz isso por você:

```
botão 2  ->  ACTION_VIEW + content://com.sims2.bundle.games/sims2.cso
             (FLAG_GRANT_READ_URI_PERMISSION, package com.armsx2)
          ->  se não atender: ACTION_VIEW em com.armsx2.MainActivity com o
              extra "path" = /storage/emulated/0/Download/Sims2/sims2.cso
          ->  se ainda não: abre o emulador e diz para adicionar a pasta
              Download/Sims2 na biblioteca (Biblioteca › +)
```

Se você preferir o caminho manual (emulador sem o app):

1. Abra o ARMSX2 e **não** toque em *Iniciar BIOS*.
2. **Biblioteca › ⋮ › Adicionar pasta de jogos** e escolha `Download/Sims2`.
3. A capa aparece; toque nela. O jogo entra no drive virtual e o BIOS é
   dispensado (boot rápido).

Para conferir que o arquivo em si está bom, rode
`python3 tools/iso_to_cso.py --check sims2.cso`: ele valida o CSO exatamente como
o `CsoFileReader` e o disco como o BIOS (PVD na trilha 16 + `SYSTEM.CNF` com
`BOOT2`). Se o CSO estiver íntegro, o problema **é sempre** a forma de abrir — não
o arquivo.

---

## 3. Instalacao no celular

### 3.1 Caminho curto: `Sims2Mobile-BUNDLE.apk` (o jogo vai dentro)

1. **Instale** o APK (990 MB). Se ja existe uma versao antiga do "Sims 2 Mobile
   (Bundle)" no aparelho, **desinstale antes** (a assinatura mudou).
2. Abra o app e toque em **1. Instalar o jogo no celular** (ele autoriza
   "Acesso a todos os arquivos" e grava `Download/Sims2/sims2.cso`).
3. Toque em **2. Abrir o jogo no ARMSX2** — o app entrega o disco ao emulador,
   que abre o jogo em vez do menu do BIOS.
4. Na 1ª vez o ARMSX2 pede a **BIOS** (`scphXXXXX.bin`, de um console que voce
   possua) e a skin (**NetherSX2** = Plumbob Glass).
5. Rode o assistente **Desempenho** e siga `docs/PERFIL-MALI-G52.md`.

> Ja tem o `sims2.cso` extraido de uma versao anterior? Baixe so o
> `Sims2Mobile-ABRIR-JOGO.apk` (**17 KB**) e pule o passo 2: o app usa o arquivo
> que ja esta la — 1 GB economizado.

### 3.2 Caminho longo: `Sims2Mobile-ARMSX2.apk` (emulador com a skin)

1. **Copie para o celular**: `dist/Sims2Mobile-ARMSX2.apk` e o seu
   `Sims 2, The (...).iso` (extraia do zip antes — o emulador le o `.iso`, nao o
   `.zip`).
2. **Instale o APK**. Se ja tem o ARMSX2/AetherSX2 instalado, **desinstale
   antes**: este APK tem assinatura propria (de homebrew), entao o Android vai
   recusar a atualizacao por cima.
3. **BIOS**: o emulador precisa de um dump da BIOS do PS2 (`scphXXXXX.bin`), de
   um console que voce possua. Coloque na pasta que ele pedir no assistente
   inicial.
4. Na tela **Skins de Controle Personalizadas**, a skin ja vem embutida: escolha
   **NetherSX2** (e o slot onde a Plumbob Glass foi gravada). Se preferir a
   versao avulsa: **Importar .zip de skin…** -> `sims2-controller-skin.zip`.
5. **Adicione o jogo**: **Biblioteca > ⋮ > Adicionar pasta de jogos** apontando
   para a pasta do `.iso`, toque na capa e jogue. Rode o assistente
   **Desempenho** e siga `docs/PERFIL-MALI-G52.md`.

> ⚠️ Desempenho honesto: PS2 em celular com Mali-G52 (Helio G85/G70, Exynos 850…)
> e o limite do limite. The Sims 2 e um jogo 3D de mundo aberto: espere algo
> entre **15 e 30 fps**, com resolucao interna reduzida. Com Snapdragon/Adreno
> sobe bastante. Para rodar liso de verdade, a versao de **GBA/DS** do The Sims 2
> e outra liga (mas nao e a que esta no seu zip).

---

## 4. O teclado virtual "Plumbob Glass"

A arte foi desenhada para o desenho real do ARMSX2 (`ContentScale.Fit` dentro de
uma caixa quadrada, com `alpha` controlado pelo slider de opacidade) — por isso
todo botão é quadrado com fundo **transparente**, nunca preto.

- 22 imagens: `cross`, `circle`, `square`, `triangle`, `up/down/left/right`,
  `l1 l2 r1 r2`, `l3 r3`, `start`, `select`, `macro1..4`, `analog_base`,
  `analog_stick`.
- Estilo: vidro escuro (gradiente + especular + bisel), aro de menta com brilho,
  símbolos embossados nas cores do DualShock e losango *plumbob* nos analógicos.
- Três camadas de antialias: formas desenhadas a 4× e reduzidas com Lanczos,
  halo radial com *clamp* nas bordas (senão o brilho virava uma "placa
  quadrada" ao escalar) e queda suave (smoothstep) nos cortes de luz.

Para mudar o tema:

```bash
# edite as cores no topo de tools/gen_skin.py  (MINT, GOLD, PLUMBOB, etc.)
python3 tools/gen_skin.py --out skin/src --preview docs/preview.png
```

Depois é só reimportar o ZIP (ou rodar `tools/build_release.sh` para gerar o APK).

### Ajustes do teclado dentro do jogo

Em **Configurações › Controles na tela**: opacidade, tamanho, posição de cada
botão (arraste), multi-touch, turbo, macros (M1–M4) e layout por jogo. A skin não
tem variante "pressionada": o app já aplica escurecimento + encolhimento ao
tocar, então o feedback continua igual.

---

## 5. Como os APKs foram construídos (reprodutível)

Pré-requisitos em `.toolchain/` (fora do git): JDK 17 (`jdk-17.0.21+9`),
Android build-tools 34 (`sdk/build-tools/34.0.0`) e a platform 34
(`sdk/platforms/android-34/android.jar`).

```bash
# 1. APK do emulador com a skin (73 MB)
curl -LO https://github.com/ARMSX2/ARMSX2/releases/download/2.9.1/ARMSX2-2.9.1-legacy-armv8.0-sdk26.apk
mv ARMSX2-2.9.1-legacy-armv8.0-sdk26.apk build/armsx2-legacy.apk
python3 tools/gen_skin.py --out skin/src --preview docs/preview.png
bash tools/build_release.sh

# 2. jogo -> CSO (já audita o disco) e o app do jogo
python3 tools/iso_to_cso.py "Sims 2, The (...).iso" build/sims2.cso
bash tools/build_bundle_apk.sh build/sims2.cso    # dist/Sims2Mobile-BUNDLE.apk
bash tools/build_bundle_apk.sh --no-asset         # dist/Sims2Mobile-ABRIR-JOGO.apk

# 3. testes do conversor
python3 -m unittest tools.test_iso_to_cso -v
```

`build_release.sh` substitui `assets/controller_skins/nethersx2*` pela nossa
arte (os dois slots embutidos do app). `build_bundle_apk.sh` compila
`MainActivity.java` + `GameProvider.java` com o `aapt2`/`d8` do build-tools,
assa o tamanho do asset, empacota o `.cso` com `zip -0` (ele já está comprimido)
e assina. Os dois rodam `zipalign -p 4` e `apksigner` (v1+v2+v3) usando
`build/sims2.keystore`, criado na primeira execução.

O código do emulador é GPL-3.0 e está em <https://github.com/ARMSX2/ARMSX2>.
Este repositório **não** redistribui a BIOS do PS2 — você usa a sua.

---


## 6. Problemas comuns

| Sintoma | Causa / solução |
|---|---|
| "App não instalado" | Existe outro ARMSX2/AetherSX2 com assinatura diferente. Desinstale o antigo. |
| "Não foi possível analisar o pacote" | Cópia corrompida — copie de novo (73 MB) e confira o sha256. |
| **“Inserir um disco com o formato para PlayStation ou PlayStation 2”** | É a tela do **BIOS sem disco**: você entrou em *Iniciar BIOS*, que é o menu do console, não o jogo. Use o botão **2. Abrir o jogo no ARMSX2** do app (v1.4+) — ele entrega o disco ao emulador. Sem o app: **Biblioteca › ⋮ › Adicionar pasta de jogos** em `Download/Sims2` e abra pela capa. Para descartar arquivo ruim: `python3 tools/iso_to_cso.py --check sims2.cso` (CSO até a v1.1 tinha offsets relativos no índice — corrigido na v1.2, e agora o script recusa esse arquivo) |
| “App não instalado” ao atualizar o app do jogo | A assinatura mudou na v1.4: desinstale o “Sims 2 Mobile (Bundle)” antigo e instale de novo — o `sims2.cso` em `Download/Sims2` **não** é apagado |
| Tela preta com áudio | Troque Renderizador Vulkan ↔ OpenGL (veja `docs/PERFIL-MALI-G52.md`). |
| Skin importada mas não aparece | O ZIP precisa ter os PNGs na **raiz** (`ic_controller_*.png`), sem subpasta. |
| Jogo não abre | Falta BIOS, ou o `.iso` ainda está dentro do `.zip`. |
| Muito lento | Perfil de Speedhack **Low-End**, Resolução de Exibição **1x PS2**, Frame Skip 1–2. |

---

## 7. Verificação dos arquivos

```
dist/SHA256.txt
```

| Arquivo | SHA-256 |
|---|---|
| `Sims2Mobile-ARMSX2.apk` | `c604cfb517dcad2fee0dd0585d3b7489d96e09d72cec9a9243ba09726c8c5464` |
| `sims2-controller-skin.zip` | `b270ee804f5fa18c5fb62125fa8430975eeeaa9c8d4c15a9b61129da923b86d0` |
| `Sims2Mobile-BUNDLE.apk` (v1.4) | `5c334d46d270b7623f34afe052eff2424c468fd0e2a0dd7663e2b9e382858275` |
| `Sims2Mobile-ABRIR-JOGO.apk` (v1.4) | `c114db94de7a044e73fdd44a3d294ae960de7bcbb8da2113a6e3d8cd260b4dc3` |
| `sims2.cso` (dentro do BUNDLE = `sims2-2048.cso`) | `ef35bb9fcbf43b6bdf7b45bc02b609d43a75675befde13f84a56089b062cab57` |

O CSO publicado é **auditado** pelo próprio script (o mesmo teste que o emulador e
o BIOS fazem):

```bash
python3 tools/iso_to_cso.py --check sims2.cso
```

O APK está assinado com certificado próprio de homebrew:

```
CN=Sims 2 Mobile, OU=Homebrew, O=Sims2Mobile, L=BR, C=BR
SHA-256: 0ab67d1838f0e157f0ddf806f7023d4832fdb0818c567424fff9e141f9935ea6
Schemes: APK Signature Scheme v2 + v3
```
