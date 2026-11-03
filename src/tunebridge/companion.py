"""Begleiter: Symbol in der Statusleiste (Tray) und schwebendes Erkennen-Icon.

Läuft als eigener, schlanker Prozess (nur Qt-Widgets, keine Browser-Engine) und spricht mit dem lokalen
SH-Tunebridge-Server über HTTP/WebSocket (127.0.0.1). Unter Linux/Wayland startet er über XWayland, weil Wayland
normalen Fenstern „immer im Vordergrund“ und freies Positionieren nicht erlaubt.

Schwebe-Icon
* Klick: Musik im Hintergrund erkennen – währenddessen Live-Pegel (echtes Spektrum der Quelle) + Fortschrittsring
* Maus drüber: Leiste fährt weich aus („Erkennen“, „App öffnen“) · Ziehen: verschieben · Rechtsklick: Menü
* Ergebnis: Cover, Titel, Künstler/Genre für ein paar Sekunden

Sparsam: Das Fenster hat eine feste Größe (kein Umbauen pro Bild), Klicks außerhalb der sichtbaren Teile gehen
per Maske an die Fenster darunter, und der Zeichen-Takt läuft nur, solange sich etwas bewegt.
Beendet sich selbst, sobald der Server weg ist oder Tray und Schwebe-Icon ausgeschaltet sind.
"""

from __future__ import annotations

import json
import math
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

ICON = Path(__file__).parent / "web" / "static" / "icon.svg"
D = 56                 # Durchmesser des Icons
PAD = 12               # Rand für Leuchten/Skalierung
H = D + 2 * PAD
PANEL_MAX = 300        # größte Ausklapp-Breite neben dem Icon
W = H + PANEL_MAX
LISTEN_S = 10          # Aufnahmedauer (wie /api/companion/scan)
WARMUP_S = 1.5         # parecord braucht etwas Anlauf


def _api(base: str, path: str, body: dict | None = None, timeout: float = 60) -> dict:
    req = urllib.request.Request(base + path, method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def main(port: int = 8765) -> None:
    from PySide6.QtCore import QObject, QPointF, QRect, QRectF, Qt, QTimer, Signal
    from PySide6.QtGui import (QAction, QBrush, QColor, QFont, QFontMetrics, QGuiApplication, QIcon, QImage,
                               QPainter, QPainterPath, QPen, QRadialGradient, QRegion)
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

    base = f"http://127.0.0.1:{port}"
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("SH-Tunebridge")
    app.setDesktopFileName("tunebridge")
    icon = QIcon(str(ICON))
    svg = QSvgRenderer(str(ICON))

    class Bus(QObject):
        result = Signal(dict)
        state = Signal(dict)
        cover = Signal(bytes)
    bus = Bus()

    st = {"busy": False, "accent": QColor("#6cc8a8"), "cfg": {}, "fails": 0, "source": "desktop",
          "bands": [0.0] * 32, "rms": -90.0, "t0": 0.0}

    def bg(fn, *a):
        threading.Thread(target=fn, args=a, daemon=True).start()

    # ------------------------------------------------------------ Live-Pegel während des Zuhörens
    def level_loop():
        try:
            from websockets.sync.client import connect
        except ImportError:
            return
        url = f"ws://127.0.0.1:{port}/ws/level?source={urllib.parse.quote(st['source'])}"
        try:
            with connect(url, open_timeout=3, close_timeout=1) as ws:
                while st["busy"]:
                    try:
                        f = json.loads(ws.recv(timeout=1))
                    except TimeoutError:
                        continue
                    if "bands" in f:
                        st["bands"], st["rms"] = f["bands"], f.get("rms", -90.0)
        except Exception:  # noqa: BLE001 – ohne Pegel geht es auch (nur Fortschrittsring)
            pass
        st["bands"], st["rms"] = [0.0] * 32, -90.0

    # ------------------------------------------------------------ Aktionen
    def scan():
        if st["busy"]:
            return
        st["busy"], st["t0"] = True, time.time()
        bubble.set_mode("listen")
        bg(level_loop)

        def run():
            try:
                r = _api(base, "/api/companion/scan", {}, timeout=120)
            except Exception as e:  # noqa: BLE001
                r = {"found": False, "error": str(e)}
            bus.result.emit(r)
        bg(run)

    def on_result(r: dict):
        st["busy"] = False
        if r.get("found"):
            bubble.show_result(r.get("title") or "?", " · ".join(x for x in (r.get("artist"), r.get("genre")) if x),
                               ok=True)
            tray.showMessage("Erkannt", f"{r.get('artist') or '?'} – {r.get('title') or '?'}", icon, 4000)
            if r.get("cover"):
                def get_cover(u=r["cover"]):
                    try:
                        with urllib.request.urlopen(u, timeout=8) as c:
                            bus.cover.emit(c.read(2_000_000))
                    except Exception:  # noqa: BLE001
                        pass
                bg(get_cover)
        elif r.get("silent"):
            bubble.show_result("Gerade ist nichts zu hören", "Läuft Musik? Quelle unter „Erkennen“ prüfen", ok=False)
        elif r.get("error"):
            bubble.show_result("Erkennen nicht möglich", r["error"][:90], ok=False)
        else:
            bubble.show_result("Nicht erkannt", r.get("hint") or "Gleich nochmal versuchen", ok=False)
    bus.result.connect(on_result)
    bus.cover.connect(lambda data: bubble.set_cover(QImage.fromData(data)))

    def open_app():
        bg(lambda: _api(base, "/api/window/show", {}, timeout=5))

    def quit_all():
        bg(lambda: _api(base, "/api/app/quit", {}, timeout=3))
        QTimer.singleShot(400, app.quit)

    def save(patch: dict):
        bg(lambda: _api(base, "/api/companion", patch, timeout=5))

    # ------------------------------------------------------------ Schwebe-Icon
    def ease(a: float, b: float, k: float) -> float:
        return b if abs(b - a) < 0.002 else a + (b - a) * k

    class Bubble(QWidget):
        def __init__(self):
            super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                             | Qt.WindowType.Tool | Qt.WindowType.NoDropShadowWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            self.setMouseTracking(True)
            self.setFixedSize(W, H)
            self.mode = "idle"            # idle | hover | listen | result
            self.side_right = True        # Leiste klappt nach rechts aus (Icon in der linken Bildschirmhälfte)
            self.hov = 0.0                # 0..1 Hover-Animation
            self.ext = 0.0                # aktuelle Breite der Leiste
            self.fade = 0.0               # Deckkraft des Leisten-Inhalts
            self.bars = [0.0] * 20
            self.pulse = 0.0
            self.inside = False
            self.hot = None               # Knopf unter der Maus
            self.press = None
            self.drag = False
            self.title = self.sub = ""
            self.ok = True
            self.cover: QImage | None = None
            self.tick = QTimer(self, interval=16, timeout=self._step)       # ~60 fps, nur solange nötig
            self.leave_t = QTimer(self, singleShot=True, interval=350, timeout=self._leave)
            self.result_t = QTimer(self, singleShot=True, interval=7000, timeout=lambda: self.set_mode("idle"))
            self.f_bold = QFont("Inter", 10)
            self.f_bold.setWeight(QFont.Weight.DemiBold)
            self.f_small = QFont("Inter", 9)

        # ---------- Geometrie: Position = linke obere Ecke des *Kreises* auf dem Bildschirm
        def circle_rect(self) -> QRectF:
            x = PAD if self.side_right else W - PAD - D
            return QRectF(x, PAD, D, D)

        def circle_pos(self):
            c = self.circle_rect()
            return self.x() + int(c.x()), self.y() + int(c.y())

        def place(self, cx: int, cy: int):
            scr = (QGuiApplication.screenAt(QRect(cx, cy, D, D).center()) or QGuiApplication.primaryScreen())
            g = scr.availableGeometry()
            cx = max(g.left(), min(cx, g.right() - D))
            cy = max(g.top(), min(cy, g.bottom() - D))
            self.side_right = cx + D / 2 < g.center().x()
            c = self.circle_rect()
            self.move(int(cx - c.x()), int(cy - c.y()))
            self._mask()

        # ---------- Zustände
        def target_ext(self) -> float:
            if self.mode == "hover":
                return 214
            if self.mode == "listen":
                return 236
            if self.mode == "result":
                fm1, fm2 = QFontMetrics(self.f_bold), QFontMetrics(self.f_small)
                w = max(fm1.horizontalAdvance(self.title), fm2.horizontalAdvance(self.sub)) + 34
                return min(PANEL_MAX - 6, max(150, w + (50 if self.cover else 0)))
            return 0

        def set_mode(self, m: str):
            if m == "idle" and self.inside and not st["busy"]:
                m = "hover"
            self.mode = m
            if m != "result":
                self.result_t.stop()
            self.tick.start()

        def show_result(self, title: str, sub: str, ok: bool):
            self.title, self.sub, self.ok, self.cover = title, sub, ok, None
            self.fade = 0.0
            self.set_mode("result")
            self.result_t.start()

        def set_cover(self, img: QImage):
            if not img.isNull() and self.mode == "result":
                self.cover = img.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                        Qt.TransformationMode.SmoothTransformation)
                self.tick.start()

        # ---------- Animation
        def _step(self):
            busy = st["busy"]
            self.hov = ease(self.hov, 1.0 if (self.inside or busy) else 0.0, 0.2)
            tgt = self.target_ext()
            self.ext = ease(self.ext, tgt, 0.2)
            want_fade = 1.0 if tgt and abs(self.ext - tgt) < tgt * 0.35 else 0.0
            self.fade = ease(self.fade, want_fade, 0.25)
            if busy:
                b = st["bands"]
                groups = [b[int(i * len(b) / 20):int((i + 1) * len(b) / 20)] or [0] for i in range(20)]
                for i, g in enumerate(groups):
                    v = max(g)
                    self.bars[i] = v if v > self.bars[i] else self.bars[i] * 0.82 + v * 0.18
                lvl = max(0.0, min(1.0, (st["rms"] + 50) / 40))
                self.pulse = ease(self.pulse, lvl, 0.3)
            else:
                self.bars = [x * 0.85 for x in self.bars]
                self.pulse = ease(self.pulse, 0.0, 0.2)
            self._mask()
            self.update()
            settled = (not busy and abs(self.ext - tgt) < 0.5 and self.hov in (0.0, 1.0) and self.fade in (0.0, 1.0)
                       and max(self.bars) < 0.01 and self.pulse == 0.0)
            if settled:
                self.tick.stop()

        def _pill(self) -> QRectF:
            c = self.circle_rect()
            h = D - 8
            w = D / 2 + self.ext
            x = c.center().x() if self.side_right else c.center().x() - w
            return QRectF(x, c.center().y() - h / 2, w, h)

        def _mask(self):
            c = self.circle_rect().adjusted(-PAD, -PAD, PAD, PAD).toRect()
            reg = QRegion(c)
            if self.ext > 1:
                reg = reg.united(QRegion(self._pill().adjusted(-3, -3, 3, 3).toRect()))
            self.setMask(reg)

        def _buttons(self) -> list[tuple[str, QRectF]]:
            p = self._pill()
            inner = p.adjusted(D / 2 + 8, 6, -8, -6) if self.side_right else p.adjusted(8, 6, -(D / 2 + 8), -6)
            gap = 6
            bw = (inner.width() - gap) / 2
            return [("scan", QRectF(inner.x(), inner.y(), bw, inner.height())),
                    ("open", QRectF(inner.x() + bw + gap, inner.y(), bw, inner.height()))]

        # ---------- Zeichnen
        def paintEvent(self, _):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            acc = st["accent"]
            c = self.circle_rect()
            ctr = c.center()
            busy = st["busy"]

            # Leiste
            if self.ext > 1:
                pill = self._pill()
                p.setPen(QPen(QColor(255, 255, 255, 22), 1))
                p.setBrush(QColor(16, 19, 24, 242))
                p.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)
                p.setOpacity(self.fade)
                if self.mode == "hover":
                    for key, r in self._buttons():
                        hot = self.hot == key
                        p.setPen(Qt.PenStyle.NoPen)
                        p.setBrush(acc if hot else QColor(255, 255, 255, 14))
                        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
                        p.setPen(QColor("#0d1a15") if hot else QColor("#e4e6ea"))
                        p.setFont(self.f_bold)
                        p.drawText(r, Qt.AlignmentFlag.AlignCenter, "Erkennen" if key == "scan" else "App öffnen")
                elif self.mode == "listen":
                    inner = pill.adjusted(D / 2 + 14, 0, -16, 0) if self.side_right else pill.adjusted(16, 0, -(D / 2 + 14), 0)
                    left = LISTEN_S + WARMUP_S - (time.time() - st["t0"])
                    p.setFont(self.f_bold)
                    p.setPen(QColor("#e4e6ea"))
                    lab = f"Hört zu · {max(1, math.ceil(left))} s" if left > 0 else "Wird erkannt …"
                    p.drawText(QRectF(inner.x(), inner.y() + 5, inner.width(), 16), Qt.AlignmentFlag.AlignLeft, lab)
                    # Spektrum (echte Pegel der Quelle)
                    n, bw = len(self.bars), inner.width() / len(self.bars)
                    base_y, mh = inner.bottom() - 7, 16
                    p.setPen(Qt.PenStyle.NoPen)
                    for i, v in enumerate(self.bars):
                        h = 2 + v * mh
                        col = QColor(acc)
                        col.setAlpha(110 + int(145 * v))
                        p.setBrush(col)
                        p.drawRoundedRect(QRectF(inner.x() + i * bw + 1, base_y - h, max(2.0, bw - 3), h), 1.5, 1.5)
                elif self.mode == "result":
                    tx = pill.x() + (D / 2 + 14 if self.side_right else 16)
                    tw = pill.width() - D / 2 - 30
                    if self.cover is not None:
                        cr = QRectF(tx, pill.center().y() - 17, 34, 34)
                        path = QPainterPath()
                        path.addRoundedRect(cr, 7, 7)
                        p.save()
                        p.setClipPath(path)
                        p.drawImage(cr, self.cover)
                        p.restore()
                        tx += 44
                        tw -= 44
                    fm = QFontMetrics(self.f_bold)
                    p.setFont(self.f_bold)
                    p.setPen(QColor("#e4e6ea") if self.ok else QColor("#e0b46a"))
                    y = pill.center().y()
                    p.drawText(QRectF(tx, y - (19 if self.sub else 9), tw, 18), Qt.AlignmentFlag.AlignVCenter,
                               fm.elidedText(self.title, Qt.TextElideMode.ElideRight, int(tw)))
                    if self.sub:
                        p.setFont(self.f_small)
                        p.setPen(QColor("#a2a8b2"))
                        p.drawText(QRectF(tx, y + 1, tw, 16), Qt.AlignmentFlag.AlignVCenter,
                                   QFontMetrics(self.f_small).elidedText(self.sub, Qt.TextElideMode.ElideRight, int(tw)))
                p.setOpacity(1.0)

            # Leuchten (Hover bzw. Lautstärke beim Zuhören)
            glow = max(self.hov * 0.55, self.pulse)
            if glow > 0.01:
                g = QRadialGradient(ctr, D / 2 + PAD)
                col = QColor(acc)
                col.setAlpha(int(110 * glow))
                g.setColorAt(0.55, col)
                col.setAlpha(0)
                g.setColorAt(1.0, col)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(g))
                p.drawEllipse(ctr, D / 2 + PAD, D / 2 + PAD)

            # Kreis (wird beim Drüberfahren / im Takt der Musik minimal größer)
            r = D / 2 * (1 + 0.06 * self.hov + 0.05 * self.pulse)
            p.setPen(QPen(QColor(acc.red(), acc.green(), acc.blue(), 120 + int(135 * self.hov)), 1.6))
            p.setBrush(QColor(18, 21, 26, 250))
            p.drawEllipse(ctr, r, r)
            if busy:
                # Fortschritt der Aufnahme + kleine Pegel-Säulen statt Logo
                el = (time.time() - st["t0"]) / (LISTEN_S + WARMUP_S)
                ring = QRectF(ctr.x() - r + 2, ctr.y() - r + 2, 2 * r - 4, 2 * r - 4)
                p.setPen(QPen(QColor(255, 255, 255, 25), 3))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(ring)
                pen = QPen(acc, 3)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                if el < 1:
                    p.drawArc(ring, 90 * 16, -int(360 * 16 * el))
                else:                       # Auswertung läuft: kreisender Bogen
                    a = int((time.time() * 360) % 360)
                    p.drawArc(ring, -a * 16, 90 * 16)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(acc)
                for i in range(5):
                    v = max(self.bars[i * 4:(i + 1) * 4] or [0])
                    h = 5 + v * 18
                    p.drawRoundedRect(QRectF(ctr.x() - 13 + i * 6, ctr.y() - h / 2, 3.4, h), 1.7, 1.7)
            else:
                s = 30 * (1 + 0.06 * self.hov)
                svg.render(p, QRectF(ctr.x() - s / 2, ctr.y() - s / 2, s, s))
            p.end()

        # ---------- Maus
        def _hit(self, pos: QPointF):
            if self.mode == "hover" and self.fade > 0.5:
                for key, r in self._buttons():
                    if r.contains(pos):
                        return key
            return None

        def enterEvent(self, _):
            self.inside = True
            self.leave_t.stop()
            if self.mode == "idle":
                self.set_mode("hover")
            self.tick.start()

        def leaveEvent(self, _):
            self.leave_t.start()

        def _leave(self):
            if self.underMouse() or self.drag:
                return
            self.inside, self.hot = False, None
            if self.mode == "hover":
                self.set_mode("idle")
            self.tick.start()

        def mousePressEvent(self, e):
            if e.button() == Qt.MouseButton.LeftButton:
                self.press = (e.globalPosition().toPoint(), self.circle_pos(), self._hit(e.position()))
                self.drag = False

        def mouseMoveEvent(self, e):
            hot = self._hit(e.position())
            if hot != self.hot:
                self.hot = hot
                self.setCursor(Qt.CursorShape.PointingHandCursor if hot or self.circle_rect().contains(e.position())
                               else Qt.CursorShape.ArrowCursor)
                self.update()
            if not self.press or self.press[2]:
                return
            d = e.globalPosition().toPoint() - self.press[0]
            if not self.drag and d.manhattanLength() > 5:
                self.drag = True
                if self.mode == "hover":
                    self.mode = "idle"
                self.tick.start()
            if self.drag:
                self.place(self.press[1][0] + d.x(), self.press[1][1] + d.y())

        def mouseReleaseEvent(self, e):
            if e.button() != Qt.MouseButton.LeftButton or not self.press:
                return
            btn, was_drag = self.press[2], self.drag
            self.press, self.drag = None, False
            if was_drag:
                save({"pos": list(self.circle_pos())})
                return
            if btn == "scan" or (btn is None and self.circle_rect().contains(e.position())):
                scan()
            elif btn == "open":
                open_app()
            elif self.mode == "result":
                self.set_mode("idle")

        def contextMenuEvent(self, e):
            menu.exec(e.globalPos())

    bubble = Bubble()

    # ------------------------------------------------------------ Tray
    tray = QSystemTrayIcon(icon)
    tray.setToolTip("SH-Tunebridge")
    menu = QMenu()
    a_scan = QAction("Jetzt erkennen", triggered=scan)
    a_open = QAction("SH-Tunebridge öffnen", triggered=open_app)
    a_bub = QAction("Schwebe-Icon anzeigen", checkable=True)
    a_bub.toggled.connect(lambda on: (save({"bubble": on}), bubble.setVisible(on)))
    a_quit = QAction("Beenden", triggered=quit_all)
    for a in (a_scan, a_open):
        menu.addAction(a)
    menu.addSeparator()
    menu.addAction(a_bub)
    menu.addSeparator()
    menu.addAction(a_quit)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda r: open_app() if r == QSystemTrayIcon.ActivationReason.Trigger else None)

    # ------------------------------------------------------------ Einstellungen vom Server übernehmen
    def apply(cfg: dict):
        if cfg.get("_gone"):
            st["fails"] += 1
            if st["fails"] >= 3:          # Server weg -> App beendet -> Begleiter auch
                app.quit()
            return
        st["fails"] = 0
        st["source"] = cfg.get("source") or "desktop"
        if cfg.get("accent") and QColor(cfg["accent"]) != st["accent"]:
            st["accent"] = QColor(cfg["accent"])
            bubble.update()
        if not cfg.get("tray") and not cfg.get("bubble"):
            app.quit()
            return
        tray.setVisible(bool(cfg.get("tray")) and QSystemTrayIcon.isSystemTrayAvailable())
        if not st["cfg"]:
            if cfg.get("pos"):
                bubble.place(*cfg["pos"])
            else:
                g = QGuiApplication.primaryScreen().availableGeometry()
                bubble.place(g.right() - D - 40, g.bottom() - D - 120)
        if bool(cfg.get("bubble")) != bubble.isVisible():
            bubble.setVisible(bool(cfg.get("bubble")))
            if bubble.isVisible():
                bubble.raise_()
        a_bub.blockSignals(True)
        a_bub.setChecked(bool(cfg.get("bubble")))
        a_bub.blockSignals(False)
        st["cfg"] = cfg
    bus.state.connect(apply)

    def poll():
        def run():
            try:
                bus.state.emit(_api(base, "/api/companion", timeout=4))
            except Exception:  # noqa: BLE001
                bus.state.emit({"_gone": True})
        bg(run)
    QTimer(app, interval=2500, timeout=poll).start()
    try:   # Einstellungen vom Start mitgegeben -> Icon sofort zeigen, Akzent/Server-Stand kommt mit der ersten Abfrage
        import os
        first = json.loads(os.environ.get("TUNEBRIDGE_COMPANION_CFG") or "{}")
        if first.get("tray") or first.get("bubble"):
            apply({**first, "accent": None})
    except (ValueError, TypeError):
        pass
    poll()
    sys.exit(app.exec())


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
