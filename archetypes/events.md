---
# =============================================================================
# ÉVÉNEMENT - Archétype Hugo pour massalia.events
# =============================================================================
# Ce fichier définit la structure d'un événement culturel à Marseille.
# Tous les champs sont documentés en français pour faciliter la maintenance.
# =============================================================================

# -----------------------------------------------------------------------------
# MÉTADONNÉES HUGO (obligatoires)
# -----------------------------------------------------------------------------

# Titre de la page Hugo - utilisé pour l'URL et le SEO
title: "{{ replace .Name "-" " " | title }}"

# Date de création du fichier - générée automatiquement
date: {{ .Date }}

# Brouillon - true par défaut pour révision avant publication
draft: true

# Date d'expiration Hugo - après cette date, la page n'est plus générée
# Format ISO 8601 - généralement minuit le lendemain de l'événement
expiryDate: {{ .Date }}

# -----------------------------------------------------------------------------
# INFORMATIONS DE L'ÉVÉNEMENT (affichage)
# -----------------------------------------------------------------------------

# Nom de l'événement - affiché sur les cartes et la page de détail
# Exemple: "Vendre la mèche"
name: ""

# URL de l'image principale (hero image)
# Chemin relatif depuis /static/ ou URL absolue
# Laisser vide si aucune image disponible
image: ""

# URL source de l'événement - lien vers le site original
# Exemple: "https://www.kelemenis.fr/fr/les-spectacles/1648/vendre-la-meche"
eventURL: ""

# Heure de début de l'événement - format 24h
# Exemple: "19:00"
startTime: ""

# Description courte de l'événement (SEO et aperçu)
# Limite recommandée: 160 caractères
description: ""

# -----------------------------------------------------------------------------
# TAXONOMIES (classification)
# -----------------------------------------------------------------------------

# Catégorie de l'événement
# Valeurs: danse, musique, theatre, art, communaute
categories:
  - ""

# Lieu de l'événement - slug du lieu
# Valeurs: klap, la-friche, la-criee, chateau-de-servieres, notre-dame-de-la-garde
locations:
  - ""

# Date au format français pour l'affichage
# Format: "jour-DD-mois" en minuscules
# Exemple: "samedi-26-janvier"
dates:
  - ""

# Tags libres pour recherche
# Exemples: "danse contemporaine", "gratuit"
tags: []

# -----------------------------------------------------------------------------
# ÉVÉNEMENTS MULTI-JOURS
# -----------------------------------------------------------------------------
# Pour un festival de 3 jours, créer 3 fichiers avec le même eventGroupId:
#   /events/2026/02/06/festival-jour-1.fr.md (dayOf: "Jour 1 sur 3")
#   /events/2026/02/07/festival-jour-2.fr.md (dayOf: "Jour 2 sur 3")
#   /events/2026/02/08/festival-jour-3.fr.md (dayOf: "Jour 3 sur 3")
# Chaque jour expire indépendamment via son propre expiryDate.

# Identifiant de groupe pour événements sur plusieurs jours
# Même valeur pour toutes les pages d'un même événement
# Format suggéré: "nom-evenement-annee" (ex: "festival-marseille-2026")
# Laisser vide pour événement sur un seul jour
eventGroupId: ""

# Numéro du jour pour événements multi-jours
# Format: "Jour X sur Y"
# Exemple: "Jour 2 sur 5"
dayOf: ""

# -----------------------------------------------------------------------------
# CYCLE DE VIE
# -----------------------------------------------------------------------------

# Événement expiré - true si l'événement est passé
expired: false

# -----------------------------------------------------------------------------
# TRAÇABILITÉ (crawler)
# -----------------------------------------------------------------------------

# Identifiant unique de la source
# Format: nom-du-site:identifiant-unique
# Exemple: "kelemenis:1648"
sourceId: ""

# Date du dernier crawl de cet événement
lastCrawled: {{ .Date }}

---

<!--
CONTENU DE L'ÉVÉNEMENT
Rédigez ici la description détaillée en français.
-->
