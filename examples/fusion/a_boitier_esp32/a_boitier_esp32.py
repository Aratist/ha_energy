"""Fusion 360 : construit un petit boîtier à clipser, sans vis, pour une carte ESP32 DevKit.

Lancer : Utilitaires → Scripts et compléments (Maj+S) → « + » → Script ou complément depuis
l'appareil → choisir ce dossier a_boitier_esp32 → Exécuter.

Deux pièces :
- « Bac » : la carte y est posée sur deux appuis, broches vers le fond, prise USB face à une
  encoche du petit côté. Un passe-fil de l'autre côté laisse sortir des fils.
- « Couvercle » : sa lèvre entre dans le bac et deux crochets se clipsent dans deux fenêtres
  des grands côtés. Deux plots maintiennent la carte. Pour l'ouvrir, enfoncer les crochets
  par les fenêtres avec un ongle ou un petit tournevis.

Chaque forme est une esquisse suivie d'une extrusion dans l'historique : on peut tout modifier
ensuite dans Fusion. Pour changer les cotes de départ, modifier les constantes ci-dessous et
relancer. Le script exporte aussi les STL (impression) et les STEP dans le sous-dossier export/.

Repère du bac : origine au centre du dessous, X le long de la carte (antenne à gauche, USB à
droite), Y en travers, Z vers le haut. Le couvercle est construit retourné, à plat comme il
s'imprime, à côté du bac. Toutes les cotes sont en mm.
Mesurer sa carte au pied à coulisse et corriger les cotes « à vérifier » avant d'imprimer.
"""
import os
import traceback

import adsk.core
import adsk.fusion

# --- Carte ESP32 DevKit (à vérifier : DevKitC 54,4 × 27,9 ; DOIT 30 broches 51,5 × 28,3)
ESP = (55, 28.5)             # longueur, largeur
PCB_EP = 1.6
COMPOSANTS_H = 3.2           # hauteur du module ESP32 et de la prise USB au-dessus du PCB
DESSOUS = 10                 # sous le PCB : broches mâles (20 pour des connecteurs Dupont)
USB = (12, 8)                # encoche de la fiche USB : largeur, hauteur

# --- Boîtier
PAROI = 2
COUVERCLE_EP = 2
LEVRE = (1.6, 4)             # épaisseur, hauteur de la lèvre du couvercle
JEU = 0.15                   # jeu de la lèvre dans le bac
PLOT = 2                     # couvercle ↔ dessus des composants
CROCHET = (7, 0.5)           # largeur, saillie des crochets
CROCHET_X = 15               # centre des crochets, de part et d'autre du milieu

# La carte est poussée contre le côté USB ; la lèvre passe autour, sans la toucher.
INTERIEUR = (ESP[0] + 5, ESP[1] + 5)
EXT = (INTERIEUR[0] + 2 * PAROI, INTERIEUR[1] + 2 * PAROI)
X_USB = INTERIEUR[0] / 2 - 0.5
X_ANTENNE = X_USB - ESP[0]
Z_PCB_DESSOUS = PAROI + DESSOUS
Z_PCB_DESSUS = Z_PCB_DESSOUS + PCB_EP
HAUTEUR = Z_PCB_DESSUS + COMPOSANTS_H + PLOT                  # hauteur des parois du bac
Z_FENETRE = (HAUTEUR - 3.4, HAUTEUR - 1.6)                   # fenêtres des crochets

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
    def plan(self, base, decalage):
        """Plan de construction parallèle à XY, XZ ou YZ, décalé de `decalage` mm."""
        plan_base = {"XY": self.comp.xYConstructionPlane,
                     "XZ": self.comp.xZConstructionPlane,
                     "YZ": self.comp.yZConstructionPlane}[base]
        if abs(decalage) < 1e-9:
            return plan_base
        cle = (base, decalage)
        if cle not in self.plans:
            entree = self.comp.constructionPlanes.createInput()
            entree.setByOffset(plan_base, adsk.core.ValueInput.createByReal(cm(decalage)))
            plan = self.comp.constructionPlanes.add(entree)
            plan.name = "Plan {} {} mm".format(base, decalage)
            plan.isLightBulbOn = False
            self.plans[cle] = plan
        return self.plans[cle]

    def esquisse(self, decalage, nom, base="XY"):
        esq = self.comp.sketches.add(self.plan(base, decalage))
        esq.name = nom
        esq.isVisible = False
        return esq

    @staticmethod
    def point(esq, x, y, z=0):
        """Point du repère de la pièce, projeté dans le plan de l'esquisse.

        Sans la mise à zéro de z, un point pris en z = 0 resterait à z = 0 au lieu d'être sur
        un plan décalé : l'extrusion partirait du dessous de la pièce.
        """
        p = esq.modelToSketchSpace(adsk.core.Point3D.create(cm(x), cm(y), cm(z)))
        p.z = 0
        return p

    def cercle(self, esq, centre, diametre):
        esq.sketchCurves.sketchCircles.addByCenterRadius(self.point(esq, *centre), cm(diametre / 2))

    def rectangle(self, esq, x1, y1, x2, y2):
        esq.sketchCurves.sketchLines.addTwoPointRectangle(self.point(esq, x1, y1), self.point(esq, x2, y2))

    def polygone(self, esq, points):
        lignes = esq.sketchCurves.sketchLines
        pts = [self.point(esq, *p) for p in points]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            lignes.addByTwoPoints(a, b)

    @staticmethod
    def profils(esq):
        coll = adsk.core.ObjectCollection.create()
        for p in esq.profiles:
            coll.add(p)
        return coll

    def extruder(self, profils, epaisseur, operation, nom, cibles=None, symetrique=False):
        feats = self.comp.features.extrudeFeatures
        entree = feats.createInput(profils, operation)
        distance = adsk.core.ValueInput.createByReal(cm(epaisseur))
        if symetrique:
            entree.setSymmetricExtent(distance, True)
        else:
            entree.setDistanceExtent(False, distance)
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

    def creuser(self, largeur, hauteur, rayon, epaisseur, z, nom):
        vide = self.pave_arrondi(largeur, hauteur, rayon, epaisseur, z, nom)
        self.combiner(self.corps, [vide], OP_COUPER, nom)

    def cylindres(self, centres, diametre, epaisseur, z, operation, nom):
        esq = self.esquisse(z, nom)
        for c in centres:
            self.cercle(esq, c, diametre)
        return self.extruder(self.profils(esq), epaisseur, operation, nom, [self.corps])

    def rectangles(self, rects, epaisseur, z, operation, nom):
        esq = self.esquisse(z, nom)
        for r in rects:
            self.rectangle(esq, *r)
        return self.extruder(self.profils(esq), epaisseur, operation, nom, [self.corps])


def construire_bac(p):
    p.pave_arrondi(EXT[0], EXT[1], 3, HAUTEUR, 0, "Coque")
    p.creuser(INTERIEUR[0], INTERIEUR[1], 1, HAUTEUR, PAROI, "Intérieur")

    # Appuis sous les deux bouts de la carte, entre les rangées de broches.
    p.rectangles([(X_ANTENNE, -7, X_ANTENNE + 8, 7), (X_USB - 8, -7, X_USB, 7)],
                 DESSOUS, PAROI, OP_JOINDRE, "Appuis carte")
    # Butées côté antenne, de part et d'autre du passe-fil, et quatre guides le long des
    # grands bords de la carte.
    butee = [(-INTERIEUR[0] / 2 - 0.5, sy * 6, X_ANTENNE - 0.3, sy * 11) for sy in (-1, 1)]
    guides = [(x, sy * (ESP[1] / 2 + 0.3), x + 3, sy * (INTERIEUR[1] / 2 + 0.5))
              for x in (X_ANTENNE + 4, X_USB - 7) for sy in (-1, 1)]
    p.rectangles(butee + guides, Z_PCB_DESSUS - PAROI, PAROI, OP_JOINDRE, "Butée et guides carte")

    # Encoche de la fiche USB, ouverte vers le haut, centrée sur la prise.
    z_usb = Z_PCB_DESSUS + COMPOSANTS_H / 2 - USB[1] / 2
    p.rectangles([(INTERIEUR[0] / 2 - 0.01, -USB[0] / 2, EXT[0] / 2 + 1, USB[0] / 2)],
                 HAUTEUR, z_usb, OP_COUPER, "Encoche USB")
    # Passe-fil au ras du fond, côté antenne, pour les fils branchés sur les broches.
    p.rectangles([(-EXT[0] / 2 - 1, -5, -INTERIEUR[0] / 2 + 0.01, 5)], 5, PAROI, OP_COUPER, "Passe-fil")

    # Aérations sous la carte.
    p.rectangles([(x, -9, x + 1.6, 9) for x in range(-12, 13, 4)], PAROI + 2, -1, OP_COUPER, "Aérations")

    # Fenêtres où se clipsent les crochets du couvercle.
    y_paroi = EXT[1] / 2 - PAROI / 2
    for sy in (-1, 1):
        esq = p.esquisse(sy * y_paroi, "Fenêtres {}".format("arrière" if sy > 0 else "avant"), "XZ")
        for c in (-CROCHET_X, CROCHET_X):
            demi = CROCHET[0] / 2 + 0.5
            p.polygone(esq, [(c - demi, sy * y_paroi, Z_FENETRE[0]), (c + demi, sy * y_paroi, Z_FENETRE[0]),
                             (c + demi, sy * y_paroi, Z_FENETRE[1]), (c - demi, sy * y_paroi, Z_FENETRE[1])])
        p.extruder(p.profils(esq), PAROI + 2, OP_COUPER, esq.name, [p.corps], symetrique=True)
    p.corps.name = "Bac"


def construire_couvercle(p):
    """Couvercle à plat, face extérieure en z = 0 ; il se retourne sur le bac (demi-tour autour de X)."""
    p.pave_arrondi(EXT[0], EXT[1], 3, COUVERCLE_EP, 0, "Plaque")

    exterieur = (INTERIEUR[0] - 2 * JEU, INTERIEUR[1] - 2 * JEU)
    levre = p.pave_arrondi(exterieur[0], exterieur[1], 1, LEVRE[1], COUVERCLE_EP, "Lèvre")
    creux = p.pave_arrondi(exterieur[0] - 2 * LEVRE[0], exterieur[1] - 2 * LEVRE[0], 0.5, LEVRE[1],
                           COUVERCLE_EP, "Creux lèvre")
    p.combiner(levre, [creux], OP_COUPER, "Évidement lèvre")
    p.combiner(p.corps, [p.comp.bRepBodies.item(1)], OP_JOINDRE, "Lèvre jointe")
    # Lèvre interrompue au-dessus de la prise USB.
    p.rectangles([(INTERIEUR[0] / 2 - 3, -USB[0] / 2, INTERIEUR[0] / 2 + 1, USB[0] / 2)],
                 LEVRE[1] + 1, COUVERCLE_EP, OP_COUPER, "Passage USB")

    # Plots qui appuient sur le module ESP32 (côté antenne) et sur la prise USB.
    # Le demi-tour autour de X garde les abscisses : mêmes X que dans le bac.
    p.cylindres([(X_ANTENNE + 12, 0), (X_USB - 3, 0)], 5, PLOT, COUVERCLE_EP, OP_JOINDRE, "Plots carte")

    # Crochets sur la face extérieure de la lèvre : face d'accroche côté plaque, rampe vers le bout.
    z_accroche = COUVERCLE_EP + HAUTEUR - Z_FENETRE[1] + 0.1
    y_ext = exterieur[1] / 2
    for c in (-CROCHET_X, CROCHET_X):
        esq = p.esquisse(c, "Crochets x = {}".format(c), "YZ")
        for sy in (-1, 1):
            p.polygone(esq, [(c, sy * (y_ext - 0.3), z_accroche),
                             (c, sy * (y_ext + CROCHET[1]), z_accroche),
                             (c, sy * (y_ext + CROCHET[1]), z_accroche + 0.5),
                             (c, sy * (y_ext - 0.3), COUVERCLE_EP + LEVRE[1] - 0.2)])
        p.extruder(p.profils(esq), CROCHET[0], OP_JOINDRE, esq.name, [p.corps], symetrique=True)

    # Aérations au-dessus de la carte, entre les plots.
    p.rectangles([(x, -9, x + 1.6, 9) for x in range(-8, 13, 4)], COUVERCLE_EP + 2, -1, OP_COUPER, "Aérations")
    p.corps.name = "Couvercle"


def exporter(design, pieces, dossier):
    os.makedirs(dossier, exist_ok=True)
    gestion = design.exportManager
    for nom, piece in pieces:
        chemin = os.path.join(dossier, "boitier-esp32-{}".format(nom))
        stl = gestion.createSTLExportOptions(piece.corps, chemin + ".stl")
        stl.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
        gestion.execute(stl)
        gestion.execute(gestion.createSTEPExportOptions(chemin + ".step", piece.comp))


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

        bac = Piece(racine, "Bac", adsk.core.Matrix3D.create())
        construire_bac(bac)

        # Couvercle posé à côté du bac, à plat.
        position = adsk.core.Matrix3D.create()
        position.translation = adsk.core.Vector3D.create(0, cm(EXT[1] + 10), 0)
        couvercle = Piece(racine, "Couvercle", position)
        construire_couvercle(couvercle)

        dossier = os.path.join(os.path.dirname(os.path.abspath(__file__)), "export")
        try:
            exporter(design, [("bac", bac), ("couvercle", couvercle)], dossier)
            message = "STL et STEP exportés dans :\n" + dossier
        except Exception:
            message = "Export STL/STEP impossible :\n" + traceback.format_exc()

        app.activeViewport.fit()
        ui.messageBox("Boîtier ESP32 construit : {:.0f} × {:.0f} × {:.0f} mm.\n\n".format(
                          EXT[0], EXT[1], HAUTEUR + COUVERCLE_EP)
                      + message
                      + "\n\nImprimer le bac fond sur le plateau et le couvercle face extérieure"
                        " sur le plateau, sans support. Le PETG rend les clips plus souples que le PLA.")
    except Exception:
        if ui:
            ui.messageBox("Échec de la construction du boîtier :\n" + traceback.format_exc())
