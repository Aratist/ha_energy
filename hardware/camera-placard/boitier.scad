// Boîtier de la caméra du placard : façade (caméra, anneau LED, micro, haut-parleur) et fond.
// Projet complet : CAMERA_PLACARD.md. OpenSCAD 2021.01 ou plus récent.
//
// Export : choisir « piece » ci-dessous (ou -D piece=\"facade\" en ligne de commande), F6, puis F7 (STL).
//   piece = "facade" : se pose face avant sur le plateau, sans support. Imprimer en PLA blanc :
//                      l'anneau LED éclaire à travers 0,8 mm de plastique (diffuseur).
//   piece = "fond"   : se pose dos sur le plateau, sans support.
//   piece = "tout"   : vue d'assemblage, pas pour l'impression.
//
// Mesurer sa carte au pied à coulisse et corriger les cotes « à vérifier » avant d'imprimer.

piece = "tout"; // ["facade", "fond", "tout"]

/* [Boîtier] */
interieur = [92, 104, 34];   // largeur, hauteur, profondeur intérieures (mm)
paroi = 2.4;
facade_ep = 2.4;
rayon = 5;                   // arrondi des angles
jeu = 0.3;                   // jeu d'emboîtement

/* [Caméra et anneau LED] — à vérifier */
camera_pos = [-24, 26];      // centre de l'objectif, depuis le centre de la façade
camera_trou = 9.5;           // l'objectif OV2640 fait 8 mm
anneau_ext = 38;             // anneau WS2812 12 LED : Ø37 mm extérieur
anneau_int = 22;             // Ø23 mm intérieur
diffuseur = 0.8;             // plastique laissé devant les LED

/* [Carte ESP32-S3] — à vérifier */
esp = [63.5, 26.5];          // longueur, largeur de la carte
esp_camera_bord = 11;        // distance objectif ↔ petit bord côté caméra
esp_hauteur = 5.5;           // face avant de la carte ↔ intérieur de la façade (hauteur de l'objectif)

/* [Haut-parleur et micro] */
hp_pos = [0, -26];
hp_diam = 40;
micro_pos = [34, -14];
micro_module = 14.5;         // INMP441 rond : Ø14 mm

/* [Fond] */
carte_mere = [60, 40];       // PCB porteur (KiCad)
carte_trous = [54, 34];      // entraxe des trous M2.5
carte_hauteur = 6;           // entretoises
carte_y = 24;                // derrière la carte ESP32 : le haut-parleur occupe le bas
passe_fil = [12, 7];         // sortie des câbles (alim, contact de porte), dessous du boîtier

$fn = 48;

ext = [interieur[0] + 2 * paroi, interieur[1] + 2 * paroi];
vis = [ext[0] / 2 - paroi - 2.5, ext[1] / 2 - paroi - 2.5];   // vis M3 dans les angles

module rect_arrondi(t, r, h) {
    linear_extrude(h)
        offset(r) square([t[0] - 2 * r, t[1] - 2 * r], center = true);
}

module coins() {
    for (sx = [-1, 1], sy = [-1, 1]) translate([sx * vis[0], sy * vis[1]]) children();
}

// ---------- Façade ----------
module facade() {
    difference() {
        union() {
            rect_arrondi(ext, rayon, facade_ep);
            // Lèvre qui entre dans le fond, interrompue aux angles pour les vis.
            difference() {
                translate([0, 0, facade_ep - 0.01])
                    rect_arrondi([interieur[0] - 2 * jeu, interieur[1] - 2 * jeu], max(rayon - paroi, 0.5), 3);
                translate([0, 0, facade_ep - 1])
                    rect_arrondi([interieur[0] - 2 * jeu - 2.4, interieur[1] - 2 * jeu - 2.4], 1, 5);
                coins() translate([0, 0, facade_ep - 1]) cylinder(d = 9, h = 5);
            }
            // Centrage du haut-parleur.
            translate([hp_pos[0], hp_pos[1], facade_ep - 0.01])
                difference() {
                    cylinder(d = hp_diam + 3.2, h = 3);
                    translate([0, 0, -1]) cylinder(d = hp_diam + 0.6, h = 5);
                }
            // Logement du micro.
            translate([micro_pos[0], micro_pos[1], facade_ep - 0.01])
                difference() {
                    cylinder(d = micro_module + 2.4, h = 2);
                    translate([0, 0, -1]) cylinder(d = micro_module + 0.4, h = 4);
                }
            // Deux plots qui portent l'extrémité de la carte ESP32 (côté caméra : l'anneau sert d'appui).
            for (sy = [-1, 1])
                translate([camera_pos[0] + esp[0] - esp_camera_bord - 4, camera_pos[1] + sy * (esp[1] / 2 - 2), facade_ep - 0.01])
                    cylinder(d = 5, h = esp_hauteur);
        }
        // Objectif.
        translate([camera_pos[0], camera_pos[1], -1]) cylinder(d = camera_trou, h = 20);
        // Logement de l'anneau LED, LED côté façade.
        translate([camera_pos[0], camera_pos[1], diffuseur])
            difference() {
                cylinder(d = anneau_ext + 0.6, h = 20);
                translate([0, 0, -1]) cylinder(d = anneau_int - 0.6, h = 22);
            }
        // Grille du haut-parleur (nid d'abeille).
        translate([hp_pos[0], hp_pos[1], -1])
            for (i = [-6:6], j = [-6:6]) {
                p = [i * 4.2 + (j % 2) * 2.1, j * 3.64];
                if (norm(p) < hp_diam / 2 - 4) translate(p) cylinder(d = 2.6, h = facade_ep + 2, $fn = 6);
            }
        // Évent du micro.
        translate([micro_pos[0], micro_pos[1], -1]) cylinder(d = 1.6, h = facade_ep + 2);
        // Vis M3 fraisées.
        coins() {
            translate([0, 0, -1]) cylinder(d = 3.4, h = 20);
            translate([0, 0, -0.01]) cylinder(d1 = 6.4, d2 = 3.4, h = 1.6);
        }
    }
}

// ---------- Fond ----------
module fond() {
    h = interieur[2] + paroi;
    difference() {
        union() {
            difference() {
                rect_arrondi(ext, rayon, h);
                translate([0, 0, paroi]) rect_arrondi([interieur[0], interieur[1]], max(rayon - paroi, 0.5), h);
            }
            // Fûts des vis d'assemblage.
            coins() cylinder(d = 7, h = h);
            // Entretoises du PCB porteur, en haut du fond (derrière la carte ESP32).
            for (sx = [-1, 1], sy = [-1, 1])
                translate([sx * carte_trous[0] / 2, carte_y + sy * carte_trous[1] / 2, 0])
                    cylinder(d = 5.5, h = paroi + carte_hauteur);
        }
        // Avant-trous M3 (vis autotaraudeuses) et M2.5.
        coins() translate([0, 0, 4]) cylinder(d = 2.6, h = h);
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx * carte_trous[0] / 2, carte_y + sy * carte_trous[1] / 2, 1.2])
                cylinder(d = 2.2, h = 20);
        // Trous de fixation en serrure dans le dos (vis Ø3,5 dans la paroi du placard).
        for (sx = [-1, 1])
            translate([sx * 25, -25, -1]) {
                cylinder(d = 7.5, h = paroi + 2);
                translate([-1.9, 0, 0]) cube([3.8, 9, paroi + 2]);
            }
        // Passe-fils sous le boîtier.
        translate([20, -ext[1] / 2 - 1, paroi + 4])
            translate([-passe_fil[0] / 2, 0, 0]) cube([passe_fil[0], paroi + 2, passe_fil[1]]);
        // Aération sur les côtés.
        for (sx = [-1, 1], k = [0:3])
            translate([sx * (ext[0] / 2), 20 - k * 8, paroi + interieur[2] / 2])
                cube([paroi * 3, 3, interieur[2] * 0.5], center = true);
    }
}

if (piece == "facade") facade();
else if (piece == "fond") fond();
else {
    color("white") translate([0, 0, interieur[2] + paroi + facade_ep + 0.5]) mirror([0, 0, 1]) facade();
    color("lightgray") fond();
}
