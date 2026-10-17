"""Linux Adminw21 v1 — a single Qt window with asynchronous Bash operations."""

import collections
import datetime
import json
import os
import sys

import psutil
import reports
import settings
from catalog import ACTIONS, FIELD_DE, PAGES
from client import command
from controls import QUICK_ACTIONS, ActionShelf
from dashboard import Dashboard
from monitor import Collector
from PySide6.QtCore import QProcess, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)
from runtime_check import check_runtime
from widgets import ACCENTS, LIGHT_ACCENTS, ElidedLabel, NumericItem, icon

PAGE_HINTS = {
    "dashboard": ("Live-Überblick · eine Karte anklicken, um Details zu erkunden.", "Live overview · select a card to explore its activity."),
    "processes": ("Prozesse finden, auswählen und gezielt verwalten.", "Find, select and manage individual processes."),
    "users": ("Konten durchsuchen und Aktionen für den gewählten Benutzer öffnen.", "Browse accounts and open actions for the selected user."),
    "groups": ("Gruppen und Mitgliedschaften übersichtlich verwalten.", "Inspect groups and manage their memberships."),
    "packages": ("Installierte Software prüfen, Pakete finden und Änderungen bestätigen.", "Inspect software, find packages and review changes."),
    "services": ("Dienststatus ansehen und ausgewählte Dienste verwalten.", "Inspect service status and manage selected services."),
    "network": ("Aktuelle Datenraten und Werkzeuge für die Verbindung.", "Current transfer rates and connection tools."),
    "files": ("Dateien finden, Verzeichnisse prüfen und gezielt bearbeiten.", "Find files, inspect directories and apply individual changes."),
    "backup": ("Archive erstellen, prüfen und kontrolliert wiederherstellen.", "Create, inspect and restore backup archives."),
    "cron": ("Zeitpläne lesen und eigene Aufgaben verwalten.", "Read schedules and manage application-owned tasks."),
    "storage": ("Datenträger, Dateisysteme und Mounts untersuchen.", "Inspect disks, filesystems and mounts."),
    "security": ("Verfügbare Sicherheitsprüfungen und Firewall-Aktionen.", "Available security checks and firewall actions."),
    "logs": ("Systemprotokolle nach Dienst und Text durchsuchen.", "Search system logs by service and text."),
    "reports": ("Systeminformationen sammeln und als Bericht speichern.", "Collect system information and export a report."),
    "settings": ("Sprache, Darstellung und verfügbare Funktionen.", "Language, appearance and available capabilities."),
}


class Sampler(QThread):
    result = Signal(object)
    failure = Signal(str)

    def __init__(self):
        super().__init__()
        self.collector = Collector()

    def run(self):
        while not self.isInterruptionRequested():
            try:
                self.result.emit(self.collector.sample())
            except (OSError, ValueError, RuntimeError, psutil.Error) as error:
                self.failure.emit(type(error).__name__ + ": " + str(error))
            for _ in range(20):
                if self.isInterruptionRequested():
                    return
                self.msleep(100)


def number(value, suffix=""):
    return "—" if value is None else f"{value:.1f}{suffix}"


def size(value):
    return "—" if value is None else f"{value / 1024**3:.2f} GiB"


class ActionDialog(QDialog):
    def __init__(self, spec, language, parent):
        super().__init__(parent)
        self.spec = spec
        self.setWindowTitle(spec[2 if language == "de" else 3])
        self.setMinimumSize(360, 240)
        outer = QVBoxLayout(self)
        heading = QLabel(self.windowTitle())
        heading.setObjectName("dialogHeading")
        heading.setWordWrap(True)
        outer.addWidget(heading)
        hint = QLabel(
            ("Änderungen werden vor der Ausführung bestätigt." if language == "de" else "Review and confirm before changes are applied.")
            if spec[5] else ("Informationen vom laufenden System ansehen." if language == "de" else "Inspect information from this system.")
        )
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        outer.addWidget(hint)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        form = QWidget()
        layout = QFormLayout(form)
        layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        scroll.setWidget(form)
        outer.addWidget(scroll, 1)
        self.fields = []
        self.bool_fields = {}
        for label, default in spec[4]:
            if spec[1] == "user.create" and label in ("Home: yes/no", "Sudo: yes/no"):
                edit = QCheckBox()
                edit.setText("Ja" if language == "de" else "Yes")
                edit.setChecked(default == "yes")
                self.bool_fields[label] = edit
            else:
                edit = QLineEdit(default)
                edit.setClearButtonEnabled(True)
            display_label = FIELD_DE.get(label, label) if language == "de" else label
            if label == "Home: yes/no":
                display_label = "Home-Verzeichnis erstellen" if language == "de" else "Create home directory"
            elif label == "Sudo: yes/no":
                display_label = "Sudo-Gruppe" if language == "de" else "Sudo group membership"
            layout.addRow(display_label, edit)
            self.fields.append(edit)
        self.password = self.confirm = None
        if spec[1] in ("user.create", "user.password"):
            self.password, self.confirm = QLineEdit(), QLineEdit()
            for edit in (self.password, self.confirm):
                edit.setEchoMode(QLineEdit.Password)
            layout.addRow("Passwort" if language == "de" else "Password", self.password)
            layout.addRow("Bestätigen" if language == "de" else "Confirm", self.confirm)
        self.notice = QLabel()
        self.notice.setWordWrap(True)
        outer.addWidget(self.notice)
        self.language = language
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        buttons.button(QDialogButtonBox.Ok).setText("Weiter" if language == "de" else "Continue")
        buttons.button(QDialogButtonBox.Ok).setObjectName("primaryButton")
        buttons.button(QDialogButtonBox.Cancel).setText("Abbrechen" if language == "de" else "Cancel")
        available = self.screen().availableGeometry()
        self.resize(min(620, available.width() - 40), min(layout.sizeHint().height() + 180, available.height() - 80))

    def validate(self):
        if self.password and (
            not self.password.text()
            or self.password.text() != self.confirm.text()
            or "\n" in self.password.text()
            or "\r" in self.password.text()
            or "\0" in self.password.text()
        ):
            self.notice.setText(
                "Passwörter stimmen nicht überein / ungültig."
                if self.language == "de"
                else "Passwords do not match / invalid."
            )
            return
        self.accept()

    def arguments(self):
        return [("yes" if f.isChecked() else "no") if isinstance(f, QCheckBox) else f.text() for f in self.fields]


class Window(QMainWindow):
    def __init__(self, start_sampler=True, start_jobs=True):
        super().__init__()
        self.preferences = settings.read()
        self.language = self.preferences["language"]
        self.history = collections.deque(maxlen=2700)
        self.snapshot, self.checks, self.process_map = {}, [], {}
        self.active_jobs = set()
        self.start_jobs = start_jobs
        self._closing = False
        self._monitor_available = None
        self.action_shelves, self.action_launchers = {}, {}
        self.action_widgets = collections.defaultdict(list)
        self.pages, self.buttons, self.headings = {}, [], []
        self.page_hints = {}
        self.setWindowTitle("Linux Adminw21 v1")
        available = self.screen().availableGeometry()
        self.setMinimumSize(min(760, max(360, available.width() - 40)), min(520, max(320, available.height() - 60)))
        self.resize(min(1440, available.width() - 40), min(960, available.height() - 60))
        self._sidebar_compact_requested = None
        main = QWidget()
        main.setObjectName("applicationRoot")
        self.setCentralWidget(main)
        root = QHBoxLayout(main)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.nav_panel = QFrame()
        self.nav_panel.setObjectName("navigation")
        self.nav_panel.setFixedWidth(200)
        nav = QVBoxLayout(self.nav_panel)
        nav.setContentsMargins(12, 18, 12, 12)
        self.brand = QLabel("  >_  ADMINW21")
        self.brand.setObjectName("brand")
        nav.addWidget(self.brand)
        self.version = QLabel("      LINUX CONTROL CENTER  ·  v1")
        self.version.setObjectName("smallMuted")
        nav.addWidget(self.version)
        nav.addSpacing(15)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setIconSize(QSize(22, 22))
        self.sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav.addWidget(self.sidebar, 1)
        self.nav_footer = QLabel("  ●  Local system")
        self.nav_footer.setObjectName("muted")
        nav.addWidget(self.nav_footer)
        root.addWidget(self.nav_panel)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        header = QFrame()
        header.setObjectName("topBar")
        header.setMinimumHeight(56)
        header.setMaximumHeight(72)
        bar = QHBoxLayout(header)
        bar.setContentsMargins(22, 10, 24, 10)
        self.collapse = QPushButton("☰")
        self.collapse.setObjectName("quietButton")
        self.collapse.setFixedWidth(35)
        self.collapse.clicked.connect(self.toggle_sidebar)
        bar.addWidget(self.collapse)
        self.breadcrumb = ElidedLabel()
        self.breadcrumb.setObjectName("breadcrumb")
        bar.addWidget(self.breadcrumb, 1)
        self.global_search = QLineEdit()
        self.global_search.setMinimumWidth(150)
        self.global_search.setMaximumWidth(390)
        self.global_search.textChanged.connect(self.filter_navigation)
        self.global_search.returnPressed.connect(self.search_everywhere)
        bar.addWidget(self.global_search, 1)
        bar.addSpacing(12)
        self.header_language = QComboBox()
        self.header_language.addItems(["DE", "EN"])
        self.header_language.setCurrentIndex(0 if self.language == "de" else 1)
        self.header_language.currentIndexChanged.connect(self.change_language)
        self.header_language.setFixedWidth(65)
        bar.addWidget(self.header_language)
        self.theme_button = QPushButton("◐")
        self.theme_button.setObjectName("iconButton")
        self.theme_button.setFixedWidth(36)
        self.theme_button.clicked.connect(lambda: self.change_theme(1 if self.preferences["theme"] == "dark" else 0))
        bar.addWidget(self.theme_button)
        self.live_badge = QLabel()
        self.live_badge.setObjectName("liveBadge")
        bar.addWidget(self.live_badge)
        self.clock = QLabel()
        self.clock.setObjectName("muted")
        self.clock.setMinimumWidth(90)
        bar.addWidget(self.clock)
        right.addWidget(header)
        self.notification = QFrame()
        self.notification.setObjectName("notification")
        notice_row = QHBoxLayout(self.notification)
        notice_row.setContentsMargins(20, 8, 20, 8)
        self.notification_label = ElidedLabel()
        notice_row.addWidget(self.notification_label, 1)
        self.notification_view = self.button(notice_row, "Ergebnis", "View result", self.show_notification_result)
        self.notification_view.setObjectName("quietButton")
        self.notification_close = QPushButton("×")
        self.notification_close.setObjectName("quietButton")
        self.notification_close.setFixedWidth(28)
        self.notification_close.clicked.connect(self.notification.hide)
        notice_row.addWidget(self.notification_close)
        right.addWidget(self.notification)
        self.notification.hide()
        self.notification_timer = QTimer(self)
        self.notification_timer.setSingleShot(True)
        self.notification_timer.timeout.connect(self.notification.hide)
        self.stack = QStackedWidget()
        self.stack.setObjectName("pageStack")
        right.addWidget(self.stack, 1)
        root.addLayout(right, 1)
        self.job_progress = QProgressBar()
        self.job_progress.setRange(0, 0)
        self.job_progress.setFixedSize(110, 6)
        self.statusBar().addPermanentWidget(self.job_progress)
        self.job_progress.hide()
        for page, german, english in PAGES:
            container = QWidget()
            vertical = QVBoxLayout(container)
            vertical.setContentsMargins(22, 16, 22, 18)
            vertical.setSpacing(14)
            title = QLabel()
            title.setObjectName("heading")
            vertical.addWidget(title)
            hint = QLabel()
            hint.setObjectName("muted")
            hint.setWordWrap(True)
            vertical.addWidget(hint)
            self.page_hints[page] = hint
            self.headings.append((title, german, english))
            self.pages[page] = (container, vertical)
            if page == "dashboard":
                self.stack.addWidget(container)
            else:
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setFrameShape(QFrame.NoFrame)
                scroll.setWidget(container)
                self.stack.addWidget(scroll)
            if page == "dashboard":
                self.build_dashboard(vertical)
            elif page == "processes":
                self.build_processes(vertical)
            elif page == "users":
                self.build_users(vertical)
            elif page == "reports":
                self.build_reports(vertical)
            elif page == "settings":
                self.build_settings(vertical)
            else:
                self.build_actions(page, vertical)
        self.sidebar.currentRowChanged.connect(self.page_changed)
        self.translate()
        self.sidebar.setCurrentRow(0)
        self.apply_theme()
        self.sampler = Sampler()
        self.sampler.result.connect(self.render)
        self.sampler.failure.connect(self.monitor_error)
        if start_sampler:
            self.sampler.start()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.auto_refresh)
        self.refresh_timer.start(10000)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        self.update_clock()
        self.shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self.shortcut.activated.connect(self.global_search.setFocus)
        self.escape_search = QShortcut(QKeySequence("Escape"), self)
        self.escape_search.activated.connect(self.global_search.clear)
        self.update_responsive_layout()
        self.update_job_controls()

    def t(self, de, en):
        return de if self.language == "de" else en

    def button(self, layout, german, english, callback):
        button = QPushButton()
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(callback)
        layout.addWidget(button)
        self.buttons.append((button, german, english))
        return button

    def build_dashboard(self, layout):
        self.dashboard = Dashboard(self)
        layout.addWidget(self.dashboard, 1)

    def table(self, headings):
        table = QTableWidget(0, len(headings))
        table.setHorizontalHeaderLabels(headings)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSortingEnabled(True)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.ElideRight)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setMinimumSectionSize(45)
        table.horizontalHeader().setSortIndicator(0, Qt.AscendingOrder)
        table.setFrameShape(QFrame.NoFrame)
        return table

    def build_processes(self, layout):
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("PID / Name / Command")
        self.search.textChanged.connect(self.render_processes)
        self.owner = QComboBox()
        self.owner.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.owner.setMinimumContentsLength(6)
        self.owner.addItem("Σ")
        self.owner.currentTextChanged.connect(self.render_processes)
        self.state = QComboBox()
        self.state.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.state.setMinimumContentsLength(6)
        self.state.addItems(["Σ", "running", "sleeping", "disk-sleep", "stopped", "zombie"])
        self.state.currentTextChanged.connect(self.render_processes)
        row.addWidget(self.search)
        row.addWidget(self.owner)
        row.addWidget(self.state)
        layout.addLayout(row)
        self.process_table = self.table(
            ["PID", "User", "Name", "CPU %", "RAM %", "RSS MiB", "Status", "PPID", "Threads", "Start", "Command"]
        )
        layout.addWidget(self.process_table)
        actions = QHBoxLayout()
        self.button(actions, "Details", "Details", self.process_details)
        self.button(actions, "SIGTERM senden", "Send SIGTERM", lambda: self.signal_process("TERM"))
        danger = self.button(actions, "SIGKILL senden", "Send SIGKILL", lambda: self.signal_process("KILL"))
        danger.setProperty("danger", True)
        layout.addLayout(actions)
        self.process_result = QPlainTextEdit()
        self.process_result.setReadOnly(True)
        self.process_result.setMaximumHeight(85)
        layout.addWidget(self.process_result)

    def build_users(self, layout):
        row = QHBoxLayout()
        self.user_filter = QLineEdit()
        self.user_filter.textChanged.connect(self.filter_users)
        self.user_kind = QComboBox()
        self.user_kind.addItems(["Σ", "Regular", "System"])
        self.user_kind.currentIndexChanged.connect(self.filter_users)
        row.addWidget(self.user_filter)
        row.addWidget(self.user_kind)
        self.create_user_button = self.button(row, "+ Benutzer", "+ New user", self.create_user)
        self.create_user_button.setObjectName("primaryButton")
        self.action_widgets["user.create"].append(self.create_user_button)
        layout.addLayout(row)
        self.uid_min = 1000
        self.users_table = self.table(["User", "UID", "GID", "Info", "Home", "Shell"])
        layout.addWidget(self.users_table)
        self.users_table.itemSelectionChanged.connect(self.update_user_controls)
        selected = QHBoxLayout()
        self.user_selection = ElidedLabel()
        self.user_selection.setObjectName("muted")
        selected.addWidget(self.user_selection, 1)
        self.user_details_button = self.button(selected, "Details", "Details", lambda: self.open_user_action("users.info"))
        self.user_password_button = self.button(selected, "Passwort ändern", "Change password", lambda: self.open_user_action("user.password"))
        layout.addLayout(selected)
        self.build_actions("users", layout, output_height=100)
        self.button(layout, "Liste aktualisieren", "Refresh list", self.load_users)
        self.update_user_controls()
        if self.start_jobs:
            QTimer.singleShot(100, self.load_users)

    def build_actions(self, page, layout, output_height=None):
        if page == "network":
            self.network_table = self.table(
                ["Interface", "State", "RX MiB/s", "TX MiB/s", "RX GiB", "TX GiB", "Errors in/out", "Drops in/out"]
            )
            self.network_table.setMaximumHeight(230)
            layout.addWidget(self.network_table)
        specs = [spec for spec in ACTIONS if spec[0] == page]
        if page in QUICK_ACTIONS:
            shelf = ActionShelf(page, specs, lambda spec: self.open_action(spec, page))
            self.action_shelves[page] = shelf
            layout.addWidget(shelf)
            for tile in shelf.tiles:
                self.action_widgets[tile.spec[1]].append(tile)
        toolbar = QHBoxLayout()
        choose = QComboBox()
        choose.setMinimumWidth(240)
        choose.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        choose.setMinimumContentsLength(16)
        choose.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.action_choices = getattr(self, "action_choices", {})
        self.action_choices[page] = (choose, specs)
        choose.currentIndexChanged.connect(self.update_job_controls)
        toolbar.addWidget(choose, 1)
        launch = self.button(
            toolbar, "Aktion öffnen", "Open action", lambda: self.open_action(specs[choose.currentIndex()], page)
        )
        launch.setObjectName("primaryButton")
        self.action_launchers[page] = launch
        layout.addLayout(toolbar)
        output = QPlainTextEdit()
        output.setReadOnly(True)
        output.setObjectName("operationOutput")
        output.setPlaceholderText(
            self.t(
                "Aktion auswählen. Ergebnisse und Fehler erscheinen hier.",
                "Choose an action. Results and errors appear here.",
            )
        )
        if output_height:
            output.setMaximumHeight(output_height)
        layout.addWidget(output, 1)
        self.pages[page] += (output,)

    def selected_user(self):
        row = self.users_table.currentRow()
        if row < 0 or self.users_table.isRowHidden(row):
            return None
        user, uid = self.users_table.item(row, 0), self.users_table.item(row, 1)
        return (user.text(), int(uid.text())) if user and uid else None

    def update_user_controls(self):
        if not hasattr(self, "user_selection"):
            return
        selected = self.selected_user()
        busy = {job.property("action") for job in self.active_jobs}
        self.user_selection.setText(
            selected[0] + f"  ·  UID {selected[1]}" if selected else self.t("Benutzer auswählen", "Select a user")
        )
        self.user_details_button.setEnabled(bool(selected) and "users.info" not in busy)
        regular = selected and self.uid_min <= selected[1] < 65534
        self.user_password_button.setEnabled(bool(regular) and "user.password" not in busy)

    def open_user_action(self, action):
        if self.selected_user():
            self.open_action(next(s for s in ACTIONS if s[1] == action), "users")

    def build_reports(self, layout):
        self.report_output = QPlainTextEdit()
        self.report_output.setReadOnly(True)
        layout.addWidget(self.report_output)
        self.button(layout, "Daten für Bericht sammeln", "Collect report data", self.collect_report)
        self.button(
            layout, "Bericht speichern (TXT / JSON / HTML)", "Export report (TXT / JSON / HTML)", self.export_report
        )

    def build_settings(self, layout):
        self.language_combo = QComboBox()
        self.language_combo.addItems(["Deutsch", "English"])
        self.language_combo.setCurrentIndex(0 if self.language == "de" else 1)
        self.language_combo.currentIndexChanged.connect(self.change_language)
        layout.addWidget(self.language_combo)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        self.theme_combo.setCurrentIndex(0 if self.preferences["theme"] == "dark" else 1)
        self.theme_combo.currentIndexChanged.connect(self.change_theme)
        layout.addWidget(self.theme_combo)
        self.build_actions("settings", layout)
        self.button(layout, "Laufende Leseaktion abbrechen", "Cancel running read operation", self.cancel_read_jobs)

    def translate(self):
        selected = self.sidebar.currentRow()
        self.sidebar.blockSignals(True)
        self.sidebar.clear()
        for page, de, en in PAGES:
            item = QListWidgetItem(icon(page), self.t(de, en))
            item.setToolTip(self.t(de, en))
            item.setData(Qt.UserRole, page)
            self.sidebar.addItem(item)
        self.sidebar.setCurrentRow(max(0, selected))
        self.sidebar.blockSignals(False)
        for label, de, en in self.headings:
            label.setText(self.t(de, en))
        for page, label in self.page_hints.items():
            label.setText(self.t(*PAGE_HINTS[page]))
        for button, de, en in self.buttons:
            button.setText(self.t(de, en))
        for shelf in self.action_shelves.values():
            for tile in shelf.tiles:
                tile.translate(self.language)
        for choose, specs in getattr(self, "action_choices", {}).values():
            current = choose.currentIndex()
            choose.clear()
            choose.addItems([spec[2 if self.language == "de" else 3] for spec in specs])
            choose.setCurrentIndex(max(0, current))
        if hasattr(self, "user_kind"):
            self.user_kind.setItemText(1, self.t("Reguläre Konten", "Regular accounts"))
            self.user_kind.setItemText(2, self.t("Systemkonten", "System accounts"))
            self.user_filter.setPlaceholderText(self.t("Benutzer suchen…", "Search users…"))
            self.users_table.setHorizontalHeaderLabels(
                [self.t("Benutzer", "User"), "UID", "GID", "Info", "Home", "Shell"]
            )
        self.process_table.setHorizontalHeaderLabels(
            [
                "PID",
                self.t("Benutzer", "User"),
                self.t("Name", "Name"),
                "CPU %",
                "RAM %",
                "RSS MiB",
                "Status",
                "PPID",
                "Threads",
                self.t("Startzeit", "Start"),
                self.t("Befehl", "Command"),
            ]
        )
        self.global_search.setPlaceholderText(
            self.t("Seite oder Prozess suchen…  Ctrl+K", "Find a page or process…  Ctrl+K")
        )
        self.nav_footer.setText(self.t("  ●  Lokales System", "  ●  Local system"))
        self.dashboard.translate()
        self.theme_button.setToolTip(self.t("Design wechseln", "Switch theme"))
        self.notification_close.setToolTip(self.t("Schließen", "Dismiss"))
        self.update_user_controls()
        self.update_job_controls()
        self.page_changed(max(0, selected))
        if self.nav_panel.width() < 100:
            self.set_compact_labels()
        self.filter_navigation(self.global_search.text())

    def change_language(self, index):
        self.language = "de" if index == 0 else "en"
        self.preferences["language"] = self.language
        for combo in (self.language_combo, self.header_language):
            combo.blockSignals(True)
            combo.setCurrentIndex(index)
            combo.blockSignals(False)
        self.persist_settings()
        self.translate()

    def change_theme(self, index):
        self.preferences["theme"] = "dark" if index == 0 else "light"
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(index)
        self.theme_combo.blockSignals(False)
        self.persist_settings()
        self.apply_theme()

    def persist_settings(self):
        try:
            settings.save(self.preferences)
        except OSError as error:
            self.statusBar().showMessage(str(error))

    def apply_theme(self):
        dark = self.preferences["theme"] == "dark"
        bg, card, fg, edge, muted = (
            ("#101823", "#192536", "#e8f0fa", "#2e4057", "#9bafc8")
            if dark
            else ("#edf1f7", "#ffffff", "#233247", "#d3dae5", "#637187")
        )
        nav, header, table = ("#121e2d", "#152131", "#162131") if dark else ("#e4eaf2", "#f7f9fc", "#f7f9fc")
        palette = QPalette(self.palette())
        for role, color in (
            (QPalette.Window, bg), (QPalette.WindowText, fg), (QPalette.Base, card),
            (QPalette.AlternateBase, table), (QPalette.Text, fg), (QPalette.Button, card),
            (QPalette.ButtonText, fg), (QPalette.Highlight, "#315d74" if dark else "#c5e5ef"),
            (QPalette.HighlightedText, fg), (QPalette.PlaceholderText, muted),
        ):
            palette.setColor(role, QColor(color))
        selected_bg, selected_fg = ("#24465b", fg) if dark else ("#c5e5ef", "#18384a")
        self.setStyleSheet(f"""
          QWidget {{ background:{bg}; color:{fg}; font-family:'DejaVu Sans','Noto Sans',sans-serif; font-size:13px; selection-background-color:{selected_bg};selection-color:{selected_fg}; }}
          QFrame#navigation {{background:{nav};border-right:1px solid {edge};}}
          QFrame#topBar {{background:{header};border-bottom:1px solid {edge};}}
          QFrame#panel {{background:{card};border:1px solid {edge};border-radius:12px;}}
          QFrame#panel[interactive="true"]:hover,QFrame#panel[interactive="true"]:focus {{border:1px solid #4cd1df;background:{'#1c3044' if dark else '#effbfc'};}}
          QFrame#panel[selected="true"] {{border:1px solid {'#376d7f' if dark else '#75aeb8'};}}
          QFrame#actionTile {{background:{card};border:1px solid {edge};border-radius:10px;}}
          QFrame#actionTile:hover,QFrame#actionTile:focus {{background:{'#20364b' if dark else '#effbfc'};border:1px solid #46b8c7;}}
          QLabel:disabled {{color:{muted};}}
          QFrame#actionTile[down="true"],QFrame#panel[down="true"] {{background:{'#29485d' if dark else '#d5edf3'};border-color:#78e2e9;}}
          QLabel#actionTitle {{font-size:13px;font-weight:600;}}
          QLabel#actionArrow {{font-size:23px;color:{muted};}}
          QFrame#notification {{background:{'#183b3b' if dark else '#e0f3ee'};border-bottom:1px solid {'#3b7866' if dark else '#a3d7c4'};}}
          QFrame#notification[error="true"] {{background:{'#422d35' if dark else '#fbe8e9'};border-color:#ad5b6c;}}
          QLabel {{background:transparent;}}
          QLabel#heading {{font-size:23px;font-weight:600;padding:0 0 2px 0;}}
          QLabel#dialogHeading {{font-size:20px;font-weight:600;}}
          QLabel#brand {{font-size:18px;font-weight:700;color:{'#56d7df' if dark else '#087e8b'};padding:6px 0;}}
          QLabel#smallMuted {{font-size:8px;color:{muted};}}
          QLabel#muted,QLabel#systemLine {{font-size:11px;color:{muted};}}
          QLabel#systemLine {{padding:5px;}}
          QLabel#panelTitle {{font-size:13px;font-weight:600;}}
          QLabel#metricValue {{font-size:26px;font-weight:600;}}
          QLabel#networkValue {{font-size:20px;font-weight:600;}}
          QLabel#badge {{background:#293f49;color:#66dec6;padding:4px 7px;border-radius:4px;font-size:9px;}}
          QLabel#liveBadge {{background:{'#203d3d' if dark else '#d7efe6'};color:{'#72dfbe' if dark else '#146849'};padding:6px 9px;border-radius:10px;font-size:10px;}}
          QLabel#liveBadge[state="error"] {{background:{'#4a3038' if dark else '#fbe4e6'};color:{'#ffb0b0' if dark else '#9c2433'};}}
          QLabel#liveBadge[state="busy"] {{background:{'#293b53' if dark else '#e0eafa'};color:{'#b2d5ff' if dark else '#265491'};}}
          QLabel#serviceChip {{background:{'#234c43' if dark else '#d9f2e7'};color:{'#70dfbb' if dark else '#126347'};border:1px solid {'#35735e' if dark else '#96cdb5'};padding:7px;border-radius:5px;font-size:11px;}}
          QLabel#failedChip {{background:{'#4e2e35' if dark else '#fbe4e6'};color:{'#ffb0b0' if dark else '#9c2433'};padding:7px;border-radius:5px;font-size:11px;}}
          QLabel#inactiveChip {{background:{table};color:{muted};padding:7px;border-radius:5px;font-size:11px;}}
          QListWidget#sidebar {{background:transparent;border:0;outline:0;}}
          QListWidget#sidebar::item {{height:39px;padding-left:9px;margin:2px 0;border-radius:5px;color:{muted};}}
          QListWidget#sidebar::item:selected {{background:{selected_bg};color:{'#72e2e5' if dark else '#125367'};border-left:3px solid #4ed1db;}}
          QListWidget#sidebar::item:hover {{background:{'#303a49' if dark else '#d8e3ee'};}}
          QPushButton {{background:{'#213248' if dark else '#ffffff'};border:1px solid {edge};border-radius:7px;padding:9px 12px;font-size:11px;}}
          QPushButton:hover {{background:{'#2a435a' if dark else '#eaf5fa'};border-color:#55bfc9;}}
          QPushButton:pressed {{background:{'#31546b' if dark else '#d3eaf3'};border-color:#78e2e9;}}
          QPushButton:focus {{border:1px solid #67d6e0;}}
          QPushButton:disabled {{background:{table};color:{muted};border-color:{edge};}}
          QPushButton#primaryButton {{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #168b9c,stop:1 #087589);color:white;border-color:#259aaa;font-weight:600;}}
          QPushButton#primaryButton:hover {{background:#1694a5;}}
          QPushButton#primaryButton:pressed {{background:#086579;}}
          QPushButton#primaryButton:disabled {{background:{edge};color:{muted};border-color:{edge};}}
          QPushButton[danger="true"] {{color:{'#ffb1bd' if dark else '#a32640'};border-color:{'#794552' if dark else '#d4a0ac'};}}
          QPushButton#segmentButton {{padding:6px 3px;font-size:10px;border-radius:5px;background:transparent;}}
          QPushButton#segmentButton:checked {{background:{'#24485b' if dark else '#ceeaf1'};color:{'#83edf0' if dark else '#0b5e71'};border-color:{'#428196' if dark else '#7cb8c5'};}}
          QPushButton#iconButton {{padding:5px;font-size:18px;}}
          QPushButton#quietButton {{background:transparent;border:0;padding:5px;}}
          QPushButton#quietButton:hover {{background:{'#284257' if dark else '#d9edf5'};}}
          QPushButton#quietButton:focus {{border:1px solid #67d6e0;}}
          QLineEdit,QComboBox {{background:{table};border:1px solid {edge};border-radius:5px;padding:7px;selection-background-color:{selected_bg};selection-color:{selected_fg};}}
          QComboBox::drop-down {{border:0;width:20px;}}
          QTableWidget {{background:{card};alternate-background-color:{table};border:0;selection-background-color:{selected_bg};selection-color:{selected_fg};}}
          QHeaderView::section {{background:{table};border:0;border-bottom:1px solid {edge};padding:8px 5px;color:{muted};font-size:11px;}}
          QPlainTextEdit {{background:{card};border:1px solid {edge};border-radius:7px;padding:12px;selection-background-color:{selected_bg};selection-color:{selected_fg};}}
          QProgressBar {{background:{table};border:0;border-radius:3px;text-align:center;font-size:9px;color:{fg};}}
          QProgressBar::chunk {{background:#2ebc9c;border-radius:3px;}}
          QScrollArea {{background:transparent;border:0;}}
          QScrollBar:vertical {{background:transparent;width:8px;margin:0;}}
          QScrollBar::handle:vertical {{background:{edge};border-radius:4px;min-height:28px;}}
          QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}}
          QScrollBar:horizontal {{background:{table};height:10px;margin:0;}}
          QScrollBar::handle:horizontal {{background:{edge};border-radius:4px;min-width:28px;}}
          QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal {{width:0;}}
          QStatusBar {{background:{header};border-top:1px solid {edge};font-size:11px;color:{muted};}}
          QToolTip {{background:{card};color:{fg};border:1px solid {edge};padding:5px;}}
        """)
        self.setPalette(palette)
        accents = ACCENTS if dark else LIGHT_ACCENTS
        for index, key in enumerate(("cpu", "memory", "disk", "network")):
            self.cards[key].setStyleSheet(f"color:{accents[index]};")
            self.dashboard.sparks[key].colors = [accents[index]]
        for index, (page, _, _) in enumerate(PAGES):
            self.sidebar.item(index).setIcon(icon(page, muted))
        for shelf in self.action_shelves.values():
            for tile in shelf.tiles:
                tile.set_accent(accents[0] if not tile.spec[5] else accents[2])
        for graph in [self.dashboard.chart, *self.dashboard.sparks.values()]:
            graph.light = not dark
            graph.update()
        self.dashboard.redraw(self.history)

    def open_action(self, spec, page):
        if any(job.property("action") == spec[1] for job in self.active_jobs):
            self.statusBar().showMessage(self.t("Diese Aktion läuft bereits.", "This action is already running."))
            return
        if not spec[4] and not spec[5]:
            self.run_action(spec[1], [], False, self.pages[page][2])
            return
        dialog = ActionDialog(spec, self.language, self)
        selected = self.selected_user() if page == "users" and spec[1] != "user.create" else None
        if selected:
            for field, (label, _) in zip(dialog.fields, spec[4], strict=True):
                if label == "Username":
                    field.setText(selected[0])
        if dialog.exec() != QDialog.Accepted:
            return
        args = dialog.arguments()
        if spec[5]:
            preview = spec[1] + "\n" + "\n".join(args)
            if QMessageBox.question(self, self.t("Änderung bestätigen", "Confirm change"), preview) != QMessageBox.Yes:
                dialog.password.clear() if dialog.password else None
                return
        secret = (dialog.password.text() + "\n").encode() if dialog.password else b""
        if dialog.password:
            dialog.password.clear()
            dialog.confirm.clear()
        self.run_action(spec[1], args, spec[5], self.pages[page][2], secret)

    def run_action(self, action, args, privileged, output, secret=b"", callback=None, quiet=False):
        if self._closing:
            return
        generation = output.property("requestGeneration") or 0
        if not quiet:
            generation += 1
            output.setProperty("requestGeneration", generation)
            self.notification.hide()
            self.notification_timer.stop()
        try:
            cmd = command(action, args, privileged)
        except RuntimeError as error:
            output.setPlainText(str(error))
            self.show_notification(action, False, output)
            return
        process = QProcess(self)
        process.setProperty("privileged", privileged)
        process.setProperty("action", action)
        self.active_jobs.add(process)
        self.update_job_controls()
        if not quiet:
            output.setPlainText(self.t("Aktion läuft: ", "Operation running: ") + action)
        # The captured password never becomes argv, environment, or output.
        pending = bytearray(secret)
        del secret

        def started():
            if pending:
                process.write(bytes(pending))
                pending[:] = b"\0" * len(pending)
                pending.clear()
            process.closeWriteChannel()

        process.started.connect(started)

        completed = False

        def finished(code, status):
            nonlocal completed
            if completed:
                return
            completed = True
            pending[:] = b"\0" * len(pending)
            pending.clear()
            raw = bytes(process.readAllStandardOutput()).decode(errors="replace")
            stderr = bytes(process.readAllStandardError()).decode(errors="replace")
            try:
                response = json.loads(raw)
                message = response["output"]
                if not isinstance(message, str) or not isinstance(response["ok"], bool):
                    raise ValueError("Invalid backend response")
                ok = response["ok"] and code == 0 and status == QProcess.NormalExit
            except (ValueError, KeyError, TypeError):
                message = (
                    stderr
                    or raw
                    or self.t(
                        "Authentifizierung abgebrochen / Backend nicht verfügbar.",
                        "Authentication cancelled / backend unavailable.",
                    )
                )
                ok = False
            if (not quiet or not ok) and (output.property("requestGeneration") or 0) == generation:
                output.setPlainText(("✓ " if ok else "⚠ ") + message)
                self.show_notification(action, ok, output)
            self.checks.append(
                {
                    "action": action,
                    "ok": ok,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "output": message if not privileged else "[administrative result]",
                }
            )
            self.checks = self.checks[-200:]
            self.active_jobs.discard(process)
            self.update_job_controls()
            if callback:
                callback(message, ok)
            if action.startswith("user.") and not self._closing:
                self.load_users()
            process.deleteLater()

        process.finished.connect(finished)

        def error(err):
            if err == QProcess.FailedToStart:
                pending[:] = b"\0" * len(pending)
                pending.clear()
                finished(127, QProcess.CrashExit)

        process.errorOccurred.connect(error)
        if not privileged and os.path.isfile("/usr/bin/timeout"):
            cmd = ["/usr/bin/timeout", "--signal=TERM", "--kill-after=2s", "60s", *cmd]
        process.start(cmd[0], cmd[1:])

    def update_job_controls(self, *_):
        busy = {job.property("action") for job in self.active_jobs}
        self.job_progress.setVisible(bool(self.active_jobs))
        for action, widgets in self.action_widgets.items():
            for widget in widgets:
                widget.setEnabled(action not in busy)
        for page, launcher in self.action_launchers.items():
            choose, specs = self.action_choices[page]
            index = choose.currentIndex()
            launcher.setEnabled(0 <= index < len(specs) and specs[index][1] not in busy)
        if busy:
            text, state = f"● {len(self.active_jobs)} " + self.t("aktiv", "running"), "busy"
        elif self._monitor_available is False:
            text, state = self.t("● Nicht verfügbar", "● Unavailable"), "error"
        else:
            text, state = ("● Live" if self._monitor_available else self.t("● Bereit", "● Ready")), "ready"
        self.live_badge.setText(text)
        self.live_badge.setProperty("state", state)
        self.live_badge.style().unpolish(self.live_badge)
        self.live_badge.style().polish(self.live_badge)
        self.update_user_controls()

    def show_notification(self, action, ok, output):
        spec = next((s for s in ACTIONS if s[1] == action), None)
        title = spec[2 if self.language == "de" else 3] if spec else action
        self.notification_label.setText(
            ("✓ " if ok else "⚠ ") + title + " · " + (
                self.t("Abgeschlossen", "Completed") if ok else self.t("Fehlgeschlagen – Ergebnis ansehen", "Failed – view result")
            )
        )
        self.notification.setProperty("error", not ok)
        self.notification.style().unpolish(self.notification)
        self.notification.style().polish(self.notification)
        self.notification_output = output
        self.notification.show()
        self.notification_timer.start(8000)

    def show_notification_result(self):
        output = getattr(self, "notification_output", None)
        for page, values in self.pages.items():
            if len(values) > 2 and values[2] is output:
                self.navigate(page)
                area = self.stack.currentWidget()
                if isinstance(area, QScrollArea):
                    area.ensureWidgetVisible(output)
                return
        if output is self.process_result:
            self.navigate("processes")
        elif output is self.report_output:
            self.navigate("reports")

    def load_users(self):
        if self._closing:
            return
        def done(message, ok):
            if not ok:
                return
            selected = self.selected_user()
            vertical = self.users_table.verticalScrollBar().value()
            for line in message.splitlines():
                if line.startswith("UID_MIN="):
                    self.uid_min = int(line.split("=", 1)[1])
            self.users_table.setSortingEnabled(False)
            lines = [line.split(":") for line in message.splitlines() if len(line.split(":")) == 7]
            self.users_table.setRowCount(len(lines))
            for row, line in enumerate(lines):
                for col, value in enumerate([line[0], line[2], line[3], line[4], line[5], line[6]]):
                    item = NumericItem(value)
                    if col in (1, 2):
                        item.setData(Qt.UserRole, int(value))
                    item.setToolTip(value)
                    self.users_table.setItem(row, col, item)
            self.users_table.setSortingEnabled(True)
            self.users_table.clearSelection()
            self.users_table.setCurrentCell(-1, -1)
            self.filter_users()
            if selected:
                for row in range(self.users_table.rowCount()):
                    if (self.users_table.item(row, 0).text(), int(self.users_table.item(row, 1).text())) == selected:
                        self.users_table.selectRow(row)
                        break
            self.users_table.verticalScrollBar().setValue(vertical)
            self.update_user_controls()

        self.run_action("users.list", [], False, self.pages["users"][2], callback=done, quiet=True)

    def filter_users(self):
        query = self.user_filter.text().lower()
        kind = self.user_kind.currentIndex()
        for row in range(self.users_table.rowCount()):
            uid = int(self.users_table.item(row, 1).text())
            regular = self.uid_min <= uid < 65534
            match = query in " ".join(self.users_table.item(row, c).text() for c in range(6)).lower()
            self.users_table.setRowHidden(row, not match or (kind == 1 and not regular) or (kind == 2 and regular))
        self.update_user_controls()

    def render(self, data):
        self._monitor_available = True
        self.snapshot = data
        root = next((item for item in data["storage"] if item["mount"] == "/"), None)
        record = {key: data[key] for key in ("monotonic", "cpu", "memory", "network", "disk")}
        record["root_usage"] = root["percent"] if root else None
        self.history.append(record)
        self.dashboard.update_data(data)
        self.network_table.setSortingEnabled(False)
        self.network_table.setRowCount(len(data["network"]))
        for row, (name, net) in enumerate(data["network"].items()):
            values = [
                name,
                "—" if net["up"] is None else ("UP" if net["up"] else "DOWN"),
                number(None if net["download"] is None else net["download"] / 1024**2),
                number(None if net["upload"] is None else net["upload"] / 1024**2),
                size(net["rx"]),
                size(net["tx"]),
                f"{net['errors_in']}/{net['errors_out']}",
                f"{net['drops_in']}/{net['drops_out']}",
            ]
            numeric = {2: net["download"], 3: net["upload"], 4: net["rx"], 5: net["tx"],
                       6: net["errors_in"] + net["errors_out"], 7: net["drops_in"] + net["drops_out"]}
            for col, value in enumerate(values):
                item = NumericItem(value)
                if col in numeric:
                    item.setData(Qt.UserRole, numeric[col])
                item.setToolTip(value)
                self.network_table.setItem(row, col, item)
        self.network_table.setSortingEnabled(True)
        self.render_processes()
        self.update_job_controls()
        if not self.active_jobs:
            self.statusBar().showMessage(
                self.t("Live · Messintervall 2 s · Sitzungen 10 s", "Live · metrics 2 s · sessions 10 s")
            )

    def redraw_graphs(self):
        self.dashboard.redraw(self.history)

    def render_processes(self):
        if not self.snapshot:
            return
        selected = self.selected_process()
        owners = ["Σ", *sorted({p["username"] or "?" for p in self.snapshot["processes"]})]
        if [self.owner.itemText(i) for i in range(self.owner.count())] != owners:
            previous = self.owner.currentText()
            self.owner.blockSignals(True)
            self.owner.clear()
            self.owner.addItems(owners)
            self.owner.setCurrentText(previous if previous in owners else "Σ")
            self.owner.blockSignals(False)
        query = self.search.text().lower()
        procs = [
            p
            for p in self.snapshot["processes"]
            if query in f"{p['pid']} {p['name']} {p['command']}".lower()
            and (self.owner.currentText() == "Σ" or p["username"] == self.owner.currentText())
            and (self.state.currentText() == "Σ" or p["status"] == self.state.currentText())
        ]
        self.process_map = {p["pid"]: p for p in procs}
        table = self.process_table
        vertical = table.verticalScrollBar().value()
        horizontal = table.horizontalScrollBar().value()
        table.setSortingEnabled(False)
        table.setRowCount(len(procs))
        for row, p in enumerate(procs):
            values = [
                p["pid"],
                p["username"],
                p["name"],
                p["cpu_percent"],
                p["memory_percent"],
                p["rss"] / 1024**2,
                p["status"],
                p["ppid"],
                p["num_threads"],
                datetime.datetime.fromtimestamp(p["create_time"]).strftime("%Y-%m-%d %H:%M:%S"),
                p["command"],
            ]
            for col, value in enumerate(values):
                item = NumericItem(
                    number(value) if isinstance(value, float) else str(value) if value is not None else "—"
                )
                if isinstance(value, (int, float)):
                    item.setData(Qt.UserRole, value)
                item.setToolTip(item.text())
                table.setItem(row, col, item)
        table.setSortingEnabled(True)
        table.clearSelection()
        table.setCurrentCell(-1, -1)
        if selected:
            for row in range(table.rowCount()):
                current = self.process_map[int(table.item(row, 0).text())]
                if (current["pid"], current["create_time"]) == (selected["pid"], selected["create_time"]):
                    table.selectRow(row)
                    break
        table.verticalScrollBar().setValue(vertical)
        table.horizontalScrollBar().setValue(horizontal)

    def selected_process(self):
        row = self.process_table.currentRow()
        item = self.process_table.item(row, 0) if row >= 0 else None
        return self.process_map.get(int(item.text())) if item else None

    def process_details(self):
        proc = self.selected_process()
        if proc:
            QMessageBox.information(self, "Process", json.dumps(proc, ensure_ascii=False, indent=2))

    def signal_process(self, sig):
        proc = self.selected_process()
        if not proc:
            return
        preview = f"SIG{sig}\nPID {proc['pid']} · {proc['username']} · {proc['name']}\n{proc['command']}\nStart: {proc['create_time']}"
        if QMessageBox.question(self, self.t("Prozess bestätigen", "Confirm process"), preview) != QMessageBox.Yes:
            return
        self.run_action("process.signal", [str(proc["pid"]), proc["start_ticks"], sig], True, self.process_result)

    def auto_refresh(self):
        if PAGES[self.sidebar.currentRow()][0] == "users" and not self.active_jobs:
            self.load_users()

    def cancel_read_jobs(self):
        self.report_cancelled = True
        for job in tuple(self.active_jobs):
            if not job.property("privileged"):
                job.terminate()

    def monitor_error(self, message):
        self._monitor_available = False
        self.update_job_controls()
        self.statusBar().showMessage(self.t("Überwachung nicht verfügbar: ", "Monitoring unavailable: ") + message)
        self.snapshot = {}
        self.process_map.clear()
        self.process_table.setRowCount(0)
        self.network_table.setRowCount(0)
        self.dashboard.set_unavailable(message)

    def collect_report(self):
        self.report_cancelled = False
        actions = iter(
            [
                "capabilities",
                "users.list",
                "groups.list",
                "services.list",
                "security.inspect",
                "network.info",
                "storage.info",
                "packages.updates",
            ]
        )

        def next_action(message=None, ok=None):
            if self.report_cancelled:
                self.report_output.setPlainText(self.t("Sammlung abgebrochen", "Collection cancelled"))
                return
            action = next(actions, None)
            if action:
                self.run_action(action, [], False, self.report_output, callback=next_action)
            else:
                self.report_output.setPlainText(json.dumps(self.checks, ensure_ascii=False, indent=2))

        next_action()

    def export_report(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.t("Bericht speichern", "Save report"),
            "adminw21-report.json",
            "JSON (*.json);;HTML (*.html);;Text (*.txt)",
        )
        if not path:
            return
        try:
            reports.write(path, self.snapshot, self.checks)
            self.statusBar().showMessage(self.t("Bericht gespeichert", "Report saved"))
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Report", str(error))

    def closeEvent(self, event):
        if any(job.property("privileged") for job in self.active_jobs):
            QMessageBox.information(
                self,
                self.t("Aktion läuft", "Operation running"),
                self.t(
                    "Bitte laufende administrative Aktion abschließen lassen.",
                    "Please wait for the administrative action to finish.",
                ),
            )
            event.ignore()
            return
        self._closing = True
        self.refresh_timer.stop()
        self.clock_timer.stop()
        self.notification_timer.stop()
        self.cancel_read_jobs()
        self.sampler.requestInterruption()
        if self.active_jobs or self.sampler.isRunning():
            self.statusBar().showMessage(self.t("Überwachung wird beendet…", "Stopping monitoring…"))
            event.ignore()
            QTimer.singleShot(100, self.close)
            return
        event.accept()

    def navigate(self, page):
        self.global_search.clear()
        for index, item in enumerate(PAGES):
            if item[0] == page:
                self.sidebar.setCurrentRow(index)
                return

    def page_changed(self, index):
        if index < 0:
            return
        self.stack.setCurrentIndex(index)
        self.breadcrumb.setText("Adminw21  ›  " + self.t(PAGES[index][1], PAGES[index][2]))

    def toggle_sidebar(self):
        self._sidebar_compact_requested = self.nav_panel.width() > 100
        self.update_responsive_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "clock"):
            self.update_responsive_layout()

    def update_responsive_layout(self):
        compact = self.width() < 1100 if self._sidebar_compact_requested is None else self._sidebar_compact_requested
        self.nav_panel.setFixedWidth(66 if compact else 200)
        self.nav_panel.layout().setContentsMargins(6 if compact else 12, 18, 6 if compact else 12, 12)
        self.brand.setText(" >_" if compact else "  >_  ADMINW21")
        self.version.setVisible(not compact)
        self.nav_footer.setVisible(not compact)
        if compact:
            self.set_compact_labels()
        else:
            for index, (_, de, en) in enumerate(PAGES):
                self.sidebar.item(index).setText(self.t(de, en))
        self.clock.setVisible(self.width() >= 1000)
        self.live_badge.setVisible(self.width() >= 1100)
        self.breadcrumb.setVisible(self.width() - self.nav_panel.width() >= 760)

    def set_compact_labels(self):
        for index in range(self.sidebar.count()):
            self.sidebar.item(index).setText("")

    def filter_navigation(self, query):
        query = query.casefold()
        for index, (page, de, en) in enumerate(PAGES):
            self.sidebar.setRowHidden(
                index, bool(query) and not any(query in value.casefold() for value in (page, de, en))
            )

    def search_everywhere(self):
        query = self.global_search.text().strip()
        if not query:
            return
        for page, de, en in PAGES:
            if query.casefold() in (page.casefold(), de.casefold(), en.casefold()):
                self.navigate(page)
                return
        self.navigate("processes")
        self.search.setText(query)

    def update_clock(self):
        self.clock.setText(datetime.datetime.now().strftime("%H:%M:%S"))
        self.clock.setToolTip(datetime.datetime.now().strftime("%d.%m.%Y"))

    def create_user(self):
        self.navigate("users")
        self.open_action(next(spec for spec in ACTIONS if spec[1] == "user.create"), "users")


def main():
    if os.geteuid() == 0 and "--test" not in sys.argv:
        print("Start the GUI as the desktop user: adminw21 --gui", file=sys.stderr)
        return 77
    try:
        check_runtime()
    except (ImportError, OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 69
    app = QApplication(sys.argv)
    app.setApplicationName("Linux Adminw21 v1")
    window = Window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
