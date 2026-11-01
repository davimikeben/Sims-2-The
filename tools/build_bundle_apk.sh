#!/usr/bin/env bash
# Gera o APK "tudo em um": app instalador + o jogo (CSO) dentro de assets/.
#
#   bash tools/build_bundle_apk.sh build/sims2-f32k.cso
#
# Saida: dist/Sims2Mobile-BUNDLE.apk
#
# O APK nao tem jogo "executavel" por dentro (isso nao existe para PS2): o
# emulador precisa de um arquivo no sistema de arquivos. Entao o app extrai o
# CSO para Download/Sims2/sims2.cso na primeira execucao e depois so abre o
# ARMSX2. O CSO ocupa ~4x menos que o ISO original.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CSO="${1:-$ROOT/build/sims2-f32k.cso}"
DIST="$ROOT/dist"
WORK="$ROOT/build/bundle"
SDK="$ROOT/.toolchain/sdk"
BT="$SDK/build-tools/34.0.0"
PLAT="$SDK/platforms/android-34/android.jar"
JAVA_HOME="${JAVA_HOME:-$ROOT/.toolchain/jdk-17.0.21+9}"
export JAVA_HOME
export PATH="$JAVA_HOME/bin:$PATH"

[ -f "$CSO" ] || { echo "CSO nao encontrado: $CSO"; exit 1; }
CSO="$(cd "$(dirname "$CSO")" && pwd)/$(basename "$CSO")"   # absoluto: o script faz cd depois
SIZE=$(stat -c%s "$CSO")
echo "==> jogo: $CSO ($(numfmt --to=iec "$SIZE"))"

rm -rf "$WORK"
mkdir -p "$WORK/classes" "$WORK/dex" "$WORK/stage/assets" "$DIST"

# ---- 1. fonte com o tamanho real do asset assado dentro -------------------- #
SRC="$WORK/MainActivity.java"
sed "s|ASSET_SIZE = 0L; // BUILD_SIZE|ASSET_SIZE = ${SIZE}L; // BUILD_SIZE|" \
    "$ROOT/app/src/com/sims2/bundle/MainActivity.java" > "$SRC"
grep -q "ASSET_SIZE = ${SIZE}L" "$SRC" || { echo "falha ao assar ASSET_SIZE"; exit 1; }

# ---- 2. manifest -> base.apk (sem recursos: usa tema do framework) -------- #
echo "==> aapt2 link"
"$BT/aapt2" link -o "$WORK/base.apk" -I "$PLAT" \
    --manifest "$ROOT/app/AndroidManifest.xml" \
    --min-sdk-version 26 --target-sdk-version 34

# ---- 3. compila + dexifica ------------------------------------------------ #
echo "==> javac + d8"
javac -encoding UTF-8 --release 8 -classpath "$PLAT" -d "$WORK/classes" "$SRC"
"$BT/d8" --release --min-api 26 --lib "$PLAT" --output "$WORK/dex" \
    "$WORK"/classes/com/sims2/bundle/*.class

# ---- 4. monta o APK ------------------------------------------------------- #
echo "==> montando APK"
cp "$WORK/base.apk" "$WORK/app.apk"
cd "$WORK"
cp dex/classes.dex .
zip -q -9 app.apk classes.dex
cp "$CSO" stage/assets/sims2.cso
# -0 = armazenar: o CSO ja esta comprimido, recomprimir so gasta tempo/CPU
( cd stage && zip -q -0 ../app.apk assets/sims2.cso )
cd "$ROOT"

# ---- 5. alinhamento + assinatura ----------------------------------------- #
echo "==> zipalign"
"$BT/zipalign" -p -f 4 "$WORK/app.apk" "$WORK/app-aligned.apk"

KS="$ROOT/build/sims2.keystore"
if [ ! -f "$KS" ]; then
  keytool -genkeypair -v -keystore "$KS" -alias sims2 -keyalg RSA -keysize 2048 \
    -validity 10000 -storepass sims2mobile -keypass sims2mobile \
    -dname "CN=Sims 2 Mobile, OU=Homebrew, O=Sims2Mobile, L=BR, C=BR" >/dev/null 2>&1
fi

echo "==> apksigner"
"$BT/apksigner" sign --ks "$KS" --ks-pass pass:sims2mobile --key-pass pass:sims2mobile \
  --v1-signing-enabled true --v2-signing-enabled true --v3-signing-enabled true \
  --out "$DIST/Sims2Mobile-BUNDLE.apk" "$WORK/app-aligned.apk"

"$BT/apksigner" verify "$DIST/Sims2Mobile-BUNDLE.apk" && echo "assinatura OK"
ls -l "$DIST/Sims2Mobile-BUNDLE.apk"
