package de.bs002.tunebridge.data

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

/** Lokale Datenbank – liegt nur in der App (nicht in Android-Sicherungen, siehe allowBackup=false). */
class Db(context: Context) : SQLiteOpenHelper(context, "tunebridge.db", null, VERSION) {

    override fun onConfigure(db: SQLiteDatabase) {
        db.enableWriteAheadLogging()
    }

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE recognitions(
                 id INTEGER PRIMARY KEY, uid TEXT UNIQUE NOT NULL, ts REAL NOT NULL, host TEXT, source TEXT,
                 engine TEXT, track TEXT NOT NULL, extra TEXT NOT NULL DEFAULT '{}',
                 synced INTEGER NOT NULL DEFAULT 0,  -- (Version 1, nicht mehr benutzt)
                 deleted INTEGER NOT NULL DEFAULT 0, -- gelöscht; bleibt, bis jeder PC die Löschung hat
                 seq INTEGER NOT NULL DEFAULT 0)     -- Änderungszähler: jeder PC merkt sich, bis wohin er alles hat"""
        )
        db.execSQL("CREATE INDEX recognitions_ts ON recognitions(ts)")
        db.execSQL("CREATE INDEX recognitions_seq ON recognitions(seq)")
        db.execSQL("CREATE TABLE playlists(pc TEXT NOT NULL, name TEXT NOT NULL, tracks TEXT NOT NULL, updated REAL NOT NULL, PRIMARY KEY(pc, name))")
        db.execSQL("CREATE TABLE ops(id INTEGER PRIMARY KEY, pc TEXT NOT NULL, body TEXT NOT NULL, ts REAL NOT NULL)")
        db.execSQL("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        if (oldVersion < 2) {
            // Version 2: mehrere PCs. Bisherige Playlists/Änderungen gehören zum bisher einzigen PC („legacy“,
            // Repository ersetzt das durch dessen Kennung). Alle eigenen Erkennungen gehen an jeden PC (noch) einmal.
            db.execSQL("ALTER TABLE recognitions ADD COLUMN seq INTEGER NOT NULL DEFAULT 0")
            db.execSQL("UPDATE recognitions SET seq = id")
            db.execSQL("CREATE INDEX IF NOT EXISTS recognitions_seq ON recognitions(seq)")
            db.execSQL("CREATE TABLE playlists2(pc TEXT NOT NULL, name TEXT NOT NULL, tracks TEXT NOT NULL, updated REAL NOT NULL, PRIMARY KEY(pc, name))")
            db.execSQL("INSERT INTO playlists2 SELECT 'legacy', name, tracks, updated FROM playlists")
            db.execSQL("DROP TABLE playlists")
            db.execSQL("ALTER TABLE playlists2 RENAME TO playlists")
            db.execSQL("ALTER TABLE ops ADD COLUMN pc TEXT NOT NULL DEFAULT 'legacy'")
            db.execSQL("INSERT OR REPLACE INTO meta(key, value) SELECT 'seq', CAST(IFNULL(MAX(id), 0) AS TEXT) FROM recognitions")
        }
    }

    fun meta(key: String): String? = readableDatabase.rawQuery("SELECT value FROM meta WHERE key=?", arrayOf(key)).use {
        if (it.moveToFirst()) it.getString(0) else null
    }

    fun meta(key: String, value: String?) {
        if (value == null) writableDatabase.delete("meta", "key=?", arrayOf(key))
        else writableDatabase.insertWithOnConflict("meta", null, ContentValues().apply {
            put("key", key); put("value", value)
        }, SQLiteDatabase.CONFLICT_REPLACE)
    }

    /** Nächster Wert des Änderungszählers (nur im Schreib-Thread aufrufen). */
    @Synchronized
    fun nextSeq(): Long {
        val n = (meta("seq")?.toLongOrNull() ?: 0L) + 1
        meta("seq", n.toString())
        return n
    }

    companion object {
        const val VERSION = 2
    }
}
