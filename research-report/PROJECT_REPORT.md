---
title: |
  CIA World Factbook Archive\
  \vspace{0.5cm}
  \large A Comprehensive Digital Preservation and Intelligence Analytics Platform
author: Milan Milkovich, MLIS
date: March 5, 2026
abstract: |
  This report documents the design, construction, and deployment of the CIA World Factbook Archive --- a research platform that preserves, structures, and visualizes 36 years of the Central Intelligence Agency's *World Factbook* (1990--2025).
  The project ingests raw source material spanning six distinct text formats, five HTML layouts, and modern JSON feeds, normalizes over one million data points across 281 geopolitical entities into a unified SQLite database, and exposes the result through a full-featured web application with interactive analytics, geospatial visualization, and a custom dashboard builder.
  The archive represents the only publicly available system that makes every edition of the CIA World Factbook queryable, comparable, and downloadable in structured form.

  \vspace{0.3cm}
  \noindent\textbf{Key Metrics:} 281 Entities | 36 Editions | 9,536 Country-Year Records | 1,071,603 Data Points | 1,775,588 Structured Sub-Values

  \noindent\textbf{Live URL:} \url{https://worldfactbookarchive.org}

  \noindent\textbf{Source Code:} \url{https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025}

documentclass: report
geometry: margin=1in
fontsize: 11pt
numbersections: true
toc: true
toc-depth: 3
header-includes:
  - \usepackage{booktabs}
  - \usepackage{longtable}
  - \usepackage{array}
  - \usepackage{graphicx}
  - \usepackage{hyperref}
  - \usepackage{fancyhdr}
  - \usepackage{xcolor}
  - \usepackage{float}
  - \usepackage{titlesec}
  - "\\titleformat{\\chapter}[hang]{\\LARGE\\bfseries}{\\thechapter.}{0.8em}{}"
  - "\\titlespacing*{\\chapter}{0pt}{0pt}{10pt}"
  - "\\titleformat{\\section}{\\Large\\bfseries}{\\thesection}{0.7em}{}"
  - "\\titlespacing*{\\section}{0pt}{16pt}{6pt}"
  - "\\titleformat{\\subsection}{\\large\\bfseries}{\\thesubsection}{0.6em}{}"
  - "\\titlespacing*{\\subsection}{0pt}{10pt}{4pt}"
  - "\\titleformat{\\subsubsection}{\\normalsize\\bfseries}{\\thesubsubsection}{0.5em}{}"
  - "\\titlespacing*{\\subsubsection}{0pt}{8pt}{3pt}"
  - \usepackage{tikz}
  - \usetikzlibrary{arrows.meta, positioning, shapes.geometric, fit, calc, backgrounds, decorations.pathreplacing}
  - \definecolor{ciaBlue}{HTML}{2D72D2}
  - \definecolor{ciaDark}{HTML}{1C2127}
  - \definecolor{ciaAccent}{HTML}{48AFF0}
  - \definecolor{ciaSurface}{HTML}{252A31}
  - \definecolor{ciaGreen}{HTML}{29A634}
  - \definecolor{ciaGold}{HTML}{F0B726}
  - \definecolor{ciaRed}{HTML}{CD4246}
  - \hypersetup{colorlinks=true, linkcolor=ciaBlue, urlcolor=ciaBlue, citecolor=ciaBlue}
  - \pagestyle{fancy}
  - \fancyhead[L]{\small CIA World Factbook Archive}
  - \fancyhead[R]{\small Project Report --- March 5, 2026}
  - \fancyfoot[C]{\thepage}
  - \renewcommand{\headrulewidth}{0.4pt}
  - \setlength{\parskip}{0.5em}
  - \setlength{\parindent}{0pt}
---

\newpage

# Genesis and Vision

## Background

The CIA *World Factbook* is the United States Intelligence Community's flagship open-source reference on every country and territory in the world.
Published annually since 1962 and made freely available to the public since 1971, it has served as the de facto standard reference for geopolitical, demographic, economic, and military data used by government analysts, journalists, researchers, and educators worldwide.

Despite its importance, no centralized archive existed that preserved every edition in structured, machine-readable form.
Older editions published as plain text files in the 1990s were scattered across university FTP mirrors and the Internet Archive.
HTML editions from the 2000s and 2010s were accessible only through the Wayback Machine, often with broken links and inconsistent formatting.
The CIA itself maintained only the current edition on its website, with each new release overwriting the previous one.

On **February 4, 2026**, the CIA discontinued publication of the World Factbook entirely, making the preservation of historical editions an urgent priority.

## The Problem

Without a structured archive, researchers faced several critical barriers:

1. **No longitudinal analysis.** Comparing a country's GDP trajectory or military spending over two decades required manually downloading and parsing dozens of files in incompatible formats.
2. **Format fragmentation.** The Factbook changed its publication format at least 12 times between 1990 and 2025, from pipe-delimited text to nested HTML to structured JSON.
3. **Entity instability.** Countries dissolved (Soviet Union, Yugoslavia), merged (Germany), renamed (Swaziland to Eswatini), and changed codes across editions.
4. **Field vocabulary drift.** The CIA renamed, merged, and restructured hundreds of data fields over the decades --- "Total area" became "Area," "National product" became "Real GDP (purchasing power parity)," and so on.
5. **Disappearing sources.** University mirrors went offline, the Wayback Machine returned incomplete captures, and the CIA's own site offered no historical access.

## Vision

The CIA World Factbook Archive was conceived as a comprehensive digital preservation and analytics platform with three objectives:

1. **Preserve** every edition of the World Factbook from 1990 through its final 2025 publication in a single, structured, queryable database.
2. **Normalize** the data across format changes, field renames, and entity reorganizations so that any indicator can be compared across any country and any year.
3. **Visualize** the data through an interactive web application that makes 36 years of intelligence-grade geopolitical data accessible to researchers, students, journalists, and the general public.

## Development Timeline

The project was built in an intensive 14-day development sprint, producing 205 commits across two repositories.
The following timeline is derived from the project's git history:

| Date | Milestone |
|------|-----------|
| Feb 16, 2026 | Initial release: ETL pipeline, SQLite database, GitHub Pages static site |
| Feb 16 | Full web application committed (FastAPI + Jinja2 + Mapbox GL JS) |
| Feb 18--19 | Migration from Plotly.js to Mapbox GL JS; v2 data drop (1996 repairs, analytics explorer) |
| Feb 20 | MIT license adopted; visitor analytics system added |
| Feb 22 | Webapp split to private repository; terrain/fog rendering; custom domain setup |
| Feb 23 | 7-layer security system; header navigation redesign; Intelligence Atlas; political dashboard; worldfactbookarchive.org launched |
| Feb 24 | Mobile responsiveness pass; accessibility compliance; analytics disk cache |
| Feb 25 | Atlas feature pack (10 tools); political drill-down; sitemap expansion |
| Feb 26 | Structured field parsing; StarDict dictionary builder; strategic intelligence layers |
| Feb 27 | Encoding corruption repair; v3.0 release |
| Feb 28 | v3.1 release (pipe delimiters, SourceFragment provenance, 18 new parsers); v3.2 (StarDict dictionaries, encoding repair); CSI Studies in Intelligence integration; COCOM boundaries |
| Mar 1 | Capital markers; UI polish; atlas performance; source attribution tags |
| Mar 2 | Foreign Leaders dashboards; Development and Inequality analysis; custom Dashboard Builder; rate limiting hardening |
| Mar 3 | v3.3 release (IsComputed flag, case-sensitive field mappings, FIPS/ISO library fix); webapp FieldValues migration complete |
| Mar 4 | v3.4 release (pipe-after-colon parser fix, +164,494 sub-values); research report updated |

## Repository Structure

The project is organized across two repositories:

- **Public archive** (`CIA-World-Factbooks-Archive-1990-2025`): ETL pipeline, raw data, SQLite database, documentation, GitHub Pages landing site. 70+ commits.
- **Private webapp** (`cia-factbook-webapp`): FastAPI application, templates, static assets, deployment configuration. 150+ commits.

## System Architecture Overview

Figure 1 presents the end-to-end system architecture, from raw CIA source material through the ETL pipeline to the production web application.

\begin{figure}[H]
\centering
\begin{tikzpicture}[
    node distance=0.8cm and 1.0cm,
    block/.style={rectangle, draw=ciaBlue, fill=ciaBlue!8, text width=2.8cm, minimum height=1.0cm, align=center, font=\small, rounded corners=3pt, line width=0.8pt},
    srcblock/.style={rectangle, draw=ciaGold, fill=ciaGold!8, text width=2.4cm, minimum height=0.9cm, align=center, font=\footnotesize, rounded corners=3pt, line width=0.8pt},
    dbblock/.style={cylinder, draw=ciaGreen, fill=ciaGreen!8, shape border rotate=90, aspect=0.25, minimum height=1.2cm, minimum width=2.8cm, align=center, font=\small, line width=0.8pt},
    webapp/.style={rectangle, draw=ciaBlue!80, fill=ciaBlue!8, text width=10cm, minimum height=1.0cm, align=center, font=\small, rounded corners=3pt, line width=0.8pt},
    infra/.style={rectangle, draw=ciaRed!80, fill=ciaRed!8, text width=2.8cm, minimum height=1.0cm, align=center, font=\small, rounded corners=3pt, line width=0.8pt},
    arr/.style={-{Stealth[length=2.5mm]}, line width=0.7pt, color=ciaBlue!70},
    label/.style={font=\scriptsize\itshape, text=black!60},
]

% Source row
\node[srcblock] (txt) {Plain Text\\1990--2001};
\node[srcblock, right=0.8cm of txt] (html) {HTML\\2002--2020};
\node[srcblock, right=0.8cm of html] (json) {JSON\\2021--2025};

% ETL row
\node[block, below=1.0cm of html] (parse) {Format-Specific\\Parsers (11)};
\node[block, right=1.0cm of parse] (canon) {Canonicalization\\1,132 $\rightarrow$ 416};
\node[block, left=1.0cm of parse] (detect) {Format\\Detection};

% Database
\node[dbblock, below=1.0cm of parse] (db) {SQLite Database\\factbook.db (656 MB)};

% Webapp row - single wide block
\node[webapp, below=1.2cm of db] (app) {\textbf{Web Application:} FastAPI + Jinja2 \textbar{} ECharts + Mapbox GL JS \textbar{} 102 Indicators};

% Infrastructure row - three separate blocks with proper spacing
\node[infra, below=1.2cm of app] (fly) {Fly.io + Docker\\Production};
\node[block, left=1.5cm of fly] (cloud) {Cloudflare\\CDN + WAF};
\node[block, right=1.5cm of fly] (sec) {7-Layer\\Security};

% Users
\node[below=0.8cm of fly, font=\small\bfseries] (users) {worldfactbookarchive.org};

% Arrows - sources to ETL
\draw[arr] (txt.south) -- ++(0,-0.3) -| (detect.north);
\draw[arr] (html.south) -- (parse.north);
\draw[arr] (json.south) -- ++(0,-0.3) -| (canon.north);

% ETL flow
\draw[arr] (detect) -- (parse);
\draw[arr] (parse) -- (canon);

% To database
\draw[arr] (canon.south) -- ++(0,-0.3) -| (db.east);
\draw[arr] (detect.south) -- ++(0,-0.3) -| (db.west);

% DB to webapp
\draw[arr] (db) -- (app);

% Webapp to production
\draw[arr] (app) -- (fly);

% Infrastructure
\draw[arr] (cloud) -- (fly);
\draw[arr] (sec) -- (fly);
\draw[arr] (fly) -- (users);

% Labels
\node[label, above=0.05cm of txt.north west, anchor=south west] {6 formats};
\node[label, above=0.05cm of html.north west, anchor=south west] {5 layouts};
\node[label, above=0.05cm of json.north west, anchor=south west] {structured};

\end{tikzpicture}
\caption{System Architecture --- from CIA source material to production web application.}
\label{fig:architecture}
\end{figure}

\newpage

# Data Acquisition and Sources

## Source Inventory

The 36 years of Factbook data were obtained from three distinct source channels, each requiring its own ingestion strategy.

### Plain Text Editions (1990--2001)

The earliest machine-readable Factbook editions were distributed as plain text files through Project Gutenberg and university FTP mirrors, most notably the University of Missouri archive.
These files used six different formatting conventions over the course of a single decade:

| Years | Format Name | Structure | Source |
|-------|-------------|-----------|--------|
| 1990 | `old` | `Country: Name` / `- Section` / `Field: value` | Project Gutenberg |
| 1991 | `tagged` | `_@_Name` / `_*_Section` / `_#_Field: value` | University of Missouri |
| 1992 | `colon` | `:Country Section` / Field on next line | University of Missouri |
| 1993--1994 | `asterisk` | `*Name, Section` / indented `Field:\n  value` | University of Missouri |
| 1995--2000 | `atsign` | `@Name:Section` / `Field: value` | University of Missouri |
| 2001 | `equals` | `@Name` / `Name Section` / `Field: value` | University of Missouri |

Each format change reflected internal reorganizations at the CIA's Directorate of Intelligence, which maintained the Factbook.

### HTML Editions (2002--2020)

From 2002 onward, the CIA published the Factbook as HTML pages on `cia.gov`.
These were retrieved from the Internet Archive's Wayback Machine as ZIP archives, each containing the full set of country pages for that year.

The HTML structure changed five times over this period:

| Years | HTML Pattern | Key Markers |
|-------|-------------|-------------|
| 2000 | Classic | Named anchors, `<b>Field:</b>` |
| 2001--2008 | Table | `<td class="FieldLabel">`, `<a name="SectionID">` |
| 2009--2014 | CollapsiblePanel | `<div class="CollapsiblePanel">`, `<span class="category">` |
| 2015--2017 | ExpandCollapse | `<h2 class="question" sectiontitle="...">` |
| 2018--2020 | Modern | `<div id="field-anchor-*">`, `<div class="category_data subfield">` |

### JSON Editions (2021--2025)

Beginning in 2021, the CIA published structured JSON data through its website.
These were obtained via the `factbook-json-cache` repository, which maintained weekly snapshots of the CIA's JSON feed.
Year-specific snapshots were extracted using git history, checking out the last commit before each year's cutoff date.

The final snapshot (2025) was captured before the CIA's February 4, 2026 discontinuation announcement.

## Data Format Evolution

Figure 2 illustrates the timeline of format changes across the 36-year publication history.
Each color band represents a distinct parsing strategy required by the ETL pipeline.

\begin{figure}[H]
\centering
\begin{tikzpicture}[
    x=0.36cm,
    yearblock/.style={minimum height=0.55cm, anchor=west, font=\tiny\bfseries, text=white, inner sep=2pt, rounded corners=1.5pt},
]

% Timeline axis
\draw[line width=0.6pt, color=black!40] (0,0) -- (36,0);
\foreach \y/\lab in {0/1990, 5/1995, 10/2000, 15/2005, 20/2010, 25/2015, 30/2020, 35/2025} {
    \draw[line width=0.4pt, color=black!40] (\y, -0.15) -- (\y, 0.15);
    \node[below, font=\tiny, color=black!60] at (\y, -0.25) {\lab};
}

% Row 3: Text formats (top row, y=2.2)
\node[font=\scriptsize\bfseries, anchor=east, color=black!70] at (-0.5, 2.2) {Text};
\node[yearblock, fill=ciaRed!80, text width=0.36cm] at (0, 2.2) {};
\node[yearblock, fill=ciaGold!80, text width=0.36cm] at (1, 2.2) {};
\node[yearblock, fill=ciaGreen!70, text width=0.36cm] at (2, 2.2) {};
\node[yearblock, fill=ciaBlue!70, text width=0.72cm] at (3, 2.2) {};
\node[yearblock, fill=violet!60, text width=2.16cm] at (5, 2.2) {};
\node[yearblock, fill=orange!60, text width=0.36cm] at (11, 2.2) {};

% Row 2: HTML formats (middle row, y=1.2)
\node[font=\scriptsize\bfseries, anchor=east, color=black!70] at (-0.5, 1.2) {HTML};
\node[yearblock, fill=teal!50, text width=0.36cm] at (10, 1.2) {};
\node[yearblock, fill=teal!60, text width=2.52cm] at (11, 1.2) {};
\node[yearblock, fill=cyan!40, text width=2.16cm] at (19, 1.2) {};
\node[yearblock, fill=ciaBlue!50, text width=1.08cm] at (25, 1.2) {};
\node[yearblock, fill=ciaBlue!70, text width=1.08cm] at (28, 1.2) {};

% Row 1: JSON format (bottom row, y=0.5)
\node[font=\scriptsize\bfseries, anchor=east, color=black!70] at (-0.5, 0.5) {JSON};
\node[yearblock, fill=ciaGreen!60, text width=1.80cm] at (31, 0.5) {};

% Text format labels (above row 3)
\node[font=\tiny, color=black!55, anchor=south] at (0.18, 2.55) {Old};
\node[font=\tiny, color=black!55, anchor=south] at (1.18, 2.55) {Tag};
\node[font=\tiny, color=black!55, anchor=south] at (2.18, 2.55) {Col};
\node[font=\tiny, color=black!55, anchor=south] at (3.36, 2.55) {Ast};
\node[font=\tiny, color=black!55, anchor=south] at (6.08, 2.55) {AtSign};
\node[font=\tiny, color=black!55, anchor=south] at (11.18, 2.55) {Eq};

% HTML format labels (above row 2)
\node[font=\tiny, color=black!55, anchor=south] at (10.18, 1.55) {Cls};
\node[font=\tiny, color=black!55, anchor=south] at (12.26, 1.55) {Table};
\node[font=\tiny, color=black!55, anchor=south] at (20.08, 1.55) {Collapsible};
\node[font=\tiny, color=black!55, anchor=south] at (25.54, 1.55) {Expand};
\node[font=\tiny, color=black!55, anchor=south] at (28.54, 1.55) {Modern};

% JSON label (below row 1)
\node[font=\tiny, color=black!55, anchor=north] at (31.9, 0.15) {Structured};

% Discontinuation marker
\draw[line width=1.2pt, color=ciaRed] (35.5, -0.3) -- (35.5, 2.8);
\node[font=\tiny\bfseries, color=ciaRed, rotate=90, anchor=south] at (35.8, 0.5) {Disc. 2026};

% Row separator lines (faint)
\draw[line width=0.3pt, color=black!15, dashed] (0, 0.85) -- (35.5, 0.85);
\draw[line width=0.3pt, color=black!15, dashed] (0, 1.75) -- (35.5, 1.75);

\end{tikzpicture}
\caption{Data format evolution across 36 years of CIA World Factbook publication (1990--2025). Text, HTML, and JSON formats are shown on separate rows; each colored segment represents a distinct parsing strategy required by the ETL pipeline.}
\label{fig:timeline}
\end{figure}

## Challenges

### Encoding Drift

Text files from the 1990s used a mixture of ASCII, Latin-1, and Windows-1252 encodings.
Characters such as accented vowels, em-dashes, and special symbols were frequently corrupted during format conversions.
A dedicated repair script (`scripts/repair_encoding_fffd.py`) was developed to detect and correct Unicode replacement characters (`U+FFFD`) in the database.

### Entity Name Changes

Over 36 years, dozens of entities changed names, codes, or political status:

- The Soviet Union dissolved into 15 successor states (1991)
- Yugoslavia fragmented into seven countries (1991--2008)
- Swaziland became Eswatini (2018)
- Czechoslovakia split into Czech Republic and Slovakia (1993)
- East Timor became Timor-Leste (2002)
- Burma became Myanmar in CIA usage

The `MasterCountries` table maps all historical name variants to a single canonical identity, enabling cross-year comparisons.

### Field Restructuring

The CIA restructured its field taxonomy repeatedly.
A field called "National product" in 1990 became "GDP" in the mid-1990s, then "GDP (purchasing power parity)" in the 2000s, and finally "Real GDP (purchasing power parity)" in recent editions.
The canonicalization layer (described in Part III) maps all 1,132 field name variants to 416 canonical names.

\newpage

# ETL Pipeline and Parsing Methodology

## Pipeline Overview

The Extract-Transform-Load pipeline converts raw Factbook source material into a normalized SQLite database through the following stages.
Figure 4 illustrates the complete data flow.

\begin{figure}[H]
\centering
\begin{tikzpicture}[
    node distance=0.5cm and 0.6cm,
    proc/.style={rectangle, draw=ciaBlue, fill=ciaBlue!8, text width=2.2cm, minimum height=1.0cm, align=center, font=\footnotesize, rounded corners=3pt, line width=0.7pt},
    src/.style={rectangle, draw=ciaGold, fill=ciaGold!10, text width=1.6cm, minimum height=0.7cm, align=center, font=\tiny, rounded corners=2pt, line width=0.6pt},
    db/.style={cylinder, draw=ciaGreen, fill=ciaGreen!10, shape border rotate=90, aspect=0.3, minimum height=1.0cm, minimum width=2.2cm, align=center, font=\footnotesize, line width=0.7pt},
    arr/.style={-{Stealth[length=2mm]}, line width=0.6pt, color=ciaBlue!60},
    note/.style={font=\tiny\itshape, color=black!50},
]

% Sources
\node[src] (s1) {Text Files\\(1990--2001)};
\node[src, right=0.3cm of s1] (s2) {HTML Pages\\(2002--2020)};
\node[src, right=0.3cm of s2] (s3) {JSON Feed\\(2021--2025)};

% Processing steps
\node[proc, below=0.8cm of s1] (detect) {Format\\Detection};
\node[proc, right=0.6cm of detect] (parse) {11 Format-\\Specific Parsers};
\node[proc, right=0.6cm of parse] (extract) {Field + Value\\Extraction};

% Second row
\node[proc, below=0.8cm of extract] (subfield) {Sub-field\\Parsing};
\node[proc, left=0.6cm of subfield] (canon) {Canonicalization\\1,132 $\rightarrow$ 416};
\node[proc, left=0.6cm of canon] (fts) {FTS5 Index\\Construction};

% Database
\node[db, below=0.8cm of canon] (database) {factbook.db\\656 MB};

% Source arrows
\draw[arr] (s1.south) -- (detect.north);
\draw[arr] (s2.south) -- (parse.north);
\draw[arr] (s3.south) -- (extract.north);

% Flow arrows (top row)
\draw[arr] (detect) -- (parse);
\draw[arr] (parse) -- (extract);

% Flow arrows (down and back)
\draw[arr] (extract) -- (subfield);
\draw[arr] (subfield) -- (canon);
\draw[arr] (canon) -- (fts);

% To database
\draw[arr] (fts.south) -- ++(0,-0.3) -| (database.north west);
\draw[arr] (canon.south) -- (database.north);
\draw[arr] (subfield.south) -- ++(0,-0.3) -| (database.north east);

% Notes
\node[note, below=0.05cm of detect.south east, anchor=north east] {year-based};
\node[note, below=0.05cm of parse.south east, anchor=north east] {6 text + 5 HTML};
\node[note, below=0.05cm of subfield.south west, anchor=north west] {pipe-delimited};
\node[note, below=0.05cm of canon.south west, anchor=north west] {7 mapping rules};
\node[note, below=0.05cm of fts.south west, anchor=north west] {full-text search};

\end{tikzpicture}
\caption{ETL pipeline data flow. Raw source material passes through format detection, parsing, sub-field extraction, canonicalization, and indexing before reaching the production SQLite database.}
\label{fig:etl}
\end{figure}

## Text Format Parsers

Six parsers handle the plain text editions from 1990 through 2001.
Each parser implements the same interface: accept raw text, return a list of `(country, section, field_name, value)` tuples.

### Old Format (1990)

The earliest format uses a simple `Country:` header followed by dash-prefixed section names and inline `Field: value` pairs.

```
Country:  Afghanistan
- Geography
Total area: 647,500 km2
- People
Population: 15,862,293 (July 1990)
```

The parser detects `Country:` lines, splits sections on `- SectionName`, and extracts inline fields using the `extract_inline_fields()` function.

### Tagged Format (1991)

A marker-based format using three-character prefixes to denote structural elements:

```
_@_Afghanistan
_*_Geography
_#_Total area: 647,500 km2
_*_People
_#_Population: 16,450,304
```

- `_@_` = Country name
- `_*_` = Section header
- `_#_` = Field entry

Continuation lines (without markers) are appended to the previous field's value.

### Colon Format (1992)

Section headers are prefixed with a colon followed by the country name and section, with field values on indented continuation lines:

```
:Afghanistan Geography
Total area:
    647,500 km2
:Afghanistan People
Population:
    16,095,664
```

The parser uses `extract_indented_fields()` to associate indented lines with their parent field names.

### Asterisk Format (1993--1994)

This format introduced hierarchical sub-fields with indentation-based nesting:

```
*Afghanistan, Geography
Location:
  South Asia, between Iran and Pakistan
Area:
 total area:
  647,500 km2
 land area:
  647,500 km2
```

In 1994, the CIA restructured its internal database, causing sub-fields to appear at column 0 instead of indented.
The parser distinguishes parent fields from sub-fields using a capitalization convention: parent field names start with a capital letter (`Area`), while sub-field names are lowercase (`total area`, `land area`).

### At-Sign Format (1995--2000)

The longest-lived text format, with two sub-variants:

**Standard variant** (1995, 1997--1998): `@CountryName:SectionName` with inline and indented fields.

```
@Afghanistan:Geography
 Location: Southern Asia, north of Pakistan
 Area:
 total area: 647,500 sq km
```

**Bare variant** (1996, 1999): `@CountryName` as a standalone line, followed by bare section headers.

The parser uses `extract_mixed_fields()` to handle both inline `Field: value` patterns and indented sub-field structures.

### Equals Format (2001)

A transitional format used only for the 2001 edition, where the HTML version was incomplete:

```
@Afghanistan

Afghanistan    Introduction
Background: Afghanistan has been...

Afghanistan    Geography
Location: Southern Asia
```

Country markers appear as `@CountryName`, followed by `CountryName    SectionName` (separated by multiple spaces).

## HTML Parsers

Five HTML parsers handle the web editions from 2000 through 2020, each adapted to the CIA's evolving web design.

### Classic HTML (2000)

Uses named anchors (`<a name="Geo">`) for sections and bold tags (`<b>Field:</b>`) for field labels.
Values appear as inline text after the closing bold tag.

### Table HTML (2001--2008)

Section anchors remain, but fields are organized in HTML tables with `<td class="FieldLabel">` containing field names and sibling `<td>` elements containing values.

### CollapsiblePanel HTML (2009--2014)

Sections are wrapped in `<div class="CollapsiblePanel">` containers.
Field names appear in `<div class="category">` elements within alternating-row tables.
Values appear in `<div class="category_data">` elements.

### ExpandCollapse HTML (2015--2017)

Section headers use `<h2 class="question" sectiontitle="Geography">`.
Fields are in `<div id="field" class="category">` with `<a>` labels.
Values follow in `<div class="category_data">` siblings.

### Modern HTML (2018--2020)

The most structured HTML format, using semantic IDs: `<div id="field-anchor-geography-location">` for field labels and `<div id="field-location">` for values.
Sub-field data appears in `<div class="category_data subfield text">` elements.

All HTML parsers use the `html_to_pipe_text()` helper function, which converts block-level HTML tags (`<br>`, `</p>`, `</div>`) into pipe separators and strips all remaining markup, producing clean pipe-delimited text suitable for database storage.

## JSON Ingestion (2021--2025)

The JSON editions require minimal parsing, as the CIA provided structured key-value data.
The `reload_json_years.py` script checks out year-specific commits from the `factbook-json-cache` repository and extracts country data from the JSON structure into the same `(country, section, field, value)` tuple format used by all other parsers.

## Field Canonicalization

Across 36 years of publication, the CIA used 1,132 distinct field name variants for what are effectively 416 unique concepts.
The canonicalization layer (`build_field_mappings.py`) applies seven mapping rules in sequence:

### Rule 1: Identity

Fields that appear in the 2024--2025 data unchanged are mapped to themselves.

### Rule 2: Dash Normalization

Inconsistent dash formatting (`Economy-overview`, `Economy--overview`) is normalized to `Economy - overview` before applying subsequent rules.

### Rule 3: Known Renames

A curated mapping table of 200+ entries handles CIA vocabulary changes:

| Original (historical) | Canonical (modern) |
|----------------------|-------------------|
| Total area | Area |
| National product | Real GDP (purchasing power parity) |
| Ethnic divisions | Ethnic groups |
| Unemployment | Unemployment rate |
| Military branches | Military and security forces |
| Comparative area | Area - comparative |

### Rule 4: Consolidation

Sub-fields that were historically published as separate entries are consolidated under a parent field:

- `Oil - production`, `Oil - consumption`, `Oil - exports`, `Oil - imports` --> **Petroleum**
- `Electricity - production`, `Electricity - consumption` --> **Electricity**

### Rule 5: Country-Specific Classification

Detects fields that are specific to individual countries (e.g., government body names from 1990s datasets) and classifies them appropriately.

### Rule 6: Noise Detection

Identifies and flags parser artifacts: single-letter field names, lowercase sub-field fragments (`total population`, `male`, `female`), and text fragments mistakenly captured as field names.
Approximately 300--400 entries are classified as noise.

### Rule 7: Manual Review

Fields not matching any automated rule are flagged for human review.

## Sub-Field Extraction

Multi-line Factbook values are stored as pipe-separated strings, preserving the hierarchical relationship between parent fields and their sub-components:

```
total: 4,250,000 | male: 2,150,000 | female: 2,100,000
agriculture: 28% | industry: 24% | services: 48%
```

This flat representation enables both full-text search and structured queries on sub-field values.

\begin{figure}[H]
\centering
\begin{tikzpicture}[
    box/.style={rectangle, draw=#1, fill=#1!8, minimum width=4cm, minimum height=1cm, align=center, font=\small, rounded corners=3pt, line width=0.7pt},
    smallbox/.style={rectangle, draw=#1, fill=#1!10, minimum width=3.2cm, minimum height=0.85cm, align=center, font=\footnotesize, rounded corners=3pt, line width=0.6pt},
    arr/.style={-{Stealth[length=2mm]}, line width=0.6pt, color=black!50},
    note/.style={font=\tiny\itshape, color=black!50},
]

% Input
\node[box=ciaDark] (input) at (0, 0) {\textbf{CountryFields.Content}\\\scriptsize 1,071,603 records};

% Normalize
\node[box=ciaGold] (norm) at (0, -2) {\textbf{normalize\_content()}\\\scriptsize Whitespace + colon-pipe fix (v3.4)};

% Router
\node[box=ciaBlue] (router) at (0, -4) {\textbf{Parser Router}\\\scriptsize CanonicalName $\rightarrow$ parser function};

% Two parser branches
\node[smallbox=ciaGreen] (dedicated) at (-2.5, -6) {\textbf{28 Dedicated}\\\textbf{Parsers}\\\scriptsize regex-based};

\node[smallbox=ciaAccent] (generic) at (2.5, -6) {\textbf{Generic}\\\textbf{Fallback}\\\scriptsize pipe-split};

% Output
\node[box=ciaGreen] (output) at (0, -8.2) {\textbf{FieldValues Table}\\\scriptsize 1,775,588 sub-values $\mid$ 2,599 sub-fields};

% Arrows
\draw[arr] (input) -- (norm);
\draw[arr] (norm) -- (router);
\draw[arr] (router) -- (dedicated);
\draw[arr] (router) -- (generic);
\draw[arr] (dedicated) -- (output);
\draw[arr] (generic) -- (output);

% Annotations
\node[note, anchor=west] at (2.3, -1) {strips pipes after colons};
\node[note, anchor=west] at (2.3, -3) {28 registered + 1 fallback};
\node[note, anchor=east] at (-4.2, -6.7) {\scriptsize Area, Population, GDP,};
\node[note, anchor=east] at (-4.2, -7.0) {\scriptsize Life Expectancy, \ldots};

\end{tikzpicture}
\caption{FieldValues extraction pipeline. Each Content record passes through normalization (where the v3.4 pipe-after-colon fix is applied), routes to one of 28 dedicated regex-based parsers or the generic fallback, and produces structured sub-values stored in the FieldValues table.}
\label{fig:fv-pipeline}
\end{figure}

## Encoding Repair

A dedicated repair script scans the database for Unicode replacement characters (`U+FFFD`), which indicate encoding corruption from the original text files.
The script cross-references corrupted fields against other years' data for the same country to infer the correct characters, then applies targeted fixes.

\newpage

# Database Design

## Schema Overview

The archive uses a normalized relational schema in SQLite, organized around six core tables.
Figure 3 presents the entity-relationship diagram.

Figure 3 presents the entity-relationship diagram in tabular form.

\begin{table}[H]
\centering
\footnotesize
\caption{Database schema --- six core tables with row counts and relationships.}
\label{tab:erd}
\begin{tabular}{p{3.2cm} p{5.5cm} p{4.3cm}}
\toprule
\textbf{Table (Rows)} & \textbf{Columns} & \textbf{Relationships} \\
\midrule
\textbf{MasterCountries} \newline (281) & MasterCountryID (PK), CanonicalCode, CanonicalName, ISOAlpha2, EntityType, AdministeringMasterCountryID & Self-referencing FK for administered territories \\[6pt]
\textbf{Countries} \newline (9,536) & CountryID (PK), Year, Code, Name, Source, MasterCountryID (FK) & FK $\rightarrow$ MasterCountries \\[6pt]
\textbf{CountryCategories} & CategoryID (PK), CountryID (FK), CategoryTitle & FK $\rightarrow$ Countries \\[6pt]
\textbf{CountryFields} \newline (1,071,603) & FieldID (PK), CategoryID (FK), CountryID (FK), FieldName, Content, SourceFragment & FK $\rightarrow$ Countries, \newline FK $\rightarrow$ CountryCategories \\[6pt]
\textbf{FieldValues} \newline (1,775,588) & ValueID (PK), FieldID (FK), SubField, NumericVal, Units, TextVal, DateEst, Rank, SourceFragment, IsComputed & FK $\rightarrow$ CountryFields; \newline 2,599 distinct sub-fields \\[6pt]
\textbf{FieldNameMappings} \newline (1,132) & MappingID (PK), OriginalName, CanonicalName, MappingType, IsNoise, FirstYear, LastYear, UseCount & Logical join on FieldName $=$ OriginalName \\[6pt]
\textbf{CountryFieldsFTS} & FTS5 virtual table & Full-text index on Content column \\
\bottomrule
\end{tabular}
\end{table}

## Design Decisions

### Flat Key-Value vs. Wide Table

The archive stores data as key-value pairs (`FieldName` + `Content`) rather than as a wide table with one column per indicator.
This design was chosen because:

1. **Schema stability.** The CIA adds, removes, and renames fields across editions. A wide table would require schema migrations for every vocabulary change.
2. **Sparse data.** Not all countries have all fields in all years. A wide table would be predominantly NULL.
3. **Full-text search.** The FTS5 index on `Content` enables search across all field values without knowing the field name in advance.

### Pipe-Delimited Sub-Values and FieldValues Table

Sub-field values within each `Content` entry are stored as pipe-delimited strings (e.g., `"total: 9,826,675 sq km | land: 9,161,966 sq km | water: 664,709 sq km"`).
Beginning with v3.0, a dedicated `FieldValues` table (1,775,588 rows) stores pre-parsed sub-field values extracted by 28 dedicated parser functions and a generic fallback.
Each row includes a `SubField` name, typed `NumericVal` and `TextVal` columns, `Units`, `DateEst`, and the CIA's own `Rank` where provided.
This dual representation supports both full-text search (on `Content`) and structured numeric queries (on `FieldValues`).

### SourceFragment Provenance

Version 3.1 added a `SourceFragment` column to `FieldValues`, preserving the original raw text fragment from which each sub-value was parsed.
This enables auditing of parse accuracy and debugging of extraction errors, providing 100\% provenance traceability.

### IsComputed Flag

Version 3.3 added an `IsComputed` boolean column to `FieldValues`, marking 640 life expectancy values that the ETL pipeline computes from male/female sub-values when the CIA omits the total.
This distinguishes original CIA data from derived values, enabling researchers to filter or flag computed entries.

### SQLite as Production Database

The project migrated from SQL Server to SQLite on February 16, 2026 for several reasons:

- **Portability:** Single-file database deploys inside a Docker container with zero configuration.
- **Performance:** Read-only workload with WAL mode and 512 MB page cache handles concurrent queries efficiently.
- **Cost:** Eliminates the need for a managed database service in production.
- **Size:** The complete database is 656 MB (including the FieldValues table and FTS5 index), small enough to bundle in the Docker image.

## Indexes

The following indexes optimize the most common query patterns:

\begin{table}[H]
\centering
\small
\begin{tabular}{p{5.5cm} p{3.5cm} p{4cm}}
\toprule
\textbf{Index} & \textbf{Columns} & \textbf{Purpose} \\
\midrule
\texttt{IX\_Countries\_Year} & Year & Year-based filtering \\
\texttt{IX\_Countries\_Code} & Code & Country lookup \\
\texttt{IX\_Countries\_MasterCountryID} & MasterCountryID & Entity mapping \\
\texttt{IX\_Categories\_Country} & CountryID & Section retrieval \\
\texttt{IX\_Fields\_Category} & CategoryID & Field listing \\
\texttt{IX\_Fields\_FieldName} & FieldName & Field name search \\
\texttt{IX\_FieldNameMappings\_} \newline \texttt{CanonicalName} & CanonicalName & Canonical name lookup \\
\bottomrule
\end{tabular}
\end{table}

## Full-Text Search

An FTS5 virtual table (`CountryFieldsFTS`) indexes the `Content` column of all 1,071,603 field records, enabling sub-second full-text search across the entire archive.

## Indicator System

The webapp defines 102 queryable indicators in `fv_indicators.py`, each mapping a human-readable label to a specific `CanonicalName` + `SubField` pair in the database.
Indicators are organized into categories:

| Category | Count | Examples |
|----------|-------|---------|
| Demographics | 19 | Population, birth rate, life expectancy |
| Age Structure | 6 | 0--14%, 15--64%, 65+% |
| Economy | 14 | GDP (PPP), GDP per capita, inflation, unemployment |
| Technology | 5 | Internet users, mobile subscriptions |
| Health | 8 | Infant mortality, physicians density, obesity |
| Environment | 6 | CO2 emissions, forest area, renewable energy |
| Military | 5 | Military expenditure, active personnel |
| Governance | 4 | Corruption index, government spending |
| Education | 3 | Literacy, education expenditure |
| Infrastructure | 6 | Airports, roadways, railways, ports |
| Other | 26 | Area, coastline, elevation, budget |

Each indicator carries formatting metadata (number format, units label, sort direction) used by the webapp's charting and table components.

## Supplementary Databases

In addition to the primary Factbook database, the platform operates two supplementary SQLite databases:

### CSI Studies in Intelligence (`csi_studies_index.sqlite`)

Contains 1,034 articles from the CIA's *Studies in Intelligence* journal, indexed with FTS5 full-text search.
The core `documents` table stores article metadata (title, year, category, author, issue URL, issue label) alongside full-text content extracted from the original HTML and PDF sources.
The companion `documents_fts` virtual table enables sub-second keyword search across the entire 34-year corpus (1992--2025).

### World Leaders (`world_leaders_structured.sqlite`)

Contains 5,696 leadership position records across 193 countries, extracted from the CIA's *Chiefs of State and Cabinet Members of Foreign Governments* directory.

| Metric | Value |
|--------|-------|
| Total records | 5,696 |
| Distinct countries | 193 |
| Tier 1 positions (heads of state/government) | 725 |
| Tier 2 positions (key ministries) | 1,425 |
| Tier 3 positions (other cabinet) | 3,546 |
| Average positions per country | 29.5 |

The single table (`leadership_records`) stores: country name, country slug, person name, role title, office subfield (12 classified categories), role level (3 tiers), source file, source order, and last-updated date.
The build pipeline (`scripts/build_world_leaders_model.py`) parses the CIA's HTML directory pages using BeautifulSoup, classifies each role into one of 12 office subfields via keyword matching, and assigns tier levels based on the subfield classification.

The database does not include U.S. leadership data because the CIA's publication covers only foreign governments.

\newpage

# Web Application Architecture

## Technology Stack

| Layer | Technology | Role |
|-------|-----------|------|
| Server | FastAPI 0.109+ | Async Python web framework |
| Templates | Jinja2 3.1+ | Server-side HTML rendering |
| Database | SQLite 3 | Read-only data store (WAL mode) |
| Charts | Apache ECharts 5 | Interactive data visualization |
| Maps | Mapbox GL JS | 3D globe and choropleth rendering |
| Styling | Custom CSS (intel-theme) | Dark Intelligence design system |
| Deployment | Fly.io + Docker | Container hosting with persistent volume |
| CDN/DNS | Cloudflare | Caching, DDoS protection, Bot Fight Mode |

Figure 5 shows the layered architecture of the web application.

\begin{figure}[H]
\centering
\begin{tikzpicture}[
    lyr/.style={rectangle, minimum width=11.5cm, minimum height=1.0cm, align=center, font=\small, rounded corners=3pt, line width=0.7pt},
    sublabel/.style={font=\tiny, color=black!55},
    arr/.style={-{Stealth[length=2mm]}, line width=0.5pt, color=black!40},
]

% Layers from top to bottom
\node[lyr, draw=ciaBlue, fill=ciaBlue!10] (user) at (0, 5.5) {\textbf{Users} --- Browser (Desktop / Mobile)};

\node[lyr, draw=ciaGold, fill=ciaGold!10] (cdn) at (0, 4.2) {\textbf{CDN Layer} --- Cloudflare (DNS, Cache, Bot Fight Mode, WAF)};

\node[lyr, draw=ciaRed, fill=ciaRed!10] (sec) at (0, 2.9) {\textbf{Security} --- Rate Limiting, Honeypots, Fingerprinting, Bans};

\node[lyr, draw=ciaBlue, fill=ciaBlue!10] (app) at (0, 1.6) {\textbf{Application} --- FastAPI + Jinja2 + ECharts + Mapbox GL JS};

\node[lyr, draw=ciaGreen, fill=ciaGreen!10] (cache) at (0, 0.3) {\textbf{Cache Layer} --- TTL/LRU In-Memory (24hr TTL, 120 entries/worker)};

\node[lyr, draw=ciaGreen, fill=ciaGreen!15] (data) at (0, -1.0) {\textbf{Data Layer} --- SQLite (factbook.db + csi.db + world\_leaders.db)};

% Arrows
\draw[arr] (user) -- (cdn);
\draw[arr] (cdn) -- (sec);
\draw[arr] (sec) -- (app);
\draw[arr] (app) -- (cache);
\draw[arr] (cache) -- (data);

% Side annotations (left)
\node[sublabel, anchor=east, align=right] at (-6.0, 3.55) {HTTPS\\TLS 1.3};
\node[sublabel, anchor=east, align=right] at (-6.0, 1.0) {JSON API +\\HTML Templates};

% Side annotations (right)
\node[sublabel, anchor=west] at (6.0, 4.2) {Edge};
\node[sublabel, anchor=west] at (6.0, 2.9) {7 layers};
\node[sublabel, anchor=west] at (6.0, 1.6) {102 indicators};
\node[sublabel, anchor=west] at (6.0, 0.3) {per-worker};
\node[sublabel, anchor=west] at (6.0, -1.0) {656 MB + FTS5};

\end{tikzpicture}
\caption{Layered architecture of the web application, from user browser through CDN, security middleware, application logic, caching, and data storage.}
\label{fig:layers}
\end{figure}

## Directory Structure

```
cia-factbook-webapp/
  webapp/
    main.py              -- Application entry, security middleware
    database.py          -- SQLite query interface
    cache.py             -- TTL/LRU query cache
    fv_indicators.py     -- 102 indicator definitions
    bot_taxonomy.py      -- User-agent classification
    routers/
      core.py            -- Home, country pages, search
      api.py             -- /api/v2/ JSON endpoints
      analysis.py        -- Analysis pages (rankings, trends, scatter)
      atlas.py           -- Intelligence Atlas
      csi.py             -- CIA Studies in Intelligence
      political.py       -- Political regime analysis
      world_leaders.py   -- Foreign leaders dashboards
      development.py     -- Development and Inequality
      export.py          -- CSV/Excel bulk export
    templates/           -- 50+ Jinja2 templates
    static/
      css/intel-theme.css
      js/dg2-echarts.js
  start.py               -- Docker startup (DB sync + Uvicorn)
  fly.toml               -- Fly.io deployment manifest
  Dockerfile             -- Container build
  deploy.sh              -- Safe deploy script
```

## Routing Architecture

The application is organized into 12+ routers, each handling a specific domain:

\begin{table}[H]
\centering
\footnotesize
\begin{tabular}{>{\raggedright}p{2.5cm} >{\raggedright}p{3.8cm} >{\raggedright\arraybackslash}p{6.5cm}}
\toprule
\textbf{Router} & \textbf{Prefix} & \textbf{Responsibility} \\
\midrule
\texttt{core.py} & \texttt{/}, \texttt{/country/} & Home, country archives, search \\
\texttt{api.py} & \texttt{/api/v2/} & JSON API: rankings, timeseries, scatter \\
\texttt{analysis.py} & \texttt{/analysis/} & Rankings, trends, scatter, changes, compare, query builder, dashboard builder \\
\texttt{atlas.py} & \texttt{/analysis/atlas} & Full-screen 3D globe with overlays \\
\texttt{csi.py} & \texttt{/analysis/csi/} & CIA Studies in Intelligence reading room \\
\texttt{political.py} & \texttt{/analysis/political} & Political regime dashboard \\
\texttt{world\_leaders.py} & \texttt{/analysis/} \newline \texttt{foreign-leaders} & Foreign leadership analysis \\
\texttt{development.py} & \texttt{/analysis/} \newline \texttt{development} & Development and inequality metrics \\
\texttt{export.py} & \texttt{/export/} & CSV and Excel bulk data export \\
\bottomrule
\end{tabular}
\end{table}

## API Layer

The `/api/v2/` endpoints provide JSON data to the frontend charts and tables.
All endpoints accept GET requests and return JSON responses.

\begin{table}[H]
\centering
\small
\begin{tabular}{p{6.5cm} p{7.5cm}}
\toprule
\textbf{Endpoint} & \textbf{Description} \\
\midrule
\texttt{/api/v2/rank/\{indicator\}/\{year\}} & Ranked list of countries by indicator value \\
\texttt{/api/v2/timeseries/\{indicator\}/\{code\}} & Time series for one country \\
\texttt{/api/v2/compare/\{year\}} & Side-by-side comparison of selected countries \\
\texttt{/api/v2/scatter} & X-Y scatter data for two indicators \\
\texttt{/api/v2/search} & Full-text search across all fields \\
\texttt{/api/v2/changes/\{indicator\}} & Year-over-year changes \\
\texttt{/api/v2/countries} & Country list with metadata \\
\bottomrule
\end{tabular}
\end{table}

## Caching Strategy

A TTL/LRU cache (`webapp/cache.py`) sits between the routers and the database.
Since the archive data is read-only historical data that only changes on deployment, aggressive caching is safe:

- **TTL:** 24-hour time-to-live on all cached queries
- **LRU:** Maximum 120 entries per worker; oldest evicted on overflow
- **Scope:** Each Uvicorn worker process maintains its own independent cache
- **Effect:** Reduces 5--30 second analysis queries to under 0.5 seconds on cache hit
- **Invalidation:** Manual via `/admin/clear-cache?key=ADMIN_KEY`

\newpage

# Design System: Dark Intelligence

## Philosophy

The visual design draws inspiration from intelligence operations centers and classified document aesthetics.
The "Dark Intelligence" theme uses a dark blue-grey palette with high-contrast text and cyan accent colors, conveying the seriousness and precision appropriate to intelligence data.

## Color Palette

### Backgrounds and Surfaces

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg-body` | `#111418` | Page background |
| `--bg-surface` | `#1C2127` | Card and panel backgrounds |
| `--bg-elevated` | `#252A31` | Elevated surfaces (modals, dropdowns) |
| `--border` | `#2F343C` | Standard borders |
| `--border-strong` | `#383E47` | Emphasized borders |

### Text Hierarchy

| Token | Hex | Usage |
|-------|-----|-------|
| `--text-bright` | `#FFFFFF` | Maximum emphasis (stat values) |
| `--text-heading` | `#E0E4E8` | Section headings |
| `--text-primary` | `#C5CBD3` | Primary body text |
| `--text-body` | `#ABB3BF` | Standard body text |
| `--text-muted` | `#7E8A98` | De-emphasized text |

### Accent Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--accent-blue` | `#2D72D2` | Primary actions, links |
| `--accent-gold` | `#F0B726` | Highlights, search results |
| `--accent-red` | `#CD4246` | Errors, critical values |
| `--accent-green` | `#29A634` | Success, positive changes |

## Component Classes

The design system provides reusable CSS classes for all UI components, ensuring visual consistency across 50+ templates:

- **`.stat-card`**: Dashboard statistics with background surface color and subtle shadow
- **`.data-table`**: Tabular data with alternating row backgrounds
- **`.filter-bar`**: Horizontal filter toolbars with inline controls
- **`.badge-*`**: Status badges (moderate, low, critical, NA)
- **`.btn`**: Button variants with hover and active states
- **`.form-control`**, **`.form-label`**: Form inputs styled for dark backgrounds
- **`.diff-*`**: Change highlighting (added, removed, modified)

## Typography

- **Font family:** Georgia, serif --- chosen for its formal, document-like quality
- **Base size:** 1.05rem with 1.65 line height
- **Rendering:** Antialiased with `text-rendering: optimizeLegibility`

## Motion

All interactive transitions use a consistent 200ms duration with cubic-bezier easing, providing responsive feedback without distraction.

## Responsive Design

The layout adapts to three breakpoints:

- **Desktop** (>1200px): Full three-panel layouts, side-by-side charts
- **Tablet** (768--1200px): Stacked panels, reduced chart widths
- **Mobile** (<768px): Single-column layout, collapsible controls, hamburger navigation

## Dual-Theme Support

While the dark theme is the default and recommended experience, a light theme override is available via `[data-theme="light"]`.
Certain elements (topbar, charts, maps) remain dark in both themes for visual consistency.

\newpage

# Feature Guide

This section documents each feature of the web application, including its purpose, how to use it, and what data it presents.

## Home Page

**URL:** `/`

The landing page presents a global search bar, summary statistics (281 entities, 36 editions, 9,536 records, 1,071,603 data points, 1,775,588 structured sub-values), and navigation cards linking to the major sections of the application.

**Usage:** Type any country name, indicator, or keyword into the search bar to find relevant data across all years. Click navigation cards to access specific analysis tools.

## Country Pages

**URL:** `/country/{code}/{year}`

Each country has a dedicated page showing the complete Factbook entry for that year, organized by section (Geography, People, Economy, Government, Military, etc.).

**Usage:**

1. Select a country from the dropdown or search.
2. Use the year navigation bar to move between editions.
3. Click section headers to expand or collapse field groups.
4. Each field shows its value as published in that year's Factbook.

**Data shown:** All fields from the selected country-year record, organized by CIA section categories.

## Country Compare

**URL:** `/analysis/compare`

Side-by-side comparison of two or more countries on key indicators for a selected year.

**Usage:**

1. Select 2--10 countries using the country picker (type to search, click to add).
2. Choose a year from the dropdown.
3. The comparison table shows all available indicators for the selected countries, with values aligned in columns.

**Data shown:** 102 queryable indicators with formatted values, units, and color-coded ranking.

## Rankings

**URL:** `/analysis/rankings`

Horizontal bar chart ranking all countries by a selected indicator for a given year.

**Usage:**

1. Choose an indicator from the categorized dropdown (Demographics, Economy, Military, etc.).
2. Select a year.
3. Optionally filter by COCOM region (AFRICOM, CENTCOM, EUCOM, INDOPACOM, SOUTHCOM, NORTHCOM) or adjust the Top N slider (5--50).
4. The bar chart updates to show ranked countries with their values.

**Data shown:** Ranked values for the selected indicator, with country flags and formatted statistics.

## Trends

**URL:** `/analysis/trends`

Multi-country time series line chart showing how an indicator changes over the 36-year archive span.

**Usage:**

1. Select an indicator.
2. Add 1--10 countries to compare.
3. Adjust the year range slider to focus on a specific period.
4. Hover over data points for exact values; scroll to zoom.

**Data shown:** Year-by-year values for each selected country, plotted as line series with distinct colors.

## Scatter Analysis

**URL:** `/analysis/scatter`

X-Y scatter plot correlating two indicators across all countries for a selected year.

**Usage:**

1. Choose an X-axis indicator (e.g., GDP per capita).
2. Choose a Y-axis indicator (e.g., Life expectancy).
3. Select a year.
4. Each bubble represents a country; bubble size reflects population.
5. Click a bubble to identify the country; hover for details.
6. A regression line shows the overall trend.

**Data shown:** Two-dimensional correlation of indicators across all sovereign nations, with statistical regression.

## Changes

**URL:** `/analysis/changes`

Year-over-year change analysis showing which countries experienced the largest absolute or percentage changes in a selected indicator.

**Usage:**

1. Choose an indicator.
2. Select two years to compare (e.g., 2020 vs. 2025).
3. Toggle between absolute change and percentage change.
4. The bar chart highlights the biggest movers in both directions.

**Data shown:** Sorted list of countries by magnitude of change, with before/after values.

## Query Builder

**URL:** `/analysis/query-builder`

A SQL-like visual interface for constructing custom indicator queries with filters, sorting, and export.

**Usage:**

1. Select one or more indicators from the categorized dropdown.
2. Add country filters (specific countries, regions, or entity types).
3. Set year range and sorting preferences.
4. Click "Run Query" to execute.
5. Results appear in a sortable, downloadable table.

**Data shown:** Custom-filtered indicator data with export to CSV.

## Dashboard Builder

**URL:** `/analysis/dashboard-builder`

A drag-and-drop canvas for composing personalized analytical dashboards from 10 widget types.

**Usage:**

1. **Add widgets:** Click widget types in the left palette (KPI Card, Rankings Bar, Time Series, Scatter Plot, Compare Table, Data Table, Country Profile, Field Text, Mini Globe, Field History).
2. **Configure:** Click the gear icon on any widget to open the config panel. Select indicators, countries, years, and other parameters. Click "Apply."
3. **Layout:** Drag widgets to reorder. Use the resize button to toggle between column spans (25%, 33%, 50%, 67%, 100%). Use up/down arrows to move widgets.
4. **Presets:** Use the toolbar dropdowns to load pre-built dashboards (Deep Dive, Factbook Layout) for any country and year.
5. **Persistence:** Dashboards auto-save to localStorage. Use Export JSON / Import JSON to share layouts.
6. **Apply All:** The "Apply Country to All" and "Apply Year to All" buttons push a single country or year setting to every compatible widget.

**Widget types:**

| Widget | Description | Data Source |
|--------|-------------|-------------|
| KPI Card | Single stat with label | `/api/v2/rank/{ind}/{year}?limit=1` |
| Rankings Bar | Horizontal bar chart | `/api/v2/rank/{ind}/{year}?limit=N` |
| Time Series | Multi-country line chart | `/api/v2/timeseries/{ind}/{code}` |
| Scatter Plot | X-Y correlation | `/api/analysis/scatter` |
| Compare Table | Multi-country comparison | `/api/v2/compare/{year}` |
| Data Table | Full ranked table | `/api/v2/rank/{ind}/{year}` |
| Country Profile | Key stats summary | Multiple API calls |
| Field Text | Raw factbook text | `/api/v2/field/{code}/{year}` |
| Mini Globe | Interactive 3D globe | Mapbox GL JS + GeoJSON |
| Field History | Year-over-year text diff | Multiple year API calls |

\begin{figure}[H]
\centering
\includegraphics[width=\textwidth]{dashboard_germany.png}

\caption{Dashboard Builder: Factbook Layout preset for Germany (2025). The drag-and-drop canvas supports 10 widget types including KPI cards, time series charts, scatter plots, comparison tables, country profiles, and mini globes. Users can load pre-built presets or compose custom dashboards with JSON export/import.}
\label{fig:dashboard}
\end{figure}

## Intelligence Atlas

**URL:** `/analysis/atlas`

A full-screen interactive 3D globe built on Mapbox GL JS with 27+ toggleable data layers, 6 analytical tools, and real-time geopolitical overlays.
The atlas comprises approximately 5,900 lines of JavaScript and represents the project's most complex single feature.

\begin{figure}[H]
\centering
\includegraphics[width=\textwidth]{atlas_eucom.png}

\caption{Intelligence Atlas: EUCOM region with three OSINT overlay layers active --- military installations (color-coded by operator nation), nuclear facilities (IAEA PRIS data), and mining/extraction sites (USGS Mineral Resources). The left panel provides 27 toggleable layers; the bottom toolbar offers projection switching, measurement tools, and COCOM regional presets.}
\label{fig:atlas}
\end{figure}

### Navigation and Map Controls

The atlas initializes as a 3D globe centered at coordinates [15, 20] with 20-degree pitch, providing a satellite-like perspective of the Earth.
Users can rotate the globe by click-dragging, zoom with scroll, and tilt with right-click drag.
A geocoder search bar (top-right) enables direct navigation to any location.

**Base Map Styles (5):** Dark (default), Satellite Streets, Outdoors, Light, and Navigation Night --- each selectable from the toolbar.

**Projections (5):** Globe (3D spherical, default), Mercator, Equal Earth, Natural Earth, and Winkel Tripel --- switchable for different analytical perspectives.

**Regional Presets (7):** One-click fly-to animations for World, EUCOM, AFRICOM, INDOPACOM, CENTCOM, SOUTHCOM, and NORTHCOM --- each with preset center, zoom, and pitch optimized for that theater.

### Layer System

The atlas organizes its 27 layers into four categories:

**Map Base Layers (11):** Terrain (DEM elevation), Hillshade, Atmosphere (3D haze), 3D Buildings, Ocean styling, Country Borders, Sub-national Boundaries (admin1), Capital Markers, State/Province Capitals, Place Labels, and Latitude/Longitude Graticule.

**Military and Security (6):** Military Installations (color-coded by operator: US, Russia, China, UK, France, Turkey, India, Japan, UAE), Nuclear Facilities (IAEA PRIS data), National Missile Capabilities (4 tiers), Missile Site Locations (7 facility types), Missile Range Rings (concentric radius visualization), and COCOM Command Regions (6 US combatant commands).

**Infrastructure and Maritime (5):** Mining and Extraction Sites (USGS), Submarine Cables (TeleGeography), Maritime Shipping Routes, Exclusive Economic Zones, and NASA VIIRS Night Lights.

**Special Effects (3):** Day/Night Solar Terminator (real-time UTC-synchronized boundary computed from orbital mechanics), Pulse Animation (animated markers on military/nuclear layers), and Territorial Disputes overlay.

### Analytical Tools

1. **Distance Measurement.** Click to place waypoints on the globe; the tool displays real-time distance in kilometers, miles, and nautical miles. Supports multi-segment measurement with undo capability.

2. **Area Measurement.** Click to place polygon vertices; double-click to close. Calculates enclosed area in km$^2$ and square miles with a draggable results panel.

3. **Screenshot Export.** Captures the current map view as a PNG image file named `atlas-[YEAR]-[TIMESTAMP].png`.

4. **Timelapse Video Recording.** Records map animation to WebM video at 24 fps / 20 Mbps bitrate. Auto-starts year playback during recording for creating temporal visualizations.

5. **Range Ring Analysis.** Renders concentric circles around missile sites showing weapon reach. Filterable by tier (nuclear triad, nuclear armed, MRBM/IRBM, SRBM), facility type (silo field, submarine base, mobile garrison, air base, test range, production, storage), and country. Includes presets for US Triad, Russia Triad, and China ICBM configurations.

6. **Bookmark System.** Saves and recalls map views including position, zoom, pitch, bearing, year, and active overlay. Persisted to localStorage.

### Data Overlays

The choropleth system offers 22 data overlays organized by domain:

**Geopolitical and Security (5):** Conflict Intensity (UCDP 2024 event data), Alliance Memberships (NATO, EU, Five Eyes, AUKUS, CSTO, SCO), Sanctions Status (comprehensive/sectoral/targeted), Political Regime Type, and Military Spending (\% GDP).

**Resources and Economy (11):** Natural Resources (richness/diversity), Oil and Gas, Precious Metals, Industrial Metals, Rare Earths and Strategic Minerals, Minerals and Mining, Energy and Power, Timber and Land, Marine Resources, GDP per Capita, and GDP (PPP).

**Demographics (4):** Population, Population Density, Life Expectancy, and Population Growth Rate.

**Communications (3):** Internet Penetration, Mobile Subscriptions per 100, and Broadband Access.

All Factbook-linked overlays connect to the year timeline slider, enabling researchers to watch how any indicator changes from 1990 to 2025.

### OSINT Military Data

The missile capabilities layer categorizes nations into four tiers with distinct color coding:

- **Nuclear Triad** (red): Nations with intercontinental land, sea, and air nuclear delivery systems
- **Nuclear Armed** (orange): Nations with regional nuclear weapons systems
- **MRBM/IRBM** (yellow): Nations with medium- or intermediate-range ballistic missiles
- **SRBM Capable** (green): Nations with short-range ballistic missile programs

The missile sites layer maps individual facilities across 7 types: ICBM silo fields, submarine bases, mobile TEL garrisons, strategic bomber air bases, missile test ranges, production facilities, and warhead/munitions storage sites.

### Country Information Card

Clicking any country opens a detailed intelligence card displaying:

- **Executive Leadership:** Head of state and head of government with tenure dates
- **Economic Indicators:** Population, GDP per capita, GDP (PPP), military spending (\% GDP), life expectancy, population growth rate
- **Political Classification:** Regime category and government structure
- **Territorial Disputes:** Full dispute text from the Factbook
- **Alliance Memberships:** NATO, EU, Five Eyes, AUKUS, CSTO, SCO with expandable definitions
- **Sanctions Status:** Comprehensive, sectoral, or targeted, with imposing entities (US/EU/UN)
- **Natural Resources:** Grouped by category with color-coded badges
- **Missile Capabilities:** Tier classification, system names, warhead count, maximum range (when missile layer is active)

**Shift+Click** enables side-by-side comparison of two countries.

**Data sources:** CIA World Factbook (1990--2025), ACA, FAS, CSIS Missile Threat, IAEA PRIS, DoD, USGS, TeleGeography, Marine Regions, NASA VIIRS, Natural Earth.

## CSI Reading Room

**URL:** `/analysis/csi/dashboard`

A searchable digital library of the CIA's *Studies in Intelligence* journal --- the agency's premier internal publication on intelligence tradecraft, history, and analysis.
The reading room indexes over 1,000 articles spanning 34 years (1992--2025) with full-text search, entity network analysis, strategic term tracking, and collection management.

### Corpus Statistics

The CSI database (`csi_studies_index.sqlite`) contains:

| Metric | Value |
|--------|-------|
| Total articles | 1,034 |
| Distinct journal issues | 106 |
| Unique authors | 277 |
| Year span | 1992--2025 (34 years) |
| PDF coverage | 97\% of all articles |
| Categories | 26 distinct classifications |

### Dashboard Analytics

The dashboard presents six KPI cards (total documents, issues, PDF coverage, unique authors, year span, top tracked term) followed by a tabbed interface:

**Charts Tab (6 visualizations):**

1. **Documents Over Time** --- bar chart showing publication volume by year, clickable for year-based filtering
2. **Topic Signals** --- horizontal bar chart displaying frequency of 7 tracked strategic terms across the entire corpus
3. **Topic Trajectories** --- multi-line chart showing how each tracked term's prevalence has shifted over 34 years
4. **Top Categories** --- pie/donut chart of article distribution by category, clickable for filtering
5. **Coverage Heatmap** --- 2D matrix of Year $\times$ Category density, revealing gaps and concentrations
6. **Top Authors** --- bar chart of the most prolific contributors, clickable for author-specific filtering

**Strategic Term Tracking.** The system monitors seven terms representing evolving intelligence priorities: *counterintelligence*, *osint*, *china*, *russia*, *terrorism*, *cyber*, and *ai*.
Each term is tracked via FTS5 queries across the full corpus, with year-by-year breakdowns enabling trend analysis of how the intelligence community's focus has shifted over three decades.

### Full-Text Search

Powered by SQLite FTS5 (Full-Text Search 5), the search system tokenizes queries and matches against the complete text of all 1,034 articles.
Results are paginated (50 per page) and can be filtered by year, category, and PDF availability.
The search API (`/api/csi/search`) returns structured JSON with document metadata and highlighted text snippets.

### Entity Network Analysis

**Entities Tab** provides an intelligence command-center view of people, organizations, and countries mentioned across the corpus.

The entity extraction pipeline applies regex-based named entity recognition (NER) to all article texts, producing a co-occurrence graph with:

- **Node types:** Country, Organization, Person, and Other
- **Known organization whitelist:** CIA, FBI, NSA, MI5, MI6, KGB, Mossad, NATO, DNI
- **Scoring function:** Multi-factor scoring combining document frequency, entity type bonuses, name length, and noise penalties
- **Trusted nodes:** Entities scoring $\geq$ 4 with $\geq$ 2 document appearances (capped at 48 nodes)
- **Edge weights:** Co-occurrence counts between entities appearing in the same articles (minimum weight 2, capped at 100 edges)

The entity command map displays:

- A searchable entity list with type filters (left panel)
- Selected entity detail with document count, top connections, top categories, and a link to filtered documents (center panel)
- **Top Connections** chart showing co-occurring entities
- **Mentions Over Time** chart showing entity frequency across years
- **Entity Comparison** tool for side-by-side analysis of two entities' timelines and shared connections

### Article Reader

Each article (`/analysis/csi/article/{doc_id}`) is presented in a cleaned reader view with:

- **Metadata header:** Year, category, author, and issue label
- **Action bar:** Links to CIA.gov source, PDF download, and back-navigation
- **Article text:** HTML-sanitized content preserving only semantic tags (paragraphs, headings, lists, tables, blockquotes)
- **Embedded PDF viewer:** 700px iframe with direct download fallback (for 97\% of articles with available PDFs)
- **Related articles:** Grid of up to 12 related articles, prioritized by same issue, then same category
- **Issue navigation:** Previous/next article links within the same journal issue

### Collection Management

Users can create named collections of articles, stored in browser localStorage:

- **Save articles** from search results or individual article pages
- **Browse collections** with tabular metadata (title, year, category)
- **Export metadata** as CSV for offline analysis
- **Batch PDF download** for entire collections
- **Cross-filter integration:** Collections can be assembled from any filtered dashboard view (time range, category, entity)

### Browse Interface

The browse page (`/analysis/csi/browse`) provides year-by-year navigation with summary statistics (article count, issue count, PDF count per year), articles grouped by issue with color-coded category tags.

## StarDict Dictionary

An offline companion product: the complete Factbook archive packaged as a StarDict-format dictionary compatible with GoldenDict (desktop) and KOReader (e-readers).

**Usage:** Download the StarDict files from the GitHub repository and import into any compatible dictionary application. Look up any country name to see its full Factbook entry.

## Political Regime Dashboard

**URL:** `/analysis/political`

An interactive geopolitical dashboard that classifies and visualizes the government type of every sovereign entity across the archive's 36-year span, with animated map transitions, regime change tracking, and predecessor state handling.

### Regime Classification

The dashboard classifies the CIA's free-text "Government type" field into seven categories:

| Category | Color | Examples |
|----------|-------|---------|
| Democracy | Blue | Presidential republic, parliamentary democracy |
| Autocracy | Red | Single-party state, authoritarian |
| Monarchy | Gold | Constitutional monarchy, absolute monarchy |
| Military regime | Grey | Military junta, provisional military government |
| Theocratic | Purple | Theocratic republic (Iran) |
| Transitional | Orange | Transitional government, in transition |
| Unknown | Slate | Insufficient data or unclassifiable |

### Visualizations

**Interactive World Map.** A Mapbox GL JS choropleth colored by regime classification, with a year slider animating changes from 1990 to 2025.
The map handles dissolved states (USSR, Yugoslavia, Czechoslovakia) by visually expanding the parent state's color across all successor territories for years prior to dissolution.

**Timeline Tab.** Tracks a single country's regime classification year by year, including predecessor context (e.g., showing Soviet Union classification for Russia's pre-1992 entries).

**Change Log Tab.** A chronological list of every regime classification change across all entities, sorted by year (most recent first).
This enables researchers to identify waves of democratization, authoritarian backsliding, or revolutionary transitions.

### Predecessor Tracking

A unique feature of the dashboard is its handling of state dissolution.
A predecessor mapping links each post-dissolution state to its parent: 14 post-Soviet states map to the Soviet Union, 6 Yugoslav successor states map to Yugoslavia, and the Czech Republic and Slovakia map to Czechoslovakia.
For years before dissolution, the map displays the parent state's regime classification across the entire territory of all successor states.

## Foreign Leaders Dashboard

**URL:** `/analysis/world-leaders`

A multi-tab analytical dashboard for the CIA's *Chiefs of State and Cabinet Members of Foreign Governments* directory, providing leadership rosters, power concentration analysis, security apparatus breakdowns, and governance structure comparisons for 193 countries.

### Data Source

The dashboard draws from `world_leaders_structured.sqlite`, a dedicated database containing **5,696 leadership positions** across **193 countries**, extracted from the CIA's official foreign government directory.
Each record includes person name, role title, classified office subfield, tier level, and source order (preserving the CIA's implicit hierarchy).

### Office Classification

Every leadership position is classified into one of 12 office subfields:

- **Executive:** Head of State, Head of Government, Deputy
- **Key Portfolios:** Foreign Affairs, Defense, Interior/Home Affairs, Justice/Rule of Law, Finance/Economy, Intelligence/Security
- **Service Portfolios:** Energy/Infrastructure, Health/Education/Social
- **Other:** All remaining cabinet positions

Positions are further assigned to three tiers: Tier 1 (heads of state/government and deputies), Tier 2 (key ministry holders), and Tier 3 (all other cabinet members).

### Analytical Metrics

**Complexity Score (0--100).** A weighted composite of cabinet size (25\%), subfield breadth (25\%), tier depth (25\%), and security portfolio concentration (25\%).
Countries with large, deeply structured, security-heavy cabinets score highest.

**Power Concentration Score (0--100).** Measures how centralized authority is within the leadership structure, based on roles-per-person ratio (30\%), multi-role holder prevalence (30\%), head-of-state/head-of-government overlap (20\%), and whether the leader holds a security portfolio (20\%).

### Dashboard Tabs

1. **Country Profiles** --- Country selector with region filter, stat cards (cabinet size, subfield breadth, security percentage, complexity score), head of state and head of government display, and full leadership roster table sortable by name, title, subfield, and tier.

2. **Comparative Analysis** --- Global bar charts for subfield distribution, tier distribution, and regional aggregates (cabinet size and security ratio per COCOM region).

3. **Browse** (`/analysis/world-leaders/browse`) --- Searchable, sortable table of all 193 countries with columns for government type, head of state, head of government, total positions, and complexity score.

4. **Governance** (`/analysis/world-leaders/governance`) --- Government type distribution across all countries, normalized to standard categories (presidential republic, parliamentary democracy, constitutional monarchy, etc.), with factbook-sourced executive/legislative/judicial structure.

5. **Concentration** (`/analysis/world-leaders/concentration`) --- Countries ranked by power concentration score, highlighting multi-role holders and head-of-state/head-of-government overlaps.

6. **Security** (`/analysis/world-leaders/security`) --- Defense, interior, and intelligence personnel counts per country, defense minister identification, military expenditure trends (latest 5 years from factbook data), and regional security aggregates.

7. **Map** (`/analysis/world-leaders/map`) --- Global choropleth colored by complexity or concentration score, with hover cards showing country summary data.

## Development and Inequality Dashboard

**URL:** `/analysis/development`

A 20-panel analytical dashboard examining global development outcomes across health, infrastructure, education, and inequality indicators, with regional heatmaps and cross-indicator correlation analysis.

### Indicators

The dashboard combines 13 development indicators from the Factbook database:

**Health and Demographics (4):** Life expectancy at birth, infant mortality rate, maternal mortality ratio, physician density.

**Infrastructure (3):** Drinking water access, sanitation facility access, electricity access (electrification rate).

**Education (3):** Adult literacy rate, education expenditure (\% of GDP), school life expectancy (male/female).

**Inequality (5):** Gini index, household income share (lowest 10\% vs. highest 10\%), population below poverty line, unemployment rate, youth unemployment rate (male/female).

### Visualization Panels

The dashboard organizes 18+ chart panels into thematic sections:

**Water and Sanitation:** Water-vs-sanitation scatter plot (diagonal reference line for parity) and sanitation access stacked bar (bottom 20 countries).

**Electrification:** Electrification rate stacked bar (bottom 20) and urban-rural electrification gap scatter.

**Health and Demographics:** Life expectancy bar (male/female grouped, bottom 20), infant mortality vs. life expectancy scatter (inverse correlation), maternal mortality bar (highest 20), and physician density vs. maternal mortality scatter.

**Education:** Adult literacy bar (male/female, bottom 20), education expenditure bar (top 20 spenders), and school life expectancy gender parity scatter.

**Inequality:** Gini index bar (most unequal 20), income distribution scatter (top 10\% vs. bottom 10\%), poverty rate bar (worst 20), unemployment bar (highest 20), youth unemployment bar (male/female), and poverty vs. Gini scatter.

**Cross-Cutting Analysis:** Water access vs. Gini scatter, life expectancy vs. Gini scatter, and a composite development scorecard (average of water + sanitation + electrification, showing bottom 10 and top 10).

**Regional Heatmap:** A 7-indicator $\times$ 6-region matrix showing capability gaps across COCOM regions (AFRICOM, CENTCOM, EUCOM, INDOPACOM, SOUTHCOM, NORTHCOM).

**Correlation Matrix:** A 12 $\times$ 12 Pearson correlation heatmap revealing structural linkages between all development indicators (e.g., the strong inverse correlation between physician density and maternal mortality).

### Unique Features

- **Percentile ranking API:** Computes a country's percentile rank on all 13 indicators, inverting "bad-is-high" metrics (mortality, unemployment, Gini) so that higher percentile always means better outcome
- **Composite development index:** Averages water, sanitation, and electrification rates into a single basic-infrastructure score; countries below 40\% face "compounding infrastructure failure"
- **Gender-disaggregated analysis:** Life expectancy, literacy, school attendance, and youth unemployment are broken into male/female series for gender gap visualization

## Search

**URL:** `/` (search bar) or `/search?q=...`

Global full-text search powered by SQLite FTS5, spanning all 1,071,603 field records across all years and entities.

**Usage:** Type any term into the search bar. Results are grouped by country and year, with matching text highlighted. Click any result to navigate to the full country page.

\newpage

# Infrastructure and Deployment

## Hosting Architecture

The application runs on **Fly.io**, a container hosting platform, in the `iad` (US East Coast) region.

| Component | Configuration |
|-----------|--------------|
| Machine | Single Fly.io machine, auto-start/stop |
| Workers | 2 Uvicorn worker processes |
| Port | 8080 (internal) |
| Volume | 1 GB persistent volume at `/data` |
| Health check | `/health` endpoint, 30s interval, 15s timeout |

## Docker Container

The application is packaged as a Docker container based on `python:3.12-slim`:

1. Install Python dependencies from `requirements.txt`
2. Copy application code and static assets
3. Bundle SQLite databases in the image (factbook.db, csi_studies_index.sqlite, world_leaders_structured.sqlite)
4. Bundle IP2Location geolocation binary
5. Entry point: `python start.py`

The `start.py` startup script performs MD5 hash comparison between bundled databases and the persistent volume, copying updated databases only when the hash changes.
This ensures database updates propagate on deployment without unnecessary I/O.

## Deployment Workflow

The `deploy.sh` script implements a git-aware safe deploy:

1. Check for uncommitted changes (`git diff`, `git diff --cached`)
2. If dirty: stash changes with timestamp (`deploy-safeguard-{ts}`)
3. Run `fly deploy` (builds from local filesystem)
4. Pop stash to restore local work

This prevents accidental deployment of unfinished code while preserving work-in-progress.

## DNS and CDN

**Cloudflare** provides DNS resolution, HTTP proxy, and security for `worldfactbookarchive.org`:

- DNS proxied through Cloudflare (orange cloud)
- Bot Fight Mode enabled (blocks known bad bots at the edge)
- SSL/TLS: Full (strict) mode
- Cache: Static assets cached at Cloudflare edge; HTML served fresh

The legacy domain `cia-factbook-archive.fly.dev` returns 301 redirects to the custom domain.

## Security Architecture

The application implements a 7-layer security system:

### Layer 1: Honeypot Endpoints

Paths like `/admin`, `/wp-admin`, `/.env`, and `/database` are disallowed in `robots.txt`.
Legitimate crawlers obey robots.txt; only malicious bots follow these paths.
Accessing a honeypot triggers an instant IP ban.

### Layer 2: User-Agent Blocking

Known bot user-agent strings (python-requests, scrapy, wget, httpx) are blocked on sight.
AI training crawlers (Claude, GPT, Grok, Perplexity) are blocked entirely.

### Layer 3: Request Fingerprinting

The system analyzes request timing variance per IP.
Humans produce irregular intervals (3.2s, 47.1s, 2.8s); bots produce uniform intervals (<1s variance).
IPs with 8+ requests showing bot-like timing patterns are auto-banned.

### Layer 4: Per-Endpoint Rate Limits

Targeted limits per path prefix:

| Path | Limit | Window |
|------|-------|--------|
| `/export/` | 10 requests | 60 seconds |
| `/analysis/` | 20 requests | 60 seconds |
| `/archive/` | 20 requests | 60 seconds |
| `/api/` | 60 requests | 60 seconds |

Exceeding limits returns HTTP 429 and records a strike.

### Layer 5: Escalating Bans

After 15 strikes within 5 minutes, the IP is banned.
Ban duration escalates on repeat offenses: 5 minutes, 30 minutes, 2 hours, 24 hours.

### Layer 6: Ban Persistence

Ban data is saved to `/data/bandata.json` on the persistent volume and reloads on server restart.
Restarting the application alone does not clear bans.

### Layer 7: Server-Wide Throttle

A global rate limit of 120 page requests per minute across all IPs prevents distributed flooding.
If exceeded, the server returns HTTP 503 (Service Busy) to shed load.

### Admin Bypass

Authenticated administrators bypass all security layers via an `ADMIN_KEY` stored as a Fly.io secret.
Authentication methods: HTTP header, browser cookie (1-year expiry), or query parameter.

Admin endpoints:

| Endpoint | Purpose |
|----------|---------|
| `/admin/unlock` | Set admin cookie |
| `/admin/clear-bans` | Clear all ban data |
| `/admin/clear-cache` | Clear query cache |
| `/admin/status` | View active bans and cache stats |

\newpage

# Supplementary Materials

## API Reference

All API endpoints accept GET requests and return JSON responses.

\begin{table}[H]
\centering
\footnotesize
\begin{tabular}{p{4.8cm} p{3.8cm} p{4.8cm}}
\toprule
\textbf{Endpoint} & \textbf{Parameters} & \textbf{Response Shape} \\
\midrule
\texttt{/api/v2/rank/} \newline \texttt{\{indicator\}/\{year\}} & \texttt{limit}, \texttt{region}, \texttt{desc} & \texttt{[\{rank, name, iso2, value, units\}]} \\[4pt]
\texttt{/api/v2/timeseries/} \newline \texttt{\{indicator\}/\{code\}} & \texttt{start\_year}, \texttt{end\_year} & \texttt{[\{year, value, units\}]} \\[4pt]
\texttt{/api/v2/compare/\{year\}} & \texttt{codes} (comma-sep ISO2) & \texttt{[\{name, iso2, indicators\}]} \\[4pt]
\texttt{/api/v2/scatter} & \texttt{x}, \texttt{y}, \texttt{year} & \texttt{[\{name, iso2, x\_val, y\_val\}]} \\[4pt]
\texttt{/api/v2/search} & \texttt{q}, \texttt{year}, \texttt{limit} & \texttt{[\{country, year, field, snippet\}]} \\[4pt]
\texttt{/api/v2/changes/} \newline \texttt{\{indicator\}} & \texttt{year\_a}, \texttt{year\_b} & \texttt{[\{name, old, new, change, pct\}]} \\[4pt]
\texttt{/api/v2/countries} & (none) & \texttt{[\{name, iso2, code, type\}]} \\[4pt]
\texttt{/api/atlas/disputes/\{year\}} & (none) & \texttt{[\{iso2, name, text\}]} \\[4pt]
\texttt{/api/atlas/infrastructure/} \newline \texttt{\{year\}} & (none) & \texttt{[\{iso2, airports, ports, ...\}]} \\[4pt]
\texttt{/api/atlas/missiles} & (none) & \texttt{[\{name, tier, systems, range\}]} \\[4pt]
\texttt{/api/csi/search} & \texttt{q}, \texttt{year}, \texttt{category} & \texttt{[\{doc\_id, title, snippet\}]} \\[4pt]
\texttt{/api/csi/dashboard} & \texttt{year\_start}, \texttt{year\_end} & \texttt{\{doc\_count, categories\}} \\
\bottomrule
\end{tabular}
\end{table}

## Indicator Categories

The complete list of 102 queryable indicators organized by category:

**Demographics (19):** Population, Population growth rate, Birth rate, Death rate, Net migration rate, Infant mortality rate (total/male/female), Life expectancy at birth (total/male/female), Total fertility rate, Median age, Urban population percentage, Sex ratio, Dependency ratio (youth/elderly/total)

**Age Structure (6):** 0--14 years, 15--24 years, 25--54 years, 55--64 years, 15--64 years, 65 years and over

**Economy (14):** Real GDP (PPP), GDP per capita (PPP), GDP (official exchange rate), Real GDP growth rate, Inflation rate, Unemployment rate, Youth unemployment rate, Public debt, Budget surplus/deficit, Current account balance, Exports, Imports, Gini index, Population below poverty line

**Technology (5):** Internet users, Broadband subscriptions, Mobile cellular subscriptions, Telephones (fixed lines), Secure internet servers

**Health (8):** Infant mortality rate, Physicians density, Hospital bed density, Obesity rate, HIV/AIDS prevalence, Drinking water access, Sanitation access, Health expenditure

**Environment (6):** CO2 emissions, Forest area, Agricultural land, Renewable energy, Electricity access, Revenue from natural resources

**Military (5):** Military expenditures (% GDP), Active military personnel, Military service age, Military branches count, Arms procurement

**Governance (4):** Corruption perceptions, Government spending, Political stability, Regulatory quality

**Education (3):** Literacy rate, Education expenditures, School life expectancy

**Infrastructure (6):** Airports, Roadways, Railways, Waterways, Ports, Merchant marine

**Other (26):** Area, Coastline, Elevation (highest/lowest), Climate zones, Natural hazards, Natural resources, Land use, Budget revenues/expenditures, Taxes, Fiscal year, Exchange rates, and more

\newpage

# Analysis and Findings

This section presents quantitative analysis of the archive's scope, data density, coverage completeness, and development metrics.
These findings contextualize the project's contribution to open-source intelligence research and digital preservation.

## Data Coverage Analysis

### Temporal Coverage by Entity

Of the 281 entities in the archive, **215 (76.5%)** have complete records spanning all 36 editions from 1990 through 2025.
An additional 30 entities have 30 or more years of coverage, bringing the 30+ year cohort to **245 entities (87.2%)**.
Only 17 entities have fewer than 20 years of data, and these are predominantly dissolved political entities (Serbia and Montenegro, Netherlands Antilles), merged territories (Iles Eparses), or newly independent states (South Sudan, Kosovo).

| Coverage Tier | Entity Count | Percentage |
|---------------|-------------|------------|
| Full (36 years) | 215 | 76.5% |
| Near-complete (30--35 years) | 30 | 10.7% |
| Substantial (20--29 years) | 19 | 6.8% |
| Partial (<20 years) | 17 | 6.0% |

This high coverage rate is notable given the geopolitical turbulence of the period.
The archive captures the emergence of 15 post-Soviet states (appearing 1992), the fragmentation of Yugoslavia into seven successor states (1992--2008), the independence of Eritrea (1993), Timor-Leste (2002), Montenegro and Serbia as separate entries (2006), Kosovo (2008), and South Sudan (2011).
It also records the dissolution of entities such as the Netherlands Antilles (last entry: 2010) and the administrative consolidation of French overseas territories like Guadeloupe, Martinique, and Reunion (last entries: 2006).

### Data Density Growth

The richness of Factbook entries has increased substantially over the archive's 36-year span.
In 1990, the average entity had approximately 63 data fields across 6 sections.
By 2025, this had grown to 125 fields across 11.6 sections --- a near-doubling of informational density:

| Decade | Avg Fields per Entity | Avg Sections per Entity | Total Fields in Decade |
|--------|----------------------|------------------------|----------------------|
| 1990s | 79.3 | 6.0--6.9 | 213,991 |
| 2000s | 107.2 | 8.8--8.9 | 286,416 |
| 2010s | 134.1 | 8.9--10.0 | 353,947 |
| 2020s | 139.5 | 10.0--11.6 | 217,249* |

\small *2020s covers 6 years (2020--2025) vs. 10 for other decades.\normalsize

\begin{figure}[H]
\centering
\begin{tikzpicture}
  % Bars (scaled to max 6cm)
  \fill[ciaBlue!50] (0, 2.4) rectangle (3.17, 3.0);
  \fill[ciaBlue!60] (0, 1.6) rectangle (4.29, 2.2);
  \fill[ciaBlue!75] (0, 0.8) rectangle (5.36, 1.4);
  \fill[ciaGreen!65] (0, 0) rectangle (5.58, 0.6);

  % Labels (left)
  \node[anchor=east, font=\small] at (-0.2, 2.7) {1990s};
  \node[anchor=east, font=\small] at (-0.2, 1.9) {2000s};
  \node[anchor=east, font=\small] at (-0.2, 1.1) {2010s};
  \node[anchor=east, font=\small] at (-0.2, 0.3) {2020s};

  % Values (right of bars)
  \node[anchor=west, font=\small\bfseries] at (3.27, 2.7) {79.3};
  \node[anchor=west, font=\small\bfseries] at (4.39, 1.9) {107.2};
  \node[anchor=west, font=\small\bfseries] at (5.46, 1.1) {134.1};
  \node[anchor=west, font=\small\bfseries] at (5.68, 0.3) {139.5};

  % Axis
  \draw[line width=0.5pt, color=black!30] (0, -0.1) -- (0, 3.1);

  % X-axis label
  \node[font=\footnotesize, color=black!50] at (2.8, -0.4) {Average fields per entity};
\end{tikzpicture}
\caption{Data density growth by decade. Average fields per entity nearly doubled from 79.3 (1990s) to 139.5 (2020s), reflecting the CIA's progressive expansion of Factbook coverage categories including internet infrastructure, health indicators, and environmental metrics.}
\label{fig:density}
\end{figure}

This growth reflects the CIA's progressive expansion of its coverage framework.
New indicator categories --- Internet infrastructure (added mid-1990s), HIV/AIDS prevalence (added early 2000s), renewable energy metrics (added 2010s), and cybersecurity indicators (added 2020s) --- were introduced as geopolitical priorities evolved.

### Format Complexity Distribution

The archive's 9,536 country-year records divide across three source format families:

| Format Family | Records | Percentage | Years Covered | Parsers Required |
|--------------|---------|------------|---------------|-----------------|
| HTML | 5,349 | 56.1% | 2000--2020 | 5 |
| Plain Text | 2,887 | 30.3% | 1990--2001 | 6 |
| JSON | 1,300 | 13.6% | 2021--2025 | 1 |

The plain text era (1990--2001) exhibits the highest format instability, with six distinct parsing grammars across 12 years --- an average format lifespan of just 2 years.
The HTML era (2000--2020) was more stable, averaging 4 years per format variant.
The JSON era (2021--2025) has maintained a single consistent schema, reflecting modern API design practices.

\begin{figure}[H]
\centering
\begin{tikzpicture}
  % Bars (scaled to max 6cm)
  \fill[ciaBlue!70] (0, 1.6) rectangle (5.61, 2.2);
  \fill[ciaGold!65] (0, 0.8) rectangle (3.03, 1.4);
  \fill[ciaGreen!65] (0, 0) rectangle (1.36, 0.6);

  % Labels (left)
  \node[anchor=east, font=\small] at (-0.2, 1.9) {HTML (2000--2020)};
  \node[anchor=east, font=\small] at (-0.2, 1.1) {Text (1990--2001)};
  \node[anchor=east, font=\small] at (-0.2, 0.3) {JSON (2021--2025)};

  % Values with record/parser counts
  \node[anchor=west, font=\small\bfseries] at (5.71, 1.9) {56.1\%};
  \node[anchor=west, font=\small\bfseries] at (3.13, 1.1) {30.3\%};
  \node[anchor=west, font=\small\bfseries] at (1.46, 0.3) {13.6\%};

  % Record and parser counts (below each percentage)
  \node[font=\tiny, color=black!50, anchor=north west] at (5.71, 1.7) {5,349 records, 5 parsers};
  \node[font=\tiny, color=black!50, anchor=north west] at (3.13, 0.9) {2,887 records, 6 parsers};
  \node[font=\tiny, color=black!50, anchor=north west] at (1.46, 0.1) {1,300 records, 1 parser};

  % Axis
  \draw[line width=0.5pt, color=black!30] (0, -0.1) -- (0, 2.3);
\end{tikzpicture}
\caption{Source format distribution across 9,536 country-year records. The plain text era requires the most parsers relative to its data share (6 parsers for 30.3\% of records), illustrating that legacy format diversity --- not data volume --- is the primary complexity driver in historical data preservation.}
\label{fig:format-dist}
\end{figure}

The disproportionate engineering effort required by the text era --- 6 parsers for 30.3% of records vs. 1 parser for 13.6% of records --- underscores a key finding: **legacy format diversity is the primary complexity driver in historical data preservation projects, not data volume.**

## Field Standardization Analysis

### Canonicalization Effectiveness

The ETL pipeline maps 1,132 distinct raw field name variants to 416 canonical names, achieving a **2.72:1 compression ratio**.
The mapping rules break down as follows:

| Rule | Mappings | Percentage | Description |
|------|---------|------------|-------------|
| Country-Specific | 355 | 31.4% | Fields unique to individual countries (e.g., governance bodies) |
| Noise | 310 | 27.4% | Parser artifacts, fragments, sub-field text captured as field names |
| Identity | 185 | 16.3% | Modern field names unchanged from source |
| Rename | 162 | 14.3% | CIA vocabulary changes across decades |
| Dash Format | 64 | 5.7% | Inconsistent dash/hyphen formatting normalized |
| Consolidation | 49 | 4.3% | Multiple sub-fields merged under parent field |
| Manual | 7 | 0.6% | Case-sensitive backfill mappings added in v3.3 |

\begin{figure}[H]
\centering
\begin{tikzpicture}
  % Bars (scaled to max 6cm, largest to smallest)
  \fill[ciaBlue!55] (0, 4.2) rectangle (5.33, 4.7);
  \fill[ciaRed!45] (0, 3.4) rectangle (4.65, 3.9);
  \fill[ciaGreen!55] (0, 2.6) rectangle (2.78, 3.1);
  \fill[ciaGold!55] (0, 1.8) rectangle (2.43, 2.3);
  \fill[ciaAccent!45] (0, 1.0) rectangle (0.96, 1.5);
  \fill[ciaBlue!35] (0, 0.2) rectangle (0.74, 0.7);
  \fill[ciaDark!35] (0, -0.6) rectangle (0.11, -0.1);

  % Labels (left)
  \node[anchor=east, font=\scriptsize] at (-0.2, 4.45) {Country-Specific};
  \node[anchor=east, font=\scriptsize] at (-0.2, 3.65) {Noise};
  \node[anchor=east, font=\scriptsize] at (-0.2, 2.85) {Identity};
  \node[anchor=east, font=\scriptsize] at (-0.2, 2.05) {Rename};
  \node[anchor=east, font=\scriptsize] at (-0.2, 1.25) {Dash Format};
  \node[anchor=east, font=\scriptsize] at (-0.2, 0.45) {Consolidation};
  \node[anchor=east, font=\scriptsize] at (-0.2, -0.35) {Manual};

  % Values + percentages (right of bars)
  \node[anchor=west, font=\scriptsize\bfseries] at (5.43, 4.45) {355 (31.4\%)};
  \node[anchor=west, font=\scriptsize\bfseries] at (4.75, 3.65) {310 (27.4\%)};
  \node[anchor=west, font=\scriptsize\bfseries] at (2.88, 2.85) {185 (16.3\%)};
  \node[anchor=west, font=\scriptsize\bfseries] at (2.53, 2.05) {162 (14.3\%)};
  \node[anchor=west, font=\scriptsize\bfseries] at (1.06, 1.25) {64 (5.7\%)};
  \node[anchor=west, font=\scriptsize\bfseries] at (0.84, 0.45) {49 (4.3\%)};
  \node[anchor=west, font=\scriptsize\bfseries] at (0.21, -0.35) {7 (0.6\%)};

  % Axis
  \draw[line width=0.5pt, color=black!30] (0, -0.7) -- (0, 4.8);

  % Summary annotation
  \node[font=\footnotesize, color=black!50] at (3.2, -1.1) {1,132 mappings $\rightarrow$ 416 canonical names (2.72:1 ratio)};
\end{tikzpicture}
\caption{Field name canonicalization rule distribution. Country-specific fields (31.4\%) and parser noise (27.4\%) together account for over half of the 1,132 raw field name variants, underscoring the importance of automated classification in legacy data normalization.}
\label{fig:canon-rules}
\end{figure}

The high proportion of country-specific fields (31.4%) reflects the 1990s-era Factbook practice of including locally relevant fields that were later standardized.
The noise detection rate (27.4%) validates the importance of automated quality filtering --- without it, over a quarter of the field vocabulary would pollute query results.

### Most Widely Reported Fields

The 20 most frequently occurring canonical fields, each appearing in over 8,900 country-year records, represent the stable core of the Factbook's coverage model:

| Rank | Field | Occurrences | Coverage Rate |
|------|-------|-------------|--------------|
| 1 | Exchange rates | 13,891 | N/A* |
| 2 | Political parties | 13,524 | N/A* |
| 3 | Broadcast media | 11,539 | N/A* |
| 4 | Climate | 10,796 | N/A* |
| 5 | Area | 10,027 | N/A* |
| 6 | Population | 9,332 | 97.9% |
| 7 | Land boundaries | 9,321 | 97.7% |
| 8 | Internet users | 9,221 | 96.7% |
| 9 | Country name | 9,064 | 95.1% |
| 10 | Flag | 8,977 | 94.1% |

\small *Fields with sub-field variants may have occurrence counts exceeding the 9,536 country-year record total due to multiple raw name variants mapping to the same canonical name.\normalsize

Population --- arguably the Factbook's most important data point --- appears in 97.9% of all country-year records, confirming near-universal coverage for core demographic indicators.

## Geopolitical Event Tracking

The archive provides a unique longitudinal record of geopolitical change.
The following entities demonstrate how the archive captures state formation, dissolution, and reorganization events:

| Event | Year | Entities Affected |
|-------|------|------------------|
| Soviet Union dissolution | 1992 | 15 new states appear (Russia, Ukraine, Kazakhstan, etc.) |
| Yugoslav breakup (Phase I) | 1992 | Croatia, Slovenia, North Macedonia, Bosnia |
| Czechoslovak dissolution | 1993 | Czech Republic, Slovakia (Slovakia already present from 1990) |
| Eritrean independence | 1993 | Eritrea appears as independent state |
| Yugoslav breakup (Phase II) | 2006 | Serbia and Montenegro split into separate entries |
| Kosovar independence | 2008 | Kosovo appears |
| South Sudanese independence | 2011 | South Sudan appears |
| Netherlands Antilles dissolution | 2010 | Entity removed; Curacao and Sint Maarten appear |

These transitions are not merely bibliographic --- the archive preserves each entity's data on both sides of the transition, enabling researchers to analyze pre/post-independence economic trajectories, demographic shifts, and political restructuring.

## Development Metrics

### Velocity Analysis

The project was completed in a 17-day intensive development sprint, producing:

| Metric | Value |
|--------|-------|
| Total commits | 220+ |
| Average commits per day | 13 |
| Archive repository commits | 70+ (Feb 16--Mar 4) |
| Webapp repository commits | 150+ (Feb 22--Mar 4) |
| Peak day commits | 30+ (Feb 23: security, atlas, political dashboard) |

The commit history reveals a phased development pattern:

1. **Days 1--2 (Feb 16--17):** Core infrastructure --- ETL pipeline, database, GitHub Pages, initial webapp
2. **Days 3--5 (Feb 18--20):** Data quality --- 1996 repairs, Plotly-to-ECharts migration, licensing
3. **Days 7--9 (Feb 22--24):** Production hardening --- security, custom domain, mobile responsiveness
4. **Days 10--12 (Feb 25--27):** Feature expansion --- atlas tools, StarDict, encoding repair
5. **Days 13--14 (Feb 28--Mar 2):** Advanced analytics --- v3.2 release, CSI integration, dashboard builder
6. **Days 15--17 (Mar 3--4):** Data quality refinement --- v3.3 (IsComputed, FIPS/ISO fix), v3.4 (pipe-after-colon parser fix recovering 164,494 sub-values), webapp FieldValues migration

### Codebase Scale

| Component | Metric |
|-----------|--------|
| ETL parsers | 11 format-specific parsers + canonicalization layer |
| Web routes | 12+ router modules |
| Templates | 50+ Jinja2 HTML templates |
| API endpoints | 15+ JSON endpoints |
| CSS design system | 1 theme file (intel-theme.css) with 40+ component classes |
| JavaScript modules | ECharts theme, chart initializers, Alpine.js components |
| Database size | 656 MB (SQLite) |
| Indicator system | 102 queryable indicators across 11 categories |

## Data Validation and Quality Assurance

### Overall Data Integrity

The archive achieves exceptional data integrity across all validation dimensions.
Of the 1,071,603 records in the database, every record contains a populated content field --- a **100\% content completeness rate** with zero null or empty values.

| Validation Metric | Result | Rate |
|-------------------|--------|------|
| Content completeness (non-null, non-empty values) | 1,071,603 / 1,071,603 | 100.0\% |
| Source fragment provenance (FieldValues table) | 1,775,588 / 1,775,588 | 100.0\% |
| Encoding integrity (zero U+FFFD replacement characters) | 0 corrupted records | 100.0\% |
| Entity coverage (distinct geopolitical entities) | 281 / 281 expected | 100.0\% |
| Year coverage (distinct annual editions) | 36 / 36 expected | 100.0\% |
| Full temporal coverage (entities with all 36 years) | 215 / 281 entities | 76.5\% |

The 100\% source fragment coverage means that every parsed sub-field value in the database can be traced back to its original source text --- a critical provenance guarantee for a research platform handling intelligence data.

### Encoding Validation

A dedicated encoding repair pipeline (`scripts/repair_encoding_fffd.py`) was developed to detect and correct Unicode replacement characters (U+FFFD, displayed as ``\texttt{?}'') introduced during text format conversions across three decades of source material.

The repair process:

1. **Detection:** Scanned all 1,071,603 records for U+FFFD characters, identifying corrupted entries concentrated in the 1996 text-format edition
2. **Mapping:** Built a bad-character mapping (`data/bad_chars.json`) from corrupted byte sequences to their correct Unicode equivalents (accented characters, special symbols, currency signs)
3. **Repair:** Applied character-level replacements across all affected records
4. **Verification:** Post-repair scan confirmed **zero remaining U+FFFD characters** across all text columns (Content, TextVal, SourceFragment)

This yields a **100\% encoding integrity rate** --- no mojibake or garbled text exists anywhere in the production database.

### Structural Duplicate Analysis

The database contains 10,786 field-name groups with more than one record per country-year combination, accounting for 11,148 additional rows.
These are **structural artifacts**, not data errors.
They arise from the CIA's own editorial practice of publishing split-entity data in the 1990s:

- **Cyprus:** Separate "Greek area" and "Turkish area" sub-fields (up to 17 duplicated field groups in 1996)
- **Serbia and Montenegro:** Separate national sub-entries within the single "Yugoslavia" entity
- **Germany (1994):** Separate "eastern" and "western" sub-entries during post-reunification statistical integration

No deduplication was applied because the split-entity values represent distinct, meaningful data points that the CIA published intentionally.

### Per-Era Validation

Validation metrics broken down by source format era confirm consistent quality across all ingestion pipelines:

| Format Era | Records | Entities | Avg Fields/Entity | Content Rate |
|------------|---------|----------|--------------------|-------------|
| Text (1990--2001) | 260,663 | 267 | 63--108 | 100\% |
| HTML (2002--2020) | 628,559 | 281 | 102--140 | 100\% |
| JSON (2021--2025) | 182,048 | 260 | 125--153 | 100\% |

The text era covers 267 entities (vs. 281 for HTML) because 14 entities did not yet exist in the 1990s (e.g., South Sudan, Kosovo, Curacao).
The JSON era covers 260 entities because the CIA consolidated several minor territories when it transitioned to structured data feeds.

### Field Name Canonicalization Validation

The canonicalization pipeline (`etl/canonicalize.py`) maps 1,132 raw field name variants to 416 canonical names.
The mapping was validated through the following process:

1. **Noise filtering:** 310 mappings (27.4\%) were identified as parser artifacts and excluded from the canonical vocabulary, preventing query pollution
2. **Rename verification:** 162 mappings (14.3\%) represent CIA vocabulary changes across decades (e.g., "National product" $\rightarrow$ "GDP", "Communists" $\rightarrow$ retired). Each was manually reviewed against source documents
3. **Consistency check:** 185 mappings (16.3\%) are identity mappings where modern field names pass through unchanged, confirming parser accuracy for contemporary formats
4. **Consolidation audit:** 49 mappings (4.3\%) merge sub-field variants under parent fields, each verified against the CIA's own field restructuring timeline
5. **Manual backfill:** 7 mappings (0.6\%) were added in v3.3 for case-sensitive field name variants that automated rules missed

The resulting canonical vocabulary achieves a **2.72:1 compression ratio** while preserving all semantically distinct information.

### Year-over-Year Growth Validation

Records per year follow an expected growth curve from 15,750 (1990) to a peak of 39,714 (2021), with a slight decline in 2024--2025 as the CIA streamlined certain fields.
The 1994 data point (28,633 records vs. 18,509 in 1993) represents a known discontinuity: the CIA restructured its internal database that year, more than doubling field coverage per entity.
This spike was validated against the original source files and confirmed as authentic rather than a parser error.

### Sub-Field Parsing Validation

The ETL pipeline extracts 1,775,588 sub-field values from the 1,071,603 parent records, yielding an average of **1.66 sub-fields per record**.
Every sub-field row includes a `SourceFragment` column containing the original source text from which the value was parsed, enabling auditors to verify any extraction against its provenance.

The parser coverage rate is **97.6\%** --- meaning that of all fields with a registered dedicated parser, 97.6\% successfully produce at least one FieldValues row.
The remaining 2.4\% are fields with genuinely unparseable content (e.g., "NA", "none", or legacy format edge cases).

### FIPS/ISO Code Resolution (v3.3)

The CIA World Factbook uses FIPS 10-4 country codes internally, while the web application and most international standards use ISO 3166-1 Alpha-2 codes.
Of the 281 entities in the archive, **173 (61.6\%)** have different FIPS and ISO codes, including six direct collisions where one country's FIPS code equals another country's ISO code (e.g., FIPS ``SG'' = Senegal, ISO ``SG'' = Singapore).

Version 3.3 resolved a library integration issue where FIPS/ISO code lookups were failing silently, causing country-level joins to return NULL for affected entities.
The fix ensured that the web application consistently uses ISO Alpha-2 codes for all external references (GeoJSON joins, URL slugs, API responses) while preserving FIPS codes for internal Factbook data lookups.

### Pipe-After-Colon Parser Fix (v3.4)

A data quality audit following community feedback (GitHub Issues \#9, \#10, \#15) identified a pipe delimiter placement bug affecting approximately 135,000 fields primarily from the 2009--2014 HTML editions.

**Root cause.** The `parse\_collapsiblepanel\_format()` function in `build\_archive.py` extracted DOM labels and values as separate list items, then joined them with `' | '`.
This produced Content strings like:

\begin{verbatim}
total: | 9,826,675 sq km | land: | 9,161,966 sq km
\end{verbatim}

The pipe landed between the label colon and its value instead of between complete sub-fields.
All 28 dedicated parser functions use regex patterns like \texttt{total\textbackslash{}s*:?\textbackslash{}s*([\textbackslash{}d,]+)\textbackslash{}s*sq\textbackslash{}s*km} which could not match through the misplaced pipe character.

**Fix.** One line added to the `normalize\_content()` function in `parse\_field\_values.py`:

\begin{verbatim}
content = re.sub(r':\s*\|\s*', ': ', content)
\end{verbatim}

This regex strips pipes that appear immediately after colons --- a pattern that only occurs in the buggy Content, never in legitimate pipe-separated sub-fields.
Since every parser calls `normalize\_content()` first, this single change fixed all 28 dedicated parser functions and the generic fallback simultaneously.

**Impact.** The fix recovered **164,494 new sub-values**, increasing the total from 1,611,094 to 1,775,588 (+10.2\%).
The biggest improvements were in the 2009--2014 range, with individual years gaining 11,000--16,000 sub-values each.

\begin{figure}[H]
\centering
\begin{tikzpicture}[
    box/.style={rectangle, draw=#1, fill=#1!8, minimum width=5cm, minimum height=0.8cm, align=center, font=\footnotesize, rounded corners=3pt, line width=0.6pt},
    arr/.style={-{Stealth[length=2mm]}, line width=0.5pt, color=black!40},
]

% Before column
\node[font=\small\bfseries, color=ciaRed] at (-3.2, 3.2) {Before v3.4};

\node[box=ciaDark, text width=5cm] (bug) at (-3.2, 2.3) {\texttt{total: | 783,562 sq km}};
\node[font=\tiny, color=black!50] at (-3.2, 1.7) {Pipe between label and value};

\node[box=ciaRed, minimum width=4cm] (fail) at (-3.2, 0.7) {Regex cannot match\\through pipe character};

\node[box=ciaRed, minimum width=4cm] (zero) at (-3.2, -0.5) {\textbf{0 FieldValues}\\{\scriptsize $\sim$135,000 fields affected}};

\draw[arr] (bug) -- (fail);
\draw[arr] (fail) -- (zero);

% After column
\node[font=\small\bfseries, color=ciaGreen] at (3.2, 3.2) {After v3.4};

\node[box=ciaGold, text width=5cm] (fix) at (3.2, 2.3) {\texttt{total: 783,562 sq km}};
\node[font=\tiny, color=black!50] at (3.2, 1.7) {Pipe stripped by normalize\_content()};

\node[box=ciaGreen, minimum width=4cm] (pass) at (3.2, 0.7) {Regex matches\\value extracted};

\node[box=ciaGreen, minimum width=4cm] (values) at (3.2, -0.5) {\textbf{+164,494 sub-values}\\{\scriptsize 1,611,094 $\rightarrow$ 1,775,588 (+10.2\%)}};

\draw[arr] (fix) -- (pass);
\draw[arr] (pass) -- (values);

% Fix arrow connecting the two columns
\draw[arr, line width=1pt, color=ciaGold] (bug.east) -- node[above, font=\tiny\bfseries, color=ciaGold] {1-line fix} (fix.west);

\end{tikzpicture}
\caption{The v3.4 pipe-after-colon fix. Left: misplaced pipe characters in 2009--2014 HTML-era Content prevented parser regex patterns from matching. Right: a single-line addition to \texttt{normalize\_content()} strips pipes immediately following colons, enabling existing parsers to recover 164,494 sub-values (+10.2\%).}
\label{fig:v34-fix}
\end{figure}

### Summary

The archive's data quality profile --- 100\% content completeness, 100\% provenance tracing, 100\% encoding integrity, 97.6\% parser coverage, and 76.5\% full temporal coverage --- exceeds the standards typical of government open-data repositories.
The structural duplicates (1.04\% of records) are documented, intentional, and traceable to the CIA's own split-entity reporting practices.

## Historical Data Highlights

The archive's longitudinal scope enables researchers to trace major global transformations directly through the CIA's own reporting.
The following examples illustrate the kinds of historical analysis the archive makes possible.

### Population Shifts and Demographic Transitions

India's overtaking of China as the world's most populous country --- one of the most anticipated demographic events of the 21st century --- is captured year by year in the archive:

| Year | China | India | Gap |
|------|-------|-------|-----|
| 1990 | 1.118 billion | 850 million | 268 million |
| 2000 | 1.262 billion | 1.014 billion | 248 million |
| 2010 | 1.330 billion | 1.173 billion | 157 million |
| 2020 | 1.394 billion | 1.326 billion | 68 million |
| 2025 | 1.407 billion | 1.419 billion | India leads by 12 million |

Russia's population decline --- a consequence of post-Soviet economic collapse, emigration, and demographic contraction --- is equally visible: from 293 million (Soviet Union, 1991) to 146 million (Russia, 2000) to 140 million (2025), a sustained 35-year decline unique among major powers.

### Economic Transformation: The Rise of China

China's GDP (purchasing power parity) trajectory, as reported by the CIA, documents the most dramatic economic ascent in modern history:

| Year | China GDP (PPP) | US GDP (PPP) | Ratio |
|------|----------------|-------------|-------|
| 1995 | \$2.98 trillion | \$6.74 trillion | 0.44 |
| 2005 | \$7.26 trillion | \$11.75 trillion | 0.62 |
| 2015 | \$17.62 trillion | \$17.42 trillion | 1.01 |
| 2025 | \$33.60 trillion | \$25.68 trillion | 1.31 |

The archive captures the exact year the CIA first assessed China's PPP-adjusted economy as surpassing the United States (2015 edition), a milestone that remains contested by other measurement methodologies.

### The Digital Revolution

Internet adoption data across 36 years documents the fastest infrastructure deployment in human history:

| Country | 2005 | 2010 | 2015 | 2020 | 2025 |
|---------|------|------|------|------|------|
| United States | 159M | 245M | 277M (87\%) | 286M (87\%) | 93\% |
| China | 94M | 389M | 627M (46\%) | 752M (54\%) | 78\% |
| India | 18M | 61M | 237M (19\%) | 447M (34\%) | 56\% |

China went from 94 million internet users in 2005 to 389 million in just five years --- adding the equivalent of the entire U.S. internet population annually.
India's digital trajectory, starting later but accelerating faster, added 400 million users between 2010 and 2020.

### The Soviet Union: A Superpower's Final Assessment

The archive's most historically significant entries may be its Soviet Union records.
The 1990 and 1991 editions represent the CIA's final assessments of the USSR as a functioning state --- intelligence snapshots of a superpower in its last months.

The 1990 entry describes a **"Communist state"** with a GNP of \$2.66 trillion, 290 million people across 22.4 million km$^2$ (2.5 times the size of the US), and "about 19 million party members."
The economy was assessed at "real growth rate 1.4\%" --- a figure the CIA itself flagged as based on reconstructed Soviet statistics.

By the 1991 edition, the entry had already changed: government type was reclassified from "Communist state" to **"in transition to multiparty federal system,"** Communist Party membership had dropped from 19 million to 15 million "with membership declining," the national holiday was still listed as "Great October Socialist Revolution, 7--8 November (1917)," and defense expenditures were reported as "63.9 billion rubles" --- with the telling notation "NA\% of GDP."

Unique Cold War-era fields preserved in the Soviet entries include:

- **"Civil air: 4,000 major transport aircraft"** --- a military-intelligence-relevant metric not tracked for Western nations
- **"Communists: about 19 million party members"** (1990), declining to "about 15 million" (1991)
- **"Strategic Rocket Forces"** listed as a military branch alongside Ground Forces, Navy, and Air Defense
- **"Organized labor: 98\% of workers are union members"** --- reflecting state-controlled trade unionism
- **"Illicit drugs: illegal producer of cannabis and opium poppy, mostly for domestic consumption"** --- a rare admission in Soviet-era intelligence
- **Leningrad** appears in the 1990 ports list; by 1991 it had been renamed to **St. Petersburg**

The 1991 edition is the Soviet Union's final Factbook appearance.
By the 1992 edition, the USSR entry vanishes entirely and 15 successor states appear: Russia, Ukraine, Belarus, Kazakhstan, Uzbekistan, Turkmenistan, Kyrgyzstan, Tajikistan, Azerbaijan, Armenia, Georgia, Moldova, Latvia, Lithuania, and Estonia --- each with its own data compiled from the wreckage of Soviet statistical systems.

### Cold War Vocabulary: Fields That Disappeared

The archive preserves entire categories of intelligence that the CIA stopped tracking after the Cold War ended.
Over 30 field names used in the 1990--1996 era were subsequently retired, reflecting shifting geopolitical priorities:

| Field | Years Active | Description |
|-------|-------------|-------------|
| Communists | 1990--1996 | Communist party membership (tracked for all nations) |
| Type | 1990--1995 | Government classification ("Communist state," "republic," etc.) |
| National product | 1993--1995 | Pre-GDP economic metric using Soviet-style accounting |
| Digraph | 1992--1995 | Two-letter intelligence classification codes |
| Data code | 1996--2000 | FIPS country codes used in intelligence databases |
| Long-form name | 1990--1992 | Full formal names (e.g., "Union of Soviet Socialist Republics") |
| Civil air | 1990--1995 | Military-relevant count of civilian transport aircraft |

These fields document a world the CIA no longer needs to measure --- a world of Communist party memberships, ruble-denominated GNPs, and military manpower calculations designed for Cold War contingency planning.

### Germany, Yugoslavia, and Czechoslovakia: Fragmentation and Reunification

The archive captures three of the 20th century's most consequential border changes:

**German Reunification (1990--1991).** The 1990 Factbook lists "Germany, Federal Republic of" (West Germany) with 73 data fields.
By 1991, the entry becomes simply "Germany" --- reflecting the October 3, 1990 reunification.
The initial unified entry has only 52 fields, as the CIA scrambled to merge two datasets; by 1994, coverage had expanded to 144 fields as the combined nation's statistics stabilized.

**Yugoslav Dissolution (1990--2008).** Yugoslavia appears as a single entry through 1991 (71 fields).
In 1992, it becomes "Serbia and Montenegro" (76 fields), while Croatia, Slovenia, Bosnia, and North Macedonia emerge as new entries.
The archive traces the full 16-year fragmentation: Serbia and Montenegro split into separate entries in 2006, and Kosovo appears independently in 2008 --- completing a process that produced seven sovereign states from one.

**Czechoslovak Dissolution (1990--1993).** Czechoslovakia appears through 1992 (76 fields).
In 1993, it splits cleanly into Czech Republic (79 fields) and Slovakia.
The Czech Republic was later renamed to Czechia in the 2016 edition.

### State Formation and Dissolution

Beyond the Cold War transitions, the archive captures state formation events across the full 36-year span.
South Sudan's first appearance (2011) shows placeholder data fields, filled progressively as the new nation's statistical infrastructure developed.
The Netherlands Antilles dissolves in 2010, spawning separate entries for Curacao and Sint Maarten.
Timor-Leste appears in 2002 following its independence referendum.

## Comparative Context

No directly comparable system exists in the open-source landscape.
While individual Factbook snapshots are available from the CIA's website (current year only), the Internet Archive (fragmented), and academic datasets (typically covering 5--10 years of a few indicators), no other project provides:

- All 36 editions (1990--2025) in a single queryable database
- Cross-year field name normalization enabling longitudinal queries
- An interactive web application with visualization, comparison, and atlas tools
- Full-text search across over one million records
- A documented ETL pipeline capable of parsing 12+ distinct source formats

The closest alternatives --- the World Bank's World Development Indicators database and the UN Statistics Division --- cover similar indicators but draw from their own survey methodologies rather than the CIA's unique intelligence-sourced compilation.
The Factbook Archive thus fills a distinct niche: preserving the U.S. Intelligence Community's own assessment of global conditions, year by year, before the publication was discontinued.

\newpage

# Limitations and Future Work

## Known Limitations

### Data Source Constraints

- **CIA editorial decisions.** The archive preserves the CIA's assessments, which may differ from other sources (World Bank, UN, IMF). The Factbook's population and GDP figures occasionally diverge from international consensus estimates, particularly for closed societies (North Korea, Eritrea) where the CIA applies its own intelligence-derived adjustments.
- **Discontinued fields.** Over 30 field categories tracked in the 1990s were subsequently retired (e.g., "Communists," "Civil air," "Digraph"). These fields have no modern equivalents, creating temporal discontinuities in longitudinal analysis.
- **Entity name instability.** Countries change names (Burma $\rightarrow$ Myanmar, Swaziland $\rightarrow$ Eswatini, Czech Republic $\rightarrow$ Czechia), and the archive's canonicalization layer must map across these transitions. Edge cases may exist where a name change was not fully captured.
- **Factbook discontinuation.** The CIA announced the discontinuation of the World Factbook in February 2026. The 2025 edition is the final edition, closing the archive at 36 years. No future data will be available for ingestion.

### Technical Constraints

- **Single-region deployment.** The application runs on a single Fly.io machine in the `iad` (US East) region. Users in Asia-Pacific or Europe experience higher latency on uncached requests.
- **SQLite concurrency.** While SQLite handles the read-only workload well, it does not support concurrent write operations. The archive's read-only nature makes this acceptable, but it precludes user-contributed annotations or corrections.
- **Per-worker cache isolation.** Each Uvicorn worker maintains its own independent TTL cache. With 2 workers, the same query may be computed twice on first access.
- **World Leaders temporal coverage.** The `world_leaders_structured.sqlite` database contains only the most recent leadership rosters (circa 2025--2026). Historical leadership data is not available because the CIA directory is a point-in-time publication.

### Parser Limitations

- **1990 format ambiguity.** The `old` text format (1990) uses minimal structural markup, making field boundary detection heuristic rather than deterministic. Some multi-paragraph field values may be incorrectly split.
- **HTML table extraction.** The 2002--2020 HTML formats use deeply nested `<div>` structures that occasionally produce extraneous whitespace or concatenated field values. The canonicalization layer filters most artifacts, but edge cases may persist.
- **Numeric value extraction.** The indicator system extracts numeric values from free-text fields using regex patterns. Unusual formatting (e.g., "approximately 3 million" vs. "3,000,000") may cause extraction failures for specific country-year combinations. The v3.4 pipe-after-colon fix resolved the largest class of such failures (164,494 sub-values recovered), but edge cases may persist in legacy formats.

## Future Work

### Data Enhancements

- **Cross-reference with World Bank WDI.** Link Factbook indicators to their World Bank equivalents, enabling side-by-side comparison of CIA assessments vs. international organization data.
- **Historical leadership integration.** Extend the World Leaders database backward using archived CIA directories (if obtainable), enabling longitudinal analysis of cabinet composition changes.
- **Structured sub-field expansion.** The v3.4 parser fix brought coverage to 97.6\%, but additional free-text fields (e.g., "Military branches," "Political parties and leaders") could be parsed into structured, queryable sub-fields with dedicated parsers.

### Platform Enhancements

- **Multi-region deployment.** Deploy read replicas in European and Asia-Pacific regions to reduce latency for international users.
- **User annotations.** Allow authenticated researchers to flag data quality issues or add contextual notes to specific country-year records without modifying the underlying database.
- **Export API expansion.** Add bulk export endpoints for researcher-defined indicator baskets in CSV, JSON, and Parquet formats.
- **Advanced chart types.** Add radar/spider charts (country profile overlays), distribution box plots (indicator spread by region), and parallel coordinate plots (multi-indicator outlier detection).

\newpage

# Credits and Acknowledgments

## Data Sources

- **Central Intelligence Agency.** *The World Factbook.* Washington, DC: CIA, 1990--2025. Public domain.
- **University of Missouri.** Historical Factbook text file archive (1990s editions).
- **Internet Archive / Wayback Machine.** Historical CIA.gov HTML snapshots (2000--2020).
- **factbook-json-cache.** GitHub repository providing structured JSON snapshots (2021--2025).
- **IP2Location.** LITE geolocation database for visitor analytics.
- **Natural Earth.** GeoJSON boundary data for atlas visualization.

## Open-Source Libraries

| Library | Role |
|---------|------|
| FastAPI | Web framework |
| Jinja2 | Template engine |
| Uvicorn | ASGI server |
| SQLite / FTS5 | Database and full-text search |
| Apache ECharts | Interactive charting |
| Mapbox GL JS | 3D globe and map rendering |
| Beautiful Soup | HTML parsing |
| Alpine.js | Lightweight frontend interactivity |
| openpyxl | Excel export generation |

## Contributors

- **Milan Milkovich, MLIS** --- Project creator, ETL pipeline development, web application development, infrastructure deployment, and design.
- **Claude (Anthropic)** --- AI development partner for ETL pipeline engineering, web application features, security architecture, database optimization, documentation, and code review across 200+ development sessions.
- Community members who reported issues and suggested improvements via GitHub Issues.

## Contact

- **Website:** [https://worldfactbookarchive.org](https://worldfactbookarchive.org)
- **GitHub:** [https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025)

\newpage

# Glossary of Acronyms

| Acronym | Definition |
|---------|-----------|
| AFRICOM | United States Africa Command |
| API | Application Programming Interface |
| ASGI | Asynchronous Server Gateway Interface |
| AUKUS | Australia, United Kingdom, United States (security pact) |
| CENTCOM | United States Central Command |
| CIA | Central Intelligence Agency |
| COCOM | Combatant Command (US military geographic command structure) |
| CSI | Center for the Study of Intelligence (CIA) |
| CSS | Cascading Style Sheets |
| CSV | Comma-Separated Values |
| DEM | Digital Elevation Model |
| DNS | Domain Name System |
| EEZ | Exclusive Economic Zone |
| ERD | Entity-Relationship Diagram |
| ETL | Extract, Transform, Load |
| EUCOM | United States European Command |
| FIPS | Federal Information Processing Standards |
| FTS5 | Full-Text Search version 5 (SQLite extension) |
| GDP | Gross Domestic Product |
| GNP | Gross National Product |
| IAEA | International Atomic Energy Agency |
| ICBM | Intercontinental Ballistic Missile |
| INDOPACOM | United States Indo-Pacific Command |
| IRBM | Intermediate-Range Ballistic Missile |
| JSON | JavaScript Object Notation |
| LRU | Least Recently Used (cache eviction policy) |
| MRBM | Medium-Range Ballistic Missile |
| NATO | North Atlantic Treaty Organization |
| NER | Named Entity Recognition |
| NORTHCOM | United States Northern Command |
| OSINT | Open-Source Intelligence |
| PPP | Purchasing Power Parity |
| PRIS | Power Reactor Information System (IAEA) |
| SCO | Shanghai Cooperation Organisation |
| SOUTHCOM | United States Southern Command |
| SRBM | Short-Range Ballistic Missile |
| SQL | Structured Query Language |
| SSL | Secure Sockets Layer |
| TEL | Transporter Erector Launcher (mobile missile platform) |
| TLS | Transport Layer Security |
| TOC | Table of Contents |
| TTL | Time-to-Live (cache expiration policy) |
| UCDP | Uppsala Conflict Data Program |
| USGS | United States Geological Survey |
| UTC | Coordinated Universal Time |
| VIIRS | Visible Infrared Imaging Radiometer Suite (NASA) |
| WAF | Web Application Firewall |
| WAL | Write-Ahead Logging (SQLite journal mode) |
| WDI | World Development Indicators (World Bank) |

---

*This report was prepared as part of the CIA World Factbook Archive project documentation.*
*Generated March 5, 2026.*
