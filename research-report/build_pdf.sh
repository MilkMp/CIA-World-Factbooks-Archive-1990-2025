#!/usr/bin/env bash
# Build the research report PDF from PROJECT_REPORT.md using pandoc + XeLaTeX.
#
# Prerequisites:
#   - Pandoc:  C:\Users\milan\AppData\Local\Pandoc\pandoc.exe
#   - MiKTeX:  C:\Users\milan\AppData\Local\Programs\MiKTeX\miktex\bin\x64\xelatex.exe
#
# Usage:
#   bash research-report/build_pdf.sh          # from repo root
#   bash build_pdf.sh                          # from research-report/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPORT_MD="$SCRIPT_DIR/PROJECT_REPORT.md"

# Auto-increment version number based on existing PDFs
LATEST=$(ls "$SCRIPT_DIR"/PROJECT_REPORT_v*.pdf 2>/dev/null \
    | sed 's/.*_v\([0-9]*\)\.pdf/\1/' \
    | sort -n \
    | tail -1)
NEXT_VERSION=$(( ${LATEST:-0} + 1 ))
OUTPUT_PDF="$SCRIPT_DIR/PROJECT_REPORT_v${NEXT_VERSION}.pdf"

# Add pandoc and MiKTeX to PATH
export PATH="/c/Users/milan/AppData/Local/Pandoc:/c/Users/milan/AppData/Local/Programs/MiKTeX/miktex/bin/x64:$PATH"

echo "Building: PROJECT_REPORT_v${NEXT_VERSION}.pdf"
echo "Source:   $REPORT_MD"
echo "Output:   $OUTPUT_PDF"
echo ""

pandoc "$REPORT_MD" \
    -o "$OUTPUT_PDF" \
    --pdf-engine=xelatex \
    --pdf-engine-opt=-interaction=nonstopmode

SIZE=$(du -h "$OUTPUT_PDF" | cut -f1)
echo ""
echo "Done: $OUTPUT_PDF ($SIZE)"
