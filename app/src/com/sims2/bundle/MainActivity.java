package com.sims2.bundle;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.List;

/**
 * O jogo vem DENTRO deste APK, comprimido em CSO (formato que o ARMSX2 lê
 * nativamente via CsoFileReader). Na primeira execução o app extrai o arquivo
 * para Download/Sims2/sims2.cso e depois só abre o emulador.
 *
 * Não há nada de mágica: o emulador precisa de um arquivo no sistema de
 * arquivos, então a extração é obrigatória — mas o CSO ocupa ~3,8x menos
 * espaço que o ISO original (3,4 GB -> ~820 MB).
 */
public class MainActivity extends Activity {

    /** Nome do arquivo dentro de assets/ e o tamanho esperado (bytes). */
    private static final String ASSET = "sims2.cso";
    // O tamanho real do CSO e assado aqui pelo build (tools/build_bundle_apk.sh).
    private static final long ASSET_SIZE = 0L; // BUILD_SIZE
    private static final String EMULATOR_PKG = "com.armsx2";
    /** Activity que trata o intent de frontend (ACTION_VIEW / extra "path"). */
    private static final String EMULATOR_MAIN = "com.armsx2.MainActivity";

    private static final int BG = Color.parseColor("#0B1315");
    private static final int FG = Color.parseColor("#E8FAF4");
    private static final int MINT = Color.parseColor("#54E8A0");
    private static final int DIM = Color.parseColor("#8FA8A3");

    private final Handler ui = new Handler(Looper.getMainLooper());
    private TextView status;
    private TextView detail;
    private ProgressBar progress;
    private Button extractBtn;
    private Button playBtn;
    private volatile boolean busy = false;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);

        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(BG);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(24);
        root.setPadding(pad, pad, pad, pad);
        scroll.addView(root);

        TextView title = new TextView(this);
        title.setText("Sims 2 Mobile");
        title.setTextColor(FG);
        title.setTextSize(30);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        root.addView(title);

        TextView sub = new TextView(this);
        sub.setText("Jogo embutido no APK • teclado virtual Plumbob Glass");
        sub.setTextColor(MINT);
        sub.setTextSize(14);
        root.addView(sub);

        detail = new TextView(this);
        detail.setTextColor(DIM);
        detail.setTextSize(13);
        detail.setPadding(0, dp(18), 0, dp(8));
        root.addView(detail);

        status = new TextView(this);
        status.setTextColor(FG);
        status.setTextSize(15);
        status.setPadding(0, dp(8), 0, dp(12));
        root.addView(status);

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(1000);
        progress.setVisibility(View.GONE);
        root.addView(progress, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(10)));

        extractBtn = mkButton("1. Instalar o jogo no celular");
        extractBtn.setOnClickListener(v -> startExtract());
        root.addView(extractBtn);

        playBtn = mkButton("2. Abrir o jogo no ARMSX2");
        playBtn.setOnClickListener(v -> openGame());
        root.addView(playBtn);

        TextView note = new TextView(this);
        note.setText("\nA BIOS do PS2 (scphXXXXX.bin) é escolhida por você na tela "
                + "\"Selecione sua BIOS\" do emulador — ela não vem no APK.\n\n"
                + "Abra o jogo pelo botão 2, nunca por \"Iniciar BIOS\": o BIOS é o menu do "
                + "console sem disco e mostra \"Inserir um disco com o formato para "
                + "PlayStation ou PlayStation 2\".\n\n"
                + "Depois de extrair, você pode desinstalar este app: o jogo continua "
                + "em Download/Sims2/" + GameProvider.FILE_NAME + ".");
        note.setTextColor(DIM);
        note.setTextSize(12);
        root.addView(note);

        setContentView(scroll);
        refresh();
    }

    private Button mkButton(String label) {
        Button bt = new Button(this);
        bt.setText(label);
        bt.setTextColor(Color.parseColor("#08120E"));
        bt.setBackgroundColor(MINT);
        bt.setTextSize(16);
        bt.setAllCaps(false);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(56));
        lp.topMargin = dp(12);
        bt.setLayoutParams(lp);
        return bt;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    // ----------------------------------------------------------------- \\
    //  Estado
    // ----------------------------------------------------------------- \\

    /** Caminho do jogo extraido (usado tambem pelo GameProvider). */
    static File target() {
        File dir = new File(Environment.getExternalStoragePublicDirectory(
                Environment.DIRECTORY_DOWNLOADS), "Sims2");
        return new File(dir, GameProvider.FILE_NAME);
    }

    private void refresh() {
        File t = target();
        boolean ready = t.isFile() && (ASSET_SIZE <= 0 || t.length() == ASSET_SIZE);
        boolean emu = isEmulatorInstalled();
        boolean temJogoNoApk = ASSET_SIZE > 0;
        if (ready) {
            status.setText("Jogo pronto: " + human(t.length()) + " em " + t.getParent());
            extractBtn.setText("Extrair novamente");
            extractBtn.setEnabled(temJogoNoApk);
        } else {
            status.setText(temJogoNoApk
                    ? "Jogo dentro deste APK: " + human(ASSET_SIZE)
                      + " (comprimido). Toque em 1 para extrair."
                    : "Nenhum jogo em " + t.getParent() + ".\n"
                      + "Copie o " + GameProvider.FILE_NAME + " para essa pasta (ou use o "
                      + "APK BUNDLE, que já traz o jogo).");
            extractBtn.setText(temJogoNoApk
                    ? "1. Instalar o jogo no celular"
                    : "1. Este APK não traz o jogo");
            extractBtn.setEnabled(temJogoNoApk);
        }
        playBtn.setText(emu ? "2. Abrir o jogo no ARMSX2" : "2. Abrir (instale o ARMSX2)");
        playBtn.setEnabled(true);
        detail.setText("Destino: " + t.getAbsolutePath());
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (!busy) refresh();
    }

    // ----------------------------------------------------------------- \\
    //  Permissao de armazenamento
    // ----------------------------------------------------------------- \\

    private boolean hasStoragePermission() {
        if (Build.VERSION.SDK_INT >= 30) {
            return Environment.isExternalStorageManager();
        }
        return checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE)
                == PackageManager.PERMISSION_GRANTED;
    }

    private void requestStoragePermission() {
        try {
            if (Build.VERSION.SDK_INT >= 30) {
                Intent i = new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                        Uri.parse("package:" + getPackageName()));
                startActivity(i);
            } else {
                requestPermissions(new String[]{Manifest.permission.WRITE_EXTERNAL_STORAGE}, 1001);
            }
        } catch (Exception e) {
            toast("Autorize o acesso a arquivos nas configuracoes do app");
        }
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] p, int[] r) {
        super.onRequestPermissionsResult(code, p, r);
        if (code == 1001) {
            if (r.length > 0 && r[0] == PackageManager.PERMISSION_GRANTED) startExtract();
            else toast("Sem permissao nao da para gravar o jogo");
        }
    }

    // ----------------------------------------------------------------- \\
    //  Emulador
    // ----------------------------------------------------------------- \\

    private void launchEmulator() {
        Intent i = getPackageManager().getLaunchIntentForPackage(EMULATOR_PKG);
        if (i == null) {
            toast("Instale primeiro o Sims2Mobile-ARMSX2.apk (o emulador)");
            return;
        }
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(i);
    }

    private boolean isEmulatorInstalled() {
        return getPackageManager().getLaunchIntentForPackage(EMULATOR_PKG) != null;
    }

    /**
     * Abre o jogo DENTRO do emulador (o disco entra no drive virtual).
     *
     * Só extrair o arquivo não basta: o ARMSX2 não varre Download/Sims2 sozinho, então a
     * biblioteca fica vazia e o usuário acaba tocando em "Iniciar BIOS" — que é o menu do
     * console sem disco, ou seja, a tela "Inserir um disco com o formato para PlayStation
     * ou PlayStation 2". O emulador aceita um intent de frontend
     * (MainActivityRuntime.handleExternalLaunchIntent), então entregamos o disco por ele:
     *
     *   1. ACTION_VIEW + content:// (é o que ES-DE/Daijishō/Cocoon usam; o filtro do
     *      ARMSX2 declara os schemes content e file);
     *   2. ACTION_VIEW na MainActivity com o extra "path" (lido pelo handleExternalLaunchIntent);
     *   3. por último, só abrir o emulador e explicar como adicionar a pasta na biblioteca.
     */
    private void openGame() {
        final File game = target();
        if (!game.isFile()) {
            toast("Extraia o jogo primeiro (botão 1)");
            startExtract();
            return;
        }
        if (!isEmulatorInstalled()) {
            toast("Instale primeiro o Sims2Mobile-ARMSX2.apk (o emulador)");
            return;
        }

        // 1) content:// — o caminho "de frontend", com permissão de leitura para o emulador.
        Intent view = new Intent(Intent.ACTION_VIEW);
        view.setDataAndType(GameProvider.uri(), GameProvider.MIME);
        view.setPackage(EMULATOR_PKG);
        view.addCategory(Intent.CATEGORY_DEFAULT);
        view.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
                | Intent.FLAG_ACTIVITY_NEW_TASK);
        if (tryStart(view, game)) return;

        // 2) intent explícito com o caminho do arquivo (o emulador tem acesso total).
        Intent byPath = new Intent(Intent.ACTION_VIEW);
        byPath.setClassName(EMULATOR_PKG, EMULATOR_MAIN);
        byPath.putExtra("path", game.getAbsolutePath());
        byPath.putExtra("game", game.getAbsolutePath());
        byPath.putExtra("rom", game.getAbsolutePath());
        byPath.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        if (tryStart(byPath, game)) return;

        // 3) não deu: abre o emulador e ensina o caminho da biblioteca.
        launchEmulator();
        toast("No ARMSX2: Biblioteca › + › adicione a pasta Download/Sims2 "
                + "(não use \"Iniciar BIOS\")");
    }

    /** Tenta abrir o jogo; devolve true quando o emulador atendeu o intent. */
    private boolean tryStart(Intent intent, File game) {
        try {
            ResolveInfo ri = getPackageManager().resolveActivity(intent, 0);
            if (ri == null) return false;
            grantReadPermission(intent);
            startActivity(intent);
            status.setText("Abrindo " + game.getName() + " no emulador...");
            return true;
        } catch (ActivityNotFoundException e) {
            return false;
        } catch (SecurityException e) {
            return false;
        } catch (Exception e) {
            return false;
        }
    }

    /**
     * O ARMSX2 guarda o jogo em "recentes" e no boot imediato usa o grant do intent;
     * oferecer a permissão persistente evita "acesso negado" nas próximas aberturas.
     */
    private void grantReadPermission(Intent intent) {
        if (intent.getData() == null) return;
        try {
            List<ResolveInfo> all = getPackageManager()
                    .queryIntentActivities(intent, PackageManager.MATCH_DEFAULT_ONLY);
            for (ResolveInfo ri : all) {
                if (ri.activityInfo != null && EMULATOR_PKG.equals(ri.activityInfo.packageName)) {
                    grantUriPermission(EMULATOR_PKG, intent.getData(),
                            Intent.FLAG_GRANT_READ_URI_PERMISSION);
                }
            }
        } catch (Exception ignored) {
        }
    }

    private void toast(String m) {
        Toast.makeText(this, m, Toast.LENGTH_LONG).show();
    }

    // ----------------------------------------------------------------- \\
    //  Extracao do jogo (asset -> Download/Sims2/sims2.cso)
    // ----------------------------------------------------------------- \\

    private void startExtract() {
        if (busy) return;
        if (ASSET_SIZE <= 0) {
            toast("Este APK não traz o jogo: copie o " + GameProvider.FILE_NAME
                    + " para Download/Sims2");
            return;
        }
        if (!hasStoragePermission()) {
            toast("Autorize \"Acesso a todos os arquivos\" para gravar o jogo");
            requestStoragePermission();
            return;
        }
        final File out = target();
        final File dir = out.getParentFile();
        if (dir != null && !dir.exists() && !dir.mkdirs()) {
            toast("Nao consegui criar " + dir);
            return;
        }
        busy = true;
        extractBtn.setEnabled(false);
        progress.setVisibility(View.VISIBLE);
        progress.setProgress(0);
        status.setText("Extraindo o jogo...");

        new Thread(() -> {
            long written = 0;
            long total = ASSET_SIZE > 0 ? ASSET_SIZE : 1;
            File tmp = new File(dir, "sims2.cso.part");
            try (InputStream in = getAssets().open(ASSET);
                 FileOutputStream fos = new FileOutputStream(tmp)) {
                byte[] buf = new byte[4 * 1024 * 1024];
                int n;
                int tick = 0;
                while ((n = in.read(buf)) > 0) {
                    fos.write(buf, 0, n);
                    written += n;
                    if ((++tick & 3) == 0) {
                        final int pct = (int) Math.min(1000, written * 1000 / total);
                        final long w = written;
                        ui.post(() -> {
                            progress.setProgress(pct);
                            status.setText("Extraindo... " + (pct / 10) + "%  ("
                                    + human(w) + " de " + human(total) + ")");
                        });
                    }
                }
                fos.flush();
                fos.getFD().sync();
            } catch (Exception e) {
                final String msg = e.getClass().getSimpleName() + ": " + e.getMessage();
                ui.post(() -> {
                    busy = false;
                    progress.setVisibility(View.GONE);
                    extractBtn.setEnabled(true);
                    status.setText("Falhou: " + msg);
                });
                tmp.delete();
                return;
            }
            // troca o arquivo final so quando a copia terminou inteira
            if (out.exists()) out.delete();
            boolean ok = tmp.renameTo(out);
            final long w = written;
            final boolean success = ok && out.length() == written;
            ui.post(() -> {
                busy = false;
                progress.setVisibility(View.GONE);
                extractBtn.setEnabled(true);
                if (success) {
                    status.setText("Pronto! " + human(w) + " gravados em "
                            + out.getParent() + " — toque em 2 para abrir o jogo.");
                    toast("Jogo instalado. Toque em 2 para abrir no ARMSX2.");
                } else {
                    status.setText("Nao consegui finalizar o arquivo (espaco livre?)");
                }
                refresh();
            });
        }, "extract").start();
    }

    private String human(long b) {
        if (b <= 0) return "?";
        if (b >= 1024L * 1024 * 1024) return String.format("%.2f GB", b / 1073741824.0);
        return String.format("%.0f MB", b / 1048576.0);
    }
}
