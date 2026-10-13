// Pandoc Typst template for paper/paper.pdf.
//
// Single column, Libertinus Serif, numbered sections, captions above tables, IEEE-style
// numeric references (pandoc --citeproc with paper/ieee.csl). The fonts named here ship
// inside Typst itself, so the build has no font dependency on the machine.
//
// Pandoc fills the dollar-delimited variables from the YAML front matter of paper/paper.md and the body
// from the Markdown. Nothing in this file is prose: every number in the paper comes from
// results/summary.json via paper/paper.md.in.

#set document(
  title: [$title$],
  author: ($for(author)$"$author$"$sep$, $endfor$),
)

#set page(
  paper: "a4",
  margin: (top: 2.4cm, bottom: 2.4cm, left: 2.3cm, right: 2.3cm),
  numbering: "1",
  number-align: center,
  header: context {
    if counter(page).get().first() > 1 [
      #set text(size: 7.5pt, fill: luma(110))
      #align(center)[$if(running-title)$$running-title$$else$$title$$endif$]
    ]
  },
)

#set text(font: "Libertinus Serif", size: 10pt, lang: "en", region: "GB")
#set par(justify: true, leading: 0.58em, spacing: 0.85em, first-line-indent: 0pt)
#set heading(numbering: "1.1")
#set list(indent: 0.8em, spacing: 0.55em)
#set enum(indent: 0.8em, spacing: 0.55em)
#set footnote.entry(separator: line(length: 25%, stroke: 0.4pt + luma(140)))

#show heading.where(level: 1): it => block(above: 1.7em, below: 0.75em)[
  #set text(size: 13pt, weight: "bold")
  #it
]
#show heading.where(level: 2): it => block(above: 1.35em, below: 0.6em)[
  #set text(size: 11pt, weight: "bold")
  #it
]
#show heading.where(level: 3): it => block(above: 1.1em, below: 0.5em)[
  #set text(size: 10pt, weight: "semibold", style: "italic")
  #it
]

#show raw: set text(font: "DejaVu Sans Mono", size: 8.3pt)
#show raw.where(block: true): it => block(
  width: 100%,
  fill: luma(247),
  inset: 7pt,
  radius: 2pt,
  it,
)

#show link: set text(fill: rgb("#1f3f73"))
#show quote: set block(inset: (left: 1.2em, right: 1.2em), above: 0.9em, below: 0.9em)
#show quote: set text(size: 9.2pt)

// Tables: caption above, header rule, light rules between rows, no vertical rules.
#show figure.where(kind: table): set figure.caption(position: top)
#show figure.where(kind: table): set block(breakable: true)
#show figure.caption: set text(size: 8.6pt)
#show figure.caption: it => block(inset: (x: 1em))[#it]
#set table(
  inset: (x: 5pt, y: 4pt),
  align: left + horizon,
  stroke: (x, y) => (
    bottom: if y == 0 { 0.6pt + black } else { 0.3pt + luma(200) },
  ),
)
#show table.cell.where(y: 0): set text(weight: "semibold", size: 8.4pt)
#show table.cell: set text(size: 8.4pt)

// Figures: centred, caption below, kept whole.
#show figure.where(kind: image): set figure.caption(position: bottom)
#show figure.where(kind: image): set block(breakable: false)
#show image: it => align(center, it)

// Bibliography block emitted by citeproc.
#show <refs>: set text(size: 8.8pt)

$if(header-includes)$
$header-includes$
$endif$

// ------------------------------------------------------------------ title block
#align(center)[
  #block(width: 92%)[
    #set par(justify: false, leading: 0.5em)
    #text(size: 16.5pt, weight: "bold")[$title$]
  ]
  #v(1.0em)
  #text(size: 11pt)[$for(author)$$author$$sep$, $endfor$]
  $if(subtitle)$
  #v(0.5em)
  #text(size: 9.5pt, fill: luma(70))[$subtitle$]
  $endif$
  $if(date)$
  #v(0.2em)
  #text(size: 9pt, fill: luma(110))[$date$]
  $endif$
]
#v(1.4em)

$if(abstract)$
#block(inset: (x: 1.6em))[
  #set text(size: 9.4pt)
  #set par(justify: true)
  #text(weight: "bold")[$if(abstract-title)$$abstract-title$$else$Abstract$endif$]
  #h(0.7em)
  $abstract$
]
#v(1.2em)
$endif$

$if(keywords)$
#block(inset: (x: 1.6em))[
  #set text(size: 8.8pt, fill: luma(70))
  #text(weight: "semibold")[Keywords] #h(0.6em) $for(keywords)$$keywords$$sep$ · $endfor$
]
#v(1.0em)
$endif$

$if(toc)$
#outline(depth: $toc-depth$, indent: 1em)
#v(1em)
$endif$

$body$

$for(include-after)$
$include-after$
$endfor$
