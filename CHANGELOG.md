# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **Eigene Domain** `controme_connect` mit eigenen Entity-IDs, damit die
  Integration unabhängig von der ursprünglichen betrieben werden kann.

### Geändert

- Die Raum-IDs werden ohne doppelte Unterstriche und ohne Umlaute erzeugt.
  Home Assistant meldet für die ursprüngliche Variante ab 2027.2, dass solche
  Entity-IDs nicht mehr unterstützt werden.
- Die Geräte-Hierarchie nutzt `via_device_id` statt des veralteten
  `via_device` (gleiche Abkündigung, ab 2027.8).
- Der Coordinator beendet sich beim Entladen und stellt die Abfrage der
  Anlage nach einem Ausfall automatisch wieder her.
