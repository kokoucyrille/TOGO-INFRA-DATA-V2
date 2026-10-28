# Rapport d'audit et de validation — Dashboard Défi 2 (territoires du Togo)

Date : 25/10/2026 · Périmètre : `dashboard.zip` (7 pages Streamlit, 5 jeux bruts, tables `outputs/data`, notebook, 136 tests initiaux).

## 1. Diagnostic initial
Projet structuré (`app.py`, `components/`, `views/`, `data/`, `utils/`, `tools/`, `tests/`) et déjà documenté. État mesuré à l'ouverture : **134 tests réussis, 2 échecs** (tous deux sur la page « Services de base » : export absent). Python 3.12.3, dépendances épinglées installées sans conflit. Le serveur réel démarre (`/_stcore/health` = ok, HTTP 200).

## 2. Problèmes détectés
| Niv. | Problème | Effet |
|---|---|---|
| **P0** | « Services de base » affichait la **moyenne simple** des taux préfectoraux (24,4 % en 2018 ; 34,5 % en 2021) | Sous-estimation d'environ 20 points face au taux national publié (45,09 % ; 57,82 %) et au taux pondéré (42,3 % ; 54,5 %) : indicateur trompeur |
| **P0** | Tableau régional de la même page : moyenne simple, non plafonnée | Même biais, plus fort pour les grandes régions |
| P1 | Export CSV absent de la page (README et tests l'annonçaient) | 2 tests en échec, fonctionnalité promise indisponible |
| P1 | Histogrammes régionaux, anneaux et tableau calculés sur les 39 préfectures **sans tenir compte des filtres** | Incohérence KPI / cartes / graphiques après filtrage |
| P1 | Panneau « Déficit croisé par région » **vide** pour 2 indicateurs sur 3 | Zone blanche trompeuse |
| P1 | Anneaux 2018 : préfecture sans taux silencieusement exclue du total | Total sous-estimé sans avertissement |
| P1 | Page sans KPI ni constats calculés (contrairement aux autres pages) | Lecture décisionnelle faible |
| P2 | 4 icônes (`fa-chart-column`, `fa-chart-pie`, + 2 ajoutées) absentes du sous-ensemble de polices embarqué | Icônes affichées vides |
| P2 | Taux nationaux écrits en dur dans la vue ; expression morte `... if False else ...` ; calcul du score dupliqué | Maintenabilité |

## 3. Corrections effectuées
- Fonctions pures ajoutées dans `utils/services.py` : `taux_pondere` (pondéré par la population 2022, plafonné à 100 %, manquants exclus du numérateur **et** du dénominateur), `population_sans_acces`, `score_deficit_croise` (rangs toujours calculés sur les 39 préfectures).
- `views/services_base.py` : 6 KPI du périmètre filtré, constats calculés (à retenir / implication / limites), histogramme annuel et tableau régional **pondérés**, tous les graphiques sur le périmètre filtré, panneau régional toujours rempli, avertissements sur les taux manquants ou plafonnés, état vide géré (`st.stop`), export CSV du périmètre filtré, taux nationaux lus depuis `utils/services.TAUX_NATIONAL`.
- Icônes remplacées par des icônes présentes dans le sous-ensemble ; test automatique ajouté.
- `README.md` corrigé : la ligne « Services de base » décrivait un quadrant et un classement cliquable qui n'existent pas sur cette page.

## 4. Contrôles indépendants des indicateurs majeurs
| Indicateur | Contrôle | Résultat |
|---|---|---|
| Taux d'accès pondéré | Recalcul manuel sur 3 lignes + recalcul numpy sur les 39 préfectures | Concordant |
| Taux pondéré vs taux national publié | Comparaison à 45,09 % / 57,82 % | Écart 2021 : −3,3 pp (54,5 vs 57,82) ; **non expliqué** : dénominateur de la source non documenté. Affiché sur la page, non masqué |
| Population sans accès (PROXY) | sans + avec = population totale (8 095 498) ; somme régions = somme préfectures | Concordant |
| Agences ouvertes | Recompte direct dans les CSV bruts (statut `{Utilise}`, catégories « Agence CEET/TdE ») | CEET 25 + TdE 46 = **71**, identique à la table |
| Score de déficit croisé | Bornes 0–100 et monotonie (meilleur accès → score plus faible) | Concordant |
| Population nationale | Somme des 39 préfectures = 8 095 498 | Concordant avec le total attendu pour 2022 |

## 5. Tests et statuts réels
| Famille | Statut | Détail |
|---|---|---|
| Techniques (syntaxe, imports, dépendances) | **Réussi** | `py_compile`, installation des versions épinglées, import des modules |
| Démarrage réel | **Réussi** | serveur Streamlit : health ok, HTTP 200, aucune erreur au journal. Ne prouve pas le rendu navigateur |
| Analytiques (formules, totaux, cas limites) | **Réussi** | 12 nouveaux tests (`test_services.py`), dont dénominateur nul, taux manquant, taux > 100 % |
| Fonctionnels (AppTest) | **Réussi** | 155 tests au total (136 initiaux + 12 + 7) ; pages, années 2018–2021, filtre région, export |
| Suite initiale | **Échec → corrigé** | 2 échecs à l'ouverture, 0 après correction |
| Rendu visuel, responsive, polices, clic sur carte, fond OpenStreetMap | **Non exécuté** | aucun navigateur disponible ici |
| Autres pages (hors Services de base) | **Partiellement vérifié** | exécution et tests existants OK ; pas de relecture analytique approfondie page par page |

## 6. Problèmes non résolus
- Rendu visuel jamais vu : alignements, hauteurs de panneaux, responsive restent à contrôler dans un navigateur.
- Écart de 3 à 4 points entre taux pondéré et taux national publié : à éclaircir avec la source.
- Les 6 autres pages n'ont pas fait l'objet d'un recalcul indépendant aussi poussé que « Services de base » ; leurs tests existants (invariants de données, comparabilité) passent.
- Pondérations de l'indice de priorité = hypothèse ; état civil non territorialisable ; deux recensements seulement.
- Carte Folium : pas de clic renvoyé à l'application.

## 7. Autoévaluation (estimation prudente)
| Critère | Note | Justification |
|---|---|---|
| C1 Ergonomie | **≈ 4 / 5** | Navigation, hiérarchie et KPI cohérents sur toutes les pages ; icônes corrigées. Non vérifié visuellement |
| C2 Analyses | **≈ 8,5 / 10** | Indicateur trompeur corrigé, calculs recoupés avec les sources, limites affichées. Retranché : dénominateur du taux d'accès inconnu, audit approfondi limité à une page |
| C3 Filtres / fluidité | **≈ 4 / 5** | Périmètre désormais cohérent entre KPI, cartes, graphiques et export ; cas vides gérés. Fluidité mesurée côté serveur seulement |
| **Total** | **≈ 16,5 / 20** | **L'objectif de 19/20 n'est pas démontrable avec les preuves disponibles** : il suppose un contrôle visuel en navigateur et une revue analytique des autres pages |
