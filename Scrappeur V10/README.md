# Scraper Local.ch

Ce programme permet de récupérer automatiquement les informations de contact (email, adresse, numéro de téléphone) depuis local.ch pour différents mots-clés.

## Fonctionnalités

- Interface graphique simple d'utilisation
- Recherche multi-mots-clés (ex: menuisier, plombier, etc.)
- Choix du nombre de pages à scraper
- Barre de progression avec statut en temps réel
- Sauvegarde automatique dans une base de données SQLite
- Export des données en Excel

## Prérequis

- Python 3.6 ou supérieur
- Chrome ou Chromium installé sur votre système

## Installation

1. Installer les dépendances :
```
pip install -r requirements.txt
```

## Utilisation

1. Lancer le programme :
```
python main.py
```

2. Dans l'interface :
   - Entrez vos mots-clés séparés par des virgules
   - Spécifiez le nombre de pages à scraper
   - Cliquez sur "Démarrer le scraping"
   - Une fois terminé, cliquez sur "Exporter en Excel" pour sauvegarder les résultats

## Notes

- Le programme utilise le mode headless de Chrome (pas de fenêtre visible)
- Les données sont sauvegardées automatiquement dans `localch_data.db`
- L'export Excel inclut un horodatage dans le nom du fichier
