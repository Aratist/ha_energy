# CLAUDE.md

Conventions du dépôt et commandes de validation : voir [AGENTS.md](AGENTS.md).
Fonctionnement de l'intégration : voir [README.md](README.md).
Historique des interventions et tâches en attente : voir [HISTORIQUE.md](HISTORIQUE.md) ;
le compléter à la fin de chaque série de travaux.

## Préférences de communication

- Répondre en français, de façon concise : l'essentiel, sans récapitulatifs ni répétitions.
- Tableaux quand c'est utile ; poser une question seulement si la réponse change l'action.

## Hypothèses retenues

- La maison consomme 400 W en permanence (talon, `baseline_power`).
- Contrat HP/HC, heures creuses 22h-6h, tarif identique toute l'année (pas de Tempo).
- Tesla BLE actif seulement quand la voiture doit être chargée : `unavailable` est normal.
- Linky : cos φ = 1 (W = VA).
- Appareils sans capteur, reconnus à leur profil : recharge des voitures la nuit (≈ 4 kW en
  continu) ; plaques électriques entre 12 h et 14 h et entre 18 h 30 et 20 h 30 (quelques
  minutes, même puissance) ; four 1 à 2 h. `energy_manager` les déduit du Linky (attribut
  `non_mesure` de la consommation).

## Installation de l'utilisateur

Home Assistant : `https://homeassistant.example.com`, avec l'extension ESPHome Device Builder.

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
adresse `AA:BB:CC:DD:EE:01`), reliée à Home Assistant par un ESP32 sous ESPHome.

- Équipement ESPHome Builder : `relais-madoka.yaml`, IP `192.168.1.<IP du relais Madoka>`, serveur web v3 sur le port 80.
- Composant externe `dasimon135/daikin_madoka` (v3.14.1), avec `madoka` **et** `madoka_base`.
- `esp32_ble.io_capability: display_yes_no` et `ble_client.numeric_comparison_reply`
  sont indispensables à l'appairage.
- L'identifiant `madoka` est réservé par ESPHome : le client BLE s'appelle `madoka_ble`.
- Mises à jour : *Installer → Sur le réseau* dans ESPHome Builder. **Ne jamais effacer la
  flash** de l'ESP32 : cela supprime l'appairage avec la télécommande.
- Si l'appairage se bloque : oublier l'appairage dans le menu Bluetooth de la télécommande,
  couper puis rallumer son Bluetooth, puis accepter le code affiché en quelques secondes.
- `on_disconnect` ne retente qu'une fois : un `interval` relance la connexion chaque minute.
  État dans HA : `binary_sensor.relais_madoka_bluetooth_connecte` ; bouton
  `button.relais_madoka_redemarrer` pour redémarrer le relais.
- L'ancien équipement `madoka-proxy.yaml` est obsolète : il lui manquait `madoka_base` et
  l'acceptation de l'appairage.
- Modèle de configuration : [projets-3d-esp32/madoka/madoka.yaml](https://github.com/Aratist/projets-3d-esp32/blob/main/madoka/madoka.yaml).

Compilation locale sous Windows, en dépannage seulement (ESPHome Builder suffit) :
lancer ESPHome depuis PowerShell, pas Git Bash (l'ESP-IDF refuse MSYS), avec des chemins
courts (`ESPHOME_ESP_IDF_PREFIX=C:\esp\idf`, projet dans `C:\esp\`). Ouvrir le port série
sans couper DTR/RTS redémarre la carte et interrompt un appairage en cours.

### Module Linky : ESP-NOW

- Module du compteur : `linky-tic.yaml` dans ESPHome Builder
  ([modèle](https://github.com/Aratist/projets-3d-esp32/blob/main/linky/linky-tic.yaml)), ESP32-C3 (MAC `AA:BB:CC:DD:EE:02`), sans Wi-Fi.
  TIC en mode standard, contrat HP/HC chez Gaz de Bordeaux (index 01 = HC, 02 = HP ; plus de
  Tempo). Il envoie ses mesures en ESP-NOW sur le canal 6 ; mises à jour en USB seulement.
- Passerelle : `linky-passerelle.yaml` ([modèle](https://github.com/Aratist/projets-3d-esp32/blob/main/linky/linky-passerelle.yaml)), ancien
  répéteur ESP32 du jardin (MAC `AA:BB:CC:DD:EE:03`, IP `192.168.1.<IP du répéteur>`), mises à jour par le
  réseau. Elle ne se connecte qu'à « Lapin » (`wifi_ssid2`, canal 6) : l'ESP-NOW suit le canal du
  point d'accès, et « Freebox-38A244 » (canal 2) couperait la liaison. Fixer le canal 6 dans la box.
- Une seule mesure remonte : `sensor.linky_consommation_instantanee` (SINSTS, VA), avec
  l'historique de l'ancien module. Elle alimente l'aide Modèle `sensor.puissance_soutiree_reseau`
  (tableau « Gestion énergie », source du surplus) et `automation.conso_maison_musique`.
  Diagnostics : `binary_sensor.linky_status` (allumé tant que le module du compteur émet),
  signal et réseau Wi-Fi de la passerelle. L'autre appareil « Linky » (Supervisor) est une
  application HA, sans rapport.
- Disponibilité suivie par des aides HA : `binary_sensor.linky_consommation_disponible`,
  `sensor.linky_disponibilite_24_h`, `sensor.linky_disponibilite_7_jours` (comptées depuis le
  5 novembre 2026 14 h 56) et `sensor.linky_coupures_24_h`.
- Le module du compteur ouvre son propre point d'accès « Linky TIC » sur le canal 6
  (mot de passe `linky_tic_ap_mdp`) : serveur web sur http://192.168.4.1, près du compteur.
- `linky.yaml` (ancienne configuration Wi-Fi + MQTT du C3) est archivé dans ESPHome Builder.
- Tableau Énergie de HA : réseau = statistiques de l'application Linky (Enedis, J-1, prix HP/HC
  dans ses options : 0,175176 / 0,132024, HC 22h-6h) ; injection = estimation
  `sensor.gestionnaire_d_energie_injection_du_jour` (revente 0 €) ; solaire = production du jour
  IzyPower + Forecast.Solar ; 10 appareils mesurés. `sensor.linky_energie_soutiree` (ancien module)
  est mort : ne pas le remettre.

### Tesla : relais Bluetooth (appairage en cours)

- ESP32 dédié, distinct du relais Madoka, sous ESPHome avec le fork `PedroKTFC/esphome-tesla-ble` (v2026.10.0), entités en français.
  Modèle : [projets-3d-esp32/tesla-ble/tesla-ble.yaml](https://github.com/Aratist/projets-3d-esp32/blob/main/tesla-ble/tesla-ble.yaml).
- L'appairage se lance par le bouton « Appairage clé BLE » (section Diagnostic de l'appareil),
  puis la carte-clé sur la console : la voiture ne propose rien dans son menu Bluetooth.
- `packages/evcc.yml` ne sert qu'avec EVCC : la recharge se pilote avec les entités de `client.yml`.
- La recharge n'est pas encore pilotée par `energy_manager` : l'ajouter une fois l'appairage réussi.
  Comparaison des solutions de pilotage gratuites : [TESLA_Module.md](TESLA_Module.md).

### Boîtiers 3D et caméra du placard

Déplacés le 6 novembre 2026 dans le dépôt privé
[Aratist/projets-3d-esp32](https://github.com/Aratist/projets-3d-esp32), avec les programmes
ESPHome des relais (Linky, Madoka, Tesla) : ce dépôt ne garde que la gestion de l'énergie.
Les modèles ESPHome cités plus haut y sont, dans `linky/`, `madoka/` et `tesla-ble/`.

### Tableau de bord « Analyse énergie »

- Tableau de bord en mode stockage (`url_path: energie-analyse`), reflété par
  [examples/analyse.yaml](examples/analyse.yaml) : garder les deux synchronisés. Les noms
  d'entités IzyPower y sont anonymisés (`izypower_cloud_maison`, `serie_…`) : adapter au vrai HA.
- Frises de l'onglet « Aujourd'hui » : « Appareils pilotés : en marche » et « Pourquoi le
  gestionnaire a décidé ainsi » (une ligne par appareil, jamais de ligne « raison ») ; « Autres
  appareils : en marche » utilise des aides Modèle basées sur la puissance
  (`binary_sensor.machine_a_laver_en_marche`, `jacuzzi_en_chauffe`, `grille_pain_en_marche`,
  `imprimante_3d_en_marche`, `pompe_dehors_devant_en_marche`, `pompe_interrupteur_en_marche`,
  `appareils_sans_capteur_en_marche`), car ces prises restent toujours allumées.
- Appareils mesurés déclarés dans `energy_manager` : jacuzzi, machine à laver, imprimante 3D et
  sa lampe, prise dehors devant (pompe), pompe (interrupteur `light.switch_pompe`), grille-pain.
- Graphiques de consommation : toutes les prises connectées avec mesure (y compris grille-pain).
  La clim du haut (relais Madoka) n'a pas de mesure de puissance : seulement dans « Allumage ».
- Une entité `climate` s'y affiche en courbe de température. Chaque clim passe donc par un
  capteur binaire (aide Modèle) : `binary_sensor.clim_bas_allumee` et
  `binary_sensor.clim_haut_allumee`, allumés quand la clim n'est pas `off`.
- Onglets « Aujourd'hui », « Historique », « Solaire », « Appareils », « Chauffage » : graphiques
  `custom:apexcharts-card` (HACS), chacun précédé d'une phrase « comment lire ». Pour modifier
  le tableau de bord, éditer `examples/analyse.yaml`, puis l'envoyer dans HA (`lovelace/config/save`).
- Tableau de pilotage « Gestion énergie » (`url_path: gestion-energie`), reflété par
  [examples/dashboard.yaml](examples/dashboard.yaml) : phrase d'état en clair, appareils pilotés
  avec la raison de chaque décision, bilan du jour, demain, Linky. Il n'utilise que les entités de
  `energy_manager` ; les anciennes aides (`input_number.consommation_de_base_maison`,
  `sensor.surplus_solaire_disponible`…) ne servent plus à rien.
- Les compteurs « du jour » de `energy_manager` (soutirage, coût, économie, chauffe, filtration…)
  repartent de zéro **à 6 h**, pas à minuit. Graphique par jour tiré de l'historique :
  `group_by: max 1d` avec `span: {end: day, offset: +6h}`. Depuis les statistiques
  long terme, prendre la variation (`change`), jamais `max` ni `state`.
