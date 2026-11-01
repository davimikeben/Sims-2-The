#!/usr/bin/env bash
# Empacota o skin pack (ZIP importavel no ARMSX2) e gera um APK com a skin
# embutida, assinado com uma chave propria.
#
#   bash tools/build_release.sh
#
# Saidas em dist/:
#   sims2-controller-skin.zip   -> importar no app (Skins > Importar .zip)
#   Sims2Mobile-ARMSX2.apk      -> APK com a skin ja embutida (sideload)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/skin/src"
DIST="$ROOT/dist"
BUILD="$ROOT/build"
SDK="$ROOT/.toolchain/sdk"
BT="$SDK/build-tools/34.0.0"
JAVA_HOME="${JAVA_HOME:-$ROOT/.toolchain/jdk-17.0.21+9}"
export JAVA_HOME
export PATH="$JAVA_HOME/bin:$PATH"

mkdir -p "$DIST"

# --------------------------------------------------------------------------- #
# 1) ZIP do skin pack
# --------------------------------------------------------------------------- #
echo "==> skin pack"
rm -f "$DIST/sims2-controller-skin.zip"
cat > "$SRC/LEIA-ME.txt" <<'TXT'
PLUMBOB GLASS - teclado virtual (skin) para ARMSX2 / PCSX2 Android

Como usar:
  1. Abra o ARMSX2
  2. Configuracoes > Controles na tela (Touch controls) > aba Skins
  3. "Importar .zip" e escolha este arquivo
  4. Selecione a skin "sims2" e pronto

Cada imagem e um botao. Para editar a arte, veja tools/gen_skin.py.
TXT
(cd "$SRC" && zip -q -9 -X "$DIST/sims2-controller-skin.zip" *.png LEIA-ME.txt)
echo "    $(du -h "$DIST/sims2-controller-skin.zip" | cut -f1)  $DIST/sims2-controller-skin.zip"

# --------------------------------------------------------------------------- #
# 2) APK com a skin embutida
# --------------------------------------------------------------------------- #
BASE_APK="${1:-$BUILD/armsx2-legacy.apk}"
OUT_APK="$DIST/Sims2Mobile-ARMSX2.apk"
echo "==> APK base: $BASE_APK"

WORK="$BUILD/apkwork"
rm -rf "$WORK"
mkdir -p "$WORK/assets/controller_skins/nethersx2" \
         "$WORK/assets/controller_skins/nethersx2_old"
cp "$SRC"/*.png "$WORK/assets/controller_skins/nethersx2/"
cp "$SRC"/*.png "$WORK/assets/controller_skins/nethersx2_old/"

cp "$BASE_APK" "$WORK/app.apk"
cd "$WORK"
# remove a arte original das duas skins embutidas e coloca a nossa
zip -q -d app.apk 'assets/controller_skins/*' >/dev/null
zip -q -9 -r app.apk assets
cd "$ROOT"

# --------------------------------------------------------------------------- #
# 3) alinhamento + assinatura
# --------------------------------------------------------------------------- #
echo "==> zipalign"
"$BT/zipalign" -p -f 4 "$WORK/app.apk" "$WORK/app-aligned.apk"

KS="$BUILD/sims2.keystore"
if [ ! -f "$KS" ]; then
  echo "==> keystore"
  keytool -genkeypair -v -keystore "$KS" -alias sims2 -keyalg RSA -keysize 2048 \
    -validity 10000 -storepass sims2mobile -keypass sims2mobile \
    -dname "CN=Sims 2 Mobile, OU=Homebrew, O=Sims2Mobile, L=BR, C=BR" >/dev/null 2>&1
fi

echo "==> apksigner"
"$BT/apksigner" sign --ks "$KS" --ks-pass pass:sims2mobile --key-pass pass:sims2mobile \
  --v1-signing-enabled true --v2-signing-enabled true --v3-signing-enabled true \
  --out "$OUT_APK" "$WORK/app-aligned.apk"

"$BT/apksigner" verify --print-certs "$OUT_APK" | head -5
echo "    $(du -h "$OUT_APK" | cut -f1)  $OUT_APK"
