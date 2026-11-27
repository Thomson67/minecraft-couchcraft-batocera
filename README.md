# Minecraft Couchcraft pour Batocera

Port autonome de Minecraft Java 26.3 pour Batocera x86-64. CLauncher 1.0.3
prépare un profil Fabric avec un pseudo local. Couchcraft 0.2.x gère l’écran
partagé et les manettes dans une seule fenêtre.

## Installer

1. Télécharge le fichier [install-minecraft-couchcraft.py](install-minecraft-couchcraft.py)
   et copie-le à la racine du partage Batocera.
2. Lance la commande suivante en SSH.

   ```sh
   python3 /userdata/install-minecraft-couchcraft.py
   ```

3. Actualise les listes d’EmulationStation. Dans **Ports**, ouvre
   **Minecraft 26.3 (Couchcraft)** et clique sur **Play**. CLauncher télécharge
   Minecraft et Fabric au premier démarrage.
4. Ouvre un monde avec J1. Sur la manette de J2, appuie sur **Start / Options**
   et choisis un profil local.

Les données, dont le runtime Java 25 et les mondes, sont dans
`/userdata/system/minecraft-couchcraft`. Au premier passage depuis l’ancien
test Couchcraft, l’installateur copie son profil, ses mondes et son cache de
jeu. L’ancienne entrée gérée reçoit le suffixe `.sh.disabled`.

## Mettre à jour et diagnostiquer

Le port recherche au lancement, au maximum une fois par jour, les correctifs
compatibles Couchcraft 0.2.x et les versions de Temurin 25. En cas d’échec, il
utilise les versions installées. Minecraft reste en 26.3 et CLauncher en 1.0.3.

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
