+++
title = "Product specification of massalia.events"
author = "Jürg Stuker"
date = "25 Jan 2025"
version = "1.0"
+++

Create an event aggregator for the city of Marseille: an event calendar. The goal of this application is to visit on a regular basis multiple websites that contain events that are happening in Marseille, then select them according to criteria, whether I want to include them or not in the event calendar we are building.

And if they adhere to the selection criteria look if the same event already exists and if not classify the event using a taxonomy and integrated in the content management system. In Hugo CMS, blog posts are used as functionality to persist the events, in the following document I will only speak about event or events.

As a result we display selected events on the event calendar that are equivalent to events found on event websites on the Internet. The focus of the event shown is one week from now. So you import everything that adheres to the selection criteria, but you only show seven days, starting from today. All the other events are hidden in the system and not shown to the user.

The user interface language for the whole application is French. So all the labels, content, whatever there is, it's in French language.

---

## Taxonomy

Taxonomy or: how these events are classified. I need a taxonomy that helps display the events to the users that are only valid one week from now. So there will be a view from today plus 6 days. Past events should be marked as past events in the repository using the expired metadata, so they're not being built into the website. The requirements for the taxonomy are still to be defined. But in minimum its everything we need to build the user interface. Read the taxonomy file in Hugo for details. Here, five examples.

### Example 1: Dance Event

| Field | Value |
|-------|-------|
| taxonomy.categories | Dance |
| taxonomy.locations | KLAP Maison pour la danse |
| metadata name | Vendre la mèche |
| taxonomy.dates | Samedi 24 janvier |
| metadata startTime | 19:00 |
| metadata URL | https://www.kelemenis.fr/fr/les-spectacles/1648/vendre-la-meche |

### Example 2: Music Event

| Field | Value |
|-------|-------|
| taxonomy.categories | Music |
| taxonomy.locations | La Friche |
| metadata name | Bashkka + 88barclub Aka Sad.H (Massilia Techno Milita) |
| taxonomy.dates | Vendredi 6 février |
| metadata startTime | 23:00 |
| metadata URL | https://shotgun.live/fr/events/bashkka-88-bar-club-aka-sad-h-massilia-techno-milita |

### Example 3: Theatre Event

| Field | Value |
|-------|-------|
| taxonomy.categories | Théâtre |
| taxonomy.locations | La Criée |
| metadata name | Les Généreux / El Ajouad |
| taxonomy.dates | Mercredi 4 février |
| metadata startTime | 15:00 |
| metadata URL | https://theatre-lacriee.com/programmation/evenements/les-genereux-el-ajouad |

### Example 4: Art Event

| Field | Value |
|-------|-------|
| taxonomy.categories | Art |
| taxonomy.locations | Galerie Château de Servières |
| metadata name | Exposition collective La Relève |
| taxonomy.dates | Mercredi 28 janvier |
| metadata startTime | 14:00 |
| metadata URL | https://www.sortiramarseille.fr/agenda/exposition-collective-la-releve-8/ |

### Example 5: Community Event

| Field | Value |
|-------|-------|
| taxonomy.categories | Community |
| taxonomy.locations | Notre-Dame de la Garde |
| metadata name | L'opération « Love ta Bonne Mère » |
| taxonomy.dates | Mercredi 11 février |
| metadata startTime | 14:00 |
| metadata URL | https://madeinmarseille.net/environnement/153752-love-ta-bonne-mere-declarer-votre-amour-a-marseille-en-la-nettoyant/ |

---

## User Interface

### Landing page / overview

The user interface should be one page and when you load the page you see all the events happening today.

- There is a navigation point that says "Today" in the center
- Below this navigation point, you have cards for all the events happening today
- Close to the navigation point "Today", there is a navigation point with the 6 days to follow

If today is Monday, the second navigation point is Tuesday, then Wednesday, and so on. If I click on this page reloads and shows event cards for the next day. This is the only functionality at the moment.

### Event card

An event card is an overview created out of the event detail that shows the most important features of an event on which the user can click and then sees on the details page all the details about the event. Now top of my head, the most important elements in the card are:

- The category of the event (`taxonomy.categories`)
- The location of the event (`taxonomy.locations`)
- The name of the event (`metadata name` in front matter)
- The date of the event (`taxonomy.dates`)
- The start time of the event (`metadata startTime` in front matter)
- The URL (`metadata URL` to the event details in front matter)

### Event detail

When a user clicks on an event card, it navigates to the event detail page. All the information from the card is repeated there, making it immediately visible that I'm in the right place. In addition, there is additional information about the event, such as:

- A short description of the event
- A picture if anything is found
- URL to the event details where the event was found

### Search functionality

Use the included search functionality in Hugo CMS to search through single events. But only look for events that are not expired yet: From today until day 7. So in the time span from today until a week from now. Basically, you have to search through the daily archives of today, plus next day, plus next day, so you totally have a 7-day outlook.

### Technical requirements

The user interface is built with Hugo using the Blowfish template. So all the pages are statically rendered for maximum performance. I want you to check if the application works on three viewports:

1. Mobile
2. Tablet
3. Desktop

And I want you to build an application that is very performant. The goal is to have a Google performance score of 100.

---

## Data persistence

To store the events, we use the blog post functionality of the Hugo content management system. So the detailed page of an event is the one post including all the taxonomy we need to gather information together to build daily archives, category archives, etc. These single events are stored in Hugo using a folder structure reflecting the event date.

If an event is detected to happen on multiple days, create multiple blog events. Try to take the same information and create multiple blog event pages so it shows up in multiple event overviews.

Keep the past events as pages in the content repository of Hugo, but don't display them anymore to the user. So use this metadata that helps mark expired pages so it's not being built into the user interface anymore.

---

## Crawling the events

It's a two-step process:

1. **Crawling**: The crawler goes out to the webpage and tries to look for all possible events to be included in the application.
2. **Selection**: The crawler then looks at the content of the event and selects if the event is selected to be integrated into the website at all (yes or no).

You find the selection criteria for events and event sites to crawl in local files.

### Crawling

The crawling process is being started manually on a local computer. The results of the process are being integrated in the CMS data structure and then uploaded to GitHub for publication.

One of the core functionalities is the functionality to visit web pages to get the event data to be included in the system. This process we call crawling, and the software component that does this is a crawler. The crawler has a list of pages to be visited which it then visits, looks for events there, tries to classify them according to event criteria or according to selection criteria, and then brings the data back to the system so it can be used to create event pages.

Part of the crawling process is not only to get text information, but also collect one hero image per event that can be used on the detail page for illustration purposes. Download this image to the local repository and do a calculation that best fits on the Blowfish template, so we have a standardized format that can be quickly loaded in the user interface.

### Selecting

When the crawler visits the source of event data, it classifies the event using a document that helps decide about wanted and unwanted events. This document is continuously refined to make the crawler more selective about the events we want to gather.

Part of the selection process is that events that have been selected (i.e., are positive in regard to the selection criteria) are then being classified. Using the taxonomy already mentioned, there are labels attached that can be later used to select and sort the data.

Part of the selection process is also to detect duplicates. The goal is to never create a page that is a duplicate of an existing page. So you may find the same event on multiple websites. You have about the same description, that is not necessarily identical, on different URLs. Your task is to find out if it's about the same event. A hint to this could be:

- The same booking link
- The same date-time-location combination

If it's likely that it's the same event only included once, you may update the existing event using additional information from the second event you found.

---

## Administrative features

### Logging

With the goal of detecting errors in the application, create an event log to which only the administrator has access. Use a functionality to switch on and off this event log using the different event levels (e.g., critical, warning, info). Go and look what like, so an administrator can debug the application.
