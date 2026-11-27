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
2. Dans Minecraft, utilise le stick gauche pour déplacer le pointeur et
   **A / ✕** pour cliquer. Pour attribuer une manette à J1 depuis un monde solo,
   appuie sur **View / Create**.
3. Ouvre un monde avec J1. Sur la manette de J2, appuie sur **Start / Options**
   et choisis un profil local.

Les données, dont le runtime Java 25 et les mondes, sont dans
`/userdata/system/minecraft-couchcraft`. Au premier passage depuis l’ancien
test Couchcraft, l’installateur copie son profil, ses mondes et son cache de
jeu. L’ancienne entrée gérée reçoit le suffixe `.sh.disabled`.

## Mettre à jour et diagnostiquer

Le port recherche au lancement, au maximum une fois par jour, les correctifs
compatibles Couchcraft 0.2.x et les versions de Temurin 25. En cas d’échec, il
utilise les versions installées. Minecraft reste en 26.3 et CLauncher en 1.0.3.

Le test active la navigation native ImGui dans CLauncher 1.0.3. Avec le JAR
officiel Couchcraft 0.2.0, il affiche aussi le pointeur de J1 lorsqu’une
manette lui est attribuée et qu’un menu est ouvert. Les binaires sont reconnus
par leur SHA-256 avant application des corrections. Les versions ultérieures
de Couchcraft utilisent leur propre rendu.

```sh
python3 /userdata/system/minecraft-couchcraft/install-minecraft-couchcraft.py mettre-a-jour
python3 /userdata/system/minecraft-couchcraft/install-minecraft-couchcraft.py verifier
```

Les journaux de CLauncher sont dans `home/.clauncher/logs` sous le dossier du
port. Fabric écarte Sodium et Iris pour la session Couchcraft.

## Projets utilisés

- [CLauncher](https://github.com/chepupel123/CLauncher)
- [Couchcraft](https://github.com/zortos293/Couchcraft)
- [Fabric](https://fabricmc.net/)
- [Eclipse Temurin](https://adoptium.net/)
