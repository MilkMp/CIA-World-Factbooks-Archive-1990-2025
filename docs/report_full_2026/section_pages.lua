-- Begin each numbered report section and appendix on a fresh page.
-- Use concise entries in the list of figures while retaining full captions.
local figure_titles = {
  ["01-source-timeline.pdf"] = "Source formats across 36 editions",
  ["02-country-years.pdf"] = "Country-year entries by edition",
  ["03-field-rows.pdf"] = "Stored field rows by edition",
  ["04-entry-distribution.pdf"] = "Field rows per entry: median and middle half",
  ["05-field-names.pdf"] = "Distinct original field labels by edition",
  ["06-categories-2025.pdf"] = "2025 field rows by source category",
  ["07-entity-editions.pdf"] = "Edition coverage per canonical entity",
  ["08-mapping-types.pdf"] = "Field-label mapping types",
  ["09-field-values.pdf"] = "Stored fields and parsed sub-values by edition",
  ["10-numeric-share.pdf"] = "Numeric sub-values by edition",
  ["11-computed-values.pdf"] = "Computed sub-values by edition",
  ["12-validation-l1.pdf"] = "L1 literal fragment hits by edition",
  ["13-validation-l3.pdf"] = "L3 matching share by edition",
  ["14-provenance-pipeline.pdf"] = "Source-to-product provenance pipeline",
  ["15-final-estimate-tokens.pdf"] = "Estimate-year tokens in 2025 fields",
  ["16-source-bytes.pdf"] = "Source files by format and bytes",
}

function Header(el)
  if el.level ~= 1 then
    return el
  end
  return {pandoc.RawBlock("latex", "\\clearpage"), el}
end

function Figure(el)
  local paragraph = el.content[1]
  local image = paragraph and paragraph.content and paragraph.content[1]
  local src = image and image.src
  local filename = src and src:match("([^/]+)$")
  local title = filename and figure_titles[filename]
  if title then
    el.caption.short = pandoc.read(title, "markdown").blocks[1].content
  end
  return el
end
