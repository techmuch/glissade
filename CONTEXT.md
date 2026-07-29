# Glissade — Domain Model & Glossary

This document records the ubiquitous language and canonical domain terminology of Glissade. It contains domain definitions and is devoid of implementation details.

## Terms

### Project
A workspace directory containing a `decks/` folder. A project may also contain a `glissade.toml` configuration file, a `.glissade/` state directory, a `themes.json` override file, an `AGENTS.md` guide, and a `glissade.schema.json` editor validation file.

### Deck
A presentation document written in JSON format. A deck consists of top-level metadata (such as `title`, `format` version, and required `glissade` version) and an ordered array of `slides`.

### Slide
A single presentation screen within a deck. Each slide defines a `layout` (e.g. `title`, `media-right`, `grid`), speaker `notes`, and optional text and media elements.

### Scaffold
The set of starter project files initialized by `glissade init` into a project directory.

### Live Notes
Presenter notes recorded on-the-fly during a presentation session via the phone remote, synced in real-time across connected views, and persisted to the project's state directory.
