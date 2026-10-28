# Rapport final de modification — Dashboard décisionnel territorial du Togo (Défi 2)

> **Hypothèse de travail à signaler.** Le fichier `Data-Lab-Defi-2.zip` n'a pas été joint à ce message : le « projet source » utilisé est le **Data Lab Défi 2 construit dans cette conversation** (notebook, `utils/`, tables, tests, journal d'anomalies, crosswalk). Si votre `Data-Lab-Defi-2.zip` est une autre version, les tables doivent être reconstruites avec `python tools/build_tables.py`.

## 1. Audit

**Template (`template-modele.zip`)** — application Streamlit « Économie Numérique », 4 pages, `components/` (header, navbar, sidebar, kpi_cards, charts, maps Folium + Plotly, tables, recommendation_cards, ui, styles, placeholder), polices Nunito Sans + Font Awesome *embarquées en sous-ensemble* (outil de régénération fourni), GeoJSON de 5 régions et 40 préfectures, 373 cantons géolocalisés, données **fictives** (`data/data.py`).
**Data Lab** — référentiel territorial 2022/2010 reconstruit et validé par somme, démographie, crosswalk 2010→2022, 5 jeux nettoyés, 30 contrôles qualité, 79 anomalies consignées, notebook, tests.
**Vérifications avant intégration** : les 40 polygones du template se rattachent aux **39 préfectures 2022** (Golfe en couvre deux : Golfe + Lomé Commune), sans trou ; 325 cantons sur 375 ont une position (87 % de la population des cantons).

## 2. Ce qui a été conservé du Data Lab
Tout le moteur d'analyse (`utils/` : territoire, prepare, quality, demography, evolution, crossfilter, export), le crosswalk et ses flags, les contrôles qualité, le journal d'anomalies, le notebook, les décisions validées (« sans agence » = agence ouverte, croissance neutre pour Golfe et Agoè-Nyivé séparés, série B de l'état civil hors analyse, `N/a` = non ouverte, `Nsp` = inconnue).

## 3. Ce qui a été repris du template
Structure `app.py` + `components/` + `views/`, en-tête (drapeau, titre du challenge, FR/EN), barre de navigation verte/or, sidebar de filtres (mécanique « appliqué immédiatement » et bouton Réinitialiser), cartes KPI, panneaux et leur CSS, barre de contrôle (Vue par · Indicateur · Afficher + Exporter), cartes Folium (zoom, info-bulles, légende, villes, boussole), tableaux HTML, cartes de recommandation, thème et polices embarquées. **Aucune donnée fictive n'est conservée** (`data/data.py` supprimé, vérifié par test).

## 4. Ce qui a été modifié ou ajouté
| Domaine | Modification |
|---|---|
| Navigation | 8 entrées (identité + 7 pages), icônes régénérées avec l'outil du template (38 icônes, toutes vérifiées présentes) |
| Filtres | Cascade **découpage → région → préfecture → commune → canton** ; année ; période ; comparabilité ; niveau de priorité ; état conservé par page |
| Composants nouveaux | `insights.py` (blocs À retenir / Point d'attention / Analyse / Implication / Recommandation, badges de comparabilité et de priorité) ; graphiques de classement cliquable, quadrant, Lorenz, histogramme, séries avec valeurs affichées et anomalies en croix, composantes empilées, concentration cumulée ; carte de points d'agences ; légendes à tranches calculées ; surbrillance d'un territoire |
| Sécurité d'affichage | `create_table` **échappe** le HTML par défaut (le gabarit ne le faisait pas) ; HTML brut seulement pour les colonnes déclarées sûres |
| Maintenance | `st.components.v1.html` (supprimable depuis 2026-06-01) remplacé par `st.iframe` avec repli ; `use_container_width` remplacé |
| Code mort | Fonctions et CSS propres au gabarit (donut opérateurs, bloc qualité, page « à venir ») supprimés |
| Charte | Palette du template conservée ; 4 de ses couleurs échouent en **texte** sur blanc (or 1,49 ; gris-bleu 2,05 ; rouge 4,29 ; blanc sur or) : réservées aux surfaces et traits, deux teintes sombres ajoutées pour le texte (rouge `#c4102f`, gris `#4f6270`) |
| Données | Services de base et indice de priorité **calculés dans le projet** (`utils/services.py`, `utils/priority.py`, `utils/story.py`), reconstruits par `tools/build_tables.py` |

## 5. Nouvelles interactions
Filtres en cascade avec réinitialisation automatique des niveaux inférieurs · bascule 6 régions 2022 / 5 régions historiques · Top 5/10/15/20 · recherche de territoire · **forage** région → préfecture → commune → canton (bouton « Explorer ») · **filtrage croisé** (la sélection d'une barre met en évidence la carte, filtre le tableau et les autres éléments) · métrique de carte au choix · Carte/Graphique/Tableau · section Électricité/CEET/TdE/Analyse croisée · année 2018–2021 · carte de points d'agences · **simulateur de pondérations** (4 scénarios + personnalisé, normalisation automatique, rang qui bouge vs référence) · fiche territoire (« Pourquoi est-il prioritaire ? », recommandation) · export CSV des données **filtrées** sur chaque page · recherche dans le journal des anomalies.

## 6. Nouveaux indicateurs et analyses
Électricité : taux plafonné, **population sans accès (PROXY)**, écart à la moyenne nationale, évolution 2018→2021 avec validité des tendances. Agences : ouvertes / en construction / inachevées / inconnues / non applicables, **agences pour 100 000 habitants**, **habitants par agence** (N/D si aucune), préfectures sans agence. Croisements : profils A–D par règles explicites, quadrant. **Indice de priorité territoriale** : 6 composantes, 4 scénarios, corrélations de Spearman (maximum 0,75 < 0,8), **506 configurations** de robustesse (graine 42), 5 unités robustes. **11 recommandations** chiffrées, chacune avec preuve, priorité, horizon et indicateur de suivi.

## 7. Contrôle des objectifs
| Objectif | Page | Indicateurs | Visualisations | Interactions | Conclusions |
|---|---|---|---|---|---|
| Profil démographique | Démographie, Vue d'ensemble | Population, poids, rang, médiane, Top 10, Gini, petits cantons | Carte (région, préfecture, commune, canton), classement, Lorenz, histogramme, tableau | Cascade, Top N, recherche, forage, filtrage croisé, export | Phrases calculées + implication + recommandation |
| Évolution 2010–2022 | Évolution | Variation, TCAM, contribution, comparabilité | Carte, classement, courbes 2010→2022, bloc Comparabilité | Niveau, indicateur, fiabilité, Top N, export | Oui, avec sensibilité Zio / Grand Lomé |
| Services de base | Services de base | Taux d'accès, population sans accès, agences / 100 000, habitants / agence | Cartes, classements, lignes 2018–2021, points d'agences, quadrant | Section, année, indicateur, clic, export | Oui |
| État civil & identité | État civil & identité | Enfants enregistrés, CNI, passeports, variations, indice base 100 | Séries avec valeurs affichées, anomalies et lacunes visibles | Bloc, indicateur, sexe, période, export | Oui (national uniquement) |
| Recommandations | Priorités & recommandations | IPT, composantes, stabilité | Carte des priorités, classement, composantes empilées, robustesse | Simulateur, filtres, fiche, export | Oui |

## 8. Tests réalisés
* **138 tests automatisés passent** (`pytest tests`, ≈ 2 min) : 8 pages (point d'entrée compris), chaque région en 6 et en 5 régions, tous les modes, sections, indicateurs et scénarios, cascade et réinitialisation, persistance des filtres, **cas sans données** (recherche, fiabilité vide, période sans année commune, poids nuls, journal), valeurs manquantes `N/D`, export CSV sur chaque page, performance, invariants de données (sommes, 33 unités ↔ 39 préfectures, 71 agences ouvertes, IPT borné et invariant à l'échelle des poids, valeur neutre, robustesse reproductible, récit calculé = données, HTML échappé, contrastes).
* **Performance mesurée côté serveur** : re-rendu de page entre 0,04 et 0,45 s à cache chaud (cible < 1 s) ; démarrage à froid d'un processus : plusieurs secondes (importations).
* **Serveur réel** : `streamlit run app.py` → `health: ok`, HTTP 200, aucune erreur au journal.
* **Notebook** : 33 cellules de code exécutées, 0 erreur ; les exports du notebook vont dans un dossier temporaire et n'écrasent jamais `outputs/data`.

### Non vérifié (aucun navigateur disponible dans cet environnement)
Rendu visuel réel (alignements, hauteurs des panneaux, débordements), responsive sur différentes résolutions, polices et icônes à l'écran, **clic direct sur un graphique ou sur la carte** (la logique est testée en fonction pure, pas le clic), fond de carte OpenStreetMap (nécessite internet). **Un passage visuel par vos soins est indispensable.**

## 9. Auto-évaluation (prudente)
| Critère | Note | Justification et réserves |
|---|---|---|
| Ergonomie / clarté / navigation | **≈ 4 / 5** | Design et navigation du template préservés, hiérarchie Observer→Agir, filtres et périmètres explicites. Réserve : non vérifié visuellement ; 7 pages denses ; hauteurs de panneaux calculées non contrôlées à l'écran |
| Pertinence des analyses | **≈ 8,5 / 10** | 5 objectifs couverts, comparabilité respectée, taux ≠ personnes, anomalies visibles, indice transparent et testé en robustesse, recommandations chiffrées. Réserves : pondérations = hypothèse, état civil non territorialisable, taux d'accès sans dénominateur |
| Interactions / filtres / fluidité | **≈ 4 / 5** | Cascade, forage, filtrage croisé, simulateur, export partout. Réserves : la carte du template (Folium) ne renvoie pas les clics : la sélection passe par le classement ; mesures de fluidité côté serveur uniquement |
| **Total** | **≈ 16,5 / 20** | Le « 20/20 » demandé n'est pas démontrable : il dépend d'un évaluateur et d'un rendu visuel que je n'ai pas pu voir |

## 10. Limites restantes
Deux recensements seulement (pas de trajectoire) · communes absentes de 2010 · Danyi 1 et 2 non séparables · Golfe et Agoè-Nyivé comparables seulement ensemble · transfert d'Adéti Kopé non entièrement quantifiable (sensibilité ESTIMATION indicative) · contours et coordonnées **indicatifs** (fournis avec le template, non officiels ; 13 communes du Grand Lomé et 50 cantons non positionnés) · taux d'accès sans dénominateur documenté (taux régionaux non reproductibles : écart jusqu'à 11,9 points pour la Maritime) · 4 unités exclues des tendances d'électricité (Agoè-Nyivé, Zio, Yoto, Blitta) · état civil et identité nationaux, 2021 absent pour l'identité · indice de priorité : poids tabulés par hypothèse, sans pondération officielle · pas d'authentification ni d'EN : le bouton EN du template reste un message « bientôt disponible ».
