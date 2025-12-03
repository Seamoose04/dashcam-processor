# WebUI

The WebUI is the **interactive front-end** for exploring processed dashcam footage. It presents a clean, searchable interface backed by metadata from the Main Server and media files stored on the Shed NAS. It is designed to be modular, extensible, and easy to expand with new views, filters, or visualizations.

This document outlines the structure, data sources, responsibilities, and future expansion points for the WebUI.

---

# 1. Responsibilities

The WebUI provides:

* A structured interface for browsing archived videos
* Plate search and filtering
* Per-plate timelines and confidence summaries
* Access to de-res’d videos stored on the Shed NAS
* Display of high-resolution plate crops for verification
* Mapping interface using per-frame GPS metadata
* Navigation and organization by date, trip, or location

It does **not** perform any heavy processing, OCR, or GPU work.

---

# 2. Data Sources

The WebUI reads data from two primary locations:

## 2.1 Main Server Database

Used for fast, structured queries such as:

* List of videos
* List of plates per video
* GPS timelines
* Vehicle metadata
* Frame timestamps
* Confidence values

The DB acts as the WebUI’s **authoritative metadata index**; no metadata is pulled from storage devices.

## 2.2 Shed NAS Filesystem

Used for serving all media:

* De-res’d archived videos
* High-res plate crops
* Best-frame thumbnails
* Optional overlay images for maps/timelines

WebUI reads these files directly through mounted storage or a lightweight file server. No metadata is stored or read from the Shed NAS.

---

# 3. Page Structure

The WebUI is organized into core, modular sections that can easily be expanded or replaced.

## 3.1 Home / Dashboard

* Recent trips
* Recently processed plates
* Views sorted by success / confidence / events

## 3.2 Video Browser

* List of all videos (by date or trip)
* Metadata summary (duration, number of plates, GPS availability)
* Click-through to video detail page

## 3.3 Video Detail Page

* Low-resolution video playback
* GPS route map
* Plate list for that video
* Best frames displayed in chronological order

## 3.4 Plate Detail Page

* High-resolution best crop
* All alternate crops
* Timeline showing detection across frames
* GPS location at time of detection
* Confidence breakdown

## 3.5 Map View (Global)

* All plate sightings plotted on a map
* Ability to select date range or plate
* Useful for cross-trip browsing

## 3.6 Search View

* Search by:

  * Plate text
  * Date
  * Confidence threshold
  * Trip
  * GPS region
* Full-text and fuzzy support

---

# 4. API & Backend Design

To remain flexible, the WebUI communicates with the backend through a small, clean API layer.

### 4.1 Metadata Endpoints (Main Server)

* `/videos/list`
* `/videos/<id>/metadata`
* `/plates/<id>/metadata`
* `/search?plate=...`
* `/gps/<video_id>`

All metadata operations are lightweight.

### 4.2 Media Endpoints (Shed NAS)

* `/archive/<video_id>/video_lowres.mp4`
* `/archive/<video_id>/plates/<crop>.jpg`
* `/archive/<video_id>/frames/<frame>.jpg`

These endpoints simply serve static files.

---

# 5. Extensibility Strategy

The WebUI is intentionally structured to support future enhancements with minimal redesign.

Possible additions:

## 5.1 Event Detection

* Hard braking events
* Near-collision detection
* Speed anomalies
* Wiper-based weather estimation

## 5.2 Annotated Timeline

* Multi-track visualization showing plates, speeds, and events

## 5.3 Expanded Filtering

* Confidence heatmaps
* Light/dark segmentation
* Vehicle type filtering

## 5.4 Future UI Modules

* Multi-trip summary comparisons
* Heatmap of high-activity zones
* Trip statistics (distance, avg speed)
* Tagging & notes per video or plate

The current modular design ensures these can all be added without restructuring the core files.

---

# 6. Failure & Recovery Behavior

If the WebUI cannot reach:

## 6.1 Main Server

* Metadata queries return empty/errored states
* UI surfaces empty states until the database is reachable again

## 6.2 Shed NAS

* Videos and images fail gracefully
* UI can substitute placeholder thumbnails

UI is designed to handle partial outages without breaking.

---

# 7. Summary

The WebUI is the **final presentation layer** of the dashcam pipeline. It combines:

* Structured metadata from the Main Server
* Archived media from the Shed NAS
* An extensible interface designed for future growth

It aims to provide an intuitive, fast, and flexible browsing experience for reviewing processed dashcam footage, with a clear separation between metadata retrieval and media serving.
