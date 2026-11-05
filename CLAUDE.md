# CLAUDE.md

Conventions du dépôt et commandes de validation : voir [AGENTS.md](AGENTS.md).
Fonctionnement de l'intégration : voir [README.md](README.md).

## Installation de l'utilisateur

Home Assistant : `https://ha.controlemoi.com`, avec l'extension ESPHome Device Builder.

### Équipements pilotés par `energy_manager`

Seuls trois équipements sont allumés ou éteints par l'intégration :

| Équipement | Entité |
|---|---|
| Clim du bas (Daikin) | `climate.daikinap85642` |
| Piscine | `switch.piscine_prise_1` |
| Chauffe-eau | `switch.chauffe_eau_prise_1` |

- **En hiver, seule la clim du bas est allumée pour le chauffage**, pour l'instant.
- La clim du haut (`climate.relais_madoka_clim_madoka`) n'est jamais allumée ni pilotée.
- Les autres appareils (jacuzzi, machine à laver, clim du haut…) sont seulement mesurés
  pour l'estimation de consommation. Ne pas ajouter d'autre charge pilotée.

### Clim du haut : relais Bluetooth Madoka

La clim du haut est commandée par une télécommande Daikin Madoka (BRC1H, Bluetooth,
adresse `AC:EB:51:C6:88:B3`), reliée à Home Assistant par un ESP32 sous ESPHome.

- Équipement ESPHome Builder : `relais-madoka.yaml`, IP `192.168.1.83`, serveur web v3 sur le port 80.
- Composant externe `dasimon135/daikin_madoka` (v3.14.1), avec `madoka` **et** `madoka_base`.
- `esp32_ble.io_capability: display_yes_no` et `ble_client.numeric_comparison_reply`
  sont indispensables à l'appairage.
- L'identifiant `madoka` est réservé par ESPHome : le client BLE s'appelle `madoka_ble`.
- Mises à jour : *Installer → Sur le réseau* dans ESPHome Builder. **Ne jamais effacer la
  flash** de l'ESP32 : cela supprime l'appairage avec la télécommande.
- Si l'appairage se bloque : oublier l'appairage dans le menu Bluetooth de la télécommande,
  couper puis rallumer son Bluetooth, puis accepter le code affiché en quelques secondes.
- L'ancien équipement `madoka-proxy.yaml` est obsolète : il lui manquait `madoka_base` et
  l'acceptation de l'appairage.
- Modèle de configuration : [examples/esphome/madoka.yaml](examples/esphome/madoka.yaml).

Compilation locale sous Windows, en dépannage seulement (ESPHome Builder suffit) :
lancer ESPHome depuis PowerShell, pas Git Bash (l'ESP-IDF refuse MSYS), avec des chemins
courts (`ESPHOME_ESP_IDF_PREFIX=C:\esp\idf`, projet dans `C:\esp\`). Ouvrir le port série
sans couper DTR/RTS redémarre la carte et interrompt un appairage en cours.

### Tesla : relais Bluetooth (appairage en cours)

- ESP32 dédié, distinct du relais Madoka, sous ESPHome avec le fork `PedroKTFC/esphome-tesla-ble` (v2026.10.0), entités en français.
  Modèle : [examples/esphome/tesla-ble.yaml](examples/esphome/tesla-ble.yaml).
- L'appairage se lance par le bouton « Appairage clé BLE » (section Diagnostic de l'appareil),
  puis la carte-clé sur la console : la voiture ne propose rien dans son menu Bluetooth.
- `packages/evcc.yml` ne sert qu'avec EVCC : la recharge se pilote avec les entités de `client.yml`.
- La recharge n'est pas encore pilotée par `energy_manager` : l'ajouter une fois l'appairage réussi.
  Comparaison des solutions de pilotage gratuites : [TESLA_Module.md](TESLA_Module.md).

### Boîtiers imprimés en 3D

Tout boîtier demandé se livre en **script Python pour Fusion 360** (API `adsk`), que l'utilisateur
lance dans Fusion : un dossier `<nom>/` avec `<nom>.py` et `<nom>.manifest`. Le script construit
chaque pièce par esquisses et extrusions, pour que l'historique reste modifiable dans Fusion, et
exporte les STL et STEP dans `export/` (ignoré par git). Pas d'OpenSCAD : Fusion 360 ne le lit pas.
Exemple : [CAMERA_PLACARD/hardware/fusion/boitier_placard/](CAMERA_PLACARD/hardware/fusion/boitier_placard/).

### Caméra du placard (en projet)

ESP32-S3 caméra, micro et haut-parleur dans le placard : météo pour Alexis, compliments pour
Marie, entre 7 h et 9 h. Tout est décrit dans [CAMERA_PLACARD/CAMERA_PLACARD.md](CAMERA_PLACARD/CAMERA_PLACARD.md).

### Tableau de bord « Analyse énergie »

- Tableau de bord en mode stockage (`url_path: energie-analyse`), reflété par
  [examples/analyse.yaml](examples/analyse.yaml) : garder les deux synchronisés.
- Groupe « Allumage des appareils » : chauffe-eau, piscine, clim bas, clim haut.
  Jacuzzi et machine à laver en sont exclus, car leurs prises restent toujours allumées.
- Une entité `climate` s'y affiche en courbe de température. Chaque clim passe donc par un
  capteur binaire (aide Modèle) : `binary_sensor.clim_bas_allumee` et
  `binary_sensor.clim_haut_allumee`, allumés quand la clim n'est pas `off`.
- Onglets « Aujourd'hui », « Solaire », « Appareils », « Économies & climat » : graphiques
  `custom:apexcharts-card` (HACS). Pour modifier le tableau de bord, éditer
  `examples/analyse.yaml`, puis l'envoyer dans HA (`lovelace/config/save`).
- Les compteurs « du jour » de `energy_manager` (soutirage, coût, économie, chauffe, filtration…)
  repartent de zéro **à 6 h**, pas à minuit. Graphique par jour tiré de l'historique :
  `group_by: max 1d` avec `span: {end: day, offset: +6h}`. Depuis les statistiques
  long terme, prendre la variation (`change`), jamais `max` ni `state`.
