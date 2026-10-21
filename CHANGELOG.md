# Änderungsprotokoll

Alle wesentlichen Änderungen an diesem Projekt sind in dieser Datei
dokumentiert.

Das Format folgt [Keep a Changelog](https://keepachangelog.com/de/1.1.0/)
und das Projekt richtet sich nach
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0]

Erste eigenständige Veröffentlichung. Grundlage ist die Integration
[homeassistant-controme-integration](https://github.com/flame4ever/homeassistant-controme-integration)
von *flame4ever*.

### Hinzugefügt

- **Rücklauftemperaturen** – die Anlage bezeichnet die Sensoren mit „RL“, was
  die ursprüngliche Erkennung nicht gefunden hat. Räume mit mehreren
  Rücklauf-Sensoren werden eindeutig benannt.
- **Abweichung** je Raum (Ist minus Soll) aus dem Endpunkt `/deviation/`.
- **Letzte Übertragung** je Raum mit dem Alter jedes einzelnen Sensors.
- **Übertragung gestört** je Raum. Die Sensoren mit längeren Zeitlimits
  (solbetriebene Raumthermostate) werden an der Datenform der API erkannt.
- **Firmware** der Anlage mit Version, Branch, Commit, Hardware und
  Betriebssystem.
- **Firmware-Update verfügbar** – die Anlage bietet den Update-Stand nur über
  die Weboberfläche. Die Prüfung läuft im Hintergrund und kann die
  Raumsensoren nicht blockieren. Die stabile Version wird getrennt von der
  Beta-Version ausgewertet.
- **Systemcheck** der Weboberfläche als Attribut: welcher Sensor steuert welchen
  Ausgang.
- **Temperaturanpassung je Modul** – nur Module, die den Raum tatsächlich
  beeinflussen, bekommen eine Entity. Wird ein Modul später aktiv, lädt sich
  die Integration selbst neu.
- **Raum-Icons** aus der Controme-Oberfläche auf den Heizungs-Entities.
- **Temporärer Modus** und die Sollwert-Vorgabe des Systems als Attribute der
  Heizungs-Entities.
- **Luftfeuchte aus Multi-Sensoren**, wenn kein eigener Feuchtesensor
  verbaut ist, dazu Helligkeit und Bewegung der Multi-Sensoren.
- **Rundung** der Abweichung und der Offsets auf zwei Nachkommastellen.
- **Echte Prüfung der Zugangsdaten** beim Einrichten: der Login an der
  Weboberfläche muss klappen, sonst geht es nicht weiter. Die Daten-Endpunkte
  der API antworten auch mit falschem Passwort.
- **Haus-Auswahl** beim Einrichten und **Neu konfigurieren** für API-Adresse,
  Haus-ID, Benutzer und Passwort.
- **Eigene Brand-Bilder** (`brand/icon.png` und `brand/logo.png`) – seit Home
  Assistant 2026.3 liefert die Integration ihre Bilder lokal aus, sie haben
  Vorrang vor dem CDN. Die Grafiken sind selbst erzeugt, es werden keine
  Markenrechte Dritter berührt.
- **Deutschsprachige Dokumentation** – Kommentare, Docstrings und Log-Meldungen
  der Integration sowie dieses Änderungsprotokoll sind vollständig auf Deutsch.
  Die englische README bleibt als englische Fassung erhalten.
- **Übersetzte Entity-Namen** – die Namen aller Entities kommen jetzt aus den
  Übersetzungsdateien statt aus dem Code. Dadurch erscheinen sie in der
  Sprache der Home-Assistant-Oberfläche, deutsch und englisch. Namen und
  Entity-IDs der eigenen Integration bleiben unverändert.
- **Manifest verweist auf das eigene Repository** – `documentation` und
  `issue_tracker` zeigen auf `github.com/acki1989/homeassistant-controme-connect`,
  `codeowners` nennt `@acki1989`.
- **Übersetzte Entity-Namen** – die Namen aller Entities kommen jetzt aus den
  Übersetzungsdateien statt aus dem Code. Dadurch erscheinen sie in der
  Sprache der Home-Assistant-Oberfläche, auf Deutsch wie auf Englisch. Zuvor
  wurden die Einträge in den Übersetzungsdateien nicht verwendet, weil der im
  Code gesetzte Name Vorrang hatte.
- **Voraussetzungen** in beiden README-Fassungen: Home Assistant 2024.11 oder
  neuer, Controme-Anlage mit Smart-Heat-OS, keine Python-Abhängigkeiten.
- **Hinweis auf die Modulnamen** – sie kommen unverändert aus der Anlage und
  werden nicht übersetzt.
- **Unit-Tests** für die reinen Hilfsfunktionen unter `tests/` (88 Tests):
  Raum-Slugs, Raum-Icons, Erkennung der Rücklauf-Sensoren, Offsets,
  Umwandlung der API-Werte, Zeitstempel der letzten Übertragung, die
  Firmware-Hilfsfunktionen sowie die Vollständigkeit der Übersetzungen und
  der Dokumentation.
- **Vollständige englische Fassung** der Dokumentation: `README.en.md`
  beschreibt jetzt denselben Umfang wie die deutsche Fassung.
- **Eigene Domain** `controme_connect` mit eigenen Entity-IDs, damit die
  Integration unabhängig von der ursprünglichen betrieben werden kann.

### Behoben

- Ein Offset von **null** wurde als fehlender Wert behandelt. Die betroffenen
  Entities standen auf `unknown`, obwohl die Anlage den Wert `0` liefert.
  Betroffen waren die Gesamtoffset-Sensoren und die Offsets der Module.
- Die Betriebsart blieb englisch. Die Anlage liefert den Zustand „Heating“,
  der Übersetzungsschlüssel hieß „heating“ und traf deshalb nie. Die Zustände
  der Betriebsart sind jetzt übersetzt und werden klein geschrieben.
- Nach einem Wechsel der Haus-ID blieben die Geräte des vorherigen Hauses als
  Waisen im Registry stehen. Sie werden jetzt beim Neu konfigurieren mit
  entfernt.
- Die Ermittlung der Haus-ID erfolgte über die API, die für jede ID dieselben
  Daten liefert. Unter der so ermittelten ID existiert die Weboberfläche
  jedoch nicht. Die Ermittlung nutzt jetzt die Weboberfläche.
- Der Hinweis auf ein verfügbares Update wertete nur den HTTP-Status aus. Die
  Fehlerseite der Weboberfläche wird mit Status 200 beantwortet und wurde
  deshalb als Update gemeldet. Jetzt wird zusätzlich der Inhalt geprüft.

### Geändert

- Die Raum-IDs werden ohne doppelte Unterstriche und ohne Umlaute erzeugt.
  Home Assistant meldet für die ursprüngliche Variante ab 2027.2, dass solche
  Entity-IDs nicht mehr unterstützt werden.
- Die Geräte-Hierarchie nutzt `via_device_id` statt des veralteten
  `via_device` (gleiche Abkündigung, ab 2027.8).
- Der Coordinator beendet sich beim Entladen und stellt die Abfrage der
  Anlage nach einem Ausfall automatisch wieder her.
