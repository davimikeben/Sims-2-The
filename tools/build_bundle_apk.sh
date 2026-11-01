#!/usr/bin/env bash
# Gera o APK "tudo em um": app instalador + o jogo (CSO) dentro de assets/.
#
#   bash tools/build_bundle_apk.sh build/sims2.cso       # APK com o jogo (~1,0 GB)
#   bash tools/build_bundle_apk.sh --no-asset            # APK leve (~20 KB)
#
# Saida: dist/Sims2Mobile-BUNDLE.apk (ou dist/Sims2Mobile-ABRIR-JOGO.apk em --no-asset)
#
# O APK nao tem jogo "executavel" por dentro (isso nao existe para PS2): o emulador
# precisa de um arquivo no sistema de arquivos. Entao o app extrai o CSO para
# Download/Sims2/sims2.cso e, no botao "2. Abrir o jogo", entrega esse arquivo ao
# ARMSX2 por um intent de frontend (ACTION_VIEW + content://) - unico jeito de o disco
# entrar no drive virtual sem passar por "Iniciar BIOS".
#
# Em --no-asset o APK nao carrega o jogo: serve para quem ja tem o .cso em
# Download/Sims2 (extraido pela versao anterior) e so precisa do app corrigido.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
WORK="$ROOT/build/bundle"
SDK="$ROOT/.toolchain/sdk"
BT="$SDK/build-tools/34.0.0"
PLAT="$SDK/platforms/android-34/android.jar"
JAVA_HOME="${JAVA_HOME:-$ROOT/.toolchain/jdk-17.0.21+9}"
export JAVA_HOME
export PATH="$JAVA_HOME/bin:$PATH"

NO_ASSET=0
CSO=""
if [ "${1:-}" = "--no-asset" ]; then
  NO_ASSET=1
  OUT="$DIST/Sims2Mobile-ABRIR-JOGO.apk"
else
  CSO="${1:-$ROOT/build/sims2.cso}"
  OUT="$DIST/Sims2Mobile-BUNDLE.apk"
  [ -f "$CSO" ] || { echo "CSO nao encontrado: $CSO (ou use --no-asset)"; exit 1; }
  CSO="$(cd "$(dirname "$CSO")" && pwd)/$(basename "$CSO")"   # absoluto: o script faz cd depois
fi

if [ "$NO_ASSET" = 1 ]; then
  SIZE=0
  echo "==> jogo: (nenhum) - APK leve, usa o .cso que ja estiver em Download/Sims2"
else
  SIZE=$(stat -c%s "$CSO")
  echo "==> jogo: $CSO ($(numfmt --to=iec "$SIZE"))"
fi

rm -rf "$WORK"
mkdir -p "$WORK/classes" "$WORK/dex" "$WORK/stage/assets" "$DIST"

# ---- 1. fonte com o tamanho real do asset assado dentro -------------------- #
SRC="$WORK/MainActivity.java"
sed "s|ASSET_SIZE = 0L; // BUILD_SIZE|ASSET_SIZE = ${SIZE}L; // BUILD_SIZE|" \
    "$ROOT/app/src/com/sims2/bundle/MainActivity.java" > "$SRC"
grep -q "ASSET_SIZE = ${SIZE}L" "$SRC" || { echo "falha ao assar ASSET_SIZE"; exit 1; }
cp "$ROOT/app/src/com/sims2/bundle/GameProvider.java" "$WORK/GameProvider.java"

# ---- 2. manifest -> base.apk (sem recursos: usa tema do framework) -------- #
echo "==> aapt2 link"
"$BT/aapt2" link -o "$WORK/base.apk" -I "$PLAT" \
    --manifest "$ROOT/app/AndroidManifest.xml" \
    --min-sdk-version 26 --target-sdk-version 34

# ---- 3. compila + dexifica ------------------------------------------------ #
echo "==> javac + d8"
javac -encoding UTF-8 --release 8 -classpath "$PLAT" -d "$WORK/classes" \
    "$SRC" "$WORK/GameProvider.java"
"$BT/d8" --release --min-api 26 --lib "$PLAT" --output "$WORK/dex" \
    "$WORK"/classes/com/sims2/bundle/*.class

# ---- 4. monta o APK ------------------------------------------------------- #
echo "==> montando APK"
cp "$WORK/base.apk" "$WORK/app.apk"
cd "$WORK"
cp dex/classes.dex .
zip -q -9 app.apk classes.dex
if [ "$NO_ASSET" = 0 ]; then
  cp "$CSO" stage/assets/sims2.cso
  # -0 = armazenar: o CSO ja esta comprimido, recomprimir so gasta tempo/CPU
  ( cd stage && zip -q -0 ../app.apk assets/sims2.cso )
fi
cd "$ROOT"

# ---- 5. alinhamento + assinatura ------------------------------------------ #
echo "==> zipalign"
"$BT/zipalign" -p -f 4 "$WORK/app.apk" "$WORK/app-aligned.apk"

KS="$ROOT/build/sims2.keystore"
if [ ! -f "$KS" ]; then
  echo "==> keystore"
  keytool -genkeypair -v -keystore "$KS" -alias sims2 -keyalg RSA -keysize 2048 \
    -validity 10000 -storepass sims2mobile -keypass sims2mobile \
    -dname "CN=Sims 2 Mobile, OU=Homebrew, O=Sims2Mobile, L=BR, C=BR" >/dev/null 2>&1
fi

echo "==> apksigner"
"$BT/apksigner" sign --ks "$KS" --ks-pass pass:sims2mobile --key-pass pass:sims2mobile \
  --v1-signing-enabled true --v2-signing-enabled true --v3-signing-enabled true \
  --out "$OUT" "$WORK/app-aligned.apk"

"$BT/apksigner" verify "$OUT" && echo "assinatura OK"
"$BT/aapt2" dump badging "$OUT" | grep -E '^(package|launchable-activity)' || true
ls -l "$OUT"
