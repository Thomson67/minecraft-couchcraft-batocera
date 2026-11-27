# Minecraft Couchcraft pour Batocera

Port autonome de Minecraft Java 26.3 pour Batocera x86-64. CLauncher 1.0.3
prépare un profil Fabric avec un pseudo local. Couchcraft 0.2.x gère l’écran
partagé et les manettes dans une seule fenêtre.

## Installer

Ferme Minecraft et CLauncher avant d’installer cette version de test. Lance la
commande suivante en SSH sur Batocera.

```sh
curl -fsSL https://raw.githubusercontent.com/Thomson67/minecraft-couchcraft-batocera/test-manette/install-minecraft-couchcraft.py -o /tmp/install-minecraft-couchcraft.py && python3 /tmp/install-minecraft-couchcraft.py
```

1. Actualise les listes d’EmulationStation. Dans **Ports**, ouvre
   **Minecraft 26.3 (Couchcraft)**. Dans CLauncher, utilise la croix ou le
   stick gauche pour sélectionner **Play**, puis **A / ✕** pour valider.
   **B / ○** annule. CLauncher télécharge Minecraft et Fabric au premier
   démarrage.
2. Minecraft démarre en plein écran après l’installation. Dans les menus,
   utilise le stick gauche pour déplacer le pointeur et **A / ✕** pour cliquer.
3. Pour jouer en écran partagé, ouvre ou crée un monde en **Solo** avec J1.
   Une fois dans le monde, appuie sur **Start / Options** sur la manette
   libre de J2 et valide son profil avec **A / ✕**. Si une manette libre doit
   être attribuée à J1, utilise **View / Create** sur celle-ci.

Les données, dont le runtime Java 25 et les mondes, sont dans
`/userdata/system/minecraft-couchcraft`. Au premier passage depuis l’ancien
test Couchcraft, l’installateur copie son profil, ses mondes et son cache de
jeu. L’ancienne entrée gérée reçoit le suffixe `.sh.disabled`.

## Clavier virtuel

Sélectionne d’abord le champ de texte dans CLauncher ou Minecraft avec J1, puis
appuie sur **Hotkey + Select**. Si Hotkey et Select sont associés au même bouton
dans EmulationStation, utilise **Hotkey + R1**. Déplace la sélection avec la
croix ou le stick gauche, valide avec **A / ✕**, et ferme avec **B / ○**.
Le clavier de création ou de renommage des profils invités reste dans Couchcraft.

Le clavier reprend l’interface de l’Ultimate Wine Toolbox et utilise les
réglages de manettes d’EmulationStation. Il requiert Python GTK 3, evdev et
uinput. En session Wayland, le port utilise XWayland pour les deux fenêtres et
le clavier s’affiche via GTK Layer Shell.

## Mettre à jour et diagnostiquer

Le port recherche au lancement, au maximum une fois par jour, les correctifs
compatibles Couchcraft 0.2.x et les versions de Temurin 25. En cas d’échec, il
utilise les versions installées. Minecraft reste en 26.3 et CLauncher en 1.0.3.

Le test fournit les manettes SDL2 à la navigation native ImGui de CLauncher
1.0.3 via [l’adaptateur GLFW](clauncher-gamepad.c). La bibliothèque est chargée
dans le lanceur uniquement. Avec le JAR officiel Couchcraft 0.2.0, le test
affiche aussi le pointeur de J1 quand une manette lui est attribuée et qu’un menu
est ouvert. Les versions ultérieures de Couchcraft utilisent leur propre rendu.

```sh
python3 /userdata/system/minecraft-couchcraft/install-minecraft-couchcraft.py mettre-a-jour
python3 /userdata/system/minecraft-couchcraft/install-minecraft-couchcraft.py verifier
```

Les journaux de CLauncher sont dans `home/.clauncher/logs` sous le dossier du
port. Le journal du clavier se trouve dans `clavier-virtuel.log`. Fabric
écarte Sodium et Iris pour la session Couchcraft.

## Projets utilisés

- [CLauncher](https://github.com/chepupel123/CLauncher)
- [Couchcraft](https://github.com/zortos293/Couchcraft)
- [Fabric](https://fabricmc.net/)
- [Eclipse Temurin](https://adoptium.net/)
