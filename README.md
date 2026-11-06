# Gestionnaire d'énergie solaire pour Home Assistant

Intégration personnalisée (`custom_components/energy_manager`) qui minimise le coût de
l'électricité d'une maison équipée de panneaux solaires et d'un abonnement heures
pleines / heures creuses : elle oriente le solaire vers le chauffe-eau, la pompe de
piscine et la clim/chauffage, reporte en heures creuses ce qui n'est pas rentable en
journée, et maintient la maison dans une bande de confort.

Elle ne parle à aucun matériel directement : elle s'appuie sur les entités que vous avez
déjà dans Home Assistant (compteur Linky/pince, onduleur, prises ou relais, thermostat).

## Installation

Via HACS (recommandé) :

1. *HACS → ⋮ → Dépôts personnalisés*, ajouter `https://github.com/Aratist/ha_energy`
   avec le type *Intégration*.
2. Rechercher *Gestionnaire d'énergie solaire* dans HACS, puis *Télécharger*.
3. Redémarrer Home Assistant.
4. *Paramètres → Appareils et services → Ajouter une intégration → Gestionnaire d'énergie solaire*.

Manuellement : copier `custom_components/energy_manager` dans `config/custom_components/`,
puis reprendre à l'étape 3.

Home Assistant 2024.12 ou plus récent est requis.

## Configuration

| Étape | Ce qu'il faut fournir |
|---|---|
| Mesures | Puissance réseau (> 0 en soutirage, < 0 en injection ; option d'inversion), consommation de la maison, production solaire, et le **talon** de consommation utilisé pour l'estimation |
| Équipements | Interrupteurs du chauffe-eau et de la pompe, entité `climate`, capteurs de puissance, sonde de piscine, température intérieure (optionnels) |
| Appareils | Liste libre d'appareils : entité qui dit s'il est allumé + puissance habituelle, et/ou capteur de puissance |
| Tarifs | Prix HP, HC et revente ; capteurs de prix optionnels (Tempo…) ; plage d'heures creuses |
| Confort | Bande hiver (19–23 °C par défaut) et bande été (24–27 °C) |
| Réglages | Puissances nominales, durées garanties, marge, hystérésis, durées min. marche/arrêt |

Tout est modifiable ensuite via le bouton **Configurer** de l'intégration.

## Fonctionnement

Toutes les 30 s :

1. **Mesures.** La consommation est celle du capteur si elle est disponible ; sinon elle est
   **estimée** = talon + appareils déclarés (mesurés ou puissance habituelle s'ils sont
   allumés) + équipements pilotés. La puissance réseau est mesurée, sinon déduite
   (consommation − production). Un capteur Linky indisponible n'arrête donc pas le pilotage.
2. **Rentabilité.** En heures pleines, un appareil différable (chauffe-eau, piscine) ne
   démarre que si le solaire couvre au moins `(HP − HC) / (HP − revente)` de sa puissance :
   au-delà, le faire tourner maintenant coûte moins cher que de l'attendre en heures creuses.
   Ce qui n'a pas pu tourner en journée est rattrapé pendant les heures creuses.
3. **Priorités selon la saison.** Hiver (novembre à mars, ou forcé via le sélecteur *Saison*) :
   chauffage > chauffe-eau > piscine. Été : chauffe-eau > piscine > clim.
4. **Confort.** En hiver, la consigne du chauffage est maintenue dans la bande ; quand le
   solaire couvre entièrement la puissance de la clim, la consigne monte au maximum de la
   bande pour stocker de la chaleur avant la soirée en heures pleines. En été, même principe
   inversé (la clim descend au minimum de la bande sur surplus). Une consigne changée à la
   main pendant un boost est respectée ; une clim éteinte n'est jamais rallumée.
5. **Chauffe-eau** : avec un capteur de puissance, une consommation nulle pendant 10 min
   alors qu'il est alimenté signifie « ballon chaud » ; en heures creuses ce signal est
   ignoré (le ballon a pu être vidé le soir, et le thermostat ne chauffe pas pour rien). **Piscine** : durée de filtration =
   température de l'eau / 2 (bornée), ou durée fixe sans sonde.
6. **Anti court-cycle** : durées minimales de marche/arrêt, et un équipement en marche n'est
   coupé que si le soutirage dépasse le seuil toléré.

Le cycle journalier commence à la fin des heures creuses.

## Entités créées

- **Mesures** : consommation (attribut `source` : mesurée/estimée), production, puissance
  réseau, puissance disponible, consommation des appareils, un capteur de puissance par
  appareil déclaré, température intérieure.
- **Tarifs** : tarif actuel (HP/HC), prix actuel, part solaire minimale rentable.
- **Bilan du jour** : soutirage, injection, autoconsommation (kWh), coût réseau et économie
  solaire (€). Remis à zéro à la fin des heures creuses. L'économie solaire est aussi
  cumulée par semaine, mois et année (attribut `period_start`), remise à zéro le lundi,
  le 1er du mois et le 1er janvier (calendrier local).
- **Pilotage** : état de chaque équipement (solaire, marche forcée, confort, terminé, en
  attente…), durées de chauffe / filtration, saison active.
- **Commandes** : sélecteur *Saison* (automatique / hiver / été), interrupteur *Pilotage
  automatique* (global) et un interrupteur *Gestion …* par équipement (piscine, clim,
  chauffe-eau) : coupé, l'équipement n'est plus du tout touché, par exemple pour garder le
  chauffage en télétravail ou piloter la pompe à la main pendant une vidange.

## Tableau de bord

Un tableau de bord prêt à coller (cartes natives uniquement) est fourni dans
[examples/dashboard.yaml](examples/dashboard.yaml).
Adaptez les entités indiquées en tête du fichier.

## Tests

La logique de décision (`engine.py`) est indépendante de Home Assistant :

```bash
python -m pytest tests
```
