# Source manifest

All primary documents were downloaded directly from mas.gov.sg on 2026-10-13 using `curl` with a
browser user-agent (the MAS site returns 403 to default `curl`). Text extracts under `text/` were
produced with PyMuPDF (`page.get_text("text")`) and carry `===== PAGE n =====` markers so that
every citation in this repository can be traced back to a page of the primary PDF.

Verify with: `cd docs/sources && shasum -a 256 -c SHA256SUMS`

| File | Description | Date | SHA-256 |
|---|---|---|---|
| `mas_airm_guidelines_2026-10-07.pdf` | **Guidelines on Artificial Intelligence Risk Management** (final, 30 pp). Primary ground truth for every `MAS-AIRM §x.y` citation. | 2026-10-07 | `d9a4095569da34078e2cd597cc992910e63cf88471c59cb654c0413dbaed5c6d` |
| `mas_response_to_feedback_P017-2025_2026-10-07.pdf` | Response to Feedback Received on Guidelines on AI Risk Management, P017-2025 (57 pp) | 2026-10-07 | `6b19d61f66bda4e4537f3566eb4eeb949eab739de85f3f3854536b092e43fa0a` |
| `mas_consultation_paper_P017-2025_2025-11-13.pdf` | Consultation Paper on Guidelines on AI Risk Management, P017-2025 (30 pp, includes draft Guidelines and Annex) | 2025-11-13 | `bcdc6fd8938ae0acd337a0aca00bc658bce8ebd9ed3e7edbe1113e795cb6f40f` |
| `mas_consultation_annex_b_submissions.pdf` | Annex B — published submissions to P017-2025 (325 pp) | 2026-10-07 | `69b75a77e52a83a8f18fc239462a629d5ff384c4396f9478e549df53409a3aa3` |
| `mas_info_paper_ai_model_risk_management_2024-12.pdf` | Information Paper on Artificial Intelligence Model Risk Management (50 pp) | 2024-12 | `757d3eba9361932021b84a817db6e370ecdf0126bc88700d7d3b09e9b341865e` |
| `mas_feat_principles_2018.pdf` | Principles to Promote Fairness, Ethics, Accountability and Transparency (FEAT) in the Use of AI and Data Analytics in Singapore's Financial Sector (15 pp) | 2018-11 | `3934194d3d17a435124f514583c337432ce002b9c6fbef736d4f33849cf3d299` |
| `mas_veritas_doc3_feat_assessment_methodology_2022.pdf` | Veritas Document 3 — FEAT Principles Assessment Methodology (59 pp) | 2022-02 | `fff1d5d58eacc64f26dc6c78a0d300899651797e9db92460d9868d801652fb64` |
| `mas_veritas_doc3a_fairness_methodology_2022.pdf` | Veritas Document 3A — FEAT Fairness Principles Assessment Methodology (71 pp) | 2022-02 | `996aecb1a7dbb666b6d15bc1a240e8ab723bba55eb8ee7d466f6c09686181763` |
| `mas_veritas_doc3c_transparency_methodology_2022.pdf` | Veritas Document 3C — FEAT Transparency Principles Assessment Methodology (45 pp) | 2022-02 | `1170ec8acc6d8b3fa9939f30566adbc02ea796a4dbdde5207e2ecec8f0bca20e` |
| `mas_veritas_doc5_methodologies_to_integration_2023.pdf` | Veritas Document 5 — From Methodologies to Integration (117 pp) | 2023-06 | `ee83de6b14e3a718c28337adc2ca255411cc6520df48454e7ce33d915ddc3638` |
| `mas_media_release_2026-10-07.html` | MAS media release "MAS Sets Out Supervisory Expectations on Responsible AI Adoption by Financial Institutions" | 2026-10-07 | `166d8061e66119818b5fb1ba25a91e47c5338aaaeb50ad3a9df0fb21f1ba4a0a` |

## Source URLs

- Guidelines: https://www.mas.gov.sg/-/media/mas-media-library/regulation/guidelines/bd/guidelines-on-artificial-intelligence-risk-management-for-financial-institutions/guidelines-on-artificial-intelligence-risk-management.pdf
- Response to Feedback: https://www.mas.gov.sg/-/media/mas-media-library/publications/consultations/bd/2025/response-to-feedback-received-on-guidelines-on-artificial-intelligence-risk-management.pdf
- Consultation paper: https://www.mas.gov.sg/-/media/mas-media-library/publications/consultations/bd/2025/final_consultation_paper_on_guidelines_on_ai_risk_management_forrelease.pdf
- Annex B submissions: https://www.mas.gov.sg/-/media/mas-media-library/publications/consultations/bd/2025/annex-b---submissions-to-consultation-paper.pdf
- Info Paper 2024: https://www.mas.gov.sg/-/media/mas-media-library/publications/monographs-or-information-paper/imd/2024/information-paper-on-ai-risk-management-final.pdf
- FEAT: https://www.mas.gov.sg/-/media/mas/news-and-publications/monographs-and-information-papers/feat-principles-final.pdf
- Veritas documents: linked from https://www.mas.gov.sg/schemes-and-initiatives/veritas
- Veritas toolkit source code (Apache-2.0): https://github.com/mas-veritas2/veritastool
- Media release: https://www.mas.gov.sg/news/media-releases/2026/mas-sets-out-supervisory-expectations-on-responsible-ai-adoption-by-financial-institutions

## Copyright

The PDFs are MAS publications and are redistributed here solely for reproducibility of the
clause index and research; copyright remains with the Monetary Authority of Singapore. If MAS
objects to redistribution the PDFs will be removed and replaced with hashes plus URLs.
