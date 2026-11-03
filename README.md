# Gestionnaire d'énergie solaire pour Home Assistant

Intégration personnalisée (`custom_components/energy_manager`) qui oriente le surplus
de vos panneaux solaires vers le chauffe-eau, la pompe de piscine et la clim/chauffage,
avec un rattrapage en heures creuses pour garantir l'eau chaude et la filtration.

Elle ne parle à aucun matériel directement : elle s'appuie sur les entités que vous avez
déjà dans Home Assistant (compteur Linky/pince, onduleur, prises ou relais, thermostat).

## Installation

1. Copier `custom_components/energy_manager` dans le dossier `config/custom_components/`
   de Home Assistant (ou ajouter ce dépôt comme dépôt personnalisé HACS).
2. Redémarrer Home Assistant.
3. *Paramètres → Appareils et services → Ajouter une intégration → Gestionnaire d'énergie solaire*.

Home Assistant 2024.12 ou plus récent est requis.

## Configuration

| Étape | Ce qu'il faut fournir |
|---|---|
| Mesures | Puissance réseau (> 0 en soutirage, < 0 en injection ; option d'inversion), **ou** consommation maison + production solaire |
| Équipements | Interrupteurs (`switch` / `input_boolean`) du chauffe-eau et de la pompe, entité `climate`, capteurs de puissance et de température d'eau (optionnels) |
| Réglages | Puissances nominales, durées garanties, heures creuses, marge, hystérésis, durées min. marche/arrêt |

Tout est modifiable ensuite via le bouton **Configurer** de l'intégration.

## Fonctionnement

Toutes les 30 s, l'intégration calcule la **puissance disponible** = injection réseau +
puissance des équipements qu'elle pilote déjà, puis l'attribue par priorité :

1. **Chauffe-eau** : démarre sur surplus. Avec un capteur de puissance, une consommation
   nulle pendant 10 min alors qu'il est alimenté signifie « ballon chaud » : terminé pour la journée.
2. **Piscine** : durée de filtration = température de l'eau / 2 (bornée min/max), ou durée fixe sans sonde.
3. **Clim / chauffage** : en mode `heat` ou `cool`, la consigne est décalée (+1 °C en chauffage,
   −1 °C en clim par défaut) tant qu'il y a du surplus, puis restaurée.

**Rattrapage** : le cycle journalier commence à la fin des heures creuses. Si la durée garantie
du chauffe-eau ou de la piscine n'est pas atteinte, l'équipement est forcé pendant les heures
creuses, ou avant la fin du cycle s'il ne reste plus assez de temps.

**Anti court-cycle** : durées minimales de marche/arrêt, et un équipement en marche n'est coupé
que si le soutirage dépasse le seuil toléré.

Si la mesure réseau devient indisponible, aucun équipement n'est démarré sur surplus.

## Entités créées

- Capteurs : puissance réseau, puissance disponible, état de chaque équipement
  (surplus, marche forcée, terminé, en attente…), durées de chauffe / filtration du jour, filtration requise.
- Interrupteurs : *Pilotage automatique* (global) et un interrupteur automatique par équipement.
  Désactivé, l'intégration ne touche plus à l'équipement (et restaure la consigne de la clim).
  Une consigne de clim changée à la main pendant un boost est respectée.

## Tableau de bord

Un tableau de bord prêt à coller (cartes natives uniquement) est fourni dans
[examples/dashboard.yaml](examples/dashboard.yaml) : jauges de puissance, état et
commande de chaque équipement, durées du jour et historiques sur 24 h.
Adaptez les entités de production, consommation et équipements indiquées en tête du fichier.

## Tests

La logique de décision (`engine.py`) est indépendante de Home Assistant :

```bash
python -m pytest tests
```
