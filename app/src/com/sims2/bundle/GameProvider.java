package com.sims2.bundle;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;

import java.io.File;
import java.io.FileNotFoundException;

/**
 * Expõe o jogo extraído (Download/Sims2/sims2.cso) por um content:// para o emulador.
 *
 * Por que isso existe: a partir do Android 10 o ARMSX2 não lê um caminho arbitrário do
 * cartão — ele recebe o disco por um intent de frontend (ACTION_VIEW) com permissão de
 * leitura sobre o URI. Sem esse provider o "Abrir o jogo" do app não teria como entregar
 * o arquivo, e o usuário acabaria na tela do BIOS ("Inserir um disco...").
 *
 * O nome do arquivo no URI importa: o PCSX2 escolhe o leitor pelo sufixo do caminho
 * (CsoFileReader para ".cso"), então o último segmento precisa continuar "sims2.cso".
 */
public class GameProvider extends ContentProvider {

    public static final String AUTHORITY = "com.sims2.bundle.games";
    public static final String FILE_NAME = "sims2.cso";
    /** Tipo genérico: o ARMSX2 não filtra mime no intent-filter do ACTION_VIEW. */
    public static final String MIME = "application/octet-stream";

    public static Uri uri() {
        return Uri.parse("content://" + AUTHORITY + "/" + FILE_NAME);
    }

    @Override
    public boolean onCreate() {
        return true;
    }

    @Override
    public String getType(Uri uri) {
        return MIME;
    }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        File game = MainActivity.target();
        if (!game.isFile()) throw new FileNotFoundException(game.getAbsolutePath());
        if (mode != null && !mode.startsWith("r")) {
            throw new FileNotFoundException("somente leitura: " + mode);
        }
        return ParcelFileDescriptor.open(game, ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection, String[] selectionArgs,
                        String sortOrder) {
        if (projection == null) {
            projection = new String[] { OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE };
        }
        File game = MainActivity.target();
        MatrixCursor cursor = new MatrixCursor(projection, 1);
        Object[] row = new Object[projection.length];
        for (int i = 0; i < projection.length; i++) {
            if (OpenableColumns.DISPLAY_NAME.equals(projection[i])) {
                row[i] = game.getName();
            } else if (OpenableColumns.SIZE.equals(projection[i])) {
                row[i] = Long.valueOf(game.length());
            } else {
                row[i] = null;
            }
        }
        cursor.addRow(row);
        return cursor;
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        return 0;
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) {
        return 0;
    }
}