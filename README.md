# Dashboard décisionnel territorial du Togo — Data Lab Défi 2

Tableau de bord **Streamlit** construit sur le *template-modele* (en-tête, navigation verte/or, filtres latéraux, cartes KPI, panneaux, cartes Plotly cliquables, cartes de recommandation)
et alimenté par les **données réelles du Data Lab** : recensements 2010 et 2022, électricité 2018–2021, agences CEET et TdE, état civil et documents d'identité.

> Où se concentre la population ? Comment évolue-t-elle ? Où sont les déficits de services ? Où faut-il agir, et pourquoi ?

## Installation et lancement

```bash
python -m venv .venv && source .venv/bin/activate        # Python 3.12 recommandé
pip install -r requirements.txt
streamlit run app.py
```

* Les cartes sont des figures Plotly **sans fond de carte externe** (contours GeoJSON locaux, `static/world_110m.json` factice servi en local) : le tableau de bord fonctionne **hors ligne**. Un clic sur un territoire met à jour les filtres globaux (partagés par URL).
* L'application lit **uniquement** `outputs/data/` (≈ 0,5 Mo de Parquet). Pour tout reconstruire à partir des fichiers bruts de `data/raw/` :

```bash
python tools/build_tables.py        # ≈ 11 s : nettoyage → référentiel → démographie → crosswalk → services → IPT → recommandations
```

## Pages (menu du template)

| Page | Question | Contenu principal | Interactions |
|---|---|---|---|
| **Vue d'ensemble** | Comprendre le pays en quelques secondes | 8 KPI, carte à indicateur choisi, classement, courbe de concentration, constats calculés | Vue par région/préfecture, 4 indicateurs, Carte/Tableau, classement cliquable, export |
| **Démographie** | Où vit la population ? | Population, poids, rangs, tailles des communes et cantons, Lorenz, distribution | Cascade découpage → région → préfecture → commune → canton, Top 5/10/15/20, recherche, forage, filtrage croisé, export |
| **Évolution 2010–2022** | Qui croît, en tenant compte du découpage ? | Variation, TCAM, contribution, cartes, bloc « Comparabilité » (HIGH / MEDIUM / LOW) | Niveau, indicateur, fiabilité, Top N, Carte/Graphique/Tableau, export |
| **Services de base** | Où l'accès est-il inégal ? | 6 KPI du périmètre filtré (population, taux d'accès **pondéré**, population sans accès PROXY, agences, agences / 100 000 hab., préfectures sans agence), 4 cartes thématiques (électricité, CEET, TdE, déficit croisé), histogrammes régionaux, anneaux 2018–2021, tableau régional pondéré, constats calculés | Région, préfecture, année 2018–2021, indicateur par carte, export CSV du périmètre filtré |
| **État civil & identité** | Comment évoluent naissances, CNI, passeports ? | Séries nationales avec anomalies visibles, indice base 100 | Bloc, indicateur, sexe, période, Graphique/Tableau, export |
| **Priorités & recommandations** | Où faut-il agir, et pourquoi ? | Indice de priorité (33 unités), robustesse, fiche territoire, recommandations chiffrées | Simulateur de pondérations (4 scénarios + personnalisé), filtres, fiche cliquable, export |
| **Méthode & données** | Comment lire ces résultats ? | Sources, formules, crosswalk, contrôles qualité, journal des anomalies, glossaire | Sections, recherche dans le journal, export |

Chaque page suit **Observer → Comparer → Interpréter → Agir** (blocs *À retenir*, *Point d'attention*, *Analyse*, *Implication*, *Recommandation*), dont **tous les chiffres sont calculés** à partir des tables.

## Principes de rigueur

* **Aucune donnée inventée** : une valeur absente s'affiche `N/D`, jamais `0`. Les anomalies de la source (taux > 100 %, années aberrantes…) sont conservées, signalées et exclues des tendances.
* **Comparabilité 2010–2022** : jamais de comparaison directe de territoires dont le périmètre a changé ; flags HIGH / MEDIUM / LOW visibles ; les LOW ne sont jamais classés.
* **Taux ≠ personnes** : la population sans accès est un **PROXY** (le dénominateur du taux d'accès n'est pas documenté).
* **Indice de priorité** : formule, composantes, pondérations (hypothèse) et robustesse affichées ; le classement est un outil d'aide à la décision.
* Étiquettes de nature : `OBSERVATION`, `CALCUL`, `PROXY`, `ESTIMATION`, `HYPOTHÈSE`.

## Structure du projet

```text
app.py                 point d'entrée : en-tête + navigation du template, pages
.streamlit/config.toml thème du template
assets/                polices et icônes embarquées (Nunito Sans, Font Awesome), drapeau
components/            composants du template (header, navbar, sidebar, kpi_cards, charts, maps, tables, recommendation_cards, ui, styles)
                       + insights.py (blocs de récit, badges) ; charts.py et maps.py étendus (classement cliquable, quadrant, Lorenz, cartes de points)
views/                 une page par menu : overview, demographie, evolution, services_base, etat_civil_identite, recommandations, methode
data/loader.py         chargement mis en cache, listes de filtres en cascade, géométries
data/query.py          application des filtres et tableaux par niveau
data/geo/              contours (préfectures, régions) et positions de cantons du template
data/raw/              fichiers bruts du Data Lab
utils/                 moteur d'analyse du Data Lab : territoire, prepare, quality, demography, evolution, services, priority, story, formats
tools/                 build_tables.py (reconstruction des tables), build_embedded_fonts.py (polices du template)
outputs/data/          tables produites (Parquet + CSV), journal d'anomalies, contrôles qualité
notebook/              Defi2_Togo.ipynb : raisonnement et résultats (chapitres 00–09)
tests/                 test_app.py (AppTest), test_data.py (invariants), test_services.py (formules des indicateurs de services, recalculs indépendants),
                       test_services_page.py (page Services de base : KPI, année, filtre région, export)
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests -q          # ≈ 2 min, 155 tests : pages, filtres, cascade, cas vides, N/D, exports, performance, invariants, contrastes, icônes, formules
```

Non couverts par les tests automatiques (à vérifier dans un navigateur) : rendu visuel, polices, responsive, clic direct sur la carte, fond de carte OpenStreetMap.

## Régénérer les icônes et polices du template

Si une nouvelle icône Font Awesome est utilisée (`fa-nom` dans le code) :

```bash
npm pack @fortawesome/fontawesome-free @fontsource/nunito-sans    # puis décompresser
python tools/build_embedded_fonts.py <dossier fontawesome>/package <dossier nunito>/package/files
```

## Audit

Voir `RAPPORT_AUDIT_FINAL.md` (problèmes détectés, corrections, contrôles indépendants, statut réel des tests, autoévaluation). `RAPPORT_MODIFICATIONS.md` conserve l'historique de la construction initiale.
