# Projects needing manual processing

Snapshot: local catalog audit, 29 September 2026. The active catalog has 209 IDPs and 58 Project Studies (267 listings). The organization review report covers 172 IDPs and 46 Project Studies (218 listings). The tables below describe two different checks of the same catalog; their rows overlap and must not be added together.

## Source and profile availability

| Active listing state | IDP | Project Study | Total | Next step | References |
|---|---:|---:|---:|---|---|
| No document link; details only in HTML | 1 | 0 | 1 | Extract the chair or detail page. | idp-198 |
| “Document” link is actually a web page, never fetched as a PDF | 7 | 7 | 14 | Correct the link type and extract the detail page. | idp-181, idp-182, idp-185, idp-205, idp-214, idp-215, idp-216; ps-054 to ps-060 |
| PDF stored, profile not yet extracted | 1 | 0 | 1 | Run or inspect profile extraction. | idp-196 |
| Extracted as `not_an_offer` | 1 | 0 | 1 | Check whether the PDF contains an offer. | idp-015 |
| Extracted, but `requires_ocr` | 1 | 0 | 1 | OCR and verify against the PDF. | idp-078 |
| Has a profile | 198 | 51 | 249 | Review profile fields and citations where flagged. | 28 flagged `unverified_citations`, listed below |
| **Total** | **209** | **58** | **267** | | |

Profiles flagged `unverified_citations` (at least one quote was not found on its cited page):

- IDP (24): idp-009, idp-010, idp-021, idp-023, idp-024, idp-028, idp-030, idp-037, idp-048, idp-064, idp-084, idp-091, idp-099, idp-114, idp-122, idp-126, idp-133, idp-137, idp-138, idp-149, idp-151, idp-170, idp-206, idp-208
- Project Study (4): ps-023, ps-026, ps-033, ps-038

Added after this snapshot: idp-225 (Chair of Media Technology, first seen 29 September 2026 at 01:08 UTC) has no document link. With it, the catalog has 210 active IDPs and two HTML-only listings.

The 14 web-page links comprise 10 URLs on `www.ie.mgt.tum.de` ending in `/` (idp-214, idp-215, idp-216, ps-054 to ps-060), three TYPO3 page URLs on `classic.fsmb.de` containing `?cHash=` (idp-181, idp-182, idp-205), and one URL on `www.cit.tum.de` (idp-185). None has a `pdf_artifacts` row. Together with the one listing without a document link, **15 active listings have their details only in HTML** and are outside PDF-only semantic extraction. The catalog currently labels these web-page links “Project document”; that card label needs correction. Among archived listings, seven IDPs and two Project Studies are HTML-only; archived listings do not appear in the active catalog.

## Organization review coverage

| Reason absent from `organization-candidates.jsonl` | IDP | Project Study | Total | Next step | References |
|---|---:|---:|---:|---|---|
| Profile has review flags | 25 | 4 | 29 | Inspect source citations; one also requires OCR. | The 28 `unverified_citations` profiles above, plus idp-078 (`requires_ocr`) |
| Linked PDF has no stored `pdf_artifacts` row | 7 | 7 | 14 | The links are web pages; extract HTML. | idp-181, idp-182, idp-185, idp-205, idp-214, idp-215, idp-216; ps-054 to ps-060 |
| PDF offer cannot be matched confidently to the listing | 3 | 1 | 4 | Match the offer manually before assigning organizations. | idp-015, idp-157, idp-220, ps-004 |
| No linked document | 1 | 0 | 1 | Extract the HTML-only offer. | idp-198 |
| No successful current profile | 1 | 0 | 1 | Run or review profile extraction. | idp-196 |
| **Active listings absent from review report** | **37** | **12** | **49** | | |

The other 218 active listings appear in [organization-candidates.jsonl](../organization-candidates.jsonl), but 37 of those rows have **no academic-unit or partner candidate** and still need source review. The 49 exclusions and 18 archived listings are itemized in [organization-uncovered-projects.jsonl](../organization-uncovered-projects.jsonl). Both JSONL files are local review snapshots ignored by Git.

The source/profile table classifies extraction state; the organization table classifies eligibility for the organization report. For example, a PDF can have a stored profile yet be omitted from organization review because its citations have review flags. These are not 49 additional projects beyond the 267 active listings.

## LMT follow-up

Updated 29 September 2026: a forced LMT recrawl found five IDP-labelled offers. The live catalog now has five active LMT listings: `idp-198`, `idp-225`, and `idp-227` to `idp-229`. Each has a separate chair-page Markdown description, a single-offer structured extraction, and a working project detail page. `idp-198` no longer includes the neighboring KalmanNet offer. The temporary duplicate `idp-226` was archived after two complete successful crawls missed it. The adapter retains PDF URLs internally and does not request the timing-out PDF host. The snapshot tables above remain historical and should be regenerated before using their counts as current totals.

## Active project lookup

These are the 49 active listings absent from the organization report. The reason is the first failing step in the report pipeline.

| Type | Reference | Project | Reason | Slug |
|---|---|---|---|---|
| IDP | idp-009 | Aufbau und Training eines Neuronalen Netzes zur Zeitreihenvorhersage von Aerodynamischen Beiwerten | profile_review_flags | `informatics-idp-hub-f59988dd4b` |
| IDP | idp-010 | Generative Machine Learning for 3D Coarse-Grained Bio-Aggregate Structure Modeling | profile_review_flags | `informatics-idp-hub-b43f168c9e` |
| IDP | idp-015 | Campaign Concierge | ambiguous_offer_match | `informatics-idp-hub-33dd8c791e` |
| IDP | idp-021 | CDP // REMASTERED | profile_review_flags | `informatics-idp-hub-f2471fccc8` |
| IDP | idp-023 | Rize Software Engineering Project | profile_review_flags | `informatics-idp-hub-e2e1ee0dc1` |
| IDP | idp-024 | Workflow Automation utilizing Business Process Engine | profile_review_flags | `informatics-idp-hub-6c7908f9ad` |
| IDP | idp-028 | CDP // MIXED | profile_review_flags | `informatics-idp-hub-3e75eb8da5` |
| IDP | idp-030 | VR for Architecture @ Start-up Visonation | profile_review_flags | `informatics-idp-hub-377e8c6b14` |
| IDP | idp-037 | Cellbyte | profile_review_flags | `informatics-idp-hub-2e447a6264` |
| IDP | idp-048 | Sensor Fusion of Event-Based and Frame-Based Cameras for Space Applications | profile_review_flags | `informatics-idp-hub-55c5c445f2` |
| IDP | idp-064 | Stereokamera-basierte Umfeldwahrnehmung für automatisierte Fahrzeuge | profile_review_flags | `informatics-idp-hub-06b79370d7` |
| IDP | idp-078 | Reinforcement Learning basierte Ladestrategie für Batterieelektrische Trucks mit Ladepunktreservierungen | profile_review_flags | `informatics-idp-hub-b58d2fd2f4` |
| IDP | idp-084 | Implementierung der planerseitigen Entscheidungsunterstützung einer menschzentrierten Dienstplanung | profile_review_flags | `informatics-idp-hub-f3f421e2c6` |
| IDP | idp-091 | Parameteroptimierung partikelbasierter Simulation mit Rein- forcement Learning [100% Remote-Arbeit möglich] | profile_review_flags | `informatics-idp-hub-76eb596456` |
| IDP | idp-099 | Sensor Fusion of Event-Based and Frame-Based Cameras for Space  Applications | profile_review_flags | `informatics-idp-hub-08ef31c94c` |
| IDP | idp-114 | Project study Ecco Collection | profile_review_flags | `informatics-idp-hub-56eded411d` |
| IDP | idp-122 | Smart Assistant utilizing Retrieval Augmented Generation | profile_review_flags | `informatics-idp-hub-e5c0146792` |
| IDP | idp-126 | Optimization of Operation Strategy for Battery Electric Trucks Considering On-route Charging and Charging Point Reservation | profile_review_flags | `informatics-idp-hub-c04c2ffb80` |
| IDP | idp-133 | Automated Integration and Extraction Pipelines for Laboratory Data using eLabFTW | profile_review_flags | `informatics-idp-hub-6e645ebb3f` |
| IDP | idp-137 | Development of Artificial Neural Networks for Image Segmentation Tasks | profile_review_flags | `informatics-idp-hub-d8a4d46e39` |
| IDP | idp-138 | Softwareentwicklung zur Bestimmung der Klimaanpassung von Gebäuden in Abhängigkeit Verschiedener Komfortmodelle | profile_review_flags | `informatics-idp-hub-7df8e86993` |
| IDP | idp-149 | [Weihenstephan] Neural Data Analysis in the Bat Auditory Cortex | profile_review_flags | `informatics-idp-hub-846d8b3123` |
| IDP | idp-151 | Next-Gen Virtual Patient - KI-gestütztes Anamnesetraining für Medizinstudierende | profile_review_flags | `informatics-idp-hub-ac1eb474ad` |
| IDP | idp-157 | Remote Sensing & Autonomous Field Monitoring | ambiguous_offer_match | `informatics-idp-hub-38cc0e0b40` |
| IDP | idp-170 | Physics-Informed Mission Optimisation for Future Space Propulsion | profile_review_flags | `informatics-idp-hub-483288c429` |
| IDP | idp-181 | MILP-basierte Einsatzplanung mobiler Energiespeicher auf batterieelektrischen Baustellen [MA/IDP] | pdf_not_stored | `idp-institute-of-automotive-technology-2b8a3c32e9` |
| IDP | idp-182 | SA/MA/IDP: KI-basierte Fehlererkennung in Technischen Zeichnungen mit Vision-Language-Modellen | pdf_not_stored | `idp-institute-for-materials-handling-material-flow-logistics-cbc192fb48` |
| IDP | idp-185 | Interdisziplinäres Projekt in einem Anwendungsfach (IDP) | pdf_not_stored | `idp-professorship-of-energy-management-technologies-7e3a9721e6` |
| IDP | idp-196 | IDP “From Prototype to SaaS: AI Workflows for Industrial B2B SaaS” with demi Technologies | no_successful_current_profile | `idp-dr-theo-sch-ller-stiftungslehrstuhl-f-r-technologie-und-innovationsmanagement-d02a81cdff` |
| IDP | idp-198 | BA , MA , IDP , FP , IP , SHK : Multi-level Fingerprinting-based Indoor Localization Scheme | no_linked_pdf | `idp-chair-of-media-technology-debfea2172` |
| IDP | idp-205 | Build an AI-Assisted Natural-Language Interface for Multi-Physics Simulation | pdf_not_stored | `idp-chair-of-aerodynamics-and-fluid-mechanics-a23be6256f` |
| IDP | idp-206 | IDP Project: Natural Language Assistant for an Open-Source Multi-Physics Library and Simulator | profile_review_flags | `idp-chair-of-aerodynamics-and-fluid-mechanics-5b978408b4` |
| IDP | idp-208 | Aufbau und Training eines Neuronalen Netzes zur Zeitreihenvorhersage von Aerodynamischen Beiwerten | profile_review_flags | `idp-chair-of-aerodynamics-and-fluid-mechanics-af1d39f8f3` |
| IDP | idp-214 | IDP @ ScopeZero | pdf_not_stored | `idp-tum-entrepreneurship-research-institute-b6b7606585` |
| IDP | idp-215 | IDP / AP @ CharterAI | pdf_not_stored | `idp-tum-entrepreneurship-research-institute-14d0f30957` |
| IDP | idp-216 | IDP @ Kalkulai: Agents that actually do the work | pdf_not_stored | `idp-tum-entrepreneurship-research-institute-86b08acd89` |
| IDP | idp-220 | IDP HUSKY: Mobile Manipulators for Construction  Applications | ambiguous_offer_match | `informatics-idp-hub-e6b5493e7c` |
| PS | ps-004 | Project studies in cooperation with Fraunhofer Institute for Applied Information Technology (FIT) (04/2022) | ambiguous_offer_match | `economics-of-energy-markets-47de4357f2` |
| PS | ps-023 | Project Study at VYONICA: Brand & Communication Strategy | profile_review_flags | `corporate-management-5defe61bbb` |
| PS | ps-026 | Project Study at Fortisana: Growth/Marketing at Consumer Health Supplements | profile_review_flags | `corporate-management-d7c752f43d` |
| PS | ps-033 | Project Study at Find your Retreat: SEO & GEO Texts & Marketing | profile_review_flags | `corporate-management-88a4d71cfe` |
| PS | ps-038 | Project Study “Business Development in the Robotics Industry” with NEDGEX | profile_review_flags | `technology-and-innovation-management-8355f29293` |
| PS | ps-054 | Project Study@ Ecoverity GmbH - EPD Verification \| Venture Business Plan | pdf_not_stored | `tum-entrepreneurship-research-institute-351b7a65a6` |
| PS | ps-055 | Project Study @ risiq: Measuring the Financial Impact of Climate Change | pdf_not_stored | `tum-entrepreneurship-research-institute-b44daf733e` |
| PS | ps-056 | Project Study@ Symbioverse | pdf_not_stored | `tum-entrepreneurship-research-institute-c7ef77b88c` |
| PS | ps-057 | Project Study@MOOSYC:  GET MOOSYC INTO EVERY ARTIST'S HEAD. | pdf_not_stored | `tum-entrepreneurship-research-institute-41fe1923bf` |
| PS | ps-058 | Project Study @ Nexus Politics | pdf_not_stored | `tum-entrepreneurship-research-institute-aea90ad0e0` |
| PS | ps-059 | Project Study @ Arqus Aerospace: Founder's Associate/Rewriting the Economics of Defence | pdf_not_stored | `tum-entrepreneurship-research-institute-405086a0f7` |
| PS | ps-060 | PROJECT STUDY @ Mabu: Founder's Associate | pdf_not_stored | `tum-entrepreneurship-research-institute-472156d4b8` |

The following 37 listings are in the organization report, but both candidate lists are empty. Their PDF or chair page needs manual organization review.

| Review ID | Reference | Project | Slug |
|---|---|---|---|
| IDP-007 | idp-211 | Scaling JAX-SPH | `idp-chair-of-aerodynamics-and-fluid-mechanics-6a852ce70e` |
| IDP-008 | idp-207 | Advancing Sci-ML Through Large Pre-Trained Video Models | `idp-chair-of-aerodynamics-and-fluid-mechanics-dfb84a678e` |
| IDP-017 | idp-186 | Active Learning-Driven Development of Machine Learning Potentials for Molecular Self-Assembly Dynamics | `idp-professorship-of-multiscale-modeling-of-fluid-materials-9309495f5c` |
| IDP-020 | idp-108 | Online Process Monitoring to Enable Adaptive Drilling Processes | `informatics-idp-hub-06798bcfd2` |
| IDP-025 | idp-144 | Efficient Retraining of ML Models for Process Monitoring | `informatics-idp-hub-13dbf9e52c` |
| IDP-026 | idp-060 | Visualization of auditory nerve fiber activation under natural and electrical stimulation | `informatics-idp-hub-16254ed334` |
| IDP-036 | idp-148 | Web-based Interactive Physics Simulation | `informatics-idp-hub-2352c9d21e` |
| IDP-037 | idp-071 | Integration of a State-of-the-art 4D Point Cloud Registration Algorithm into the Open Python Library py4dgeo | `informatics-idp-hub-235cca1afa` |
| IDP-041 | idp-101 | Anomaly Detection in Battery Systems: A Comparative Study of Principal Component Analysis Methods and Data Preprocessing Techniques | `informatics-idp-hub-25a06be61a` |
| IDP-048 | idp-163 | Transfer Learning of Graph Neural Networks for Implicit Solvent Modeling | `informatics-idp-hub-2ebfac7f46` |
| IDP-056 | idp-022 | FPGA-Based Active Magnetic Field Compensation for Medical Physics Applications | `informatics-idp-hub-3695d35f5b` |
| IDP-057 | idp-139 | Development and Evaluation of AI Agents for Simulating Human Wayfinding | `informatics-idp-hub-3b931d2b0d` |
| IDP-061 | idp-155 | Improving Scientific Software in Behavioral Science | `informatics-idp-hub-45cc3641dc` |
| IDP-062 | idp-116 | Opportunity to contribute to clinical innovation in orthopedic medicine using the power of artificial intelligence | `informatics-idp-hub-45d52bcc09` |
| IDP-064 | idp-066 | Full Stack / Frontend Developer | `informatics-idp-hub-46e8b43fbf` |
| IDP-067 | idp-056 | Computer Vision–Based Eye Tracking as a Diagnostic Tool | `informatics-idp-hub-4d5a03d69e` |
| IDP-068 | idp-095 | Comprehensive Customer Analytics Dashboard – BoxOrganizer | `informatics-idp-hub-4ed2760a81` |
| IDP-071 | idp-040 | Faster Analysis Methods for Combined fMCG and ECG Data | `informatics-idp-hub-520bfdd06b` |
| IDP-082 | idp-042 | AUTONOMOUS MOTORSPORT | `informatics-idp-hub-658de483d2` |
| IDP-085 | idp-092 | Foundation Models for Process Monitoring in Vibration-Assisted Drilling | `informatics-idp-hub-6a50125b8d` |
| IDP-090 | idp-047 | Scaling JAX-SPH | `informatics-idp-hub-76d00c456a` |
| IDP-093 | idp-080 | Benchmarking ML models for Computational Fluid Dynamics | `informatics-idp-hub-786eb3340a` |
| IDP-095 | idp-143 | [Weihenstephan] An application of Industrial Internet of Things (IIoT) in crystallization | `informatics-idp-hub-7ac6dfd75b` |
| IDP-096 | idp-135 | LLM4Agri – Textbasierte Agrarberater für nachhaltige Landwirtschaft | `informatics-idp-hub-7b70fc7b00` |
| IDP-104 | idp-034 | Benchmarking ML models for Computational Fluid Dynamics | `informatics-idp-hub-856d4b6523` |
| IDP-108 | idp-070 | App trifft Lehre | `informatics-idp-hub-890b85bf86` |
| IDP-112 | idp-075 | Invariant Features for Learning Equivariant Lagrangian Fluid Mechanics | `informatics-idp-hub-92a88dc230` |
| IDP-122 | idp-150 | Portierung einer interaktiven Gaming-Umgebung auf Apple Vision Pro | `informatics-idp-hub-a0b776daed` |
| IDP-136 | idp-142 | Deep Tech Early Team Scaling | `informatics-idp-hub-be9150f272` |
| IDP-138 | idp-027 | 3D Simulation of Vibration-Assisted Drilling | `informatics-idp-hub-cc2cd91504` |
| IDP-139 | idp-117 | Development of a User‑Friendly Database for the Energy Model Generator TIMES | `informatics-idp-hub-cf177964ab` |
| IDP-152 | idp-104 | Quantum Technology Job Postings | `informatics-idp-hub-e08e48e071` |
| IDP-165 | idp-025 | Accelerating Scientific ML through Multi-GPU Scaling | `informatics-idp-hub-f07515aa47` |
| IDP-166 | idp-094 | Travel Behavior and Policy Impacts | `informatics-idp-hub-f3abd23f7f` |
| IDP-169 | idp-068 | Eyetracking in behavioral research | `informatics-idp-hub-f8a306f648` |
| PS-029 | ps-003 | Project Study in Sustainable Metals & Minerals Mining in collaboration with the University of Texas at Austin | `economics-of-energy-markets-e96483ed3c` |
| PS-043 | ps-036 | Project Study “Go-to-Market & Sales Strategy of AI-powered PCB assembly hardware” with HefexLabs | `technology-and-innovation-management-8ecbe04832` |
