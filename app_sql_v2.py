from flask import Flask, render_template, request, jsonify, session
import re
import datetime
import os
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

# Télécharger les ressources NLTK nécessaires
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Clé secrète pour les sessions

# Fonction pour détecter automatiquement les options avancées pour les requêtes SELECT
def detect_advanced_options(description):
    """Détecte automatiquement les options avancées pour les requêtes SELECT"""
    description_lower = description.lower()

    # Tokenisation et nettoyage du texte
    tokens = word_tokenize(description_lower, language='french')
    french_stopwords = set(stopwords.words('french'))
    tokens = [token for token in tokens if token not in french_stopwords]

    # Options avancées pertinentes pour les requêtes SELECT
    advanced_options = {
        "cte": False,          # Common Table Expressions (WITH)
        "window": False,       # Fonctions de fenêtre
        "recursive": False,    # Requêtes récursives
        "subquery": False,     # Sous-requêtes
        "join": False,         # Jointures complexes
        "aggregate": False,    # Fonctions d'agrégation
        "groupby": False,      # Groupement
        "having": False,       # Filtrage après groupement
        "orderby": False,      # Tri
        "limit": False,        # Limitation des résultats
        "distinct": False      # Valeurs distinctes
    }

    # Mots-clés et patterns pour chaque option
    option_patterns = {
        "cte": {
            "keywords": ["cte", "with", "avec", "table temporaire", "table commune", "expression de table commune"],
            "patterns": [r"(?:utilise|avec|using)\s+(?:une|des)?\s+(?:cte|with|table(?:s)?\s+commune(?:s)?)",
                        r"(?:table(?:s)?\s+temporaire(?:s)?)",
                        r"(?:expression(?:s)?\s+de\s+table(?:s)?\s+commune(?:s)?)"]
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
        "subquery": {
            "keywords": ["sous-requête", "subquery", "requête imbriquée", "nested query", "in", "exists", "any", "all"],
            "patterns": [r"(?:sous[-\s]requête(?:s)?|requête(?:s)?\s+imbriquée(?:s)?)",
                        r"(?:où\s+existe(?:nt)?|where\s+exists)",
                        r"(?:dans\s+(?:une|la|des|les)?\s+(?:autre(?:s)?\s+)?requête(?:s)?)",
                        r"(?:in|exists|any|all)"]
        },
        "join": {
            "keywords": ["join", "jointure", "inner join", "left join", "right join", "full join", "cross join", "natural join"],
            "patterns": [r"(?:jointure(?:s)?|join)",
                        r"(?:inner|left|right|full|cross|natural)\s+join",
                        r"(?:jointure(?:s)?\s+(?:interne(?:s)?|externe(?:s)?|gauche|droite|complète(?:s)?|croisée(?:s)?|naturelle(?:s)?))",
                        r"(?:reli(?:er|ant)|lier|lié(?:e)?(?:s)?)\s+(?:avec|à|aux?|les?|la)"]
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
            "keywords": ["limit", "limiter", "limite", "top", "first", "offset", "premiers", "premières"],
            "patterns": [r"(?:limit(?:er|é(?:e)?(?:s)?)?|limite(?:r)?)",
                        r"(?:top|first|offset)",
                        r"(?:les?\s+\d+\s+premier(?:s|ères)?)",
                        r"(?:seulement|uniquement)\s+\d+",
                        r"(?:limit(?:é)?\s+à\s+\d+)"]
        },
        "distinct": {
            "keywords": ["distinct", "unique", "différent", "sans doublon", "sans répétition"],
            "patterns": [r"(?:distinct|unique|différent(?:e)?(?:s)?)",
                        r"(?:sans\s+(?:doublon|répétition)(?:s)?)",
                        r"(?:valeur(?:s)?\s+unique(?:s)?)",
                        r"(?:élimin(?:er|ant)\s+(?:les\s+)?doublon(?:s)?)"]
        }
    }

    # Détecter les options avancées
    for option, patterns_info in option_patterns.items():
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
    if "hiérarchie" in description_lower or ("niveau" in description_lower and "parent" in description_lower):
        advanced_options["recursive"] = True

    if "classement" in description_lower or "rang" in description_lower:
        advanced_options["window"] = True

    if "temporaire" in description_lower and "résultat" in description_lower:
        advanced_options["cte"] = True

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

# Fonction pour ajouter une requête à l'historique
def add_to_history(description, query, advanced_options=None):
    """Ajoute une requête à l'historique des requêtes"""
    if 'query_history' not in session:
        session['query_history'] = []

    # Créer un nouvel enregistrement d'historique
    history_entry = {
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'description': description,
        'query': query,
        'type': 'SELECT',  # Toujours SELECT car l'application est spécialisée
        'advanced_options': advanced_options or {}
    }

    # Ajouter l'enregistrement à l'historique
    session['query_history'].insert(0, history_entry)  # Ajouter au début pour avoir les plus récents en premier

    # Limiter l'historique à 50 entrées
    if len(session['query_history']) > 50:
        session['query_history'] = session['query_history'][:50]

    # Sauvegarder la session
    session.modified = True

def extract_tables_and_fields(description):
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
                        "quand", "où", "je", "tu", "il", "elle", "nous", "vous", "ils", "elles"]

        # Mots qui sont souvent des noms de tables
        table_indicators = ["utilisateurs", "users", "clients", "customers", "produits", "products",
                           "commandes", "orders", "ventes", "sales", "employés", "employees",
                           "catégories", "categories", "articles", "items", "factures", "invoices"]

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
            tables = ["utilisateurs"]  # Table par défaut

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
            "utilisateurs": ["id", "nom", "prenom", "email", "date_inscription"],
            "users": ["id", "name", "first_name", "email", "registration_date"],
            "clients": ["id", "nom", "prenom", "email", "telephone"],
            "customers": ["id", "name", "email", "phone"],
            "produits": ["id", "nom", "prix", "description", "categorie"],
            "products": ["id", "name", "price", "description", "category"],
            "commandes": ["id", "date", "client_id", "montant", "statut"],
            "orders": ["id", "date", "customer_id", "amount", "status"],
            "ventes": ["id", "date", "produit_id", "quantite", "montant"],
            "sales": ["id", "date", "product_id", "quantity", "amount"],
            "employés": ["id", "nom", "prenom", "poste", "salaire"],
            "employees": ["id", "name", "first_name", "position", "salary"]
        }

        # Patterns pour détecter les champs
        field_patterns = [
            r"(?:le|la|les)\s+(?:champ|colonne|attribut)s?\s+(\w+)",
            r"(?:afficher|montrer|sélectionner|obtenir)\s+(?:le|la|les)?\s+(\w+)",
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

            # Si toujours aucun champ, utiliser des champs génériques
            if not potential_fields:
                potential_fields = ["id", "nom", "date", "montant"]

        fields = list(set(potential_fields))  # Éliminer les doublons

    return tables, fields

def generate_sql_query(description):
    """Génère une requête SQL SELECT avancée basée sur une description en langage naturel"""
    # Détecter les options avancées
    advanced_options = detect_advanced_options(description)

    # Extraire les tables et champs
    tables, fields = extract_tables_and_fields(description)

    # Vérifier si des tables ont été trouvées
    if not tables:
        return "Erreur: Impossible de déterminer les tables à utiliser dans la requête.\n\nExemple de format: 'Je veux une requête qui sélectionne les champs nom, prénom des tables utilisateurs où id > 100'\n\nPour des requêtes plus avancées, vous pouvez spécifier:\n- Des fonctions d'agrégation (COUNT, SUM, AVG, MAX, MIN)\n- Des groupements (GROUP BY)\n- Des sous-requêtes\n- Des jointures complexes\n- Des conditions avancées (HAVING, IN, EXISTS)"

    # Construction de la clause WITH (CTE) si nécessaire
    with_clause = ""
    if advanced_options.get("cte", False):
        # Générer une CTE simple
        cte_name = f"cte_{tables[0]}"
        cte_select = "SELECT * FROM " + tables[0]

        # Ajouter une condition si possible
        if "où" in description.lower() or "where" in description.lower() or "condition" in description.lower():
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
                if any(keyword in description.lower() for keyword in ["count", "nombre", "compter", "comptage"]) and field in ["id", "utilisateur", "client", "commande"]:
                    processed_fields.append(f"COUNT({field})")
                elif any(keyword in description.lower() for keyword in ["sum", "somme", "total", "montant"]) and field in ["montant", "prix", "valeur", "quantite", "quantité"]:
                    processed_fields.append(f"SUM({field})")
                elif any(keyword in description.lower() for keyword in ["avg", "moyenne", "moyen"]) and field in ["montant", "prix", "valeur", "age", "âge", "quantite", "quantité"]:
                    processed_fields.append(f"AVG({field})")
                elif any(keyword in description.lower() for keyword in ["max", "maximum", "plus grand", "plus élevé"]) and field in ["montant", "prix", "valeur", "date", "age", "âge", "quantite", "quantité"]:
                    processed_fields.append(f"MAX({field})")
                elif any(keyword in description.lower() for keyword in ["min", "minimum", "plus petit", "plus bas"]) and field in ["montant", "prix", "valeur", "date", "age", "âge", "quantite", "quantité"]:
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
    if "left join" in description.lower() or "jointure externe gauche" in description.lower() or "gauche" in description.lower():
        join_type = "LEFT JOIN"
    elif "right join" in description.lower() or "jointure externe droite" in description.lower() or "droite" in description.lower():
        join_type = "RIGHT JOIN"
    elif "full join" in description.lower() or "jointure complète" in description.lower() or "complète" in description.lower():
        join_type = "FULL JOIN"
    elif "cross join" in description.lower() or "jointure croisée" in description.lower() or "produit cartésien" in description.lower():
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
                if join_keyword in description.lower():
                    parts = description.lower().split(join_keyword)
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
        if keyword in description.lower():
            parts = description.lower().split(keyword)
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
                if keyword in description.lower():
                    parts = description.lower().split(keyword)
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
            if keyword in description.lower():
                parts = description.lower().split(keyword)
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
            if "count" in description.lower():
                having_clause = "\nHAVING COUNT(*) > 1"
            elif "sum" in description.lower() or "total" in description.lower():
                having_clause = "\nHAVING SUM(montant) > 0"
            elif "avg" in description.lower() or "moyenne" in description.lower():
                having_clause = "\nHAVING AVG(montant) > 0"
            elif "max" in description.lower() or "maximum" in description.lower():
                having_clause = "\nHAVING MAX(montant) > 0"
            elif "min" in description.lower() or "minimum" in description.lower():
                having_clause = "\nHAVING MIN(montant) > 0"

    # Recherche d'instructions de tri (ORDER BY)
    order_clause = ""
    order_keywords = ["trier", "ordonner", "ordre", "order by", "sort", "classer"]

    # Si l'option de tri est détectée
    if advanced_options.get("orderby", False):
        for keyword in order_keywords:
            if keyword in description.lower():
                parts = description.lower().split(keyword)
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
            if keyword in description.lower():
                parts = description.lower().split(keyword)
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

    return query + explanation, advanced_options

@app.route('/')
def index():
    """Route principale pour afficher la page d'accueil"""
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    """Route pour traiter les requêtes de génération SQL"""
    data = request.json
    text = data.get('text', '')

    # Générer la requête SQL
    result, advanced_options = generate_sql_query(text)

    # Ajouter la requête à l'historique
    add_to_history(text, result, advanced_options)

    # Déterminer si des options avancées ont été détectées
    has_advanced_options = any(advanced_options.values())

    return jsonify({
        'result': result,
        'detected_type': 'SELECT',  # Toujours SELECT car l'application est spécialisée
        'advanced_options': advanced_options,
        'has_advanced_options': has_advanced_options,
        'history': session.get('query_history', [])
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

if __name__ == '__main__':
    app.run(debug=True)
