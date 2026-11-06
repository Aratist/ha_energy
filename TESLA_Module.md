# Pilotage gratuit de la recharge Tesla depuis Home Assistant

Besoin : démarrer ou arrêter la recharge et régler le courant **entre 5 A et 16 A** (monophasé),
avec des changements toutes les quelques minutes pour suivre le surplus solaire depuis `energy_manager`.

Recherche du 2026-11-04. Les dates de version viennent de l'API GitHub. Ce qui n'a pas pu être
vérifié est marqué **[non vérifié]**.

## Recommandation

1. **ESPHome BLE**, sur l'ESP32 déjà en place (fork PedroKTFC, modèle
   [projets-3d-esp32/tesla-ble/tesla-ble.yaml](https://github.com/Aratist/projets-3d-esp32/blob/main/tesla-ble/tesla-ble.yaml)). C'est la seule solution
   entièrement locale, sans compte Tesla, sans coût et sans quota de commandes. Elle fournit déjà
   les entités « Charge » et « Ampérage de charge ».
   À régler : l'appairage, la portée Bluetooth depuis l'emplacement de l'ESP32. Le fork yoziru
   (v2026.10.3) sert de solution de secours.
2. **Intégration officielle « Tesla Fleet »**, en secours si le Bluetooth reste instable.
   Elle est gratuite tant que l'usage reste sous le crédit mensuel de 10 $ de Tesla. Il faut un
   compte développeur Tesla approuvé et un domaine public qui héberge une clé.
3. **TeslaBleHttpProxy sur un Raspberry Pi**, seulement si l'ESP32 n'arrive pas à s'appairer
   et qu'un Raspberry Pi est disponible. Il n'y a pas d'entités Home Assistant natives.

Écartées :

| Solution | Raison |
|---|---|
| tesla-local-control | Peu active |
| Wall Connector | En lecture seule |
| Borne OCPP ou OpenEVSE | Borne à acheter, minimum de 6 A |
| evcc | Fait double emploi avec `energy_manager` |
| Teslemetry, Tessie | Payantes |

## Comparaison

| Solution | Coût | Prérequis | Entités Home Assistant | Local / cloud | Limites | Activité |
|---|---|---|---|---|---|---|
| **A. ESPHome BLE** (PedroKTFC ou yoziru) | 0 €, ESP32 déjà acheté | ESP32 à 5–10 m de la voiture, clé BLE appairée, VIN | Interrupteur « Charge », réglage « Ampérage de charge », réglage « Limite de charge », bouton « Réveiller » | Entièrement local | Appairage délicat. Valeurs lues seulement quand la voiture est éveillée. Nombre maximal de clés sur la voiture **[non vérifié]**. | PedroKTFC v2026.10.0 (2026-10-25). yoziru v2026.10.3 (2026-10-19). Commits le 2026-11-01. |
| **B. Tesla Fleet** (intégration officielle de Home Assistant) | Gratuit sous le crédit de 10 $/mois | Compte développeur Tesla approuvé, domaine public pour la clé, clé virtuelle ajoutée dans l'app Tesla | « Charge current », « Charge », « Charge limit », « Wake » | Cloud | 30 commandes/min et 3 réveils/min par véhicule. Facturation au-delà du crédit. | Intégrée à Home Assistant 2026.10, maintenue |
| **C. TeslaBleHttpProxy** (wimaha) | 0 € + un Raspberry Pi ou un autre ordinateur avec Bluetooth | Docker ou module complémentaire Home Assistant, clé BLE | Pas d'entités natives : API HTTP (`charge_start`, `charge_stop`, `set_charging_amps`) via `rest_command` ou un pont MQTT (Lenart12/TeslaBle2Mqtt-addon, petit projet) | Local | Pas d'authentification sur l'API. Monopolise l'adaptateur Bluetooth. | v2.5.0 (2026-10-19) |
| **D. tesla-local-control** (iainbullock/tesla_ble_mqtt_docker) | 0 € + Raspberry Pi 3 ou plus récent | Broker MQTT, `tesla-control` en Bluetooth | Entités MQTT découvertes automatiquement. Réglage d'ampérage et marche/arrêt **[non vérifiés]**. | Local | Interrogation conseillée toutes les 660 s ou plus | v0.5.0 (2025-02-23), peu active |
| **E. Wall Connector Gen3** | Borne à acheter | — | Capteurs seulement | Local | Lecture seule : l'ampérage se règle par la voiture | — |
| **F. OCPP (lbbrhzn/ocpp) ou OpenEVSE** | Borne compatible à acheter | Borne pilotable | Courant réglé par la borne | Local | Souvent 6 A minimum côté borne, donc 6–16 A | OCPP v0.12.2 (2026-10-19) |
| **G. evcc** | Gratuit pour les véhicules Tesla (jeton payant seulement pour certaines bornes) | Compte développeur Tesla. Pilotage par Bluetooth via TeslaBleHttpProxy, ou par Fleet avec un proxy de signature. | MQTT / API vers Home Assistant | Local en Bluetooth | Gère lui-même le surplus solaire, en concurrence avec `energy_manager` | 0.318.2 (2026-11-01), très active |
| **H. Intégration HACS « tesla »** (Alandtse) | Gratuit | Jeton de rafraîchissement généré par une application tierce | **[non étudiées]** | Cloud | **[non étudiées]** | v3.28.0 (2026-10-22) |

Home Assistant n'a pas d'intégration Tesla Bluetooth intégrée. Les intégrations Tesla incluses dans
Home Assistant sont `tesla_fleet`, `tesla_wall_connector`, `teslemetry` et `tessie`.

Pour le fork ESPHome, `packages/evcc.yml` ne sert qu'avec evcc. Les entités de `client.yml`
suffisent pour piloter la recharge.

## Tesla Fleet : coûts et limites

| Type | Tarif Tesla |
|---|---|
| Commandes | 1 $ les 1000 |
| Lectures de données | 1 $ les 500 |
| Réveils | 1 $ les 50 |
| Données en continu | 1 $ les 150 000 signaux |

- Tesla offre un crédit de 10 $ par mois et par compte. Aucune baisse n'a été trouvée pour 2026 **[non vérifié]**.
- Limites : 30 commandes/min, 3 réveils/min, 60 lectures de données/min par véhicule. Elles sont
  partagées entre les applications qui accèdent à la même voiture.
- Home Assistant signe lui-même les commandes : pas besoin du proxy de signature de Tesla.
  La clé publique s'héberge sous `.well-known/appspecific/`, par exemple avec le module
  complémentaire NGINX SSL proxy, ou via FleetKey.net ou MyTeslamate.com.
- Par défaut, l'intégration interroge la voiture toutes les 10 min quand elle est éveillée.

Estimation du coût mensuel pour ce cas (calcul fait par la recherche, **[non vérifié]**) :

| Usage | Quantité par mois | Coût |
|---|---|---|
| Interrogation de la voiture éveillée 24 h/24 | 4320 lectures | ≈ 8,64 $ |
| Changement d'ampérage toutes les 5 min, 10 h de soleil par jour | 3600 commandes | ≈ 3,60 $ |

Le total peut dépasser le crédit de 10 $. Pour rester gratuit, espacer l'interrogation et n'envoyer
une commande que quand la consigne change vraiment.

## Contraintes de pilotage

- **5 A minimum** : c'est le plancher constaté côté voiture. Une consigne plus basse est acceptée,
  jusqu'à 0 A, mais la voiture reste à environ 0,8–0,9 A à 0 A. La plage 5–16 A n'est donc pas
  gênée. Côté borne, le minimum est souvent de 6 A.
- **Quota quotidien** : un plafond d'environ 50 commandes par jour est cité pour l'ancienne API
  cloud. La page actuelle de Tesla ne mentionne que les limites par minute **[non vérifié]**.
  Le Bluetooth n'est soumis à aucun quota.
- **Réveil et batterie** : pendant la recharge, la voiture est déjà éveillée, donc changer
  l'ampérage ne coûte rien de plus. Branchée mais endormie, elle est réveillée par une commande.
  Une interrogation trop fréquente l'empêche de se rendormir (yoziru #169, PedroKTFC #312).
  Le rythme d'interrogation de base de PedroKTFC (10 s) ne la réveille pas.
- **Pour `energy_manager`** : n'envoyer une nouvelle consigne d'ampérage que si elle change,
  et n'envoyer de commande que si la voiture est branchée.

## Non vérifié

- Entités exactes de tesla_ble_mqtt_docker pour le marche/arrêt et l'ampérage.
- Prix de Teslemetry, Tessie et du proxy de signature de MyTeslamate.
- Comportement sous 5 A sur les voitures récentes, existence d'un quota quotidien.
- Crédit Fleet de 10 $ en 2026, latence réelle du Bluetooth, nombre maximal de clés par voiture.

## Sources

- https://www.home-assistant.io/integrations/tesla_fleet/
- https://www.home-assistant.io/integrations/tesla_wall_connector/
- https://developer.tesla.com/docs/fleet-api/billing-and-limits
- https://teslemetry.com/blog/tesla-fleet-api-pay-per-use
- https://docs.evcc.io/en/blog/2025/01/20/tesla-api-update
- https://docs.evcc.io/en/sponsorship
- https://github.com/evcc-io/evcc/discussions/8050
- https://github.com/evcc-io/evcc/discussions/14687
- https://github.com/PedroKTFC/esphome-tesla-ble
- https://github.com/yoziru/esphome-tesla-ble
- https://github.com/wimaha/TeslaBleHttpProxy
- https://github.com/iainbullock/tesla_ble_mqtt_docker
- https://github.com/teslamotors/vehicle-command
- https://github.com/lbbrhzn/ocpp
- Cités dans les résultats de recherche, non lus en entier : teslamate-org/teslamate discussion 4426,
  support.teslafi.com (consigne sous 5 A)
