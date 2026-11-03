# Official template mapping

Owner: captain report editor. Rebuild when report.md or figure data changes.
Template: official-template.docx (retained copy of the user supplied template).
SHA256: d15a2aa186f600cb9c234bffd9deff0c4e9b05c569643d8a81d536f66f424f0c
Source-code review snapshot: 87ff28c011806f5e5fcf86b741c8f4caa55c7f5e

A4, one section; margins top/bottom 1440 twips, left/right 1800 twips.
Header distance 851 twips; footer 992 twips. Body width 8306 twips.
Preserve the official purple FPGA header image, horizontal rule, all header/footer
parts and relationships, styles, numbering, themes and original media byte-for-byte.
Preserve section geometry and the original PAGE fields. Word exports update page
numbers in the PDF; the original DOCX field definitions remain intact.

Editable slots: title, abstract, five main sections and their original subsections.
Use the template's 18 pt centered title, 14 pt bold main headings, 12 pt body,
Song Chinese type with Times New Roman Latin text and 1.5 body line spacing.
Main headings keep their template wording. Subheading numbers are explicit text
to avoid inheriting the template's instruction-list numbering.
Additional cloned body paragraphs, tables, equations, figures and captions are
allowed inside the original slots. Tables use 10.5 pt text for numeric comparison.
New figures use 9–11 pt equivalent labels at final width and editable SVG sources.

Three real-photo slots are intentionally reserved and explicitly marked in this
review draft because the team has not taken photographs. No illustrative image
is presented as an actual photograph. This draft requires those images before
submission. Refer to README.md for the exact shooting checklist.

Renderer: packaged render_docx.py was attempted; LibreOffice was absent.
Fallback: isolated hidden Microsoft Word COM PDF export, then pypdfium2 page
rendering and visual inspection. Original template is opened read-only.
