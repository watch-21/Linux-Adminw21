"""Native dashboard layout backed by Collector measurements."""

import json
import time

from controls import InteractivePanel, SegmentedControl
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QBoxLayout,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from widgets import ACCENTS, LIGHT_ACCENTS, ElidedLabel, Graph, NumericItem, Panel, duration

SESSION_ROLE = Qt.UserRole + 1


def number(value, suffix=""):
    return "—" if value is None else f"{value:.1f}{suffix}"


def size(value):
    return "—" if value is None else f"{value / 1024**3:.1f} GiB"


class Dashboard(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.data = {}
        self.sessions = []
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)
        scroll = QScrollArea()
        self.scroll = scroll
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidgetResizable(True)
        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(0, 0, 3, 0)
        outer.setSpacing(14)
        root.addWidget(scroll)
        scroll.setWidget(content)
        metrics = QGridLayout()
        self.metrics = metrics
        self._compact = None
        metrics.setSpacing(12)
        self.metric_panels, self.sparks, self.metric_notes = {}, {}, {}
        window.cards, window.graphs = {}, {}
        for index, key in enumerate(("cpu", "memory", "disk", "network")):
            panel = InteractivePanel()
            panel.activated.connect(lambda k=key: self.select_metric(k))
            panel.setMinimumHeight(123)
            panel.body.setContentsMargins(16, 12, 16, 12)
            panel.body.setSpacing(6)
            panel.setProperty("metric", True)
            arrow = QLabel("↗")
            arrow.setObjectName("muted")
            panel.header.addWidget(arrow)
            value = QLabel("—")
            value.setObjectName("metricValue")
            if key == "network":
                value.setObjectName("networkValue")
            value.setStyleSheet(f"color:{ACCENTS[index]};")
            note = QLabel("—")
            note.setObjectName("muted")
            spark = Graph([ACCENTS[index]], compact=True, maximum=100 if key in ("cpu", "memory", "disk") else None)
            spark.setMaximumHeight(24)
            panel.body.addWidget(value)
            panel.body.addWidget(note)
            panel.body.addWidget(spark)
            window.cards[key] = value
            self.metric_panels[key] = panel
            self.metric_notes[key] = note
            self.sparks[key] = spark
            metrics.addWidget(panel, 0, index)
        outer.addLayout(metrics)
        middle = QHBoxLayout()
        self.middle = middle
        middle.setSpacing(14)
        self.activity = Panel()
        self.mode = QComboBox()
        self.mode.addItems(["CPU / RAM", "Netzwerk", "Datenträger"])
        self.mode.setMinimumWidth(125)
        self.mode.currentIndexChanged.connect(lambda: self.redraw(window.history))
        self.mode.currentIndexChanged.connect(self.update_selection)
        self.activity.header.addWidget(self.mode)
        controls = QHBoxLayout()
        self.range = QComboBox(self.activity)
        self.range.addItems(["60 s", "5 min", "15 min", "Session · 90 min max."])
        self.range.currentIndexChanged.connect(lambda: self.redraw(window.history))
        self.range.hide()
        self.segments = SegmentedControl(["60 s", "5 min", "15 min", "90 min"])
        self.segments.changed.connect(self.range.setCurrentIndex)
        self.range.currentIndexChanged.connect(self.segments.set_index)
        self.interface = QComboBox()
        self.interface.addItem("Σ")
        self.interface.setMinimumWidth(80)
        self.interface.currentIndexChanged.connect(lambda: self.redraw(window.history))
        controls.addWidget(self.segments, 1)
        controls.addWidget(self.interface)
        self.legend = QLabel()
        self.legend.setObjectName("muted")
        self.activity.body.addLayout(controls)
        self.chart = Graph([ACCENTS[0], ACCENTS[1]], maximum=100)
        self.chart.setMinimumHeight(170)
        self.activity.body.addWidget(self.chart, 1)
        footer = QHBoxLayout()
        footer.addWidget(self.legend)
        self.hover_readout = ElidedLabel()
        self.hover_readout.setObjectName("muted")
        footer.addWidget(self.hover_readout, 1)
        self.activity.body.addLayout(footer)
        self.chart.hovered.connect(self.show_hover)
        middle.addWidget(self.activity, 11)
        self.session_panel = Panel()
        self.session_count = QLabel("—")
        self.session_count.setObjectName("badge")
        self.session_panel.header.addWidget(self.session_count)
        self.session_table = window.table(["User", "Groups", "Session", "Source", "Since"])
        self.session_table.setMinimumHeight(150)
        self.session_table.setMinimumWidth(0)
        self.session_table.verticalHeader().setDefaultSectionSize(36)
        self.session_table.horizontalHeader().setStretchLastSection(False)
        self.session_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.session_table.setColumnWidth(0, 115)
        self.session_table.setColumnWidth(2, 70)
        self.session_table.setColumnWidth(3, 120)
        self.session_table.setColumnWidth(4, 65)
        self.session_table.itemDoubleClicked.connect(lambda: self.show_selected_session())
        self.session_empty = QLabel(self.session_table.viewport())
        self.session_empty.setObjectName("muted")
        self.session_empty.setAlignment(Qt.AlignCenter)
        self.session_empty.setWordWrap(True)
        self.session_empty.setTextFormat(Qt.PlainText)
        self.session_empty.setAttribute(Qt.WA_TransparentForMouseEvents)
        empty_layout = QVBoxLayout(self.session_table.viewport())
        empty_layout.setContentsMargins(12, 8, 12, 8)
        empty_layout.addWidget(self.session_empty)
        self.session_panel.body.addWidget(self.session_table, 1)
        self.session_hint = QLabel()
        self.session_hint.setWordWrap(True)
        self.session_hint.setObjectName("muted")
        self.session_panel.body.addWidget(self.session_hint)
        actions = QHBoxLayout()
        window.button(actions, "Benutzer verwalten", "Manage users", lambda: window.navigate("users"))
        self.session_details = window.button(actions, "Details", "Details", self.show_selected_session)
        self.session_details.setEnabled(False)
        self.session_table.itemSelectionChanged.connect(
            lambda: self.session_details.setEnabled(self.selected_session() is not None)
        )
        self.session_panel.body.addLayout(actions)
        middle.addWidget(self.session_panel, 11)
        outer.addLayout(middle, 1)
        bottom = QHBoxLayout()
        self.bottom = bottom
        bottom.setSpacing(14)
        self.alert_panel = Panel()
        self.alert_summary = QLabel()
        self.alert_summary.setWordWrap(True)
        self.alert_summary.setTextFormat(Qt.PlainText)
        self.alert_panel.body.addWidget(self.alert_summary, 1)
        quick = QHBoxLayout()
        window.button(quick, "Benutzer erstellen", "Create user", window.create_user)
        window.button(quick, "Prozesse öffnen", "Open processes", lambda: window.navigate("processes"))
        self.alert_panel.body.addLayout(quick)
        bottom.addWidget(self.alert_panel, 11)
        self.service_panel = Panel()
        self.service_text = QLabel()
        self.service_text.setObjectName("muted")
        self.service_text.setWordWrap(True)
        self.service_panel.body.addWidget(self.service_text)
        self.service_rows = QGridLayout()
        self.service_rows.setColumnStretch(0, 1)
        self.service_rows.setColumnStretch(1, 1)
        self.service_panel.body.addLayout(self.service_rows)
        self.ram_bar, self.storage_bar = QProgressBar(), QProgressBar()
        for bar in (self.ram_bar, self.storage_bar):
            bar.setRange(0, 100)
            bar.setFixedHeight(18)
            self.service_panel.body.addWidget(bar)
        bottom.addWidget(self.service_panel, 11)
        outer.addLayout(bottom)
        self.system_line = QLabel("—")
        self.system_line.setObjectName("systemLine")
        self.system_line.setWordWrap(True)
        outer.addWidget(self.system_line)
        self.details = QPlainTextEdit(self)
        self.details.setReadOnly(True)
        self.details.hide()
        window.details = self.details
        window.range, window.interface = self.range, self.interface
        # Extra graph instances preserve the module API for inspection/tests.
        window.graphs = {
            key: Graph([ACCENTS[i]], self, maximum=100 if key in ("cpu", "memory") else None)
            for i, key in enumerate(("cpu", "memory", "network", "disk"))
        }
        for graph in window.graphs.values():
            graph.hide()
        self.translate()
        self.update_selection()

    def select_metric(self, key):
        self.mode.setCurrentIndex({"cpu": 0, "memory": 0, "network": 1, "disk": 2}[key])
        self.update_selection()
        self.scroll.ensureWidgetVisible(self.activity, 0, 12)

    def update_selection(self, *_):
        mode = self.mode.currentIndex()
        for key, panel in self.metric_panels.items():
            selected = mode == {"cpu": 0, "memory": 0, "network": 1, "disk": 2}[key]
            panel.setProperty("selected", selected)
            panel.style().unpolish(panel)
            panel.style().polish(panel)

    def show_hover(self, record):
        if not record:
            self.hover_readout.setText(self.t("Mit der Maus Werte ansehen", "Hover to inspect values"))
            return
        values = record["values"]
        names = self.chart.series_names
        parts = [
            (names[i] if i < len(names) else str(i + 1)) + " " + number(value, self.chart.unit)
            for i, value in enumerate(values)
        ]
        self.hover_readout.setText("  ·  ".join(parts))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "middle"):
            return
        compact = self.width() < 960
        columns = 1 if self.width() < 560 else 2 if compact else 4
        state = (compact, columns)
        if state == self._compact:
            return
        self._compact = state
        direction = QBoxLayout.TopToBottom if compact else QBoxLayout.LeftToRight
        self.middle.setDirection(direction)
        self.bottom.setDirection(direction)
        panels = [self.metric_panels[key] for key in ("cpu", "memory", "disk", "network")]
        for panel in panels:
            self.metrics.removeWidget(panel)
        for index, panel in enumerate(panels):
            self.metrics.addWidget(panel, index // columns, index % columns)
        for column in range(4):
            self.metrics.setColumnStretch(column, 1 if column < columns else 0)

    def t(self, de, en):
        return self.window.t(de, en)

    def translate(self):
        for key, de, en in [
            ("cpu", "CPU-Auslastung", "CPU usage"),
            ("memory", "Arbeitsspeicher", "Memory"),
            ("disk", "Speicherplatz · /", "Storage · /"),
            ("network", "Netzwerk · MiB/s", "Network · MiB/s"),
        ]:
            self.metric_panels[key].title.setText(self.t(de, en))
            self.metric_panels[key].setToolTip(self.t("Klicken: zugehöriges Diagramm öffnen", "Click to open this activity chart"))
            self.metric_panels[key].setAccessibleName(self.t(de, en))
        self.activity.title.setText(self.t("Systemaktivität", "System activity"))
        self.session_panel.title.setText(self.t("Angemeldete Benutzer", "Logged-in users"))
        self.alert_panel.title.setText(self.t("Systemmeldungen", "System notices"))
        self.service_panel.title.setText(self.t("Dienste & Ressourcen", "Services & resources"))
        self.session_table.setHorizontalHeaderLabels(
            [
                self.t("Benutzer", "User"),
                self.t("Gruppen", "Groups"),
                self.t("Sitzung", "Session"),
                self.t("Quelle", "Source"),
                self.t("Seit", "Since"),
            ]
        )
        self.mode.setItemText(1, self.t("Netzwerk", "Network"))
        self.mode.setItemText(2, self.t("Datenträger", "Disk activity"))
        self.range.setItemText(3, self.t("Sitzung · max. 90 min", "Session · max. 90 min"))
        self.segments.buttons[3].setToolTip(self.range.itemText(3))
        self.show_hover(None)
        if not self.data:
            self.session_empty.setText(self.t("Sitzungsinformationen werden gelesen…", "Reading session information…"))
        if self.data:
            self.update_data(self.data)
        else:
            self.redraw(self.window.history)

    def update_data(self, data):
        self.data = data
        window = self.window
        window.cards["cpu"].setText(number(data["cpu"], " %"))
        window.cards["memory"].setText(number(data["memory"]["percent"], " %"))
        root = next((item for item in data["storage"] if item["mount"] == "/"), None)
        window.cards["disk"].setText(number(root["percent"] if root else None, " %"))
        self.metric_notes["cpu"].setText(f"{data['logical']} " + self.t("logische Kerne", "logical cores"))
        self.metric_notes["memory"].setText(f"{size(data['memory']['used'])} / {size(data['memory']['total'])}")
        self.metric_notes["disk"].setText(self.t("Frei: ", "Free: ") + (size(root["free"]) if root else "—"))
        self.metric_notes["network"].setText(self.t("↓ Empfangen   ↑ Gesendet", "↓ Receive   ↑ Send"))
        choices = ["Σ", *data["network"]]
        if [self.interface.itemText(i) for i in range(self.interface.count())] != choices:
            selected = self.interface.currentText()
            self.interface.blockSignals(True)
            self.interface.clear()
            self.interface.addItems(choices)
            self.interface.setCurrentText(selected if selected in choices else "Σ")
            self.interface.blockSignals(False)
        self.update_sessions(data.get("session_data", {}))
        translations = {
            "Interface addresses unavailable: permissions or netlink access": self.t(
                "Netzwerkadressen nicht verfügbar (Berechtigung)", "Network addresses unavailable (permission)"
            ),
            "Interface state unavailable: permissions or ioctl access": self.t(
                "Schnittstellenstatus nicht verfügbar (Berechtigung)", "Interface state unavailable (permission)"
            ),
        }
        notices = [translations.get(item, item) for item in data.get("warnings", [])]
        failed = data["system"].get("services", {}).get("failed")
        if failed:
            notices.insert(0, self.t(f"{failed} fehlgeschlagene Dienste", f"{failed} failed services"))
        if data["memory"]["percent"] >= 90:
            notices.insert(0, self.t("Hohe RAM-Auslastung", "High memory usage"))
        self.alert_summary.setText(
            "\n\n".join(("• " + line for line in notices[:3]))
            if notices
            else self.t("Keine Warnungen aus den verfügbaren Prüfungen.", "No warnings from the available checks.")
        )
        self.alert_summary.setToolTip("\n".join(notices))
        services = data["system"].get("services", {})
        active, failed = services.get("active"), services.get("failed")
        self.service_text.setText(
            self.t("Aktiv: ", "Active: ")
            + str(active if active is not None else "—")
            + "   ·   "
            + self.t("Fehlgeschlagen: ", "Failed: ")
            + str(failed if failed is not None else "—")
        )
        self.service_text.setToolTip(services.get("status", "unavailable"))
        if active is None:
            self.service_text.setText(self.t("systemd-Status nicht verfügbar", "systemd status unavailable"))
        while self.service_rows.count():
            item = self.service_rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        items = services.get("items", [])
        if items:
            for index, service in enumerate(sorted(items, key=lambda item: item["state"] != "failed")[:4]):
                label = ElidedLabel(service["unit"].removesuffix(".service"))
                label.setObjectName({"active": "serviceChip", "failed": "failedChip"}.get(service["state"], "inactiveChip"))
                label.setToolTip(f"{service['unit']} · {service['state']} / {service['substate']}")
                self.service_rows.addWidget(label, index // 2, index % 2)
        self.ram_bar.setValue(round(data["memory"]["percent"]))
        self.ram_bar.setFormat("RAM  %p%")
        self.storage_bar.setValue(round(root["percent"]) if root else 0)
        self.storage_bar.setFormat(
            self.t("Speicher  %p%", "Storage  %p%")
            if root
            else self.t("Speicher nicht verfügbar", "Storage unavailable")
        )
        system = data["system"]
        uptime = int(system["uptime"])
        self.system_line.setText(
            f"{system['host']}  ·  {system['distribution'] or '—'}  ·  {system['kernel']}  ·  "
            + self.t("Laufzeit: ", "Uptime: ")
            + f"{uptime // 86400}d {uptime // 3600 % 24}h {uptime // 60 % 60}m"
        )
        self.details.setPlainText(
            json.dumps({key: value for key, value in data.items() if key != "processes"}, ensure_ascii=False, indent=2)
        )
        self.redraw(window.history)

    def update_sessions(self, record):
        selected = self.selected_session()
        identity = (selected["username"], selected.get("id")) if selected else None
        vertical = self.session_table.verticalScrollBar().value()
        self.sessions = record.get("sessions", []) if record.get("available") else []
        self.session_empty.setVisible(not self.sessions)
        self.session_empty.setText(
            self.t("◎  Keine sichtbaren Sitzungen\nKeine Logins in dieser Quelle gemeldet.", "◎  No visible sessions\nNo logins reported by this source.")
            if record.get("available") else self.t("Sitzungsinformationen nicht verfügbar.", "Session information unavailable.")
        )
        self.session_table.setSortingEnabled(False)
        self.session_table.setRowCount(len(self.sessions))
        for row, session in enumerate(self.sessions):
            groups = ", ".join(session.get("groups", [])) or "—"
            kind = session.get("type") or "—"
            if session.get("tty"):
                kind += " · " + session["tty"]
            values = [
                session["username"],
                groups,
                kind,
                session.get("host") or self.t("Lokal", "Local"),
                duration(session.get("start")),
            ]
            for col, value in enumerate(values):
                item = NumericItem(value)
                item.setData(SESSION_ROLE, row)
                if col == 4 and session.get("start") is not None:
                    item.setData(Qt.UserRole, max(0, time.time() - session["start"]))
                item.setToolTip(value)
                self.session_table.setItem(row, col, item)
        self.session_table.setSortingEnabled(True)
        self.session_table.clearSelection()
        self.session_table.setCurrentCell(-1, -1)
        if identity:
            for row in range(self.session_table.rowCount()):
                session = self.sessions[self.session_table.item(row, 0).data(SESSION_ROLE)]
                if (session["username"], session.get("id")) == identity:
                    self.session_table.selectRow(row)
                    break
        self.session_table.verticalScrollBar().setValue(vertical)
        self.session_details.setEnabled(self.selected_session() is not None)
        unique = len({session["username"] for session in self.sessions})
        self.session_count.setText(
            f"{unique} " + self.t("Benutzer", "users") + f" / {len(self.sessions)} " + self.t("Sitzungen", "sessions")
            if record.get("available")
            else "—"
        )
        source = record.get("source") or self.t("nicht verfügbar", "unavailable")
        message = (
            self.t("Doppelklick für Gruppen & Sitzungsdetails.", "Double-click for groups and session details.")
            if self.sessions
            else self.t("Keine sichtbaren Sitzungen in dieser Quelle.", "No sessions visible in this source.")
        )
        if not record.get("available"):
            message = self.t("Sitzungsinformationen nicht verfügbar.", "Session information unavailable.")
        self.session_hint.setText(message + "  ·  " + source)
        self.session_hint.setToolTip("\n".join(record.get("limitations", [])))

    def selected_session(self):
        row = self.session_table.currentRow()
        item = self.session_table.item(row, 0) if row >= 0 else None
        index = item.data(SESSION_ROLE) if item else None
        return self.sessions[index] if isinstance(index, int) and 0 <= index < len(self.sessions) else None

    def set_unavailable(self, message):
        self.data = {}
        for key, card in self.window.cards.items():
            card.setText("—")
            self.metric_notes[key].setText(self.t("Nicht verfügbar", "Unavailable"))
        for graph in [self.chart, *self.sparks.values()]:
            graph.points, graph.times = [], []
            graph.clear_hover()
            graph.update()
        self.update_sessions({"available": False, "limitations": [message]})
        self.alert_summary.setText(message)
        self.service_text.setText(self.t("Nicht verfügbar", "Unavailable"))
        while self.service_rows.count():
            item = self.service_rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for bar in (self.ram_bar, self.storage_bar):
            bar.setValue(0)
            bar.setFormat("—")

    def show_selected_session(self):
        record = self.selected_session()
        if not record:
            return
        dialog = QDialog(self.window)
        dialog.setWindowTitle(record["username"] + " · " + self.t("Gruppen & Sitzungen", "Groups & sessions"))
        dialog.resize(650, 490)
        layout = QVBoxLayout(dialog)
        title = QLabel(record["username"])
        title.setObjectName("heading")
        layout.addWidget(title)
        primary = record.get("primary_group") or "—"
        supplementary = ", ".join(record.get("supplementary_groups", [])) or "—"
        label = QLabel(
            self.t("Primäre Gruppe: ", "Primary group: ")
            + primary
            + "\n"
            + self.t("Zusätzliche Gruppen: ", "Supplementary groups: ")
            + supplementary
        )
        label.setWordWrap(True)
        label.setTextFormat(Qt.PlainText)
        layout.addWidget(label)
        output = QPlainTextEdit()
        output.setReadOnly(True)
        related = [s for s in self.sessions if s["username"] == record["username"]]
        output.setPlainText(json.dumps(related, ensure_ascii=False, indent=2))
        layout.addWidget(output)
        hint = QLabel(
            self.t(
                "Angezeigt werden konfigurierte Gruppen. Laufende Sitzungen können ältere Gruppen haben. Eine sudo/wheel-Mitgliedschaft ersetzt keine Prüfung der sudo-Regeln.",
                "Groups are configured memberships. Existing sessions can retain older groups. sudo/wheel membership is not proof of sudo authorization.",
            )
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        close = QPushButton(self.t("Schließen", "Close"))
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def redraw(self, history):
        if not history or not self.data:
            return
        seconds = [60, 300, 900, 5400][self.range.currentIndex()]
        rows = [row for row in history if row["monotonic"] >= history[-1]["monotonic"] - seconds]
        selected = self.interface.currentText()

        def rates(row):
            values = [
                value
                for name, value in row["network"].items()
                if (selected == "Σ" and name != "lo") or name == selected
            ]
            return [
                sum(value[key] for value in values) / 1024**2
                if values and all(value[key] is not None for value in values)
                else None
                for key in ("download", "upload")
            ]

        cpu = [[row["cpu"]] for row in rows]
        ram = [[row["memory"]["percent"]] for row in rows]
        network = [rates(row) for row in rows]
        disk = [
            [None if row["disk"][key] is None else row["disk"][key] / 1024**2 for key in ("read", "write")]
            for row in rows
        ]
        times = [row["monotonic"] for row in rows]
        self.window.graphs["cpu"].points = cpu
        self.window.graphs["memory"].points = ram
        self.window.graphs["network"].points = network
        self.window.graphs["disk"].points = disk
        self.window.cards["network"].setText("↓ " + number(network[-1][0]) + "\n↑ " + number(network[-1][1]))
        for key, points in [("cpu", cpu), ("memory", ram), ("network", [[row[0]] for row in network])]:
            self.sparks[key].points = points
            self.sparks[key].times = times
            self.sparks[key].update()
        self.sparks["disk"].points = [[row.get("root_usage")] for row in rows]
        self.sparks["disk"].times = times
        self.sparks["disk"].update()
        mode = self.mode.currentIndex()
        colors = LIGHT_ACCENTS if self.window.preferences["theme"] == "light" else ACCENTS
        if mode == 0:
            self.chart.points = [[row[0], other[0]] for row, other in zip(cpu, ram, strict=True)]
            self.chart.maximum = 100
            self.chart.colors = colors[:2]
            self.chart.series_names, self.chart.unit = ["CPU", "RAM"], " %"
            self.legend.setText(
                f'<span style="color:{colors[0]}">● CPU</span> &nbsp; <span style="color:{colors[1]}">● RAM</span> · %'
            )
        elif mode == 1:
            self.chart.points, self.chart.maximum, self.chart.colors = network, None, colors[:2]
            self.chart.series_names, self.chart.unit = ["RX", "TX"], " MiB/s"
            self.legend.setText("↓ RX   ↑ TX · MiB/s")
        else:
            self.chart.points, self.chart.maximum, self.chart.colors = disk, None, [colors[2], colors[3]]
            self.chart.series_names = [self.t("Lesen", "Read"), self.t("Schreiben", "Write")]
            self.chart.unit = " MiB/s"
            self.legend.setText("R / W · MiB/s")
        self.chart.times = times
        self.chart.refresh_hover()
        self.chart.update()
