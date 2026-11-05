"""Fusion 360 : construit le boîtier de la caméra du placard (façade et fond).

Projet complet : CAMERA_PLACARD/CAMERA_PLACARD.md à la racine du dépôt.

Lancer : Utilitaires → Scripts et compléments (Maj+S) → « + » → Script ou complément depuis
l'appareil → choisir ce dossier boitier_placard → Exécuter.

Le script crée un nouveau document avec deux composants, « Façade » et « Fond ». Chaque forme
est une esquisse suivie d'une extrusion dans l'historique : on peut tout modifier ensuite dans
Fusion. Pour changer les cotes de départ, modifier les constantes ci-dessous et relancer.
Il exporte aussi les STL (impression) et les STEP dans le sous-dossier export/.

Repère de chaque pièce : origine au centre, X vers la droite, Y vers le haut,
Z vers l'intérieur du boîtier. Toutes les cotes sont en mm.
Mesurer sa carte au pied à coulisse et corriger les cotes « à vérifier » avant d'imprimer.
"""
import math
import os
import traceback

import adsk.core
import adsk.fusion

# --- Boîtier
INTERIEUR = (92, 104, 34)    # largeur, hauteur, profondeur intérieures
PAROI = 2.4
FACADE_EP = 2.4
RAYON = 5                    # arrondi des angles
JEU = 0.3                    # jeu d'emboîtement

# --- Caméra et anneau LED (à vérifier)
CAMERA_POS = (-24, 26)       # centre de l'objectif, depuis le centre de la façade
CAMERA_TROU = 9.5            # l'objectif OV2640 fait 8 mm
ANNEAU_EXT = 38              # anneau WS2812 12 LED : Ø37 mm extérieur
ANNEAU_INT = 22              # Ø23 mm intérieur
DIFFUSEUR = 0.8              # plastique laissé devant les LED

# --- Carte ESP32-S3 (à vérifier)
ESP = (63.5, 26.5)           # longueur, largeur de la carte
ESP_CAMERA_BORD = 11         # distance objectif ↔ petit bord côté caméra
ESP_HAUTEUR = 5.5            # face avant de la carte ↔ intérieur de la façade (hauteur de l'objectif)

# --- Haut-parleur et micro
HP_POS = (0, -26)
HP_DIAM = 40
MICRO_POS = (34, -14)
MICRO_MODULE = 14.5          # INMP441 rond : Ø14 mm

# --- Fond
CARTE_TROUS = (54, 34)       # entraxe des trous M2.5 du PCB porteur 60 × 40 mm (KiCad)
CARTE_HAUTEUR = 6            # entretoises
CARTE_Y = 24                 # derrière la carte ESP32 : le haut-parleur occupe le bas
PASSE_FIL = (12, 7)          # sortie des câbles (alim, contact de porte), dessous du boîtier

EXT = (INTERIEUR[0] + 2 * PAROI, INTERIEUR[1] + 2 * PAROI)
VIS = (EXT[0] / 2 - PAROI - 2.5, EXT[1] / 2 - PAROI - 2.5)   # vis M3 dans les angles
COINS = [(sx * VIS[0], sy * VIS[1]) for sx in (-1, 1) for sy in (-1, 1)]

OP_NOUVEAU = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
OP_JOINDRE = adsk.fusion.FeatureOperations.JoinFeatureOperation
OP_COUPER = adsk.fusion.FeatureOperations.CutFeatureOperation


def cm(v):
    """L'API de Fusion travaille en cm."""
    return v / 10.0


class Piece:
    """Un composant et son corps unique, construit à coups d'esquisses et d'extrusions."""

    def __init__(self, racine, nom, transformation):
        occurrence = racine.occurrences.addNewComponent(transformation)
        self.comp = occurrence.component
        self.comp.name = nom
        self.plans = {}

    # ----- outils
    def plan(self, z):
        if abs(z) < 1e-9:
            return self.comp.xYConstructionPlane
        if z not in self.plans:
            entree = self.comp.constructionPlanes.createInput()
            entree.setByOffset(self.comp.xYConstructionPlane, adsk.core.ValueInput.createByReal(cm(z)))
            plan = self.comp.constructionPlanes.add(entree)
            plan.name = "Plan z = {} mm".format(z)
            plan.isLightBulbOn = False
            self.plans[z] = plan
        return self.plans[z]

    def esquisse(self, z, nom):
        esq = self.comp.sketches.add(self.plan(z))
        esq.name = nom
        esq.isVisible = False
        return esq

    @staticmethod
    def point(x, y):
        # Plan parallèle à XY : l'esquisse a les mêmes axes X et Y que le composant.
        return adsk.core.Point3D.create(cm(x), cm(y), 0)

    def cercle(self, esq, centre, diametre):
        esq.sketchCurves.sketchCircles.addByCenterRadius(self.point(*centre), cm(diametre / 2))

    def rectangle(self, esq, x1, y1, x2, y2):
        esq.sketchCurves.sketchLines.addTwoPointRectangle(self.point(x1, y1), self.point(x2, y2))

    @staticmethod
    def profils(esq, boucles=None):
        coll = adsk.core.ObjectCollection.create()
        for p in esq.profiles:
            if boucles is None or p.profileLoops.count == boucles:
                coll.add(p)
        return coll

    def extruder(self, profils, epaisseur, operation, nom, cibles=None):
        feats = self.comp.features.extrudeFeatures
        entree = feats.createInput(profils, operation)
        entree.setDistanceExtent(False, adsk.core.ValueInput.createByReal(cm(epaisseur)))
        if cibles:
            entree.participantBodies = cibles
        feat = feats.add(entree)
        feat.name = nom
        return feat

    @property
    def corps(self):
        return self.comp.bRepBodies.item(0)

    def combiner(self, cible, outils, operation, nom):
        coll = adsk.core.ObjectCollection.create()
        for o in outils:
            coll.add(o)
        entree = self.comp.features.combineFeatures.createInput(cible, coll)
        entree.operation = operation
        entree.isKeepToolBodies = False
        self.comp.features.combineFeatures.add(entree).name = nom

    # ----- formes
    def pave_arrondi(self, largeur, hauteur, rayon, epaisseur, z, nom):
        """Nouveau corps : pavé centré, arêtes verticales arrondies."""
        esq = self.esquisse(z, nom)
        self.rectangle(esq, -largeur / 2, -hauteur / 2, largeur / 2, hauteur / 2)
        corps = self.extruder(self.profils(esq), epaisseur, OP_NOUVEAU, nom).bodies.item(0)
        aretes = adsk.core.ObjectCollection.create()
        for a in corps.edges:
            d, f = a.startVertex.geometry, a.endVertex.geometry
            if abs(d.x - f.x) < 1e-6 and abs(d.y - f.y) < 1e-6:
                aretes.add(a)
        conges = self.comp.features.filletFeatures
        entree = conges.createInput()
        r = adsk.core.ValueInput.createByReal(cm(rayon))
        try:
            entree.edgeSetInputs.addConstantRadiusEdgeSet(aretes, r, True)
        except AttributeError:   # anciennes versions de l'API
            entree.addConstantRadiusEdgeSet(aretes, r, True)
        conges.add(entree).name = "Congés " + nom
        return corps

    def cylindres(self, centres, diametre, epaisseur, z, operation, nom, cibles=None):
        esq = self.esquisse(z, nom)
        for c in centres:
            self.cercle(esq, c, diametre)
        return self.extruder(self.profils(esq), epaisseur, operation, nom, cibles)

    def anneau(self, centre, d_ext, d_int, epaisseur, z, operation, nom):
        esq = self.esquisse(z, nom)
        self.cercle(esq, centre, d_ext)
        self.cercle(esq, centre, d_int)
        return self.extruder(self.profils(esq, boucles=2), epaisseur, operation, nom, [self.corps])

    def rectangles(self, rects, epaisseur, z, nom):
        esq = self.esquisse(z, nom)
        for r in rects:
            self.rectangle(esq, *r)
        return self.extruder(self.profils(esq), epaisseur, OP_COUPER, nom, [self.corps])


def construire_facade(p):
    p.pave_arrondi(EXT[0], EXT[1], RAYON, FACADE_EP, 0, "Plaque")

    # Lèvre qui entre dans le fond, interrompue aux angles pour les vis.
    levre = p.pave_arrondi(INTERIEUR[0] - 2 * JEU, INTERIEUR[1] - 2 * JEU, max(RAYON - PAROI, 0.5), 3, FACADE_EP, "Lèvre")
    creux = p.pave_arrondi(INTERIEUR[0] - 2 * JEU - 2.4, INTERIEUR[1] - 2 * JEU - 2.4, 1, 3, FACADE_EP, "Creux lèvre")
    p.combiner(levre, [creux], OP_COUPER, "Évidement lèvre")
    levre = p.comp.bRepBodies.item(1)
    p.cylindres(COINS, 9, 3, FACADE_EP, OP_COUPER, "Dégagement vis", [levre])
    p.combiner(p.comp.bRepBodies.item(0), [p.comp.bRepBodies.item(1)], OP_JOINDRE, "Lèvre jointe")

    # Centrage du haut-parleur, logement du micro.
    p.anneau(HP_POS, HP_DIAM + 3.2, HP_DIAM + 0.6, 3, FACADE_EP, OP_JOINDRE, "Centrage haut-parleur")
    p.anneau(MICRO_POS, MICRO_MODULE + 2.4, MICRO_MODULE + 0.4, 2, FACADE_EP, OP_JOINDRE, "Logement micro")

    # Deux plots qui portent l'extrémité de la carte ESP32 (côté caméra : l'anneau LED sert d'appui).
    x_plot = CAMERA_POS[0] + ESP[0] - ESP_CAMERA_BORD - 4
    plots = [(x_plot, CAMERA_POS[1] + sy * (ESP[1] / 2 - 2)) for sy in (-1, 1)]
    p.cylindres(plots, 5, ESP_HAUTEUR, FACADE_EP, OP_JOINDRE, "Plots ESP32", [p.corps])

    # Objectif, logement de l'anneau LED (LED côté façade), évent du micro.
    p.cylindres([CAMERA_POS], CAMERA_TROU, 20, -1, OP_COUPER, "Objectif", [p.corps])
    p.anneau(CAMERA_POS, ANNEAU_EXT + 0.6, ANNEAU_INT - 0.6, 20, DIFFUSEUR, OP_COUPER, "Logement anneau LED")
    p.cylindres([MICRO_POS], 1.6, FACADE_EP + 2, -1, OP_COUPER, "Évent micro", [p.corps])

    # Grille du haut-parleur en quinconce.
    trous = []
    for i in range(-6, 7):
        for j in range(-6, 7):
            dx, dy = i * 4.2 + (j % 2) * 2.1, j * 3.64
            if math.hypot(dx, dy) < HP_DIAM / 2 - 4:
                trous.append((HP_POS[0] + dx, HP_POS[1] + dy))
    p.cylindres(trous, 2.6, FACADE_EP + 2, -1, OP_COUPER, "Grille haut-parleur", [p.corps])

    # Vis M3 fraisées, tête côté face avant (z = 0).
    p.cylindres(COINS, 3.4, 20, -1, OP_COUPER, "Perçages M3", [p.corps])
    gestion = adsk.fusion.TemporaryBRepManager.get()
    base = p.comp.features.baseFeatures.add()
    base.name = "Fraisures"
    base.startEdit()
    for x, y in COINS:
        cone = gestion.createCylinderOrCone(
            adsk.core.Point3D.create(cm(x), cm(y), cm(-0.01)), cm(3.2),
            adsk.core.Point3D.create(cm(x), cm(y), cm(1.6)), cm(1.7))
        p.comp.bRepBodies.add(cone, base)
    base.finishEdit()
    outils = [base.bodies.item(i) for i in range(base.bodies.count)]
    p.combiner(p.corps, outils, OP_COUPER, "Fraisures M3")
    p.corps.name = "Façade"


def construire_fond(p):
    h = INTERIEUR[2] + PAROI
    p.pave_arrondi(EXT[0], EXT[1], RAYON, h, 0, "Coque")
    vide = p.pave_arrondi(INTERIEUR[0], INTERIEUR[1], max(RAYON - PAROI, 0.5), h, PAROI, "Intérieur")
    p.combiner(p.comp.bRepBodies.item(0), [vide], OP_COUPER, "Évidement")

    # Fûts des vis d'assemblage et entretoises du PCB porteur (derrière la carte ESP32).
    entretoises = [(sx * CARTE_TROUS[0] / 2, CARTE_Y + sy * CARTE_TROUS[1] / 2) for sx in (-1, 1) for sy in (-1, 1)]
    p.cylindres(COINS, 7, h, 0, OP_JOINDRE, "Fûts M3", [p.corps])
    p.cylindres(entretoises, 5.5, PAROI + CARTE_HAUTEUR, 0, OP_JOINDRE, "Entretoises PCB", [p.corps])

    # Avant-trous M3 (vis autotaraudeuses) et M2.5.
    p.cylindres(COINS, 2.6, h, 4, OP_COUPER, "Avant-trous M3", [p.corps])
    p.cylindres(entretoises, 2.2, 20, 1.2, OP_COUPER, "Avant-trous M2.5", [p.corps])

    # Trous de fixation en serrure dans le dos (vis Ø3,5 dans la paroi du placard).
    esq = p.esquisse(-1, "Trous en serrure")
    for sx in (-1, 1):
        x = sx * 25
        p.cercle(esq, (x, -25), 7.5)
        p.rectangle(esq, x - 1.9, -25, x + 1.9, -16)
    p.extruder(p.profils(esq), PAROI + 2, OP_COUPER, "Trous en serrure", [p.corps])

    # Passe-fils sous le boîtier.
    y0 = -EXT[1] / 2 - 1
    p.rectangles([(20 - PASSE_FIL[0] / 2, y0, 20 + PASSE_FIL[0] / 2, y0 + PAROI + 2)],
                 PASSE_FIL[1], PAROI + 4, "Passe-fils")

    # Aérations sur les côtés.
    fentes = []
    for sx in (-1, 1):
        for k in range(4):
            x, y = sx * EXT[0] / 2, 20 - k * 8
            fentes.append((x - PAROI * 1.5, y - 1.5, x + PAROI * 1.5, y + 1.5))
    hauteur = INTERIEUR[2] * 0.5
    p.rectangles(fentes, hauteur, PAROI + INTERIEUR[2] / 2 - hauteur / 2, "Aérations")
    p.corps.name = "Fond"


def exporter(design, pieces, dossier):
    os.makedirs(dossier, exist_ok=True)
    gestion = design.exportManager
    for nom, piece in pieces:
        stl = gestion.createSTLExportOptions(piece.corps, os.path.join(dossier, "boitier-{}.stl".format(nom)))
        stl.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
        gestion.execute(stl)
        gestion.execute(gestion.createSTEPExportOptions(os.path.join(dossier, "boitier-{}.step".format(nom)), piece.comp))


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
        racine = design.rootComponent

        fond = Piece(racine, "Fond", adsk.core.Matrix3D.create())
        construire_fond(fond)

        # Façade retournée (demi-tour autour de Y) et posée sur le fond, 0,5 mm au-dessus.
        position = adsk.core.Matrix3D.create()
        position.setWithCoordinateSystem(
            adsk.core.Point3D.create(0, 0, cm(INTERIEUR[2] + PAROI + FACADE_EP + 0.5)),
            adsk.core.Vector3D.create(-1, 0, 0),
            adsk.core.Vector3D.create(0, 1, 0),
            adsk.core.Vector3D.create(0, 0, -1))
        facade = Piece(racine, "Façade", position)
        construire_facade(facade)

        dossier = os.path.join(os.path.dirname(os.path.abspath(__file__)), "export")
        try:
            exporter(design, [("facade", facade), ("fond", fond)], dossier)
            message = "STL et STEP exportés dans :\n" + dossier
        except Exception:
            message = "Export STL/STEP impossible :\n" + traceback.format_exc()

        app.activeViewport.fit()
        ui.messageBox("Boîtier du placard construit.\n\n" + message
                      + "\n\nImprimer la façade face avant sur le plateau, en PLA blanc,"
                        " et le fond dos sur le plateau, sans support.")
    except Exception:
        if ui:
            ui.messageBox("Échec de la construction du boîtier :\n" + traceback.format_exc())
