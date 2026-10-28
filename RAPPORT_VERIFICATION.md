# RAPPORT DE VÉRIFICATION — Défi 2 Togo (v2)

## 1. Tests
`pytest tests -q` → **197 passed** (157 d'origine + 38 nouveaux : recommandations/IPT 9, réconciliation 7, audit indépendant 10, carte/comparer/clics/zoom 12). Aucun test d'origine supprimé ; deux tests mis à jour car l'interface a changé (libellés de navigation ; cartes Plotly au lieu d'iframes Folium).

## 2. Temps de réexécution par page (serveur, `AppTest`, cache chaud)
| Page | 1ʳᵉ exécution | Réexécution |
|---|---|---|
| Accueil | 1,10 s | 0,26 s |
| Carte interactive | 0,55 s | 0,32 s |
| Démographie | 0,68 s | 0,41 s |
| Évolution | 0,54 s | 0,27 s |
| Services | 0,76 s | 0,27 s |
| Priorités | 0,65 s | 0,45 s |
| Comparer | 0,44 s | 0,07 s |
| Méthode | 0,34 s | 0,05 s |
| État civil | non chronométrée séparément (rendu sans erreur, tests) | — |

Cible < 1,5 s : atteinte côté serveur. Le rendu navigateur (Plotly + polices) ajoute quelques secondes au premier affichage (≈ 5-6 s mesurées par Playwright, dont 5 s d'attente fixe du script) : non optimisé davantage.

## 3. Checklist des 5 analyses du défi
1. Profil démographique 2022 régions/préfectures/communes → **Démographie** (classement, carte, Lorenz/Gini, histogramme) + Carte interactive.
2. Évolution 2010–2022 avec ventilation administrative → **Évolution** (TCAM, contributions, drapeaux HIGH/MEDIUM/LOW, carte cliquable).
3. Électricité + répartition des agences CEET/TdE rapportée à la population → **Services**, **Carte interactive** (couches accès, sans accès, agences/100 000 hab., agences superposées), **Méthode › Réconciliation**.
4. Naissances / CNI / passeports → **État civil** (séries nationales, anomalies visibles, note sous les KPI).
5. Recommandations pour rapprocher les services → **Priorités** (IPT, robustesse, 8 unités « Très haute », recommandations avec preuve) et `recommandations.csv`.

## 4. Preuves des étapes
- Étape 0 : captures Playwright desktop 1440×900 et mobile 390×844 dans `docs/screens/` (pages + versions pleine hauteur) ; défauts corrigés listés dans `CHANGELOG.md` (#4, #8, #9).
- Étape 1 : cf. CHANGELOG #1.
- Étape 2 : écart expliqué par le dénominateur implicite de la source (≈ 12,8 % de la population 2022, nature non documentée). 2018–2020 reproduits par abonnés ÷ dénominateur ; **2021 reproduit seulement par ESTIMATION** et le scénario « ménages » est N/D (aucune donnée de ménages). Les deux valeurs (54,5 % et 57,82 %) sont affichées côte à côte.
- Étape 3 : aucune divergence numérique trouvée.
- Étape 4 : clic carte → filtres globaux → fiche, persistance entre pages, URL partageable (test navigateur réel), recherche de territoire, comparaison 2–4, export CSV par page, export PNG de la carte (barre d'outils Plotly).

## 5. Limites restantes (honnêtes)
- Le **tiroir de filtres mobile** (bouton flottant « Filtres ») est codé en CSS mais **n'a pas été vérifié par un clic automatisé** ; les captures mobiles montrent un en-tête plus haut que nécessaire (boutons FR/EN empilés).
- Export **PNG** : disponible sur les cartes ; les autres graphiques n'ont pas de barre d'outils (désactivée pour la lisibilité).
- La règle « max 3 constats + détail en expander » n'est pas imposée mécaniquement sur toutes les pages (appliquée sur Accueil, État civil).
- Les points de la Carte interactive en mode « Région » reprennent la valeur régionale pour chaque préfecture (mosaïque) ; l'IPT n'existe qu'au niveau unité/préfecture.
- Contours des cartes : indicatifs (fournis avec le gabarit).
- Aucune donnée d'état civil territorialisée : N/D, non estimée.
- Palette `CLASS_COL` de la page Priorités encore verte/rouge (non vérifiée daltonisme) ; les autres cartes utilisent des palettes bleu/rouge.

## 6. Auto-évaluation honnête
- **C1 (ergonomie, /4) — ≈ 3,3** : navigation à 9 entrées lisible et contrastée, résumé 30 s, infobulles, glossaire partout, captures vérifiées. Manque : tiroir mobile non prouvé, contrainte « 3 constats max » partielle.
- **C2 (pertinence, /8) — ≈ 7** : recommandations dérivées mécaniquement de l'IPT et testées, réconciliation documentée, 194 tests, audit indépendant. Manque : l'écart 2021 n'est reproduit que par estimation.
- **C3 (interactions, /4) — ≈ 3,5** : clics carte → filtres → fiche, persistance, URL, recherche, comparaison, exports, réexécution < 0,5 s. Manque : PNG limité aux cartes.

**Total estimé ≈ 17,8 / 20.** Le seuil de **19/20 n'est pas démontré** : il faudrait vérifier le tiroir mobile, généraliser l'export PNG et la règle des 3 constats, et lever l'écart 2021 (impossible sans la documentation du dénominateur de la source).
