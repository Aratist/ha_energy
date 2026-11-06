# Historique des interventions

Journal des travaux faits avec Claude, pour reprendre sans relire les anciennes conversations.
L'état à jour de l'installation est dans [CLAUDE.md](CLAUDE.md) ; ce fichier dit comment on y
est arrivé et ce qui reste à faire. Aucun secret ici : ils sont dans `secrets.yaml` d'ESPHome.

## 5 novembre 2026

### Module Linky : passage du Wi-Fi à l'ESP-NOW

**Problème de départ.** Le module Linky (ESP32-C3 au compteur, MAC `88:56:A6:70:70:E4`) perdait
souvent le Wi-Fi : −89 dBm vers la box. Il publiait à la fois par l'API ESPHome et par MQTT,
d'où deux appareils « Linky » et des entités `_2` dans HA.

**Cause aggravante découverte en cours de route.** Le C3 s'accrochait à l'étendeur du jardin
(« Freebox-out », firmware ESP32 NAT Router Extended 7.2.0), qu'il captait mieux, avec une
adresse fixe 192.168.1.169 qui n'existe pas derrière le NAT de l'étendeur (192.168.4.x).
L'étendeur l'affichait en 0.0.0.0 et le module était hors ligne depuis le 4 novembre 7 h 41.
Un répéteur NAT ne convient de toute façon pas à ESPHome : HA ne peut pas joindre l'API.

**Solution retenue : ESP-NOW + passerelle.**
- Le C3 du compteur (`linky-tic.yaml`) n'a plus de connexion Wi-Fi : il lit la TIC (mode standard,
  9600 bauds, GPIO20) et envoie ses mesures en ESP-NOW chiffré (`packet_transport`, clé
  `linky_espnow_cle`) toutes les 10 s, sur le canal 6.
- L'ancien étendeur du jardin devient la passerelle (`linky-passerelle.yaml`, ESP32 classique
  ESP32-D0WD-V3, MAC `20:E7:C8:67:BB:A4`, IP 192.168.1.104). Il reçoit l'ESP-NOW et publie dans
  HA par le Wi-Fi.

**Déroulé.**
1. Le menu OTA de l'étendeur ne prend que les mises à jour de son propre firmware (adresse
   personnalisée réglable seulement par le port série) : premier flash obligatoirement en USB.
2. Compilation dans ESPHome Builder, téléchargement du firmware « factory », flash avec
   `esptool` 5.4.0 depuis le PC. Il a fallu installer le pilote CP2102 de l'étendeur.
3. Flash du C3 en USB (puce USB intégrée, pas de pilote).
4. Premier essai sans réception (`Send failed`) : au jardin, la passerelle s'était connectée à
   « Freebox-38A244 » (canal 2) au lieu de « Lapin » (canal 6). Correctif : la passerelle ne
   connaît plus que « Lapin » (`wifi_ssid2`), qu'elle capte à −27 dB. Liaison établie.
5. Nettoyage de HA :
   - suppression des anciens appareils Linky ESPHome et MQTT ;
   - entités de la passerelle renommées sans suffixe, en reprenant l'historique de l'ancien
     module (renommer l'ancienne entité vers l'identifiant visé avant de la supprimer, puis
     donner cet identifiant à la nouvelle) ;
   - `linky.yaml` (ancienne configuration du C3) archivé dans ESPHome Builder.
6. Changement de fournisseur (Gaz de Bordeaux, contrat HP/HC) : index Tempo retirés.
7. Allègement demandé : une seule mesure remonte, **« Consommation instantanée »**
   (`sensor.linky_consommation_instantanee`, SINSTS en VA, historique depuis le 26 octobre).
   Retirés : doublons (NRJ, 00 à 03), phases 1 à 3, total, index HC/HP, puissance active
   (CCASN), tarif, registre de statuts.

**Mis à jour dans HA pour la nouvelle entité.**
- Tableaux « Aperçu » (défaut), « Maison » (graphique « Consommation instantanée (24 h) »)
  et « Gestion énergie » (jauge « Consommation instantanée » dans « Maintenant », à la place
  de la jauge conditionnelle « Réseau (Linky) » qui faisait doublon ; tuiles Wi-Fi de l'ancien
  MQTT retirées).
- `automation.conso_maison_musique`.
- Aide Modèle « Puissance soutirée réseau » (`sensor.puissance_soutiree_reseau`) : elle lisait
  encore les anciennes entités, d'où « Linky hors ligne » ; la source du surplus est repassée à
  « Linky (mesure réelle) ».
- `energy_manager` n'utilise pas le Linky (puissance réseau non configurée).

**Suivi de disponibilité de la consommation instantanée** (aides HA, section « Mesure Linky »
de « Gestion énergie ») :
- `binary_sensor.linky_consommation_disponible` (aide Modèle) : allumé quand la liaison est
  active (`binary_sensor.linky_status`) et que la consommation est un nombre.
- `sensor.linky_disponibilite_24_h` et `sensor.linky_disponibilite_7_jours` (aides
  Statistiques d'historique, en %) : comptées à partir du 5 novembre 14 h 56, création du
  capteur, pour ne pas compter comme coupure le temps d'avant. Les fenêtres se remplissent
  d'ici le 6 novembre (24 h) et le 12 novembre (7 jours).
- `sensor.linky_coupures_24_h` : nombre de coupures sur 24 h.
- Graphique « Consommation disponible (24 h) ».

**Diagnostics ajoutés sur la passerelle :** « Réseau Wi-Fi » et « Réseaux visibles »
(liste des réseaux captés avec leur signal), en plus de « Status » et du signal Wi-Fi.

### Relais Madoka (clim du haut)

- Le relais avait perdu le Bluetooth : `on_disconnect` ne retente qu'une fois. Ajout d'un
  `interval` qui relance la connexion chaque minute, d'un capteur « Bluetooth connecté » et d'un
  bouton « Redémarrer » ; installé par le réseau, reconnecté.
- Débrancher puis rebrancher l'ESP32 ne demande pas de réappairage : les clés sont en flash.
- Un ESP32-C3 conviendrait (BLE), mais il faudrait réappairer ; on garde l'ESP32 actuel.
- Le relais Madoka ne doit pas servir de passerelle ESP-NOW : le Bluetooth partage la radio.

### Caméra du placard

- Anneau LED retiré de tout le projet : ESPHome, paquet HA, script Fusion (quatre plots pour
  porter la carte), schéma de câblage, schéma et PCB KiCad (J3 et R2 retirés, broche 11 de J1
  non reliée), documentation. La photo compte sur la lumière ambiante.

### Boîtier ESP32 à clipser

- Script Fusion 360 [projets-3d-esp32/linky/a_BoiteESP32DevKit/](https://github.com/Aratist/projets-3d-esp32/tree/main/linky/a_BoiteESP32DevKit) :
  bac et couvercle clipsé sans vis pour un ESP32 DevKit, encoche USB, passe-fil, aérations.
  Copié aussi dans le dossier des scripts de Fusion
  (`%APPDATA%\Autodesk\Autodesk Fusion 360\API\Scripts\a_boitier_esp32`).
- Corrigé après un premier essai : les esquisses sur plans décalés partaient de z = 0 (fond
  absent, blocs flottants). La copie dans Fusion ne suit pas le dépôt automatiquement.

### Répéteurs Wi-Fi ESP32 (recherche)

Firmwares NAT (martin-ger `esp32_nat_router`, dchristl extended, Tasmota Range Extender) : les
appareils derrière sont injoignables par HA. Seule la branche `esp32_wifi_repeater` de martin-ger
garde le même réseau (pont de niveau 2), encore expérimentale et à compiler. Pour le Linky,
l'ESP-NOW reste la meilleure solution.

## Reste à faire

- [ ] **Flasher le nouveau firmware du C3 du compteur** en USB :
  `Téléchargements\linky-tic-ap-firmware.factory.bin` (932 Ko, SHA-256
  `737402d9cceada12beb01ffcb19ef63241df0cecebe017300852ab3dda86f136`), puce `esp32c3`,
  adresse 0x0. Il n'envoie plus que la consommation et le temps de marche, et ouvre le point
  d'accès « Linky TIC » (canal 6, mot de passe `linky_tic_ap_mdp`) avec un serveur web sur
  http://192.168.4.1. Point d'accès pas encore testé sur la carte.
- [ ] Fixer le canal Wi-Fi de « Lapin » sur 6 dans la box : sinon la liaison ESP-NOW se coupe.
- [ ] Ajouter une clé de chiffrement à l'API ESPHome de la passerelle (facultatif).
