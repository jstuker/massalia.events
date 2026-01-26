---
title: "Événements"
description: "Tous les événements culturels à Marseille : danse, musique, théâtre, art et communauté."

# Cascade defaults for all events in this section
cascade:
  # Display settings for event pages
  showDate: true
  showReadingTime: false
  showWordCount: false
  showAuthor: false
---

Bienvenue sur l'agenda culturel de Marseille. Découvrez les événements de la semaine : spectacles de danse, concerts, pièces de théâtre, expositions et activités communautaires.

## Structure des événements

Les événements sont organisés par date dans une structure `/events/YYYY/MM/DD/`:

```
/content/events/
├── _index.fr.md
├── 2026/
│   └── 01/
│       ├── 26/
│       │   └── vendre-la-meche.fr.md
│       ├── 27/
│       │   ├── concert-la-friche.fr.md
│       │   └── theatre-la-criee.fr.md
│       └── 29/
│           └── exposition-la-releve.fr.md
```

Pour créer un nouvel événement:
```bash
hugo new events/2026/01/30/nom-evenement.fr.md --kind events
```
