# Minecraft Couchcraft pour Batocera

Port autonome pour Batocera **x86-64**, avec Minecraft Java, Fabric et Couchcraft. Le lanceur CLauncher prépare un profil avec un pseudo local. Couchcraft permet de jouer à la manette et en écran partagé dans la même fenêtre. La [release v0.2.0](https://github.com/Thomson67/minecraft-couchcraft-batocera/releases/tag/v0.2.0) utilise Minecraft Java 26.3 et Java 25.

## Installation ou mise à jour

Ferme Minecraft et CLauncher si une session est ouverte. Depuis une connexion SSH à Batocera, exécute cette commande.

```sh
(cd /tmp && curl -fsSLO https://github.com/Thomson67/minecraft-couchcraft-batocera/releases/latest/download/install-minecraft-couchcraft.py && python3 install-minecraft-couchcraft.py)
```

La commande installe la [dernière release stable](https://github.com/Thomson67/minecraft-couchcraft-batocera/releases/latest). Une connexion Internet est nécessaire pour l’installation et le premier lancement.

1. Actualise les listes dans EmulationStation, puis ouvre **Ports → Minecraft**.
2. Dans CLauncher, appuie sur **Start / Options** ou clique sur **Play**. CLauncher télécharge Minecraft et Fabric au premier lancement.
3. Minecraft démarre en plein écran après l’installation. Garde le profil Fabric configuré pour Couchcraft.

Pour une installation depuis le partage Batocera, télécharge `install-minecraft-couchcraft.py` depuis la page de la release, copie-le dans `/userdata` et lance `python3 /userdata/install-minecraft-couchcraft.py` en SSH.

La mise à jour reprend les mondes, les contenus et les réglages existants. Elle remplace l’ancienne entrée **Minecraft 26.3 (Couchcraft)** créée par le port et reprend ses métadonnées et visuels EmulationStation.

## Commandes à la manette

| Action | Commande |
| --- | --- |
| Déplacer le pointeur dans CLauncher | Stick gauche ou croix directionnelle |
| Déplacer le pointeur dans les menus Minecraft | Stick gauche |
| Cliquer | **A** sur Xbox ou **✕** sur PlayStation |
| Lancer **Play** depuis CLauncher | **Start / Options** |
| Ouvrir ou fermer le clavier virtuel | **Hotkey + Select** ou **Hotkey + R1** si Hotkey et Select sont associés au même bouton |
| Revenir à EmulationStation | **Hotkey + Start / Options** ferme Minecraft et CLauncher |

Pour utiliser le clavier virtuel, sélectionne d’abord le champ de texte avec J1. Déplace-toi avec la croix ou le stick gauche, valide avec **A / ✕**, ferme avec **B / ○**. Couchcraft affiche son propre clavier pour les profils invités.

## Écran partagé et LAN

- **Sur la même machine**. Avec J1, crée ou ouvre un monde en **Solo**. Une fois dans le monde, appuie sur **Start / Options** sur la manette de J2 et sélectionne son profil. Si tu dois attribuer une manette libre à J1, appuie sur **View / Create** sur cette manette.
- **Depuis une autre machine**. Les mondes solo s’ouvrent automatiquement au LAN. Rejoins le monde dans **Multijoueur** sur une machine du même réseau avec une version Minecraft compatible. Si le monde ne s’affiche pas dans la liste, utilise **Connexion directe** avec l’adresse IP de l’hôte et le port indiqué dans le chat.
- **Désactiver l’ouverture automatique au LAN**. Ferme Minecraft et ajoute le suffixe `.disabled` à `couchcraft-lan-auto-1.0.0-mc26.3.jar` dans `/userdata/saves/minecraft/mods`. Retire le suffixe pour le réactiver.

## Mondes, mods et packs

Les données du jeu sont dans **`/userdata/saves/minecraft`**. Tu peux y accéder depuis le partage **saves → minecraft** et y ajouter tes contenus quand Minecraft est fermé.

| Chemin relatif | Contenu |
| --- | --- |
| `saves/` | Mondes Minecraft |
| `saves/<monde>/datapacks/` | Datapacks d’un monde |
| `mods/` | Mods compatibles avec Fabric et la version de Minecraft installée |
| `resourcepacks/` | Packs de ressources à activer dans le jeu |
| `config/` | Réglages des mods |
| `screenshots/` | Captures d’écran |

Le lanceur et Java sont installés dans `/userdata/system/minecraft-couchcraft`. Le port utilise son propre dossier et son propre Java.

## Mises à jour et dépannage

Le port vérifie au lancement, au maximum une fois par jour, les correctifs compatibles de **Couchcraft 0.2.x** et de **Temurin 25**. La version de Minecraft et celle de CLauncher sont fixées par la release. Pour installer une nouvelle release du port, relance la commande SSH ci-dessus.

Pour vérifier l’installation ou déclencher manuellement la recherche de correctifs, utilise les commandes suivantes, avec Minecraft et CLauncher fermés.

```sh
python3 /userdata/system/minecraft-couchcraft/install-minecraft-couchcraft.py verifier
python3 /userdata/system/minecraft-couchcraft/install-minecraft-couchcraft.py mettre-a-jour
```

| Journal | Emplacement |
| --- | --- |
| Minecraft | `/userdata/saves/minecraft/logs/latest.log` |
| CLauncher | `/userdata/system/minecraft-couchcraft/home/.clauncher/logs/` |
| Manette dans CLauncher | `/userdata/system/minecraft-couchcraft/manette-clauncher.log` |
| Clavier virtuel | `/userdata/system/minecraft-couchcraft/clavier-virtuel.log` |

Le port désactive Sodium et Iris pour la session Couchcraft. Si les raccourcis manette ne répondent pas, vérifie l’affectation de **Hotkey**, **Start** et **Select** ou **R1** dans EmulationStation.

## Projets utilisés

- [CLauncher](https://github.com/chepupel123/CLauncher)
- [Couchcraft](https://github.com/zortos293/Couchcraft)
- [Fabric](https://fabricmc.net/)
- [Eclipse Temurin](https://adoptium.net/)
