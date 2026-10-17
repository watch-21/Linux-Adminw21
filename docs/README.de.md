# Linux Adminw21 v1

![Linux Adminw21 — Linux administration, desktop and terminal](assets/banner.svg)

**Linux-Ressourcen überwachen und alltägliche Administrationsaufgaben über eine native Desktop-Oberfläche oder das Terminal erledigen.**

[ZIP herunterladen](https://github.com/watch-21/Linux-Adminw21/archive/refs/heads/main.zip) · [English](../README.md) · [Abhängigkeiten](LINUX_DEPENDENCIES.md) · [Fehlerbehebung](TROUBLESHOOTING.md) · [Funktionsumfang](FEATURE_STATUS.md)

Linux Adminw21 verbindet Live-Monitoring mit Benutzer-, Gruppen-, Prozess-, Dienst- und Paketverwaltung. Die PySide6-Oberfläche und die Bash-Terminaloberfläche verwenden denselben Administrations-Backend. Die Anwendung unterstützt **Deutsch und Englisch** sowie **helle und dunkle** Desktop-Themes.

## Funktionen

| Bereich | Möglichkeiten |
|---|---|
| Systemübersicht | CPU, RAM, Swap, Datenträger und Netzwerk mit Live-Diagrammen und wählbaren Zeitbereichen |
| Benutzer und Gruppen | Konten und Mitgliedschaften verwalten; sichtbare Login-Sitzungen und Gruppen prüfen |
| Prozesse | Suchen, filtern, sortieren, Details prüfen und bestätigte TERM-/KILL-Signale senden |
| Dienste und Pakete | Unterstützte systemd-Dienste und Paketmanager der Distribution verwenden |
| Netzwerk | Schnittstellen, Adressen, Routen, DNS und Sockets prüfen; begrenzte Mitschnitte bei verfügbaren Voraussetzungen |
| Backups und Cron | Archive erstellen/prüfen, in geschützte leere Ziele wiederherstellen und unterstützte Zeitpläne verwalten |
| Dateien und Sicherheit | Unterstützte Dateiaktionen sowie SSH-, Firewall-, Login- und Journal-Abfragen |
| Berichte | Daten sammeln und als TXT, JSON oder HTML mit Zeitstempeln und fehlgeschlagenen Prüfungen exportieren |

Messwertkarten öffnen den zugehörigen Bereich. Diagramme bieten Probenwerte und Zeitbereiche; Seitensuche und kontextbezogene Aktionen erleichtern die Navigation. Details und Grenzen stehen im [Funktionsumfang](FEATURE_STATUS.md).

## Installation

Erforderlich: **Linux, Bash, Python 3.10+**, GNU coreutils/findutils und die jeweiligen Administrationsprogramme. Die GUI benötigt außerdem native Qt-Bibliotheken, Python-venv/pip, PolicyKit `pkexec` und einen laufenden PolicyKit-Agent im Desktop.

1. [Quellcode als ZIP herunterladen](https://github.com/watch-21/Linux-Adminw21/archive/refs/heads/main.zip) oder mit `git clone https://github.com/watch-21/Linux-Adminw21.git` klonen.
2. Entpacken und ein Terminal im Projektordner öffnen.
3. Die [Abhängigkeiten der Distribution](LINUX_DEPENDENCIES.md) installieren.
4. Ausführen:

```bash
sudo ./install.sh
adminw21 --gui
```

Die GUI als **normaler Desktop-Benutzer** starten. Privilegierte Aktionen authentifizieren sich über PolicyKit. Die GUI nicht mit `sudo` starten.

Der Installer prüft QtCore, QtGui, QtWidgets und psutil. Fehlende, unvollständige oder inkompatible Python-Pakete führen zur Einrichtung eines privaten venv; dafür wird Zugang zum Python-Paketindex benötigt. Native Bibliotheksfehler liefern eine Diagnose. Systempakete werden nicht automatisch installiert oder entfernt.

### Nur Terminal

```bash
sudo ./install.sh --terminal-only
sudo adminw21 --terminal
```

Optional werden `dialog` oder `whiptail` verwendet; andernfalls erscheint ein nummeriertes Menü.

## Benutzung

- **Ressourcen:** Übersicht öffnen, Messwert auswählen und Zeitbereich setzen. CPU-/I/O-Raten benötigen zwei Proben.
- **Login-Sitzungen:** Sitzungsdetails zeigen Quellen und Gruppen. Konten und aktive Sitzungen sind verschieden; utmp kann grafische Logins auslassen.
- **Konten:** Benutzer/Gruppen öffnen und Aktion wählen. Passwörter werden verdeckt eingegeben und bestätigt.
- **Prozesse:** Tabelle filtern, Zeile wählen und Details öffnen. Signalaktionen verlangen Bestätigung und schützen wesentliche Prozesse.
- **Berichte:** Zuerst Daten sammeln, danach TXT/JSON/HTML exportieren. Fehlgeschlagene Prüfungen bleiben sichtbar.
- **Darstellung:** Deutsch/Englisch und Dark/Light wählen; Einstellungen werden pro Benutzer gespeichert.

Statusabfragen ohne Root:

```bash
adminw21 --version
adminw21 --diagnose
adminw21 --health
adminw21 --users
```

`--users` listet Kontonamen. Login-Sitzungen stehen in der Sitzungsansicht der GUI.

## Update und Deinstallation

Den neuen Quellcode herunterladen und erneut `sudo ./install.sh` ausführen. Der Installer prüft die Anwendung vor dem Wechsel, archiviert vorherige Dateien und stellt sie nach einem fehlgeschlagenen Wechsel wieder her.

- Anwendung: `/usr/local/share/adminw21`
- Launcher: `/usr/local/bin/adminw21`
- Installationsarchive: `/var/backups/adminw21`

```bash
sudo /usr/local/share/adminw21/uninstall.sh
```

Die Deinstallation prüft Registrierungen, entfernt eigene Launcher/Policy und archiviert das Programmverzeichnis. Einstellungen, Logs, Daten, Backups und Systempakete bleiben erhalten. Unbekannte alte Launcher müssen manuell geprüft werden.

## Kompatibilität und Grenzen

Die verfügbaren Werkzeuge und Berechtigungen bestimmen den Funktionsumfang. Paketadapter: APT, DNF/YUM, Pacman, Zypper, APK, XBPS und Portage. Dienständerungen verwenden systemd. Alpine benötigt native musl-kompatible Qt-Pakete. Python 3.10/3.11 verwendet PySide6 6.8.3.

Der lokale Regressionstest verzeichnet **127 erfolgreiche und einen übersprungenen Test**. Das bestätigt nicht jede Linux-Distribution, jeden Boot-/X11-/Wayland-Stack oder echte PolicyKit-Dialoge. Paket-, Dienst-, Firewall-, Mitschnitt- und zeitgesteuerte Änderungen benötigen weitere native Tests.

Backup-Wiederherstellung verlangt ein leeres rootkontrolliertes Ziel und verweigert Links/Spezialdateien. Der Cron-Editor unterstützt numerische Zeitpläne und feste Aufgaben. Siehe [Kompatibilität](LINUX_COMPATIBILITY.md), [Funktionsumfang](FEATURE_STATUS.md) und [Testbericht](TEST_REPORT.md).

## Weitere Dokumentation

- [Fehlerbehebung](TROUBLESHOOTING.md)
- [Architektur und Datenpfade](ARCHITECTURE.md)
- [Tests und Entwicklung](TEST_REPORT.md)
- [QEMU-Testumgebungen](QEMU_TESTING.md)
- [Änderungen](CHANGELOG.md)

Fehlerberichte sollten Distribution, Python-Version, Oberflächenmodus, Schritte und genaue Fehlermeldung enthalten. Passwörter, private Schlüssel und persönliche Systemdaten vor dem Teilen aus Logs entfernen.
