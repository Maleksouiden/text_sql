from flask import Flask, render_template, request, jsonify, session
import re
import datetime
import os
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import sqlparse

# Télécharger les ressources NLTK nécessaires
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Clé secrète pour les sessions

# Fonction avancée pour détecter le type de requête SQL
def detect_sql_type(description):
    """Détecte intelligemment le type de requête SQL à partir de la description"""
    description_lower = description.lower()

    # Dictionnaire de mots-clés avec poids pour une meilleure détection
    sql_keywords = {
        "SELECT": {
            "keywords": ["sélectionner", "select", "afficher", "montrer", "lister", "obtenir", "récupérer",
                        "chercher", "trouver", "voir", "extraire", "query", "requête", "interroger",
                        "données", "data", "information", "résultat", "quels sont", "combien", "qui", "quand"],
            "weight": 1.0,
            "patterns": [
                r"(?:affiche|montre|liste|donne|trouve)(?:-moi)?\s+(?:les?|tous\s+les|toutes\s+les)?",
                r"(?:je\s+(?:veux|souhaite|aimerais|voudrais)\s+(?:voir|obtenir|avoir|connaître))",
                r"(?:quels?\s+sont|combien\s+(?:de|d'))",
                r"(?:recherche|cherche|trouve)"
            ]
        },
        "INSERT": {
            "keywords": ["insérer", "insert", "ajouter", "créer une ligne", "créer un enregistrement",
                        "nouvelle entrée", "nouvelle ligne", "nouveau", "nouvelle", "enregistrer", "stocker"],
            "weight": 1.2,
            "patterns": [
                r"(?:ajoute|insère|crée|enregistre|stocke)",
                r"(?:nouvelle?|nouveau)\s+(?:ligne|enregistrement|entrée|donnée)",
                r"(?:je\s+(?:veux|souhaite|aimerais|voudrais)\s+(?:ajouter|insérer|créer|enregistrer))"
            ]
        },
        "UPDATE": {
            "keywords": ["mettre à jour", "update", "modifier", "changer", "actualiser", "éditer",
                        "remplacer", "corriger", "ajuster"],
            "weight": 1.2,
            "patterns": [
                r"(?:modifie|change|mets?\s+à\s+jour|actualise|édite|remplace|corrige)",
                r"(?:je\s+(?:veux|souhaite|aimerais|voudrais)\s+(?:modifier|changer|mettre\s+à\s+jour))"
            ]
        },
        "DELETE": {
            "keywords": ["supprimer", "delete", "effacer", "enlever", "retirer", "éliminer", "détruire", "ôter"],
            "weight": 1.3,
            "patterns": [
                r"(?:supprime|efface|enlève|retire|élimine|détruis)",
                r"(?:je\s+(?:veux|souhaite|aimerais|voudrais)\s+(?:supprimer|effacer|enlever|retirer))"
            ]
        },
        "CREATE": {
            "keywords": ["créer", "create", "nouvelle", "nouveau", "définir", "construire", "structure", "schéma"],
            "weight": 1.4,
            "patterns": [
                r"(?:crée|définis|construis)\s+(?:une|la|ma)?\s+(?:table|vue|index|procédure|fonction|trigger)",
                r"(?:nouvelle|nouveau)\s+(?:table|vue|index|procédure|fonction|trigger)",
                r"(?:je\s+(?:veux|souhaite|aimerais|voudrais)\s+(?:créer|définir))"
            ]
        },
        "ALTER": {
            "keywords": ["modifier", "alter", "changer", "ajouter", "supprimer", "structure", "schéma"],
            "weight": 1.4,
            "patterns": [
                r"(?:modifie|change|altère)\s+(?:la|ma|une)?\s+(?:table|vue|index|procédure|fonction|trigger)",
                r"(?:ajoute|supprime|retire|modifie)\s+(?:une|la|des|les)?\s+(?:colonne|contrainte|index)",
                r"(?:je\s+(?:veux|souhaite|aimerais|voudrais)\s+(?:modifier|changer))"
            ]
        },
        "DROP": {
            "keywords": ["supprimer", "drop", "effacer", "détruire", "éliminer"],
            "weight": 1.5,
            "patterns": [
                r"(?:supprime|efface|détruis|élimine)\s+(?:la|ma|une)?\s+(?:table|vue|index|procédure|fonction|trigger)",
                r"(?:je\s+(?:veux|souhaite|aimerais|voudrais)\s+(?:supprimer|effacer|détruire))"
            ]
        },
        "TRUNCATE": {
            "keywords": ["vider", "truncate", "effacer tout", "supprimer tout", "réinitialiser"],
            "weight": 1.5,
            "patterns": [
                r"(?:vide|efface|réinitialise)\s+(?:la|ma|une)?\s+table",
                r"(?:supprime|efface)\s+(?:toutes\s+les|tous\s+les)\s+(?:données|enregistrements)",
                r"(?:je\s+(?:veux|souhaite|aimerais|voudrais)\s+(?:vider|réinitialiser))"
            ]
        }
    }

    # Scores pour chaque type de requête
    scores = {sql_type: 0 for sql_type in sql_keywords}

    # Calculer les scores basés sur les mots-clés
    for sql_type, type_info in sql_keywords.items():
        # Vérifier les mots-clés
        for keyword in type_info["keywords"]:
            if keyword in description_lower:
                scores[sql_type] += type_info["weight"]

        # Vérifier les patterns (expressions régulières)
        for pattern in type_info["patterns"]:
            if re.search(pattern, description_lower):
                scores[sql_type] += type_info["weight"] * 1.5  # Les patterns ont plus de poids

    # Analyse contextuelle supplémentaire
    if "table" in description_lower and "existe" in description_lower:
        scores["SELECT"] += 0.5  # Probablement une vérification d'existence

    if "nombre" in description_lower or "count" in description_lower:
        scores["SELECT"] += 0.8  # Probablement un comptage

    if "moyenne" in description_lower or "somme" in description_lower or "total" in description_lower:
        scores["SELECT"] += 0.8  # Probablement une agrégation

    if "si" in description_lower and "existe" in description_lower:
        scores["SELECT"] += 0.5  # Probablement une condition d'existence

    # Détection des tables et champs mentionnés pour affiner l'analyse
    tables_match = re.search(r"tables?\s+(\w+(?:,\s*\w+)*)", description_lower)
    if tables_match:
        scores["SELECT"] += 0.3  # Mention explicite de tables favorise SELECT

    champs_match = re.search(r"champs?\s+(\w+(?:,\s*\w+)*)", description_lower)
    if champs_match:
        scores["SELECT"] += 0.3  # Mention explicite de champs favorise SELECT

    # Trouver le type avec le score le plus élevé
    max_score = 0
    detected_type = "SELECT"  # Par défaut

    for sql_type, score in scores.items():
        if score > max_score:
            max_score = score
            detected_type = sql_type

    # Si aucun type n'a un score significatif, on suppose que c'est une requête SELECT
    if max_score < 0.5:
        return "SELECT"

    return detected_type

# Fonction pour détecter automatiquement les options avancées pour les requêtes SQL
def detect_advanced_options(description, sql_type):
    """Détecte automatiquement les options avancées pour les requêtes SQL"""
    description_lower = description.lower()

    # Tokenisation et nettoyage du texte
    tokens = word_tokenize(description_lower, language='french')
    french_stopwords = set(stopwords.words('french'))
    tokens = [token for token in tokens if token not in french_stopwords]

    # Options avancées communes à tous les types de requêtes
    common_options = {
        "subquery": False,     # Sous-requêtes
        "cte": False,          # Common Table Expressions (WITH)
        "join": False,         # Jointures
        "condition": False,    # Conditions (WHERE)
        "transaction": False,  # Transactions
        "case": False,         # Expressions CASE
        "function": False,     # Fonctions SQL
    }

    # Options spécifiques par type de requête
    type_specific_options = {
        "SELECT": {
            "distinct": False,      # Valeurs distinctes
            "aggregate": False,     # Fonctions d'agrégation
            "groupby": False,       # Groupement
            "having": False,        # Filtrage après groupement
            "orderby": False,       # Tri
            "limit": False,         # Limitation des résultats
            "offset": False,        # Décalage des résultats
            "window": False,        # Fonctions de fenêtre
            "recursive": False,     # Requêtes récursives
            "union": False,         # UNION, INTERSECT, EXCEPT
        },
        "INSERT": {
            "values": False,        # Valeurs explicites
            "select": False,        # INSERT ... SELECT
            "multiple": False,      # Insertion multiple
            "returning": False,     # Clause RETURNING
            "upsert": False,        # INSERT ... ON CONFLICT (UPSERT)
        },
        "UPDATE": {
            "multiple_columns": False,  # Mise à jour de plusieurs colonnes
            "from": False,              # Clause FROM
            "returning": False,         # Clause RETURNING
        },
        "DELETE": {
            "truncate": False,      # TRUNCATE au lieu de DELETE
            "returning": False,     # Clause RETURNING
            "cascade": False,       # Suppression en cascade
        },
        "CREATE": {
            "if_not_exists": False,  # IF NOT EXISTS
            "constraints": False,    # Contraintes
            "indexes": False,        # Index
            "foreign_keys": False,   # Clés étrangères
            "temporary": False,      # Tables temporaires
            "view": False,           # Vues
            "procedure": False,      # Procédures stockées
            "trigger": False,        # Déclencheurs
        },
        "ALTER": {
            "add_column": False,     # Ajout de colonne
            "drop_column": False,    # Suppression de colonne
            "modify_column": False,  # Modification de colonne
            "rename": False,         # Renommage
            "constraints": False,    # Contraintes
        },
        "DROP": {
            "if_exists": False,      # IF EXISTS
            "cascade": False,        # CASCADE
        }
    }

    # Initialiser les options en fonction du type de requête
    advanced_options = common_options.copy()
    if sql_type in type_specific_options:
        advanced_options.update(type_specific_options[sql_type])

    # Mots-clés et patterns pour les options communes
    common_patterns = {
        "subquery": {
            "keywords": ["sous-requête", "subquery", "requête imbriquée", "nested query", "in", "exists", "any", "all"],
            "patterns": [r"(?:sous[-\s]requête(?:s)?|requête(?:s)?\s+imbriquée(?:s)?)",
                        r"(?:où\s+existe(?:nt)?|where\s+exists)",
                        r"(?:dans\s+(?:une|la|des|les)?\s+(?:autre(?:s)?\s+)?requête(?:s)?)",
                        r"(?:in|exists|any|all)"]
        },
        "cte": {
            "keywords": ["cte", "with", "avec", "table temporaire", "table commune", "expression de table commune"],
            "patterns": [r"(?:utilise|avec|using)\s+(?:une|des)?\s+(?:cte|with|table(?:s)?\s+commune(?:s)?)",
                        r"(?:table(?:s)?\s+temporaire(?:s)?)",
                        r"(?:expression(?:s)?\s+de\s+table(?:s)?\s+commune(?:s)?)"]
        },
        "join": {
            "keywords": ["join", "jointure", "inner join", "left join", "right join", "full join", "cross join", "natural join"],
            "patterns": [r"(?:jointure(?:s)?|join)",
                        r"(?:inner|left|right|full|cross|natural)\s+join",
                        r"(?:jointure(?:s)?\s+(?:interne(?:s)?|externe(?:s)?|gauche|droite|complète(?:s)?|croisée(?:s)?|naturelle(?:s)?))",
                        r"(?:reli(?:er|ant)|lier|lié(?:e)?(?:s)?)\s+(?:avec|à|aux?|les?|la)"]
        },
        "condition": {
            "keywords": ["where", "où", "condition", "filtre", "filtrer", "quand", "lorsque", "si"],
            "patterns": [r"(?:où|where|quand|lorsque|si)",
                        r"(?:avec\s+(?:une|des)?\s+condition(?:s)?)",
                        r"(?:filtr(?:er|ant|é))",
                        r"(?:seulement\s+(?:si|quand|lorsque))"]
        },
        "transaction": {
            "keywords": ["transaction", "commit", "rollback", "begin", "start transaction", "savepoint"],
            "patterns": [r"(?:transaction|commit|rollback|begin|start\s+transaction|savepoint)",
                        r"(?:valider|annuler|commencer|débuter)\s+(?:une|la)?\s+transaction"]
        },
        "case": {
            "keywords": ["case", "when", "then", "else", "end", "cas", "quand", "alors", "sinon", "fin"],
            "patterns": [r"(?:case|when|then|else|end)",
                        r"(?:cas|quand|alors|sinon|fin)",
                        r"(?:différents?\s+cas)",
                        r"(?:selon\s+(?:la|le|les)?\s+valeur(?:s)?)"]
        },
        "function": {
            "keywords": ["function", "fonction", "procedure", "procédure", "appeler", "call"],
            "patterns": [r"(?:function|fonction|procedure|procédure)",
                        r"(?:appel(?:er|ant)|call)",
                        r"(?:utiliser|exécuter)\s+(?:une|la|des|les)?\s+(?:fonction|procédure)"]
        }
    }

    # Mots-clés et patterns pour les options spécifiques à SELECT
    select_patterns = {
        "distinct": {
            "keywords": ["distinct", "unique", "différent", "sans doublon", "sans répétition"],
            "patterns": [r"(?:distinct|unique|différent(?:e)?(?:s)?)",
                        r"(?:sans\s+(?:doublon|répétition)(?:s)?)",
                        r"(?:valeur(?:s)?\s+unique(?:s)?)",
                        r"(?:élimin(?:er|ant)\s+(?:les\s+)?doublon(?:s)?)"]
        },
        "aggregate": {
            "keywords": ["count", "sum", "avg", "min", "max", "moyenne", "somme", "total", "minimum", "maximum", "compter", "calculer"],
            "patterns": [r"(?:count|sum|avg|min|max|moyenne|somme|total|minimum|maximum)",
                        r"(?:compt(?:er|age)|calcul(?:er)?|somme(?:r)?)\s+(?:le|la|les|des?|du|total)",
                        r"(?:nombre\s+(?:de|d'))",
                        r"(?:valeur(?:s)?\s+(?:moyenne(?:s)?|minimal(?:es)?|maximal(?:es)?))"]
        },
        "groupby": {
            "keywords": ["group by", "grouper", "regrouper", "groupement", "regroupement", "par"],
            "patterns": [r"(?:group(?:er|é(?:e)?(?:s)?)?|regroup(?:er|é(?:e)?(?:s)?)?)\s+par",
                        r"(?:group\s+by)",
                        r"(?:par\s+(?:groupe(?:s)?|catégorie(?:s)?|type(?:s)?))"]
        },
        "having": {
            "keywords": ["having", "ayant", "avec condition", "filtrer groupes", "filtrer après groupement"],
            "patterns": [r"(?:having|ayant)",
                        r"(?:avec\s+(?:une|des)?\s+condition(?:s)?)\s+(?:sur|après)\s+(?:le|les)?\s+group(?:e|ement)(?:s)?",
                        r"(?:filtr(?:er|ant))\s+(?:les|des)?\s+groupe(?:s)?",
                        r"(?:après\s+(?:avoir|le)?\s+group(?:é|ement))"]
        },
        "orderby": {
            "keywords": ["order by", "trier", "ordonner", "tri", "ordre", "sort", "asc", "desc", "ascendant", "descendant"],
            "patterns": [r"(?:order\s+by|trier|ordonner|tri(?:é)?(?:e)?(?:s)?|ordre)",
                        r"(?:par\s+ordre\s+(?:croissant|décroissant))",
                        r"(?:(?:a|de)scendant)",
                        r"(?:du\s+plus\s+(?:petit|grand)\s+au\s+plus\s+(?:grand|petit))"]
        },
        "limit": {
            "keywords": ["limit", "limiter", "limite", "top", "first", "premiers", "premières"],
            "patterns": [r"(?:limit(?:er|é(?:e)?(?:s)?)?|limite(?:r)?)",
                        r"(?:top|first)",
                        r"(?:les?\s+\d+\s+premier(?:s|ères)?)",
                        r"(?:seulement|uniquement)\s+\d+",
                        r"(?:limit(?:é)?\s+à\s+\d+)"]
        },
        "offset": {
            "keywords": ["offset", "décalage", "sauter", "skip", "à partir de"],
            "patterns": [r"(?:offset|décalage|sauter|skip)",
                        r"(?:à\s+partir\s+(?:du|de\s+la|des?)\s+\d+)",
                        r"(?:commencer\s+(?:au|à\s+la|aux?)\s+\d+)"]
        },
        "window": {
            "keywords": ["window", "fenêtre", "over", "partition by", "partitionner", "rank", "dense_rank", "row_number", "ntile", "lead", "lag"],
            "patterns": [r"(?:fonction(?:s)?\s+de\s+fenêtre(?:s)?)",
                        r"(?:partition(?:ner)?|over|rank|dense_rank|row_number|ntile|lead|lag)",
                        r"(?:calcul(?:er)?)\s+(?:sur|par)\s+(?:groupe(?:s)?|fenêtre(?:s)?|partition(?:s)?)"]
        },
        "recursive": {
            "keywords": ["recursive", "récursif", "récursive", "récursion", "with recursive", "hierarchie", "hiérarchique", "arbre", "tree"],
            "patterns": [r"(?:requête(?:s)?\s+récursive(?:s)?)",
                        r"(?:with\s+recursive)",
                        r"(?:hiérarch(?:ie|ique)|arbre|tree|parent(?:s)?(?:\s+et)?\s+enfant(?:s)?)",
                        r"(?:structure(?:s)?\s+(?:récursive(?:s)?|hiérarchique(?:s)?|en\s+arbre))"]
        },
        "union": {
            "keywords": ["union", "intersect", "except", "union all", "combiner", "fusionner", "unir"],
            "patterns": [r"(?:union|intersect|except|union\s+all)",
                        r"(?:combin(?:er|ant)|fusionn(?:er|ant)|unir|unissant)",
                        r"(?:résultats?\s+(?:de|des)\s+(?:plusieurs|deux|trois|multiple(?:s)?)\s+requêtes?)"]
        }
    }

    # Mots-clés et patterns pour les options spécifiques à INSERT
    insert_patterns = {
        "values": {
            "keywords": ["values", "valeurs", "données", "data"],
            "patterns": [r"(?:values|valeurs|données|data)",
                        r"(?:avec\s+(?:les|des)?\s+valeurs)",
                        r"(?:spécifi(?:er|ant)\s+(?:les|des)?\s+valeurs)"]
        },
        "select": {
            "keywords": ["insert select", "insérer select", "insérer à partir de", "insert from"],
            "patterns": [r"(?:insert\s+select|insérer\s+select)",
                        r"(?:insérer\s+à\s+partir\s+de)",
                        r"(?:insert\s+from)",
                        r"(?:utiliser\s+(?:une|des|les)?\s+(?:autre(?:s)?\s+)?requête(?:s)?\s+pour\s+insérer)"]
        },
        "multiple": {
            "keywords": ["multiple", "plusieurs", "batch", "lot", "masse"],
            "patterns": [r"(?:multiple|plusieurs|batch|lot|masse)",
                        r"(?:insérer\s+(?:plusieurs|multiple(?:s)?|beaucoup\s+de)\s+(?:lignes|enregistrements|données))",
                        r"(?:insertion\s+(?:multiple|en\s+masse|par\s+lot))"]
        },
        "returning": {
            "keywords": ["returning", "retournant", "retourner", "récupérer"],
            "patterns": [r"(?:returning|retournant|retourner|récupérer)",
                        r"(?:obtenir\s+(?:les|des)?\s+(?:valeurs|données|id|identifiants)\s+(?:insérées|créées))",
                        r"(?:récupérer\s+(?:les|des)?\s+(?:valeurs|données|id|identifiants)\s+(?:après|suite\s+à)\s+(?:l'|une\s+)?insertion)"]
        },
        "upsert": {
            "keywords": ["upsert", "on conflict", "on duplicate key", "merge", "insérer ou mettre à jour"],
            "patterns": [r"(?:upsert|on\s+conflict|on\s+duplicate\s+key|merge)",
                        r"(?:insérer\s+ou\s+mettre\s+à\s+jour)",
                        r"(?:si\s+(?:existe|présent)\s+(?:alors|sinon)\s+(?:mettre\s+à\s+jour|modifier))"]
        }
    }

    # Mots-clés et patterns pour les options spécifiques à UPDATE
    update_patterns = {
        "multiple_columns": {
            "keywords": ["plusieurs colonnes", "multiple colonnes", "multiples champs", "plusieurs champs"],
            "patterns": [r"(?:plusieurs|multiple(?:s)?)\s+(?:colonnes|champs|attributs)",
                        r"(?:mettre\s+à\s+jour\s+(?:plusieurs|multiple(?:s)?)\s+(?:colonnes|champs|attributs))"]
        },
        "from": {
            "keywords": ["from", "à partir de", "en utilisant", "using"],
            "patterns": [r"(?:from|à\s+partir\s+de|en\s+utilisant|using)",
                        r"(?:mettre\s+à\s+jour\s+(?:en\s+utilisant|à\s+partir\s+de)\s+(?:une|des|les)?\s+(?:autre(?:s)?\s+)?(?:table(?:s)?|donnée(?:s)?))"]
        }
    }

    # Mots-clés et patterns pour les options spécifiques à DELETE
    delete_patterns = {
        "truncate": {
            "keywords": ["truncate", "vider", "tout supprimer", "effacer tout"],
            "patterns": [r"(?:truncate|vider|tout\s+supprimer|effacer\s+tout)",
                        r"(?:supprimer\s+(?:toutes\s+les|tous\s+les)\s+(?:données|enregistrements|lignes))"]
        },
        "cascade": {
            "keywords": ["cascade", "en cascade", "avec dépendances", "incluant les dépendances"],
            "patterns": [r"(?:cascade|en\s+cascade)",
                        r"(?:avec\s+(?:les|des)?\s+dépendances)",
                        r"(?:incluant\s+(?:les|des)?\s+(?:dépendances|liées|associées))"]
        }
    }

    # Mots-clés et patterns pour les options spécifiques à CREATE
    create_patterns = {
        "if_not_exists": {
            "keywords": ["if not exists", "si n'existe pas", "si non existant", "seulement si"],
            "patterns": [r"(?:if\s+not\s+exists|si\s+n'existe\s+pas|si\s+non\s+existant)",
                        r"(?:seulement\s+si\s+(?:la|une)?\s+table\s+n'existe\s+pas)",
                        r"(?:créer\s+(?:uniquement|seulement)\s+si\s+(?:n'existe\s+pas|absente))"]
        },
        "constraints": {
            "keywords": ["constraint", "contrainte", "check", "unique", "not null", "primary key"],
            "patterns": [r"(?:constraint|contrainte|check|unique|not\s+null|primary\s+key)",
                        r"(?:avec\s+(?:des|les)?\s+contraintes)",
                        r"(?:ajouter\s+(?:des|les)?\s+contraintes)"]
        },
        "indexes": {
            "keywords": ["index", "indice", "indexer"],
            "patterns": [r"(?:index|indice|indexer)",
                        r"(?:avec\s+(?:des|les)?\s+index)",
                        r"(?:créer\s+(?:des|les)?\s+index)"]
        },
        "foreign_keys": {
            "keywords": ["foreign key", "clé étrangère", "référence", "references"],
            "patterns": [r"(?:foreign\s+key|clé\s+étrangère|référence|references)",
                        r"(?:avec\s+(?:des|les)?\s+(?:clés\s+étrangères|références))",
                        r"(?:référençant|qui\s+référence)"]
        },
        "temporary": {
            "keywords": ["temporary", "temp", "temporaire", "provisoire"],
            "patterns": [r"(?:temporary|temp|temporaire|provisoire)",
                        r"(?:table\s+(?:temporaire|provisoire))",
                        r"(?:créer\s+(?:une)?\s+table\s+(?:temporaire|provisoire))"]
        },
        "view": {
            "keywords": ["view", "vue", "virtual table", "table virtuelle"],
            "patterns": [r"(?:view|vue|virtual\s+table|table\s+virtuelle)",
                        r"(?:créer\s+(?:une)?\s+vue)",
                        r"(?:définir\s+(?:une)?\s+vue)"]
        },
        "procedure": {
            "keywords": ["procedure", "procédure", "stored procedure", "procédure stockée"],
            "patterns": [r"(?:procedure|procédure|stored\s+procedure|procédure\s+stockée)",
                        r"(?:créer\s+(?:une)?\s+procédure)",
                        r"(?:définir\s+(?:une)?\s+procédure)"]
        },
        "trigger": {
            "keywords": ["trigger", "déclencheur", "event", "événement"],
            "patterns": [r"(?:trigger|déclencheur|event|événement)",
                        r"(?:créer\s+(?:un)?\s+(?:trigger|déclencheur))",
                        r"(?:définir\s+(?:un)?\s+(?:trigger|déclencheur))"]
        }
    }

    # Mots-clés et patterns pour les options spécifiques à ALTER
    alter_patterns = {
        "add_column": {
            "keywords": ["add column", "ajouter colonne", "nouvelle colonne", "ajout de colonne"],
            "patterns": [r"(?:add\s+column|ajouter\s+(?:une)?\s+colonne|nouvelle\s+colonne|ajout\s+de\s+colonne)",
                        r"(?:ajouter\s+(?:un|le)?\s+champ)",
                        r"(?:créer\s+(?:une)?\s+(?:nouvelle)?\s+colonne)"]
        },
        "drop_column": {
            "keywords": ["drop column", "supprimer colonne", "enlever colonne", "retirer colonne"],
            "patterns": [r"(?:drop\s+column|supprimer\s+(?:une)?\s+colonne|enlever\s+(?:une)?\s+colonne|retirer\s+(?:une)?\s+colonne)",
                        r"(?:supprimer\s+(?:un|le)?\s+champ)",
                        r"(?:éliminer\s+(?:une)?\s+colonne)"]
        },
        "modify_column": {
            "keywords": ["modify column", "alter column", "change column", "modifier colonne", "changer colonne"],
            "patterns": [r"(?:modify\s+column|alter\s+column|change\s+column|modifier\s+(?:une)?\s+colonne|changer\s+(?:une)?\s+colonne)",
                        r"(?:modifier\s+(?:un|le)?\s+champ)",
                        r"(?:changer\s+(?:le)?\s+type)"]
        },
        "rename": {
            "keywords": ["rename", "renommer", "changer nom", "nouveau nom"],
            "patterns": [r"(?:rename|renommer|changer\s+(?:le)?\s+nom|nouveau\s+nom)",
                        r"(?:renommer\s+(?:une|la)?\s+(?:table|colonne|champ))",
                        r"(?:changer\s+(?:le)?\s+nom\s+(?:de|d'une|de\s+la)\s+(?:table|colonne|champ))"]
        }
    }

    # Mots-clés et patterns pour les options spécifiques à DROP
    drop_patterns = {
        "if_exists": {
            "keywords": ["if exists", "si existe", "si existant", "seulement si"],
            "patterns": [r"(?:if\s+exists|si\s+existe|si\s+existant)",
                        r"(?:seulement\s+si\s+(?:la|une)?\s+table\s+existe)",
                        r"(?:supprimer\s+(?:uniquement|seulement)\s+si\s+(?:existe|présente))"]
        },
        "cascade": {
            "keywords": ["cascade", "en cascade", "avec dépendances", "incluant les dépendances"],
            "patterns": [r"(?:cascade|en\s+cascade)",
                        r"(?:avec\s+(?:les|des)?\s+dépendances)",
                        r"(?:incluant\s+(?:les|des)?\s+(?:dépendances|liées|associées))"]
        }
    }

    # Regrouper tous les patterns par type de requête
    all_patterns = {
        "common": common_patterns,
        "SELECT": select_patterns,
        "INSERT": insert_patterns,
        "UPDATE": update_patterns,
        "DELETE": delete_patterns,
        "CREATE": create_patterns,
        "ALTER": alter_patterns,
        "DROP": drop_patterns
    }

    # Détecter les options communes
    for option, patterns_info in common_patterns.items():
        # Vérifier les mots-clés
        for keyword in patterns_info["keywords"]:
            if keyword in description_lower:
                advanced_options[option] = True
                break

        # Si l'option n'est pas encore détectée, vérifier les patterns
        if not advanced_options[option]:
            for pattern in patterns_info["patterns"]:
                if re.search(pattern, description_lower):
                    advanced_options[option] = True
                    break

    # Détecter les options spécifiques au type de requête
    if sql_type in all_patterns:
        type_patterns = all_patterns[sql_type]
        for option, patterns_info in type_patterns.items():
            if option in advanced_options:  # Vérifier que l'option existe pour ce type
                # Vérifier les mots-clés
                for keyword in patterns_info["keywords"]:
                    if keyword in description_lower:
                        advanced_options[option] = True
                        break

                # Si l'option n'est pas encore détectée, vérifier les patterns
                if not advanced_options[option]:
                    for pattern in patterns_info["patterns"]:
                        if re.search(pattern, description_lower):
                            advanced_options[option] = True
                            break

    # Analyse contextuelle supplémentaire
    if sql_type == "SELECT":
        # Détection des tables et champs mentionnés
        tables_match = re.search(r"tables?\s+(\w+(?:,\s*\w+)*)", description_lower)
        if tables_match and "," in tables_match.group(1):
            advanced_options["join"] = True  # Plusieurs tables impliquent probablement des jointures

        # Détection des fonctions d'agrégation
        if re.search(r"(?:moyenne|somme|total|count|min|max|nombre\s+de)", description_lower):
            advanced_options["aggregate"] = True

            # Si agrégation détectée, vérifier s'il y a un groupement
            if re.search(r"(?:par|pour\s+chaque|selon|en\s+fonction\s+de)\s+\w+", description_lower):
                advanced_options["groupby"] = True

    return advanced_options

# Fonction pour extraire intelligemment les tables et champs mentionnés dans la description
def extract_tables_and_fields(description, sql_type):
    """Extrait intelligemment les tables et champs mentionnés dans la description"""
    description_lower = description.lower()

    # Extraction des tables
    tables = []
    tables_pattern = r"tables?\s+(\w+(?:,\s*\w+)*)"
    tables_match = re.search(tables_pattern, description_lower, re.IGNORECASE)

    if tables_match:
        tables = [t.strip() for t in tables_match.group(1).split(',')]
    else:
        # Recherche de noms de tables potentiels dans la description
        potential_tables = []
        words = description_lower.split()

        # Mots à ignorer car ce sont probablement des mots communs et non des noms de tables
        ignore_words = ["select", "from", "where", "group", "by", "having", "order", "limit", "join",
                        "inner", "left", "right", "full", "cross", "natural", "on", "and", "or", "not",
                        "in", "between", "like", "is", "null", "as", "distinct", "all", "les", "des",
                        "pour", "avec", "sans", "dans", "qui", "que", "quoi", "comment", "pourquoi",
                        "quand", "où", "je", "tu", "il", "elle", "nous", "vous", "ils", "elles",
                        "insert", "into", "values", "update", "set", "delete", "create", "alter", "drop",
                        "table", "view", "index", "procedure", "function", "trigger", "constraint"]

        # Mots qui sont souvent des noms de tables
        table_indicators = ["utilisateurs", "users", "clients", "customers", "produits", "products",
                           "commandes", "orders", "ventes", "sales", "employés", "employees",
                           "catégories", "categories", "articles", "items", "factures", "invoices",
                           "fournisseurs", "suppliers", "stocks", "inventory", "paiements", "payments",
                           "livraisons", "shipments", "adresses", "addresses", "commentaires", "comments"]

        # Chercher d'abord les indicateurs de tables
        for indicator in table_indicators:
            if indicator in description_lower:
                potential_tables.append(indicator)

        # Si aucun indicateur n'est trouvé, chercher d'autres mots potentiels
        if not potential_tables:
            for word in words:
                # Nettoyer le mot
                clean_word = re.sub(r'[^\w]', '', word)
                if clean_word and clean_word not in ignore_words and len(clean_word) > 2:
                    # Vérifier si le mot ressemble à un nom de table (singulier ou pluriel)
                    if clean_word.endswith('s'):
                        potential_tables.append(clean_word)

        # Utiliser les tables potentielles ou une table générique
        if potential_tables:
            tables = potential_tables[:2]  # Limiter à 2 tables pour éviter le bruit
        else:
            # Table par défaut selon le type de requête
            if sql_type == "SELECT" or sql_type == "DELETE":
                tables = ["utilisateurs"]
            elif sql_type == "INSERT":
                tables = ["utilisateurs"]
            elif sql_type == "UPDATE":
                tables = ["utilisateurs"]
            elif sql_type == "CREATE" or sql_type == "DROP" or sql_type == "ALTER":
                tables = ["nouvelle_table"]

    # Extraction des champs
    fields = []
    fields_pattern = r"champs?\s+(\w+(?:,\s*\w+)*)"
    fields_match = re.search(fields_pattern, description_lower, re.IGNORECASE)

    if fields_match:
        fields = [f.strip() for f in fields_match.group(1).split(',')]
    else:
        # Recherche de noms de champs potentiels dans la description
        potential_fields = []

        # Champs communs par type de table
        common_fields = {
            "utilisateurs": ["id", "nom", "prenom", "email", "date_inscription", "mot_de_passe", "role", "statut"],
            "users": ["id", "name", "first_name", "email", "registration_date", "password", "role", "status"],
            "clients": ["id", "nom", "prenom", "email", "telephone", "adresse", "ville", "pays", "code_postal"],
            "customers": ["id", "name", "email", "phone", "address", "city", "country", "postal_code"],
            "produits": ["id", "nom", "prix", "description", "categorie", "stock", "date_creation", "fournisseur_id"],
            "products": ["id", "name", "price", "description", "category", "stock", "creation_date", "supplier_id"],
            "commandes": ["id", "date", "client_id", "montant", "statut", "adresse_livraison", "date_livraison"],
            "orders": ["id", "date", "customer_id", "amount", "status", "shipping_address", "delivery_date"],
            "ventes": ["id", "date", "produit_id", "quantite", "montant", "client_id", "vendeur_id"],
            "sales": ["id", "date", "product_id", "quantity", "amount", "customer_id", "seller_id"],
            "employés": ["id", "nom", "prenom", "poste", "salaire", "date_embauche", "departement", "manager_id"],
            "employees": ["id", "name", "first_name", "position", "salary", "hire_date", "department", "manager_id"]
        }

        # Patterns pour détecter les champs
        field_patterns = [
            r"(?:le|la|les)\s+(?:champ|colonne|attribut)s?\s+(\w+)",
            r"(?:afficher|montrer|sélectionner|obtenir|insérer|mettre à jour)\s+(?:le|la|les)?\s+(\w+)",
            r"(?:valeurs?|données?)\s+(?:de|du|des|pour)\s+(?:la|le|les)?\s+(\w+)"
        ]

        for pattern in field_patterns:
            matches = re.finditer(pattern, description_lower)
            for match in matches:
                if match.group(1) not in ["table", "tables", "champ", "champs", "colonne", "colonnes"]:
                    potential_fields.append(match.group(1))

        # Si aucun champ n'est trouvé, utiliser des champs communs basés sur les tables détectées
        if not potential_fields:
            for table in tables:
                if table in common_fields:
                    potential_fields.extend(common_fields[table])

            # Si toujours aucun champ, utiliser des champs génériques selon le type de requête
            if not potential_fields:
                if sql_type == "SELECT":
                    potential_fields = ["id", "nom", "date", "montant"]
                elif sql_type == "INSERT" or sql_type == "UPDATE":
                    potential_fields = ["nom", "email", "date", "statut"]
                elif sql_type == "CREATE":
                    potential_fields = ["id", "nom", "description", "date_creation", "statut"]

        fields = list(set(potential_fields))  # Éliminer les doublons

    return tables, fields

# Fonction pour corriger une requête SQL
def correct_sql_query(query):
    """Corrige une requête SQL en détectant et corrigeant les erreurs courantes"""
    # Vérifier si la requête est vide
    if not query or query.strip() == "":
        return {
            "corrected": False,
            "original": query,
            "corrected_query": query,
            "errors": ["La requête est vide"],
            "suggestions": ["Veuillez fournir une requête SQL valide"]
        }

    # Nettoyer la requête
    original_query = query
    query = query.strip()

    # Analyser la requête avec sqlparse
    try:
        parsed = sqlparse.parse(query)
        if not parsed:
            return {
                "corrected": False,
                "original": original_query,
                "corrected_query": query,
                "errors": ["Impossible d'analyser la requête"],
                "suggestions": ["Vérifiez la syntaxe de votre requête"]
            }
    except Exception as e:
        return {
            "corrected": False,
            "original": original_query,
            "corrected_query": query,
            "errors": [f"Erreur lors de l'analyse de la requête: {str(e)}"],
            "suggestions": ["Vérifiez la syntaxe de votre requête"]
        }

    # Initialiser les variables pour les corrections
    corrected = False
    errors = []
    suggestions = []
    corrected_query = query

    # Détecter le type de requête
    query_type = None
    if parsed[0].tokens:
        first_token = parsed[0].tokens[0]
        if first_token.ttype is sqlparse.tokens.Keyword.DML:
            query_type = str(first_token).upper()
        elif first_token.ttype is sqlparse.tokens.Keyword.DDL:
            query_type = str(first_token).upper()

    # Si le type de requête n'est pas détecté, essayer de le détecter manuellement
    if not query_type:
        if re.match(r'^\s*SELECT\b', query, re.IGNORECASE):
            query_type = "SELECT"
        elif re.match(r'^\s*INSERT\b', query, re.IGNORECASE):
            query_type = "INSERT"
        elif re.match(r'^\s*UPDATE\b', query, re.IGNORECASE):
            query_type = "UPDATE"
        elif re.match(r'^\s*DELETE\b', query, re.IGNORECASE):
            query_type = "DELETE"
        elif re.match(r'^\s*CREATE\b', query, re.IGNORECASE):
            query_type = "CREATE"
        elif re.match(r'^\s*ALTER\b', query, re.IGNORECASE):
            query_type = "ALTER"
        elif re.match(r'^\s*DROP\b', query, re.IGNORECASE):
            query_type = "DROP"

    # Si le type de requête n'est toujours pas détecté, c'est une erreur
    if not query_type:
        errors.append("Type de requête non reconnu")
        suggestions.append("La requête doit commencer par un mot-clé SQL valide (SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP)")
        return {
            "corrected": False,
            "original": original_query,
            "corrected_query": corrected_query,
            "errors": errors,
            "suggestions": suggestions
        }

    # Vérifier les erreurs courantes selon le type de requête
    if query_type == "SELECT":
        # Vérifier si FROM est présent
        if not re.search(r'\bFROM\b', query, re.IGNORECASE):
            errors.append("Clause FROM manquante")
            suggestions.append("Ajoutez une clause FROM pour spécifier la table source")
            corrected_query = re.sub(r'^\s*SELECT\b(.*?)(?:\bWHERE\b|$)', r'SELECT\1 FROM table_name WHERE', corrected_query, flags=re.IGNORECASE)
            corrected = True

        # Vérifier les virgules dans la liste des champs
        select_clause_match = re.search(r'SELECT\s+(.*?)\s+FROM', query, re.IGNORECASE | re.DOTALL)
        if select_clause_match:
            select_clause = select_clause_match.group(1)
            # Vérifier les espaces sans virgules entre les champs
            if re.search(r'[a-zA-Z0-9_]+\s+[a-zA-Z0-9_]+', select_clause) and not re.search(r'[a-zA-Z0-9_]+\s*,\s*[a-zA-Z0-9_]+', select_clause) and not re.search(r'\*', select_clause):
                errors.append("Virgules manquantes entre les champs dans la clause SELECT")
                suggestions.append("Ajoutez des virgules pour séparer les champs dans la clause SELECT")
                corrected_select = re.sub(r'([a-zA-Z0-9_]+)\s+([a-zA-Z0-9_]+)', r'\1, \2', select_clause)
                corrected_query = corrected_query.replace(select_clause, corrected_select)
                corrected = True

        # Vérifier les conditions WHERE
        where_clause_match = re.search(r'WHERE\s+(.*?)(?:\bGROUP BY\b|\bHAVING\b|\bORDER BY\b|\bLIMIT\b|$)', query, re.IGNORECASE | re.DOTALL)
        if where_clause_match:
            where_clause = where_clause_match.group(1)
            # Vérifier les opérateurs de comparaison manquants
            if re.search(r'[a-zA-Z0-9_]+\s+[\'"]', where_clause) or re.search(r'[a-zA-Z0-9_]+\s+\d+', where_clause):
                errors.append("Opérateur de comparaison manquant dans la clause WHERE")
                suggestions.append("Ajoutez un opérateur de comparaison (=, <, >, <=, >=, !=) dans la clause WHERE")
                corrected_where = re.sub(r'([a-zA-Z0-9_]+)\s+([\'"])', r'\1 = \2', where_clause)
                corrected_where = re.sub(r'([a-zA-Z0-9_]+)\s+(\d+)', r'\1 = \2', corrected_where)
                corrected_query = corrected_query.replace(where_clause, corrected_where)
                corrected = True

    elif query_type == "INSERT":
        # Vérifier si INTO est présent
        if not re.search(r'\bINTO\b', query, re.IGNORECASE):
            errors.append("Mot-clé INTO manquant")
            suggestions.append("Utilisez la syntaxe 'INSERT INTO table_name'")
            corrected_query = re.sub(r'^\s*INSERT\b\s+', r'INSERT INTO ', corrected_query, flags=re.IGNORECASE)
            corrected = True

        # Vérifier si VALUES ou SELECT est présent
        if not re.search(r'\bVALUES\b', query, re.IGNORECASE) and not re.search(r'\bSELECT\b', query, re.IGNORECASE):
            errors.append("Clause VALUES ou SELECT manquante")
            suggestions.append("Ajoutez une clause VALUES ou SELECT après la liste des colonnes")
            # Essayer de détecter la fin de la liste des colonnes
            columns_match = re.search(r'\(([^)]+)\)', query)
            if columns_match:
                corrected_query = re.sub(r'\(([^)]+)\)', r'(\1) VALUES ()', corrected_query)
            else:
                corrected_query += " VALUES ()"
            corrected = True

    elif query_type == "UPDATE":
        # Vérifier si SET est présent
        if not re.search(r'\bSET\b', query, re.IGNORECASE):
            errors.append("Clause SET manquante")
            suggestions.append("Ajoutez une clause SET pour spécifier les colonnes à mettre à jour")
            table_match = re.search(r'UPDATE\s+([a-zA-Z0-9_]+)', query, re.IGNORECASE)
            if table_match:
                corrected_query = re.sub(r'UPDATE\s+([a-zA-Z0-9_]+)', r'UPDATE \1 SET column = value', corrected_query, flags=re.IGNORECASE)
            else:
                corrected_query += " SET column = value"
            corrected = True

    elif query_type == "DELETE":
        # Vérifier si FROM est présent
        if not re.search(r'\bFROM\b', query, re.IGNORECASE):
            errors.append("Clause FROM manquante")
            suggestions.append("Utilisez la syntaxe 'DELETE FROM table_name'")
            corrected_query = re.sub(r'^\s*DELETE\b\s+', r'DELETE FROM ', corrected_query, flags=re.IGNORECASE)
            corrected = True

    elif query_type == "CREATE":
        # Vérifier si TABLE, VIEW, INDEX, etc. est présent
        if not any(re.search(rf'\b{obj}\b', query, re.IGNORECASE) for obj in ["TABLE", "VIEW", "INDEX", "PROCEDURE", "FUNCTION", "TRIGGER"]):
            errors.append("Type d'objet à créer manquant")
            suggestions.append("Spécifiez le type d'objet à créer (TABLE, VIEW, INDEX, etc.)")
            corrected_query = re.sub(r'^\s*CREATE\b\s+', r'CREATE TABLE ', corrected_query, flags=re.IGNORECASE)
            corrected = True

        # Pour CREATE TABLE, vérifier si les parenthèses sont présentes
        if re.search(r'\bTABLE\b', query, re.IGNORECASE) and not re.search(r'\([^)]*\)', query):
            errors.append("Définition des colonnes manquante")
            suggestions.append("Ajoutez des parenthèses avec la définition des colonnes")
            table_match = re.search(r'CREATE\s+TABLE\s+([a-zA-Z0-9_]+)', query, re.IGNORECASE)
            if table_match:
                corrected_query = re.sub(r'CREATE\s+TABLE\s+([a-zA-Z0-9_]+)', r'CREATE TABLE \1 (id INT PRIMARY KEY, name VARCHAR(255))', corrected_query, flags=re.IGNORECASE)
            else:
                corrected_query += " (id INT PRIMARY KEY, name VARCHAR(255))"
            corrected = True

    # Vérifier les erreurs de syntaxe générales

    # Point-virgule manquant à la fin
    if not query.rstrip().endswith(';'):
        errors.append("Point-virgule manquant à la fin de la requête")
        suggestions.append("Ajoutez un point-virgule à la fin de la requête")
        corrected_query = corrected_query.rstrip() + ";"
        corrected = True

    # Parenthèses non équilibrées
    open_parentheses = query.count('(')
    close_parentheses = query.count(')')
    if open_parentheses != close_parentheses:
        errors.append("Parenthèses non équilibrées")
        if open_parentheses > close_parentheses:
            suggestions.append(f"Ajoutez {open_parentheses - close_parentheses} parenthèse(s) fermante(s)")
            corrected_query = corrected_query.rstrip(';') + ")" * (open_parentheses - close_parentheses) + ";"
        else:
            suggestions.append(f"Supprimez {close_parentheses - open_parentheses} parenthèse(s) fermante(s) ou ajoutez des parenthèses ouvrantes")
            # Difficile de corriger automatiquement ce cas
        corrected = True

    # Guillemets non équilibrés
    single_quotes = len(re.findall(r'(?<![\\])[\'"]', query))
    if single_quotes % 2 != 0:
        errors.append("Guillemets non équilibrés")
        suggestions.append("Assurez-vous que chaque guillemet ouvrant a un guillemet fermant correspondant")
        # Difficile de corriger automatiquement ce cas

    # Mots-clés SQL mal orthographiés
    common_keywords = {
        "SLECT": "SELECT", "INSRT": "INSERT", "UPDTE": "UPDATE", "DELTE": "DELETE",
        "WHER": "WHERE", "GRUP": "GROUP", "ORDR": "ORDER", "HAVIN": "HAVING",
        "FRMO": "FROM", "JION": "JOIN", "INNR": "INNER", "LEFTT": "LEFT",
        "RIGTH": "RIGHT", "FULLL": "FULL", "LIMTI": "LIMIT", "OFSET": "OFFSET"
    }

    for misspelled, correct in common_keywords.items():
        if re.search(rf'\b{misspelled}\b', query, re.IGNORECASE):
            errors.append(f"Mot-clé SQL mal orthographié: {misspelled}")
            suggestions.append(f"Remplacez '{misspelled}' par '{correct}'")
            corrected_query = re.sub(rf'\b{misspelled}\b', correct, corrected_query, flags=re.IGNORECASE)
            corrected = True

    # Retourner les résultats
    return {
        "corrected": corrected,
        "original": original_query,
        "corrected_query": corrected_query,
        "errors": errors,
        "suggestions": suggestions
    }

# Fonction pour analyser et comprendre la demande de l'utilisateur
def analyze_user_request(description):
    """Analyse en profondeur la demande de l'utilisateur pour mieux comprendre ses besoins"""
    # Nettoyer et normaliser la description
    description_clean = description.lower().strip()

    # Analyser l'intention principale
    intent = {
        "action": None,  # SELECT, INSERT, etc.
        "purpose": None,  # analyse, rapport, mise à jour, etc.
        "data_focus": [],  # champs ou données spécifiques mentionnés
        "conditions": [],  # conditions ou filtres mentionnés
        "format": None,  # format de sortie souhaité (graphique, tableau, etc.)
        "priority": None,  # performance, précision, etc.
        "ambiguities": [],  # points ambigus nécessitant clarification
        "confidence": 0.0  # niveau de confiance dans l'analyse
    }

    # Détecter l'action principale (type de requête)
    if any(word in description_clean for word in ["sélectionner", "select", "afficher", "montrer", "lister", "obtenir", "récupérer"]):
        intent["action"] = "SELECT"
        intent["confidence"] += 0.3
    elif any(word in description_clean for word in ["insérer", "insert", "ajouter", "créer une ligne", "nouvelle entrée"]):
        intent["action"] = "INSERT"
        intent["confidence"] += 0.3
    elif any(word in description_clean for word in ["mettre à jour", "update", "modifier", "changer", "actualiser"]):
        intent["action"] = "UPDATE"
        intent["confidence"] += 0.3
    elif any(word in description_clean for word in ["supprimer", "delete", "effacer", "enlever", "retirer"]):
        intent["action"] = "DELETE"
        intent["confidence"] += 0.3
    elif any(word in description_clean for word in ["créer", "create", "nouvelle table", "nouveau schéma"]):
        intent["action"] = "CREATE"
        intent["confidence"] += 0.3
    elif any(word in description_clean for word in ["modifier structure", "alter", "changer structure"]):
        intent["action"] = "ALTER"
        intent["confidence"] += 0.3
    elif any(word in description_clean for word in ["supprimer table", "drop", "effacer table"]):
        intent["action"] = "DROP"
        intent["confidence"] += 0.3

    # Détecter l'objectif/but
    if any(word in description_clean for word in ["analyser", "analyse", "tendance", "évolution", "comparer"]):
        intent["purpose"] = "analyse"
        intent["confidence"] += 0.1
    elif any(word in description_clean for word in ["rapport", "reporting", "bilan", "résumé"]):
        intent["purpose"] = "rapport"
        intent["confidence"] += 0.1
    elif any(word in description_clean for word in ["surveiller", "monitoring", "suivre", "alerter"]):
        intent["purpose"] = "surveillance"
        intent["confidence"] += 0.1
    elif any(word in description_clean for word in ["archiver", "historiser", "sauvegarder"]):
        intent["purpose"] = "archivage"
        intent["confidence"] += 0.1

    # Détecter le focus sur les données
    data_focus_patterns = [
        r"(?:champs?|colonnes?)\s+([a-zA-Z0-9_,\s]+)",
        r"(?:données|informations)\s+(?:sur|de|concernant)\s+([a-zA-Z0-9_,\s]+)",
        r"(?:afficher|montrer|sélectionner)\s+(?:les?|la)?\s+([a-zA-Z0-9_,\s]+)"
    ]

    for pattern in data_focus_patterns:
        matches = re.finditer(pattern, description_clean)
        for match in matches:
            if match.group(1):
                # Extraire et nettoyer les champs mentionnés
                fields = [field.strip() for field in match.group(1).split(",")]
                intent["data_focus"].extend(fields)
                intent["confidence"] += 0.05 * len(fields)

    # Détecter les conditions/filtres
    condition_patterns = [
        r"(?:où|where|quand|lorsque|si)\s+([^.]+)",
        r"(?:avec|ayant)\s+(?:la|les|une|des)?\s+(?:condition|filtre)s?\s+([^.]+)",
        r"(?:pour|uniquement)\s+(?:les|des)?\s+([^.]+\s+(?:supérieur|inférieur|égal|contient|commence|finit))"
    ]

    for pattern in condition_patterns:
        matches = re.finditer(pattern, description_clean)
        for match in matches:
            if match.group(1):
                intent["conditions"].append(match.group(1).strip())
                intent["confidence"] += 0.1

    # Détecter le format souhaité
    if any(word in description_clean for word in ["graphique", "chart", "visualiser", "diagramme", "histogramme"]):
        intent["format"] = "graphique"
        intent["confidence"] += 0.1
    elif any(word in description_clean for word in ["tableau", "table", "grille", "liste"]):
        intent["format"] = "tableau"
        intent["confidence"] += 0.1
    elif any(word in description_clean for word in ["export", "csv", "excel", "fichier"]):
        intent["format"] = "export"
        intent["confidence"] += 0.1

    # Détecter les priorités
    if any(word in description_clean for word in ["rapide", "performance", "optimisé", "efficace"]):
        intent["priority"] = "performance"
        intent["confidence"] += 0.05
    elif any(word in description_clean for word in ["précis", "exact", "détaillé", "complet"]):
        intent["priority"] = "précision"
        intent["confidence"] += 0.05
    elif any(word in description_clean for word in ["simple", "basique", "facile"]):
        intent["priority"] = "simplicité"
        intent["confidence"] += 0.05

    # Détecter les ambiguïtés
    if intent["action"] is None:
        intent["ambiguities"].append("type_requete")
        intent["confidence"] -= 0.2

    if not intent["data_focus"] and intent["action"] in ["SELECT", "INSERT", "UPDATE"]:
        intent["ambiguities"].append("champs")
        intent["confidence"] -= 0.1

    # Rechercher des tables mentionnées
    table_pattern = r"(?:tables?|depuis|from)\s+([a-zA-Z0-9_,\s]+)"
    table_matches = re.search(table_pattern, description_clean)
    if not table_matches and intent["action"] is not None:
        intent["ambiguities"].append("tables")
        intent["confidence"] -= 0.2

    return intent

# Fonction pour générer une requête SQL basée sur une description en langage naturel
def generate_sql_query(description):
    """Génère une requête SQL basée sur une description en langage naturel"""
    # Analyser la demande de l'utilisateur
    user_intent = analyze_user_request(description)

    # Si la confiance est trop faible, demander des clarifications
    if user_intent["confidence"] < 0.3:
        clarification_message = "Je ne suis pas sûr de bien comprendre votre demande. Pourriez-vous préciser :\n\n"

        if "type_requete" in user_intent["ambiguities"]:
            clarification_message += "- Quel type d'opération souhaitez-vous effectuer ? (sélectionner, insérer, mettre à jour, supprimer, etc.)\n"

        if "tables" in user_intent["ambiguities"]:
            clarification_message += "- Sur quelle(s) table(s) souhaitez-vous travailler ?\n"

        if "champs" in user_intent["ambiguities"]:
            clarification_message += "- Quels champs ou données spécifiques vous intéressent ?\n"

        return clarification_message, "UNKNOWN", {}

    # Appliquer les connaissances acquises des interactions précédentes
    suggested_type, suggested_tables, suggested_fields = apply_learned_knowledge(description)

    # Utiliser l'action détectée, la suggestion ou détecter le type de requête SQL
    sql_type = user_intent["action"] if user_intent["action"] else (suggested_type or detect_sql_type(description))

    # Détecter les options avancées
    advanced_options = detect_advanced_options(description, sql_type)

    # Extraire les tables et champs
    tables, fields = extract_tables_and_fields(description, sql_type)

    # Compléter avec les tables suggérées si aucune table n'a été trouvée
    if not tables and suggested_tables:
        tables = suggested_tables

    # Compléter avec les champs de l'analyse d'intention
    if not fields and user_intent["data_focus"]:
        fields = [field for field in user_intent["data_focus"] if len(field) > 1]

    # Compléter avec les champs suggérés si aucun champ n'a été trouvé
    if not fields and suggested_fields:
        fields = suggested_fields

    # Vérifier si des tables ont été trouvées
    if not tables:
        return "Erreur: Impossible de déterminer les tables à utiliser dans la requête.\n\nExemple de format: 'Je veux une requête qui sélectionne les champs nom, prénom des tables utilisateurs où id > 100'\n\nPour des requêtes plus avancées, vous pouvez spécifier:\n- Des fonctions d'agrégation (COUNT, SUM, AVG, MAX, MIN)\n- Des groupements (GROUP BY)\n- Des sous-requêtes\n- Des jointures complexes\n- Des conditions avancées (HAVING, IN, EXISTS)", sql_type, advanced_options

    # Générer la requête en fonction du type détecté
    if sql_type == "SELECT":
        query = generate_select_query(description, tables, fields, advanced_options)
    elif sql_type == "INSERT":
        query = generate_insert_query(description, tables, fields, advanced_options)
    elif sql_type == "UPDATE":
        query = generate_update_query(description, tables, fields, advanced_options)
    elif sql_type == "DELETE":
        query = generate_delete_query(description, tables, advanced_options)
    elif sql_type == "CREATE":
        query = generate_create_query(description, tables, fields, advanced_options)
    elif sql_type == "ALTER":
        query = generate_alter_query(description, tables, fields, advanced_options)
    elif sql_type == "DROP":
        query = generate_drop_query(description, tables, advanced_options)
    else:
        query = "Erreur: Type de requête non supporté."

    return query, sql_type, advanced_options

# Fonction pour générer une requête SELECT
def generate_select_query(description, tables, fields, advanced_options):
    """Génère une requête SQL SELECT basée sur une description en langage naturel"""
    description_lower = description.lower()

    # Construction de la clause WITH (CTE) si nécessaire
    with_clause = ""
    if advanced_options.get("cte", False):
        # Générer une CTE simple
        cte_name = f"cte_{tables[0]}"
        cte_select = "SELECT * FROM " + tables[0]

        # Ajouter une condition si possible
        if "où" in description_lower or "where" in description_lower or "condition" in description_lower:
            cte_select += " WHERE id > 0"  # Condition générique

        with_clause = f"WITH {cte_name} AS (\n  {cte_select}\n)\n"

        # Remplacer la table principale par la CTE
        tables[0] = cte_name

    # Construction de la clause SELECT
    if not fields:
        select_clause = "SELECT *"
    else:
        # Vérifier si des fonctions d'agrégation sont demandées
        processed_fields = []

        # Détecter les fonctions d'agrégation
        aggregation_needed = advanced_options.get("aggregate", False)

        for field in fields:
            # Appliquer des fonctions d'agrégation si nécessaire
            if aggregation_needed:
                # Détecter quelle fonction d'agrégation appliquer à quel champ
                if any(keyword in description_lower for keyword in ["count", "nombre", "compter", "comptage"]) and field in ["id", "utilisateur", "client", "commande"]:
                    processed_fields.append(f"COUNT({field})")
                elif any(keyword in description_lower for keyword in ["sum", "somme", "total", "montant"]) and field in ["montant", "prix", "valeur", "quantite", "quantité"]:
                    processed_fields.append(f"SUM({field})")
                elif any(keyword in description_lower for keyword in ["avg", "moyenne", "moyen"]) and field in ["montant", "prix", "valeur", "age", "âge", "quantite", "quantité"]:
                    processed_fields.append(f"AVG({field})")
                elif any(keyword in description_lower for keyword in ["max", "maximum", "plus grand", "plus élevé"]) and field in ["montant", "prix", "valeur", "date", "age", "âge", "quantite", "quantité"]:
                    processed_fields.append(f"MAX({field})")
                elif any(keyword in description_lower for keyword in ["min", "minimum", "plus petit", "plus bas"]) and field in ["montant", "prix", "valeur", "date", "age", "âge", "quantite", "quantité"]:
                    processed_fields.append(f"MIN({field})")
                else:
                    # Si le champ ne correspond à aucune fonction d'agrégation, l'utiliser tel quel
                    # Mais si GROUP BY est nécessaire, s'assurer que ce champ est inclus dans GROUP BY
                    processed_fields.append(field)
            else:
                processed_fields.append(field)

        # Ajouter DISTINCT si mentionné
        distinct_clause = ""
        if advanced_options.get("distinct", False):
            distinct_clause = "DISTINCT "

        select_clause = f"SELECT {distinct_clause}{', '.join(processed_fields)}"

    # Construction de la clause FROM
    from_clause = f"FROM {tables[0]}"

    # Détection du type de jointure demandé
    join_type = "INNER JOIN"  # Par défaut
    if "left join" in description_lower or "jointure externe gauche" in description_lower or "gauche" in description_lower:
        join_type = "LEFT JOIN"
    elif "right join" in description_lower or "jointure externe droite" in description_lower or "droite" in description_lower:
        join_type = "RIGHT JOIN"
    elif "full join" in description_lower or "jointure complète" in description_lower or "complète" in description_lower:
        join_type = "FULL JOIN"
    elif "cross join" in description_lower or "jointure croisée" in description_lower or "produit cartésien" in description_lower:
        join_type = "CROSS JOIN"

    # Ajout de jointures si plusieurs tables ou si l'option de jointure est détectée
    joins = ""
    if len(tables) > 1 or advanced_options.get("join", False):
        # S'assurer qu'il y a au moins deux tables
        if len(tables) < 2:
            # Ajouter une table supplémentaire si nécessaire
            if tables[0].endswith('s'):  # Table au pluriel
                related_table = tables[0][:-1]  # Version singulier
            else:
                related_table = tables[0] + "_details"
            tables.append(related_table)

        for i in range(1, len(tables)):
            # Recherche d'une condition de jointure spécifique
            custom_join_condition = None

            for join_keyword in ["joindre", "join", "relier", "lier", "avec"]:
                if join_keyword in description_lower:
                    parts = description_lower.split(join_keyword)
                    if len(parts) > 1:
                        # Essayer de trouver une condition de jointure
                        for cond_keyword in ["sur", "on", "avec", "using", "where", "où", "par"]:
                            if cond_keyword in parts[1]:
                                join_cond_parts = parts[1].split(cond_keyword)
                                if len(join_cond_parts) > 1:
                                    join_cond = join_cond_parts[1].strip()
                                    # Extraire jusqu'au prochain point ou fin de phrase
                                    end_cond = join_cond.find('.')
                                    if end_cond != -1:
                                        join_cond = join_cond[:end_cond]

                                    # Nettoyer la condition
                                    join_cond = join_cond.strip()
                                    if join_cond:
                                        # Essayer de construire une condition de jointure valide
                                        if "=" not in join_cond and "." not in join_cond:
                                            # Supposer que c'est un nom de colonne
                                            join_cond = f"{tables[0]}.{join_cond} = {tables[i]}.{join_cond}"

                                        custom_join_condition = join_cond
                                        break

            # Si une condition personnalisée est trouvée, l'utiliser
            if custom_join_condition:
                joins += f"\n{join_type} {tables[i]} ON {custom_join_condition}"
            else:
                # Sinon, utiliser la jointure par défaut
                # Essayer de deviner une meilleure condition de jointure
                if tables[0].endswith('s') and tables[i] == tables[0][:-1]:
                    # Relation one-to-many probable (ex: users -> user)
                    joins += f"\n{join_type} {tables[i]} ON {tables[0]}.{tables[i]}_id = {tables[i]}.id"
                elif tables[i].endswith('s') and tables[0] == tables[i][:-1]:
                    # Relation many-to-one probable (ex: user -> users)
                    joins += f"\n{join_type} {tables[i]} ON {tables[0]}.id = {tables[i]}.{tables[0]}_id"
                else:
                    # Relation générique
                    joins += f"\n{join_type} {tables[i]} ON {tables[0]}.id = {tables[i]}.{tables[0]}_id"

    # Recherche de conditions WHERE
    where_clause = ""
    condition_keywords = ["où", "where", "condition", "filtre", "filtrer", "quand", "lorsque", "si"]

    for keyword in condition_keywords:
        if keyword in description_lower:
            parts = description_lower.split(keyword)
            if len(parts) > 1:
                condition_text = parts[1].strip()
                # Extraction de la condition jusqu'au prochain point ou fin de phrase
                end_condition = condition_text.find('.')
                if end_condition != -1:
                    condition_text = condition_text[:end_condition]

                # Amélioration des conditions
                # Remplacer les expressions en langage naturel par des opérateurs SQL
                condition_text = condition_text.replace(" égal à ", " = ")
                condition_text = condition_text.replace(" égale à ", " = ")
                condition_text = condition_text.replace(" égal ", " = ")
                condition_text = condition_text.replace(" égale ", " = ")
                condition_text = condition_text.replace(" supérieur à ", " > ")
                condition_text = condition_text.replace(" supérieure à ", " > ")
                condition_text = condition_text.replace(" inférieur à ", " < ")
                condition_text = condition_text.replace(" inférieure à ", " < ")
                condition_text = condition_text.replace(" plus grand que ", " > ")
                condition_text = condition_text.replace(" plus grande que ", " > ")
                condition_text = condition_text.replace(" plus petit que ", " < ")
                condition_text = condition_text.replace(" plus petite que ", " < ")
                condition_text = condition_text.replace(" contient ", " LIKE '%' || ")
                condition_text = condition_text.replace(" commence par ", " LIKE ")
                condition_text = condition_text.replace(" finit par ", " LIKE '%")

                # Essayer de construire une condition WHERE valide
                # Si la condition ne contient pas d'opérateur de comparaison, en ajouter un
                if not any(op in condition_text for op in ["=", ">", "<", ">=", "<=", "!=", "<>", "LIKE", "IN", "BETWEEN", "IS"]):
                    # Chercher un nom de champ potentiel
                    field_value_match = re.search(r'(\w+)\s+(\w+)', condition_text)
                    if field_value_match:
                        field = field_value_match.group(1)
                        value = field_value_match.group(2)

                        # Déterminer si la valeur est numérique
                        if value.isdigit():
                            condition_text = f"{field} = {value}"
                        else:
                            condition_text = f"{field} = '{value}'"

                where_clause = f"\nWHERE {condition_text}"
                break

    # Si aucune condition WHERE n'est trouvée mais qu'une sous-requête est demandée
    if not where_clause and advanced_options.get("subquery", False):
        # Générer une sous-requête simple
        if len(tables) > 1:
            where_clause = f"\nWHERE {tables[0]}.id IN (SELECT id FROM {tables[1]} WHERE active = 1)"
        else:
            where_clause = f"\nWHERE id IN (SELECT id FROM related_table WHERE active = 1)"

    # Recherche de GROUP BY
    group_by_clause = ""
    group_keywords = ["group by", "grouper par", "grouper", "regrouper", "par"]

    # Si l'option de groupement est détectée
    if advanced_options.get("groupby", False):
        # Chercher les champs de groupement potentiels
        group_fields = []

        # Si des champs sont spécifiés et qu'il y a des fonctions d'agrégation
        if fields and advanced_options.get("aggregate", False):
            # Utiliser les champs qui ne sont pas dans des fonctions d'agrégation
            for field in fields:
                if not any(f"{func}({field})" in processed_fields for func in ["COUNT", "SUM", "AVG", "MAX", "MIN"]):
                    group_fields.append(field)

        # Si aucun champ n'est trouvé, essayer de détecter dans la description
        if not group_fields:
            for keyword in group_keywords:
                if keyword in description_lower:
                    parts = description_lower.split(keyword)
                    if len(parts) > 1:
                        group_text = parts[1].strip()
                        # Extraction du groupe jusqu'au prochain point ou fin de phrase
                        end_group = group_text.find('.')
                        if end_group != -1:
                            group_text = group_text[:end_group]

                        # Chercher des noms de champs potentiels
                        field_match = re.search(r'(\w+)', group_text)
                        if field_match:
                            group_fields.append(field_match.group(1))

        # Si des champs de groupement sont trouvés, construire la clause GROUP BY
        if group_fields:
            group_by_clause = f"\nGROUP BY {', '.join(group_fields)}"
        # Sinon, utiliser un champ par défaut si des fonctions d'agrégation sont utilisées
        elif advanced_options.get("aggregate", False) and fields:
            # Utiliser le premier champ qui n'est pas dans une fonction d'agrégation
            for field in fields:
                if not any(f"{func}({field})" in ' '.join(processed_fields) for func in ["COUNT", "SUM", "AVG", "MAX", "MIN"]):
                    group_by_clause = f"\nGROUP BY {field}"
                    break

    # Recherche de HAVING
    having_clause = ""
    having_keywords = ["having", "ayant", "avec condition", "avec filtre", "après groupement"]

    # Si l'option HAVING est détectée
    if advanced_options.get("having", False) and group_by_clause:
        for keyword in having_keywords:
            if keyword in description_lower:
                parts = description_lower.split(keyword)
                if len(parts) > 1:
                    having_text = parts[1].strip()
                    # Extraction de la condition jusqu'au prochain point ou fin de phrase
                    end_having = having_text.find('.')
                    if end_having != -1:
                        having_text = having_text[:end_having]

                    # Essayer de construire une condition HAVING valide
                    # Si la condition ne contient pas d'opérateur de comparaison, en ajouter un
                    if not any(op in having_text for op in ["=", ">", "<", ">=", "<=", "!=", "<>", "LIKE", "IN", "BETWEEN", "IS"]):
                        # Chercher un nom de champ potentiel
                        field_value_match = re.search(r'(\w+)\s+(\w+)', having_text)
                        if field_value_match:
                            field = field_value_match.group(1)
                            value = field_value_match.group(2)

                            # Déterminer si la valeur est numérique
                            if value.isdigit():
                                having_text = f"COUNT({field}) > {value}"
                            else:
                                having_text = f"COUNT({field}) > 0"

                    having_clause = f"\nHAVING {having_text}"
                    break

        # Si aucune condition HAVING n'est trouvée mais que l'option est activée
        if not having_clause and advanced_options.get("aggregate", False):
            # Générer une condition HAVING par défaut
            if "count" in description_lower:
                having_clause = "\nHAVING COUNT(*) > 1"
            elif "sum" in description_lower or "total" in description_lower:
                having_clause = "\nHAVING SUM(montant) > 0"
            elif "avg" in description_lower or "moyenne" in description_lower:
                having_clause = "\nHAVING AVG(montant) > 0"
            elif "max" in description_lower or "maximum" in description_lower:
                having_clause = "\nHAVING MAX(montant) > 0"
            elif "min" in description_lower or "minimum" in description_lower:
                having_clause = "\nHAVING MIN(montant) > 0"

    # Recherche d'instructions de tri (ORDER BY)
    order_clause = ""
    order_keywords = ["trier", "ordonner", "ordre", "order by", "sort", "classer"]

    # Si l'option de tri est détectée
    if advanced_options.get("orderby", False):
        for keyword in order_keywords:
            if keyword in description_lower:
                parts = description_lower.split(keyword)
                if len(parts) > 1:
                    order_text = parts[1].strip()
                    # Extraction de l'ordre jusqu'au prochain point ou fin de phrase
                    end_order = order_text.find('.')
                    if end_order != -1:
                        order_text = order_text[:end_order]

                    # Détection de l'ordre (ascendant/descendant)
                    if "desc" in order_text.lower() or "décroissant" in order_text.lower() or "descendant" in order_text.lower():
                        direction = "DESC"
                    else:
                        direction = "ASC"

                    # Extraction du champ de tri
                    order_field = None

                    # Chercher un nom de champ dans le texte de tri
                    field_match = re.search(r'(?:par|sur|selon)\s+(?:le|la|les)?\s+(\w+)', order_text)
                    if field_match:
                        order_field = field_match.group(1)
                    else:
                        # Chercher parmi les champs spécifiés
                        for field in fields:
                            if field.lower() in order_text:
                                order_field = field
                                break

                    if order_field:
                        order_clause = f"\nORDER BY {order_field} {direction}"
                    elif fields:
                        # Si aucun champ spécifique n'est trouvé, utiliser le premier champ
                        order_clause = f"\nORDER BY {fields[0]} {direction}"
                    else:
                        # Si aucun champ n'est spécifié, utiliser id
                        order_clause = f"\nORDER BY id {direction}"

                    break

    # Recherche de limite (LIMIT)
    limit_clause = ""
    limit_keywords = ["limite", "limiter", "limit", "maximum", "max", "top", "premiers"]

    # Si l'option de limite est détectée
    if advanced_options.get("limit", False):
        for keyword in limit_keywords:
            if keyword in description_lower:
                parts = description_lower.split(keyword)
                if len(parts) > 1:
                    limit_text = parts[1].strip()
                    # Recherche d'un nombre dans le texte de limite
                    limit_match = re.search(r'\d+', limit_text)
                    if limit_match:
                        limit_value = limit_match.group(0)
                        limit_clause = f"\nLIMIT {limit_value}"
                        break

        # Si aucune limite n'est trouvée mais que l'option est activée
        if not limit_clause:
            # Générer une limite par défaut
            limit_clause = "\nLIMIT 10"

    # Construction de la requête complète
    # Ajouter la clause WITH si nécessaire
    if advanced_options.get("cte", False) and with_clause:
        query = f"{with_clause}{select_clause}\n{from_clause}{joins}{where_clause}{group_by_clause}{having_clause}{order_clause}{limit_clause};"
    else:
        query = f"{select_clause}\n{from_clause}{joins}{where_clause}{group_by_clause}{having_clause}{order_clause}{limit_clause};"

    # Ajout d'une explication détaillée
    explanation = "\n\n-- Explication de la requête :\n"
    explanation += f"-- Cette requête sélectionne {'tous les champs (*)' if not fields else 'les champs: ' + ', '.join(fields)}\n"
    explanation += f"-- De la table principale: {tables[0]}\n"

    if len(tables) > 1:
        explanation += f"-- Avec des jointures de type {join_type} sur: {', '.join(tables[1:])}\n"

    if where_clause:
        explanation += f"-- Filtrée par la condition: {where_clause.replace('WHERE', '').strip()}\n"

    if group_by_clause:
        explanation += f"-- Groupée par: {group_by_clause.replace('GROUP BY', '').strip()}\n"

    if having_clause:
        explanation += f"-- Avec condition sur les groupes: {having_clause.replace('HAVING', '').strip()}\n"

    if order_clause:
        explanation += f"-- Triée par: {order_clause.replace('ORDER BY', '').strip()}\n"

    if limit_clause:
        explanation += f"-- Limitée à: {limit_clause.replace('LIMIT', '').strip()} résultats\n"

    # Options avancées détectées
    active_options = [option for option, enabled in advanced_options.items() if enabled]
    if active_options:
        explanation += f"-- Options avancées détectées: {', '.join(active_options)}\n"

    return query + explanation

# Fonction pour générer une requête INSERT
def generate_insert_query(description, tables, fields, advanced_options):
    """Génère une requête SQL INSERT basée sur une description en langage naturel"""
    description_lower = description.lower()

    # Vérifier si des tables ont été trouvées
    if not tables:
        return "Erreur: Impossible de déterminer la table pour l'insertion."

    # Utiliser la première table comme cible de l'insertion
    table = tables[0]

    # Vérifier si des champs ont été trouvés
    if not fields:
        return "Erreur: Impossible de déterminer les champs pour l'insertion."

    # Déterminer si l'insertion doit se faire à partir d'une requête SELECT
    insert_from_select = advanced_options.get("select", False) or "select" in description_lower or "sélectionner" in description_lower

    # Construire la requête INSERT
    if insert_from_select:
        # Construire une requête INSERT ... SELECT
        select_table = tables[1] if len(tables) > 1 else f"{table}_source"

        # Construire la clause SELECT
        select_clause = f"SELECT {', '.join(fields)} FROM {select_table}"

        # Ajouter une condition WHERE si mentionnée
        if "où" in description_lower or "where" in description_lower or "condition" in description_lower:
            select_clause += " WHERE id > 0"  # Condition générique

        # Construire la requête complète
        query = f"INSERT INTO {table} ({', '.join(fields)})\n{select_clause};"
    else:
        # Construire une requête INSERT ... VALUES

        # Générer des valeurs fictives pour chaque champ
        values = []
        for field in fields:
            if field.lower() in ["id", "identifiant", "code"]:
                values.append("1")  # Valeur numérique pour les ID
            elif field.lower() in ["nom", "prenom", "name", "first_name", "last_name", "description", "titre", "title"]:
                values.append("'Exemple'")  # Chaîne pour les noms
            elif field.lower() in ["email", "mail", "courriel"]:
                values.append("'exemple@email.com'")  # Email
            elif field.lower() in ["date", "date_creation", "date_inscription", "creation_date", "registration_date"]:
                values.append("CURRENT_DATE")  # Date actuelle
            elif field.lower() in ["montant", "prix", "price", "amount", "valeur", "value", "cout", "cost"]:
                values.append("100.00")  # Valeur monétaire
            elif field.lower() in ["quantite", "quantity", "nombre", "number", "count"]:
                values.append("10")  # Quantité
            elif field.lower() in ["statut", "status", "etat", "state"]:
                values.append("'actif'")  # Statut
            elif field.lower().endswith("_id") or field.lower().endswith("id"):
                values.append("1")  # Clé étrangère
            else:
                values.append("'valeur'")  # Valeur par défaut

        # Vérifier si l'insertion doit être multiple
        if advanced_options.get("multiple", False) or "multiple" in description_lower or "plusieurs" in description_lower:
            # Générer une deuxième ligne de valeurs légèrement différentes
            values2 = []
            for field in fields:
                if field.lower() in ["id", "identifiant", "code"]:
                    values2.append("2")  # Valeur numérique pour les ID
                elif field.lower() in ["nom", "prenom", "name", "first_name", "last_name", "description", "titre", "title"]:
                    values2.append("'Exemple2'")  # Chaîne pour les noms
                elif field.lower() in ["email", "mail", "courriel"]:
                    values2.append("'exemple2@email.com'")  # Email
                elif field.lower() in ["date", "date_creation", "date_inscription", "creation_date", "registration_date"]:
                    values2.append("CURRENT_DATE")  # Date actuelle
                elif field.lower() in ["montant", "prix", "price", "amount", "valeur", "value", "cout", "cost"]:
                    values2.append("200.00")  # Valeur monétaire
                elif field.lower() in ["quantite", "quantity", "nombre", "number", "count"]:
                    values2.append("20")  # Quantité
                elif field.lower() in ["statut", "status", "etat", "state"]:
                    values2.append("'inactif'")  # Statut
                elif field.lower().endswith("_id") or field.lower().endswith("id"):
                    values2.append("2")  # Clé étrangère
                else:
                    values2.append("'valeur2'")  # Valeur par défaut

            # Construire la requête avec insertion multiple
            query = f"INSERT INTO {table} ({', '.join(fields)})\nVALUES\n({', '.join(values)}),\n({', '.join(values2)});"
        else:
            # Construire la requête avec insertion simple
            query = f"INSERT INTO {table} ({', '.join(fields)})\nVALUES ({', '.join(values)});"

    # Ajouter la clause RETURNING si demandée
    if advanced_options.get("returning", False) or "returning" in description_lower or "retourner" in description_lower:
        # Supprimer le point-virgule final
        query = query.rstrip(";")
        # Ajouter la clause RETURNING
        query += f"\nRETURNING id, {fields[0] if fields else '*'};"

    # Ajouter une explication détaillée
    explanation = "\n\n-- Explication de la requête :\n"
    explanation += f"-- Cette requête insère des données dans la table: {table}\n"
    explanation += f"-- Pour les champs: {', '.join(fields)}\n"

    if insert_from_select:
        explanation += f"-- Les données sont sélectionnées depuis la table: {select_table}\n"
    else:
        explanation += "-- Avec des valeurs spécifiées directement\n"

    if advanced_options.get("multiple", False) or "multiple" in description_lower or "plusieurs" in description_lower:
        explanation += "-- Insertion de plusieurs lignes en une seule requête\n"

    if advanced_options.get("returning", False) or "returning" in description_lower or "retourner" in description_lower:
        explanation += "-- Retourne les identifiants des lignes insérées\n"

    # Options avancées détectées
    active_options = [option for option, enabled in advanced_options.items() if enabled]
    if active_options:
        explanation += f"-- Options avancées détectées: {', '.join(active_options)}\n"

    return query + explanation

# Fonction pour générer une requête UPDATE
def generate_update_query(description, tables, fields, advanced_options):
    """Génère une requête SQL UPDATE basée sur une description en langage naturel"""
    description_lower = description.lower()

    # Vérifier si des tables ont été trouvées
    if not tables:
        return "Erreur: Impossible de déterminer la table à mettre à jour."

    # Utiliser la première table comme cible de la mise à jour
    table = tables[0]

    # Vérifier si des champs ont été trouvés
    if not fields:
        return "Erreur: Impossible de déterminer les champs à mettre à jour."

    # Construire la clause SET
    set_clauses = []
    for field in fields:
        if field.lower() in ["id", "identifiant", "code"]:
            # Généralement, on ne met pas à jour les ID
            continue
        elif field.lower() in ["nom", "prenom", "name", "first_name", "last_name", "description", "titre", "title"]:
            set_clauses.append(f"{field} = 'Nouveau nom'")
        elif field.lower() in ["email", "mail", "courriel"]:
            set_clauses.append(f"{field} = 'nouveau@email.com'")
        elif field.lower() in ["date", "date_creation", "date_inscription", "creation_date", "registration_date"]:
            set_clauses.append(f"{field} = CURRENT_DATE")
        elif field.lower() in ["montant", "prix", "price", "amount", "valeur", "value", "cout", "cost"]:
            set_clauses.append(f"{field} = 150.00")
        elif field.lower() in ["quantite", "quantity", "nombre", "number", "count"]:
            set_clauses.append(f"{field} = 15")
        elif field.lower() in ["statut", "status", "etat", "state"]:
            set_clauses.append(f"{field} = 'modifié'")
        elif field.lower().endswith("_id") or field.lower().endswith("id"):
            set_clauses.append(f"{field} = 2")
        else:
            set_clauses.append(f"{field} = 'nouvelle valeur'")

    # S'assurer qu'il y a au moins une clause SET
    if not set_clauses:
        set_clauses.append("champ = 'nouvelle valeur'")

    # Construire la clause WHERE
    where_clause = ""
    condition_keywords = ["où", "where", "condition", "filtre", "filtrer", "quand", "lorsque", "si"]

    for keyword in condition_keywords:
        if keyword in description_lower:
            parts = description_lower.split(keyword)
            if len(parts) > 1:
                condition_text = parts[1].strip()
                # Extraction de la condition jusqu'au prochain point ou fin de phrase
                end_condition = condition_text.find('.')
                if end_condition != -1:
                    condition_text = condition_text[:end_condition]

                # Amélioration des conditions
                # Remplacer les expressions en langage naturel par des opérateurs SQL
                condition_text = condition_text.replace(" égal à ", " = ")
                condition_text = condition_text.replace(" égale à ", " = ")
                condition_text = condition_text.replace(" égal ", " = ")
                condition_text = condition_text.replace(" égale ", " = ")

                # Essayer de construire une condition WHERE valide
                # Si la condition ne contient pas d'opérateur de comparaison, en ajouter un
                if not any(op in condition_text for op in ["=", ">", "<", ">=", "<=", "!=", "<>", "LIKE", "IN", "BETWEEN", "IS"]):
                    # Chercher un nom de champ potentiel
                    field_value_match = re.search(r'(\w+)\s+(\w+)', condition_text)
                    if field_value_match:
                        field = field_value_match.group(1)
                        value = field_value_match.group(2)

                        # Déterminer si la valeur est numérique
                        if value.isdigit():
                            condition_text = f"{field} = {value}"
                        else:
                            condition_text = f"{field} = '{value}'"

                where_clause = f" WHERE {condition_text}"
                break

    # Si aucune condition WHERE n'est trouvée, ajouter une condition par défaut
    if not where_clause:
        where_clause = " WHERE id = 1"

    # Construire la requête UPDATE
    query = f"UPDATE {table}\nSET {', '.join(set_clauses)}{where_clause};"

    # Ajouter la clause RETURNING si demandée
    if advanced_options.get("returning", False) or "returning" in description_lower or "retourner" in description_lower:
        # Supprimer le point-virgule final
        query = query.rstrip(";")
        # Ajouter la clause RETURNING
        query += f"\nRETURNING id, {fields[0] if fields else '*'};"

    # Ajouter une explication détaillée
    explanation = "\n\n-- Explication de la requête :\n"
    explanation += f"-- Cette requête met à jour des données dans la table: {table}\n"
    explanation += f"-- Pour les champs: {', '.join(field.split(' = ')[0] for field in set_clauses)}\n"
    explanation += f"-- Avec la condition: {where_clause.replace('WHERE', '').strip()}\n"

    if advanced_options.get("returning", False) or "returning" in description_lower or "retourner" in description_lower:
        explanation += "-- Retourne les identifiants des lignes mises à jour\n"

    # Options avancées détectées
    active_options = [option for option, enabled in advanced_options.items() if enabled]
    if active_options:
        explanation += f"-- Options avancées détectées: {', '.join(active_options)}\n"

    return query + explanation

# Fonction pour générer une requête DELETE
def generate_delete_query(description, tables, advanced_options):
    """Génère une requête SQL DELETE basée sur une description en langage naturel"""
    description_lower = description.lower()

    # Vérifier si des tables ont été trouvées
    if not tables:
        return "Erreur: Impossible de déterminer la table pour la suppression."

    # Utiliser la première table comme cible de la suppression
    table = tables[0]

    # Vérifier si TRUNCATE est demandé au lieu de DELETE
    if advanced_options.get("truncate", False) or "truncate" in description_lower or "vider" in description_lower or "tout supprimer" in description_lower:
        # Construire une requête TRUNCATE
        query = f"TRUNCATE TABLE {table};"

        # Ajouter une explication détaillée
        explanation = "\n\n-- Explication de la requête :\n"
        explanation += f"-- Cette requête vide complètement la table: {table}\n"
        explanation += "-- TRUNCATE est plus rapide que DELETE pour supprimer toutes les lignes\n"

        # Options avancées détectées
        active_options = [option for option, enabled in advanced_options.items() if enabled]
        if active_options:
            explanation += f"-- Options avancées détectées: {', '.join(active_options)}\n"

        return query + explanation

    # Construire la clause WHERE
    where_clause = ""
    condition_keywords = ["où", "where", "condition", "filtre", "filtrer", "quand", "lorsque", "si"]

    for keyword in condition_keywords:
        if keyword in description_lower:
            parts = description_lower.split(keyword)
            if len(parts) > 1:
                condition_text = parts[1].strip()
                # Extraction de la condition jusqu'au prochain point ou fin de phrase
                end_condition = condition_text.find('.')
                if end_condition != -1:
                    condition_text = condition_text[:end_condition]

                # Amélioration des conditions
                # Remplacer les expressions en langage naturel par des opérateurs SQL
                condition_text = condition_text.replace(" égal à ", " = ")
                condition_text = condition_text.replace(" égale à ", " = ")
                condition_text = condition_text.replace(" égal ", " = ")
                condition_text = condition_text.replace(" égale ", " = ")

                # Essayer de construire une condition WHERE valide
                # Si la condition ne contient pas d'opérateur de comparaison, en ajouter un
                if not any(op in condition_text for op in ["=", ">", "<", ">=", "<=", "!=", "<>", "LIKE", "IN", "BETWEEN", "IS"]):
                    # Chercher un nom de champ potentiel
                    field_value_match = re.search(r'(\w+)\s+(\w+)', condition_text)
                    if field_value_match:
                        field = field_value_match.group(1)
                        value = field_value_match.group(2)

                        # Déterminer si la valeur est numérique
                        if value.isdigit():
                            condition_text = f"{field} = {value}"
                        else:
                            condition_text = f"{field} = '{value}'"

                where_clause = f" WHERE {condition_text}"
                break

    # Si aucune condition WHERE n'est trouvée, ajouter une condition par défaut
    # (pour éviter de supprimer toutes les lignes par accident)
    if not where_clause:
        where_clause = " WHERE id = 1"

    # Construire la requête DELETE
    query = f"DELETE FROM {table}{where_clause};"

    # Ajouter la clause RETURNING si demandée
    if advanced_options.get("returning", False) or "returning" in description_lower or "retourner" in description_lower:
        # Supprimer le point-virgule final
        query = query.rstrip(";")
        # Ajouter la clause RETURNING
        query += "\nRETURNING id;";

    # Ajouter une explication détaillée
    explanation = "\n\n-- Explication de la requête :\n"
    explanation += f"-- Cette requête supprime des données de la table: {table}\n"
    explanation += f"-- Avec la condition: {where_clause.replace('WHERE', '').strip()}\n"

    if advanced_options.get("returning", False) or "returning" in description_lower or "retourner" in description_lower:
        explanation += "-- Retourne les identifiants des lignes supprimées\n"

    # Options avancées détectées
    active_options = [option for option, enabled in advanced_options.items() if enabled]
    if active_options:
        explanation += f"-- Options avancées détectées: {', '.join(active_options)}\n"

    return query + explanation

# Fonction pour générer une requête CREATE
def generate_create_query(description, tables, fields, advanced_options):
    """Génère une requête SQL CREATE basée sur une description en langage naturel"""
    description_lower = description.lower()

    # Vérifier si des tables ont été trouvées
    if not tables:
        return "Erreur: Impossible de déterminer le nom de l'objet à créer."

    # Utiliser la première table comme nom de l'objet à créer
    object_name = tables[0]

    # Déterminer le type d'objet à créer
    object_type = "TABLE"  # Par défaut

    if "vue" in description_lower or "view" in description_lower:
        object_type = "VIEW"
    elif "index" in description_lower:
        object_type = "INDEX"
    elif "procédure" in description_lower or "procedure" in description_lower:
        object_type = "PROCEDURE"
    elif "fonction" in description_lower or "function" in description_lower:
        object_type = "FUNCTION"
    elif "trigger" in description_lower or "déclencheur" in description_lower:
        object_type = "TRIGGER"

    # Construire la requête selon le type d'objet
    if object_type == "TABLE":
        # Vérifier si des champs ont été trouvés
        if not fields:
            fields = ["id", "nom", "description", "date_creation", "statut"]

        # Générer les définitions de colonnes
        column_definitions = []
        for field in fields:
            if field.lower() in ["id", "identifiant", "code"]:
                column_definitions.append(f"{field} INT PRIMARY KEY")
            elif field.lower() in ["nom", "prenom", "name", "first_name", "last_name", "titre", "title"]:
                column_definitions.append(f"{field} VARCHAR(100) NOT NULL")
            elif field.lower() in ["description", "commentaire", "comment", "texte", "text"]:
                column_definitions.append(f"{field} TEXT")
            elif field.lower() in ["email", "mail", "courriel"]:
                column_definitions.append(f"{field} VARCHAR(100) UNIQUE")
            elif field.lower() in ["date", "date_creation", "date_inscription", "creation_date", "registration_date"]:
                column_definitions.append(f"{field} DATE")
            elif field.lower() in ["montant", "prix", "price", "amount", "valeur", "value", "cout", "cost"]:
                column_definitions.append(f"{field} DECIMAL(10, 2)")
            elif field.lower() in ["quantite", "quantity", "nombre", "number", "count"]:
                column_definitions.append(f"{field} INT")
            elif field.lower() in ["statut", "status", "etat", "state"]:
                column_definitions.append(f"{field} VARCHAR(20)")
            elif field.lower().endswith("_id") or field.lower().endswith("id"):
                # Déterminer la table référencée
                referenced_table = field.lower().replace("_id", "")
                column_definitions.append(f"{field} INT REFERENCES {referenced_table}(id)")
            else:
                column_definitions.append(f"{field} VARCHAR(100)")

        # Ajouter IF NOT EXISTS si demandé
        if_not_exists = ""
        if advanced_options.get("if_not_exists", False) or "if not exists" in description_lower or "si n'existe pas" in description_lower:
            if_not_exists = " IF NOT EXISTS"

        # Ajouter TEMPORARY si demandé
        temporary = ""
        if advanced_options.get("temporary", False) or "temporary" in description_lower or "temporaire" in description_lower:
            temporary = " TEMPORARY"

        # Construire la requête CREATE TABLE
        query = f"CREATE{temporary} TABLE{if_not_exists} {object_name} (\n  {',\n  '.join(column_definitions)}\n);"

    elif object_type == "VIEW":
        # Construire une requête SELECT simple pour la vue
        select_query = f"SELECT * FROM {tables[1] if len(tables) > 1 else 'table_source'}"

        # Ajouter une condition WHERE si mentionnée
        if "où" in description_lower or "where" in description_lower or "condition" in description_lower:
            select_query += " WHERE status = 'actif'"  # Condition générique

        # Ajouter IF NOT EXISTS si demandé
        if_not_exists = ""
        if advanced_options.get("if_not_exists", False) or "if not exists" in description_lower or "si n'existe pas" in description_lower:
            if_not_exists = " IF NOT EXISTS"

        # Construire la requête CREATE VIEW
        query = f"CREATE VIEW{if_not_exists} {object_name} AS\n{select_query};"

    elif object_type == "INDEX":
        # Déterminer la table et les colonnes pour l'index
        index_table = tables[1] if len(tables) > 1 else "table_name"
        index_columns = fields if fields else ["column_name"]

        # Ajouter IF NOT EXISTS si demandé
        if_not_exists = ""
        if advanced_options.get("if_not_exists", False) or "if not exists" in description_lower or "si n'existe pas" in description_lower:
            if_not_exists = " IF NOT EXISTS"

        # Construire la requête CREATE INDEX
        query = f"CREATE INDEX{if_not_exists} {object_name} ON {index_table} ({', '.join(index_columns)});"

    else:
        # Pour les autres types d'objets, retourner un message d'erreur
        return f"Erreur: La génération de requêtes CREATE {object_type} n'est pas encore supportée."

    # Ajouter une explication détaillée
    explanation = "\n\n-- Explication de la requête :\n"
    explanation += f"-- Cette requête crée un(e) {object_type}: {object_name}\n"

    if object_type == "TABLE":
        explanation += f"-- Avec les colonnes: {', '.join(fields)}\n"

        if advanced_options.get("if_not_exists", False) or "if not exists" in description_lower or "si n'existe pas" in description_lower:
            explanation += "-- La table ne sera créée que si elle n'existe pas déjà\n"

        if advanced_options.get("temporary", False) or "temporary" in description_lower or "temporaire" in description_lower:
            explanation += "-- La table sera temporaire (supprimée à la fin de la session)\n"

    elif object_type == "VIEW":
        explanation += f"-- Basée sur la requête: {select_query}\n"

    elif object_type == "INDEX":
        explanation += f"-- Sur la table: {index_table}\n"
        explanation += f"-- Pour les colonnes: {', '.join(index_columns)}\n"

    # Options avancées détectées
    active_options = [option for option, enabled in advanced_options.items() if enabled]
    if active_options:
        explanation += f"-- Options avancées détectées: {', '.join(active_options)}\n"

    return query + explanation

# Fonction pour générer une requête ALTER
def generate_alter_query(description, tables, fields, advanced_options):
    """Génère une requête SQL ALTER basée sur une description en langage naturel"""
    description_lower = description.lower()

    # Vérifier si des tables ont été trouvées
    if not tables:
        return "Erreur: Impossible de déterminer la table à modifier."

    # Utiliser la première table comme cible de la modification
    table = tables[0]

    # Déterminer le type de modification à effectuer
    if advanced_options.get("add_column", False) or "ajouter colonne" in description_lower or "add column" in description_lower:
        # Modification: Ajouter une colonne

        # Vérifier si des champs ont été trouvés
        if not fields:
            return "Erreur: Impossible de déterminer les colonnes à ajouter."

        # Générer les définitions de colonnes à ajouter
        column_definitions = []
        for field in fields:
            if field.lower() in ["id", "identifiant", "code"]:
                column_definitions.append(f"ADD COLUMN {field} INT")
            elif field.lower() in ["nom", "prenom", "name", "first_name", "last_name", "titre", "title"]:
                column_definitions.append(f"ADD COLUMN {field} VARCHAR(100)")
            elif field.lower() in ["description", "commentaire", "comment", "texte", "text"]:
                column_definitions.append(f"ADD COLUMN {field} TEXT")
            elif field.lower() in ["email", "mail", "courriel"]:
                column_definitions.append(f"ADD COLUMN {field} VARCHAR(100)")
            elif field.lower() in ["date", "date_creation", "date_inscription", "creation_date", "registration_date"]:
                column_definitions.append(f"ADD COLUMN {field} DATE")
            elif field.lower() in ["montant", "prix", "price", "amount", "valeur", "value", "cout", "cost"]:
                column_definitions.append(f"ADD COLUMN {field} DECIMAL(10, 2)")
            elif field.lower() in ["quantite", "quantity", "nombre", "number", "count"]:
                column_definitions.append(f"ADD COLUMN {field} INT")
            elif field.lower() in ["statut", "status", "etat", "state"]:
                column_definitions.append(f"ADD COLUMN {field} VARCHAR(20)")
            elif field.lower().endswith("_id") or field.lower().endswith("id"):
                column_definitions.append(f"ADD COLUMN {field} INT")
            else:
                column_definitions.append(f"ADD COLUMN {field} VARCHAR(100)")

        # Construire la requête ALTER TABLE ADD COLUMN
        query = f"ALTER TABLE {table}\n{column_definitions[0]};"

        # Ajouter une explication détaillée
        explanation = "\n\n-- Explication de la requête :\n"
        explanation += f"-- Cette requête ajoute une colonne à la table: {table}\n"
        explanation += f"-- Colonne ajoutée: {fields[0]}\n"

    elif advanced_options.get("drop_column", False) or "supprimer colonne" in description_lower or "drop column" in description_lower:
        # Modification: Supprimer une colonne

        # Vérifier si des champs ont été trouvés
        if not fields:
            return "Erreur: Impossible de déterminer les colonnes à supprimer."

        # Construire la requête ALTER TABLE DROP COLUMN
        query = f"ALTER TABLE {table}\nDROP COLUMN {fields[0]};"

        # Ajouter une explication détaillée
        explanation = "\n\n-- Explication de la requête :\n"
        explanation += f"-- Cette requête supprime une colonne de la table: {table}\n"
        explanation += f"-- Colonne supprimée: {fields[0]}\n"

    elif advanced_options.get("modify_column", False) or "modifier colonne" in description_lower or "alter column" in description_lower:
        # Modification: Modifier une colonne

        # Vérifier si des champs ont été trouvés
        if not fields:
            return "Erreur: Impossible de déterminer les colonnes à modifier."

        # Déterminer le nouveau type de données
        new_type = "VARCHAR(100)"  # Par défaut

        if "texte" in description_lower or "text" in description_lower:
            new_type = "TEXT"
        elif "entier" in description_lower or "integer" in description_lower or "int" in description_lower:
            new_type = "INT"
        elif "decimal" in description_lower or "nombre" in description_lower or "number" in description_lower:
            new_type = "DECIMAL(10, 2)"
        elif "date" in description_lower:
            new_type = "DATE"
        elif "booléen" in description_lower or "boolean" in description_lower:
            new_type = "BOOLEAN"

        # Construire la requête ALTER TABLE ALTER COLUMN
        query = f"ALTER TABLE {table}\nALTER COLUMN {fields[0]} TYPE {new_type};"

        # Ajouter une explication détaillée
        explanation = "\n\n-- Explication de la requête :\n"
        explanation += f"-- Cette requête modifie le type d'une colonne de la table: {table}\n"
        explanation += f"-- Colonne modifiée: {fields[0]}\n"
        explanation += f"-- Nouveau type: {new_type}\n"

    elif advanced_options.get("rename", False) or "renommer" in description_lower or "rename" in description_lower:
        # Modification: Renommer une table ou une colonne

        if "colonne" in description_lower or "column" in description_lower:
            # Renommer une colonne

            # Vérifier si des champs ont été trouvés
            if not fields or len(fields) < 2:
                return "Erreur: Impossible de déterminer l'ancien et le nouveau nom de la colonne."

            # Construire la requête ALTER TABLE RENAME COLUMN
            query = f"ALTER TABLE {table}\nRENAME COLUMN {fields[0]} TO {fields[1]};"

            # Ajouter une explication détaillée
            explanation = "\n\n-- Explication de la requête :\n"
            explanation += f"-- Cette requête renomme une colonne de la table: {table}\n"
            explanation += f"-- Ancien nom: {fields[0]}\n"
            explanation += f"-- Nouveau nom: {fields[1]}\n"

        else:
            # Renommer une table

            # Vérifier si une nouvelle table a été trouvée
            new_table = tables[1] if len(tables) > 1 else f"new_{table}"

            # Construire la requête ALTER TABLE RENAME TO
            query = f"ALTER TABLE {table}\nRENAME TO {new_table};"

            # Ajouter une explication détaillée
            explanation = "\n\n-- Explication de la requête :\n"
            explanation += f"-- Cette requête renomme une table\n"
            explanation += f"-- Ancien nom: {table}\n"
            explanation += f"-- Nouveau nom: {new_table}\n"

    else:
        # Modification par défaut: Ajouter une contrainte

        # Construire la requête ALTER TABLE ADD CONSTRAINT
        query = f"ALTER TABLE {table}\nADD CONSTRAINT {table}_constraint CHECK (id > 0);"

        # Ajouter une explication détaillée
        explanation = "\n\n-- Explication de la requête :\n"
        explanation += f"-- Cette requête ajoute une contrainte à la table: {table}\n"
        explanation += f"-- Contrainte: CHECK (id > 0)\n"

    # Options avancées détectées
    active_options = [option for option, enabled in advanced_options.items() if enabled]
    if active_options:
        explanation += f"-- Options avancées détectées: {', '.join(active_options)}\n"

    return query + explanation

# Fonction pour générer une requête DROP
def generate_drop_query(description, tables, advanced_options):
    """Génère une requête SQL DROP basée sur une description en langage naturel"""
    description_lower = description.lower()

    # Vérifier si des tables ont été trouvées
    if not tables:
        return "Erreur: Impossible de déterminer l'objet à supprimer."

    # Utiliser la première table comme nom de l'objet à supprimer
    object_name = tables[0]

    # Déterminer le type d'objet à supprimer
    object_type = "TABLE"  # Par défaut

    if "vue" in description_lower or "view" in description_lower:
        object_type = "VIEW"
    elif "index" in description_lower:
        object_type = "INDEX"
    elif "procédure" in description_lower or "procedure" in description_lower:
        object_type = "PROCEDURE"
    elif "fonction" in description_lower or "function" in description_lower:
        object_type = "FUNCTION"
    elif "trigger" in description_lower or "déclencheur" in description_lower:
        object_type = "TRIGGER"
    elif "contrainte" in description_lower or "constraint" in description_lower:
        object_type = "CONSTRAINT"

    # Ajouter IF EXISTS si demandé
    if_exists = ""
    if advanced_options.get("if_exists", False) or "if exists" in description_lower or "si existe" in description_lower:
        if_exists = " IF EXISTS"

    # Ajouter CASCADE si demandé
    cascade = ""
    if advanced_options.get("cascade", False) or "cascade" in description_lower or "en cascade" in description_lower:
        cascade = " CASCADE"

    # Construire la requête DROP
    query = f"DROP {object_type}{if_exists} {object_name}{cascade};"

    # Ajouter une explication détaillée
    explanation = "\n\n-- Explication de la requête :\n"
    explanation += f"-- Cette requête supprime un(e) {object_type}: {object_name}\n"

    if advanced_options.get("if_exists", False) or "if exists" in description_lower or "si existe" in description_lower:
        explanation += "-- L'objet ne sera supprimé que s'il existe\n"

    if advanced_options.get("cascade", False) or "cascade" in description_lower or "en cascade" in description_lower:
        explanation += "-- Supprime également tous les objets qui dépendent de celui-ci\n"

    # Options avancées détectées
    active_options = [option for option, enabled in advanced_options.items() if enabled]
    if active_options:
        explanation += f"-- Options avancées détectées: {', '.join(active_options)}\n"

    return query + explanation

# Fonction pour ajouter une requête à l'historique et apprendre des interactions
def add_to_history(description, query, sql_type, advanced_options=None, user_intent=None):
    """Ajoute une requête à l'historique des requêtes et apprend des interactions"""
    if 'query_history' not in session:
        session['query_history'] = []

    # Créer un nouvel enregistrement d'historique
    history_entry = {
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'description': description,
        'query': query,
        'type': sql_type,
        'advanced_options': advanced_options or {},
        'user_intent': user_intent or {}
    }

    # Ajouter l'enregistrement à l'historique
    session['query_history'].insert(0, history_entry)  # Ajouter au début pour avoir les plus récents en premier

    # Limiter l'historique à 50 entrées
    if len(session['query_history']) > 50:
        session['query_history'] = session['query_history'][:50]

    # Sauvegarder la session
    session.modified = True

    # Apprendre des interactions précédentes
    learn_from_interaction(description, query, sql_type, advanced_options, user_intent)

# Fonction pour apprendre des interactions précédentes
def learn_from_interaction(description, query, sql_type, advanced_options, user_intent):
    """Apprend des interactions précédentes pour améliorer les futures générations"""
    if 'learning_patterns' not in session:
        session['learning_patterns'] = {
            'phrases': {},  # Phrases clés et leurs associations
            'tables': {},   # Tables fréquemment utilisées
            'fields': {},   # Champs fréquemment utilisés
            'patterns': []  # Modèles de requêtes fréquents
        }

    learning = session['learning_patterns']

    # Extraire les phrases clés de la description (3-5 mots consécutifs)
    words = description.lower().split()
    for i in range(len(words) - 2):
        for j in range(3, 6):  # Phrases de 3 à 5 mots
            if i + j <= len(words):
                phrase = ' '.join(words[i:i+j])
                if phrase not in learning['phrases']:
                    learning['phrases'][phrase] = {
                        'count': 0,
                        'sql_types': {},
                        'tables': {},
                        'fields': {}
                    }

                # Incrémenter le compteur
                learning['phrases'][phrase]['count'] += 1

                # Associer au type SQL
                if sql_type not in learning['phrases'][phrase]['sql_types']:
                    learning['phrases'][phrase]['sql_types'][sql_type] = 0
                learning['phrases'][phrase]['sql_types'][sql_type] += 1

                # Extraire les tables et champs de la requête
                tables_match = re.findall(r'FROM\s+([a-zA-Z0-9_]+)', query, re.IGNORECASE)
                if tables_match:
                    for table in tables_match:
                        # Associer la table à la phrase
                        if table not in learning['phrases'][phrase]['tables']:
                            learning['phrases'][phrase]['tables'][table] = 0
                        learning['phrases'][phrase]['tables'][table] += 1

                        # Mettre à jour les statistiques globales des tables
                        if table not in learning['tables']:
                            learning['tables'][table] = 0
                        learning['tables'][table] += 1

                # Extraire les champs de la requête
                fields_match = re.findall(r'SELECT\s+(.*?)\s+FROM', query, re.IGNORECASE | re.DOTALL)
                if fields_match and fields_match[0] != '*':
                    fields_list = fields_match[0].split(',')
                    for field_item in fields_list:
                        field = field_item.strip().split(' ')[0].split('.')[-1]  # Nettoyer le nom du champ
                        # Associer le champ à la phrase
                        if field not in learning['phrases'][phrase]['fields']:
                            learning['phrases'][phrase]['fields'][field] = 0
                        learning['phrases'][phrase]['fields'][field] += 1

                        # Mettre à jour les statistiques globales des champs
                        if field not in learning['fields']:
                            learning['fields'][field] = 0
                        learning['fields'][field] += 1

    # Enregistrer un modèle de requête si c'est une requête SELECT
    if sql_type == "SELECT" and user_intent and user_intent.get('confidence', 0) > 0.5:
        # Créer une version simplifiée de la requête (template)
        template = query
        # Remplacer les valeurs spécifiques par des placeholders
        template = re.sub(r'WHERE\s+\w+\s*=\s*[\'"]?[a-zA-Z0-9_]+[\'"]?', 'WHERE field = :value', template)
        template = re.sub(r'WHERE\s+\w+\s*>\s*\d+', 'WHERE field > :number', template)
        template = re.sub(r'WHERE\s+\w+\s*<\s*\d+', 'WHERE field < :number', template)
        template = re.sub(r'LIMIT\s+\d+', 'LIMIT :limit', template)

        # Ajouter le template à la liste des modèles
        pattern_entry = {
            'template': template,
            'purpose': user_intent.get('purpose'),
            'action': user_intent.get('action'),
            'count': 1
        }

        # Vérifier si ce modèle existe déjà
        pattern_exists = False
        for i, pattern in enumerate(learning['patterns']):
            if pattern['template'] == template:
                learning['patterns'][i]['count'] += 1
                pattern_exists = True
                break

        if not pattern_exists:
            learning['patterns'].append(pattern_entry)

    # Sauvegarder les modifications
    session['learning_patterns'] = learning
    session.modified = True

# Fonction pour utiliser les connaissances acquises
def apply_learned_knowledge(description):
    """Utilise les connaissances acquises pour améliorer la génération de requêtes"""
    if 'learning_patterns' not in session:
        return None, None, None

    learning = session['learning_patterns']

    # Initialiser les suggestions
    suggested_type = None
    suggested_tables = []
    suggested_fields = []

    # Rechercher les phrases correspondantes
    words = description.lower().split()
    matched_phrases = []

    for i in range(len(words) - 2):
        for j in range(5, 2, -1):  # Commencer par les phrases les plus longues
            if i + j <= len(words):
                phrase = ' '.join(words[i:i+j])
                if phrase in learning['phrases']:
                    matched_phrases.append((phrase, learning['phrases'][phrase]['count']))

    # Trier les phrases par nombre d'occurrences
    matched_phrases.sort(key=lambda x: x[1], reverse=True)

    # Utiliser les 3 meilleures correspondances
    top_matches = matched_phrases[:3]

    if top_matches:
        # Déterminer le type SQL le plus probable
        type_counts = {}
        table_counts = {}
        field_counts = {}

        for phrase, _ in top_matches:
            phrase_data = learning['phrases'][phrase]

            # Compter les types SQL
            for sql_type, count in phrase_data['sql_types'].items():
                if sql_type not in type_counts:
                    type_counts[sql_type] = 0
                type_counts[sql_type] += count

            # Compter les tables
            for table, count in phrase_data['tables'].items():
                if table not in table_counts:
                    table_counts[table] = 0
                table_counts[table] += count

            # Compter les champs
            for field, count in phrase_data['fields'].items():
                if field not in field_counts:
                    field_counts[field] = 0
                field_counts[field] += count

        # Déterminer le type SQL le plus probable
        if type_counts:
            suggested_type = max(type_counts.items(), key=lambda x: x[1])[0]

        # Déterminer les tables les plus probables (jusqu'à 2)
        if table_counts:
            suggested_tables = [table for table, _ in sorted(table_counts.items(), key=lambda x: x[1], reverse=True)[:2]]

        # Déterminer les champs les plus probables (jusqu'à 5)
        if field_counts:
            suggested_fields = [field for field, _ in sorted(field_counts.items(), key=lambda x: x[1], reverse=True)[:5]]

    return suggested_type, suggested_tables, suggested_fields

# Routes de l'application
@app.route('/')
def index():
    """Route principale pour afficher la page d'accueil"""
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    """Route pour traiter les requêtes de génération SQL"""
    data = request.json
    text = data.get('text', '')

    # Analyser l'intention de l'utilisateur
    user_intent = analyze_user_request(text)

    # Générer la requête SQL
    result, sql_type, advanced_options = generate_sql_query(text)

    # Ajouter la requête à l'historique avec l'intention utilisateur
    add_to_history(text, result, sql_type, advanced_options, user_intent)

    # Déterminer si des options avancées ont été détectées
    has_advanced_options = any(advanced_options.values())

    # Préparer les suggestions basées sur l'apprentissage
    suggested_type, suggested_tables, suggested_fields = apply_learned_knowledge(text)

    # Créer un message de suggestion si pertinent
    suggestion_message = None
    if suggested_tables or suggested_fields:
        suggestion_message = "Basé sur vos requêtes précédentes, je suggère : "
        if suggested_tables:
            suggestion_message += f"Tables: {', '.join(suggested_tables)}. "
        if suggested_fields:
            suggestion_message += f"Champs: {', '.join(suggested_fields[:3])}"
            if len(suggested_fields) > 3:
                suggestion_message += f" et {len(suggested_fields) - 3} autres"

    return jsonify({
        'result': result,
        'detected_type': sql_type,
        'advanced_options': advanced_options,
        'has_advanced_options': has_advanced_options,
        'history': session.get('query_history', []),
        'user_intent': user_intent,
        'suggestion': suggestion_message
    })

@app.route('/history', methods=['GET'])
def get_history():
    """Route pour récupérer l'historique des requêtes"""
    return jsonify({
        'history': session.get('query_history', [])
    })

@app.route('/clear_history', methods=['POST'])
def clear_history():
    """Route pour effacer l'historique des requêtes"""
    session['query_history'] = []
    session.modified = True
    return jsonify({'success': True})

@app.route('/extract_fields', methods=['POST'])
def extract_fields():
    """Route pour extraire les champs d'une requête SQL pour les graphiques"""
    data = request.json
    query = data.get('query', '')

    # Extraire les champs de la requête
    fields = []

    # Rechercher les champs dans la clause SELECT
    select_match = re.search(r'SELECT\s+(.*?)\s+FROM', query, re.IGNORECASE | re.DOTALL)
    if select_match:
        select_clause = select_match.group(1)

        # Supprimer les fonctions d'agrégation pour obtenir les noms de champs
        select_clause = re.sub(r'(COUNT|SUM|AVG|MAX|MIN)\s*\(\s*([^)]+)\s*\)', r'\2', select_clause)

        # Diviser par les virgules et nettoyer
        fields = [field.strip() for field in select_clause.split(',')]

        # Supprimer les alias
        fields = [re.sub(r'(?i)\s+AS\s+\w+$', '', field) for field in fields]

        # Supprimer les noms de table qualifiés
        fields = [re.sub(r'^\w+\.', '', field) for field in fields]

        # Supprimer les astérisques
        fields = [field for field in fields if field != '*']

    return jsonify({
        'fields': fields
    })

@app.route('/correct_query', methods=['POST'])
def correct_query_route():
    """Route pour corriger une requête SQL"""
    data = request.json
    query = data.get('query', '')

    # Corriger la requête SQL
    correction_result = correct_sql_query(query)

    # Ajouter des suggestions d'amélioration basées sur l'apprentissage
    if 'learning_patterns' in session:
        learning = session['learning_patterns']

        # Ajouter des suggestions basées sur les modèles fréquents
        if correction_result.get("corrected_query") and "SELECT" in correction_result.get("corrected_query", ""):
            # Trouver des modèles similaires
            similar_patterns = []
            for pattern in learning.get('patterns', []):
                if pattern.get('action') == "SELECT" and pattern.get('count', 0) > 1:
                    similar_patterns.append(pattern)

            # Trier par nombre d'occurrences
            similar_patterns.sort(key=lambda x: x.get('count', 0), reverse=True)

            # Ajouter jusqu'à 2 suggestions de modèles fréquents
            for pattern in similar_patterns[:2]:
                suggestion = f"Modèle fréquent: {pattern.get('template')}"
                if pattern.get('purpose'):
                    suggestion += f" (utilisé pour: {pattern.get('purpose')})"

                if suggestion not in correction_result.get("suggestions", []):
                    correction_result.setdefault("suggestions", []).append(suggestion)

        # Suggérer des tables fréquemment utilisées
        if not re.search(r'\bFROM\s+\w+\b', query, re.IGNORECASE):
            top_tables = sorted(learning.get('tables', {}).items(), key=lambda x: x[1], reverse=True)[:3]
            if top_tables:
                tables_suggestion = "Tables fréquemment utilisées: " + ", ".join([table for table, _ in top_tables])
                correction_result.setdefault("suggestions", []).append(tables_suggestion)

        # Suggérer des champs fréquemment utilisés
        if "SELECT *" in query:
            top_fields = sorted(learning.get('fields', {}).items(), key=lambda x: x[1], reverse=True)[:5]
            if top_fields:
                fields_suggestion = "Champs spécifiques fréquemment utilisés: " + ", ".join([field for field, _ in top_fields])
                correction_result.setdefault("suggestions", []).append(fields_suggestion)

    return jsonify(correction_result)

if __name__ == '__main__':
    app.run(debug=True)