---
title: |
  CIA World Factbook Archive\
  \vspace{0.3cm}
  \large Executive Summary
author: Milan Milkovich, MLIS
date: March 5, 2026
documentclass: article
geometry: margin=1in
fontsize: 11pt
header-includes:
  - \usepackage{booktabs}
  - \usepackage{longtable}
  - \usepackage{array}
  - \usepackage{graphicx}
  - \usepackage{hyperref}
  - \usepackage{fancyhdr}
  - \usepackage{xcolor}
  - \usepackage{float}
  - \usepackage{tikz}
  - \usetikzlibrary{arrows.meta, positioning, shapes.geometric}
  - \definecolor{ciaBlue}{HTML}{2D72D2}
  - \definecolor{ciaDark}{HTML}{1C2127}
  - \definecolor{ciaAccent}{HTML}{48AFF0}
  - \definecolor{ciaGreen}{HTML}{29A634}
  - \definecolor{ciaGold}{HTML}{F0B726}
  - \definecolor{ciaRed}{HTML}{CD4246}
  - \hypersetup{colorlinks=true, linkcolor=ciaBlue, urlcolor=ciaBlue}
  - \pagestyle{fancy}
  - \fancyhead[L]{\small CIA World Factbook Archive}
  - \fancyhead[R]{\small Executive Summary}
  - \fancyfoot[C]{\thepage}
  - \renewcommand{\headrulewidth}{0.4pt}
  - \setlength{\parskip}{0.5em}
  - \setlength{\parindent}{0pt}
---

## The Problem

On **February 4, 2026**, the CIA discontinued the *World Factbook* --- its flagship open-source intelligence reference covering every country and territory in the world.
Published annually since 1962, the Factbook had served as the de facto standard for geopolitical, demographic, economic, and military data.
No centralized archive existed that preserved historical editions in structured, machine-readable form.

## The Solution

The **CIA World Factbook Archive** is a digital preservation and analytics platform that ingests, normalizes, and visualizes **36 years** of the World Factbook (1990--2025).
Built in a 17-day development sprint, it is the only publicly available system that makes every edition queryable, comparable, and downloadable.
No comparable platform exists --- the World Bank WDI and UN Statistics Division cover similar indicators but draw from their own methodologies, not the CIA's intelligence-sourced assessments.

The archive is designed for researchers, journalists, students, educators, and policymakers who need longitudinal access to intelligence-grade geopolitical data.
All source data is U.S. government public domain, and the platform's code is open source.

\begin{table}[H]
\centering
\begin{tabular}{ll}
\toprule
\textbf{Metric} & \textbf{Value} \\
\midrule
Geopolitical entities & 281 (countries, territories, oceans, world) \\
Annual editions & 36 (1990--2025) \\
Country-year records & 9,536 \\
Data points (fields) & 1,071,603 \\
Structured sub-values & 1,775,588 \\
Distinct sub-field types & 2,599 \\
Source format variants & 12 (6 text, 5 HTML, 1 JSON) \\
Field name variants & 1,132 $\rightarrow$ 416 canonical names \\
Database size & 656 MB (SQLite) \\
Parser coverage & 97.6\% \\
Content completeness & 100\% \\
\bottomrule
\end{tabular}
\end{table}

## Technical Architecture

**ETL Pipeline.** Eleven format-specific parsers ingest raw source material spanning six plain text formats (1990--2001), five HTML layouts (2002--2020), and structured JSON (2021--2025).
A canonicalization layer maps 1,132 raw field name variants to 416 standardized names, and 28 dedicated sub-field parsers extract 1,775,588 typed values (numeric, text, date, rank) into a queryable FieldValues table.

**Database.** A normalized SQLite schema with six core tables, full-text search (FTS5), and optimized indexes.
Every parsed sub-value includes a SourceFragment column preserving the original source text for 100\% provenance traceability.

**Web Application.** FastAPI + Jinja2 + Apache ECharts + Mapbox GL JS, deployed on Fly.io with Cloudflare CDN.
The "Dark Intelligence" design system provides a consistent visual identity across all pages.

## Key Features

\begin{table}[H]
\centering
\small
\begin{tabular}{p{3.5cm} p{9.5cm}}
\toprule
\textbf{Feature} & \textbf{Description} \\
\midrule
Country Browser & Browse any country's Factbook entry for any year (1990--2025). Side-by-side year comparison with text diff highlighting. \\[4pt]
Trend Analysis & Multi-country line charts for 102 indicators across 36 years. \\[4pt]
Rankings & Ranked tables and bar charts for any indicator and year, filterable by region. \\[4pt]
Intelligence Atlas & Full-screen 3D globe with 27 data layers: military installations, nuclear facilities, missile ranges, mining sites, submarine cables, shipping routes, COCOM regions, night lights, and more. 6 analytical tools including distance/area measurement and timelapse recording. \\[4pt]
Dashboard Builder & Drag-and-drop canvas with 10 widget types (KPI cards, time series, scatter plots, comparison tables, mini globes). Pre-built presets and JSON export/import. \\[4pt]
Data Explorer & Custom SQL-like queries across 102 indicators with CSV export. \\[4pt]
CSI Library & Full-text search across 1,034 CIA \textit{Studies in Intelligence} journal articles (1992--2025). \\[4pt]
World Leaders & 5,696 leadership records across 193 countries from the CIA Chiefs of State directory. \\
\bottomrule
\end{tabular}
\end{table}

## Data Quality

The archive achieves exceptional data integrity:

- **100\%** content completeness --- zero null or empty values across 1,071,603 records
- **100\%** provenance tracing --- every sub-value links to its original source text
- **100\%** encoding integrity --- zero Unicode replacement characters after repair
- **97.6\%** parser coverage --- sub-field extraction succeeds on nearly all eligible fields
- **76.5\%** full temporal coverage --- 215 of 281 entities have all 36 years of data

## Historical Significance

The archive captures major geopolitical events through the CIA's own assessments:

- **Soviet Union dissolution** (1991): Final CIA assessments of the USSR, including Cold War-era fields like "Communists: 19 million party members" and "Strategic Rocket Forces"
- **China's economic rise**: The exact year the CIA assessed China's PPP-adjusted GDP as surpassing the US (2015 edition)
- **India overtakes China** in population: 1.419B vs 1.407B in the 2025 edition
- **Yugoslav fragmentation** (1991--2008): Seven successor states tracked from emergence through stabilization
- **30+ retired field categories**: Cold War intelligence metrics that disappeared after 1996

## Access

\begin{table}[H]
\centering
\begin{tabular}{ll}
\toprule
\textbf{Resource} & \textbf{URL} \\
\midrule
Live Application & \url{https://worldfactbookarchive.org} \\
Source Code & \url{https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025} \\
Full Report (62 pages) & Available in the \texttt{research-report/} directory \\
\bottomrule
\end{tabular}
\end{table}

\vspace{0.5cm}

\noindent\textit{This executive summary accompanies the full project report (62 pages) which details the ETL pipeline, parsing methodology, database design, web application architecture, data validation, and historical analysis.}

\vspace{0.3cm}

\noindent\textbf{Author:} Milan Milkovich, MLIS\quad\textbf{AI Partner:} Claude (Anthropic)\quad\textbf{Date:} March 5, 2026
