from flask import Flask, render_template, request, jsonify, session
import re
import datetime
import os
import json
import sqlparse
import requests
import html

app = Flask(__name__)
app.secret_key = 'sql_bot_secret_key'  # Clé secrète pour les sessions

# Configuration des modèles pré-entraînés
MODEL_PATHS = {
    "text-to-sql": "juierror/text-to-sql-with-table-schema",  # T5 pour texte → SQL
    "sql-correction": "mrm8488/t5-base-finetuned-sql-correction"  # T5 pour correction SQL
}

# Chargement des modèles et tokenizers
models = {}
tokenizers = {}
pipelines = {}

# Clé API HuggingFace (à remplacer par votre propre clé si nécessaire)
HUGGINGFACE_API_KEY = None  # Mettre votre clé API ici si vous en avez une

# Modèle de traduction
TRANSLATION_MODEL = "Helsinki-NLP/opus-mt-fr-en"

# Fonction pour traduire du français vers l'anglais
def translate_fr_to_en(text):
    """Traduit un texte du français vers l'anglais en utilisant l'API HuggingFace"""
    try:
        # Utiliser l'API HuggingFace pour la traduction
        result = query_huggingface_api(TRANSLATION_MODEL, text)

        if result:
            # Extraire le texte traduit
            if isinstance(result, list) and len(result) > 0:
                if "translation_text" in result[0]:
                    return result[0]["translation_text"]
                else:
                    return result[0].get("text", text)
            else:
                return str(result)
        else:
            # Utiliser une traduction de secours basée sur des règles simples
            return fallback_translate_fr_to_en(text)
    except Exception as e:
        print(f"Erreur lors de la traduction: {str(e)}")
        return fallback_translate_fr_to_en(text)

# Fonction de traduction de secours basée sur des règles simples
def fallback_translate_fr_to_en(text):
    """Traduit un texte du français vers l'anglais en utilisant des règles simples"""
    # Dictionnaire de traduction pour les mots-clés SQL courants
    translation_dict = {
        # Mots-clés de requête
        "sélectionner": "select",
        "sélectionne": "select",
        "afficher": "select",
        "affiche": "select",
        "montrer": "select",
        "montre": "select",
        "lister": "select",
        "liste": "select",
        "obtenir": "select",
        "obtiens": "select",
        "récupérer": "select",
        "récupère": "select",
        "chercher": "select",
        "cherche": "select",
        "trouver": "select",
        "trouve": "select",

        "insérer": "insert",
        "insère": "insert",
        "ajouter": "insert",
        "ajoute": "insert",
        "créer une ligne": "insert",
        "crée une ligne": "insert",

        "mettre à jour": "update",
        "mets à jour": "update",
        "modifier": "update",
        "modifie": "update",
        "changer": "update",
        "change": "update",
        "actualiser": "update",
        "actualise": "update",

        "supprimer": "delete",
        "supprime": "delete",
        "effacer": "delete",
        "efface": "delete",
        "enlever": "delete",
        "enlève": "delete",
        "retirer": "delete",
        "retire": "delete",

        "créer": "create",
        "crée": "create",
        "nouvelle table": "create table",
        "nouveau schéma": "create schema",

        # Clauses SQL
        "où": "where",
        "quand": "when",
        "groupe par": "group by",
        "grouper par": "group by",
        "ordonner par": "order by",
        "trier par": "order by",
        "limiter à": "limit",
        "limite": "limit",
        "joindre": "join",
        "jointure": "join",
        "distinct": "distinct",
        "unique": "distinct",

        # Tables et champs courants
        "utilisateurs": "users",
        "utilisateur": "user",
        "clients": "customers",
        "client": "customer",
        "produits": "products",
        "produit": "product",
        "commandes": "orders",
        "commande": "order",
        "catégories": "categories",
        "catégorie": "category",

        # Champs courants
        "identifiant": "id",
        "nom": "name",
        "prénom": "first_name",
        "nom de famille": "last_name",
        "email": "email",
        "courriel": "email",
        "adresse": "address",
        "téléphone": "phone",
        "prix": "price",
        "quantité": "quantity",
        "date": "date",
        "description": "description",
        "statut": "status",
        "état": "status",

        # Fonctions d'agrégation
        "compter": "count",
        "compte": "count",
        "somme": "sum",
        "moyenne": "avg",
        "minimum": "min",
        "maximum": "max",

        # Opérateurs
        "égal à": "equal to",
        "égale à": "equal to",
        "égal": "equal",
        "égale": "equal",
        "supérieur à": "greater than",
        "supérieure à": "greater than",
        "inférieur à": "less than",
        "inférieure à": "less than",
        "entre": "between",
        "comme": "like",
        "ressemble à": "like",
        "dans": "in",
        "est nul": "is null",
        "n'est pas nul": "is not null",

        # Conjonctions
        "et": "and",
        "ou": "or",
        "non": "not",

        # Prépositions
        "de": "of",
        "du": "of the",
        "des": "of the",
        "dans": "in",
        "avec": "with",
        "sans": "without",
        "pour": "for",
        "par": "by",

        # Autres termes utiles
        "tous": "all",
        "toutes": "all",
        "chaque": "each",
        "plusieurs": "several",
        "certains": "some",
        "certaines": "some",
        "aucun": "none",
        "aucune": "none",
        "premier": "first",
        "première": "first",
        "dernier": "last",
        "dernière": "last",
        "récent": "recent",
        "récente": "recent",
        "ancien": "old",
        "ancienne": "old",
        "actif": "active",
        "active": "active",
        "inactif": "inactive",
        "inactive": "inactive"
    }

    # Remplacer les mots-clés français par leurs équivalents anglais
    translated_text = text.lower()
    for fr_word, en_word in translation_dict.items():
        translated_text = translated_text.replace(fr_word, en_word)

    # Ajouter un préfixe pour indiquer au modèle qu'il s'agit d'une requête SQL
    translated_text = "Generate SQL query: " + translated_text

    return translated_text

def load_model(model_type):
    """Vérifie si un modèle est disponible (fonction de compatibilité)"""
    print(f"Les modèles locaux ne sont pas disponibles. Utilisation de l'API HuggingFace pour {model_type}.")
    return None

# Fonction pour utiliser l'API HuggingFace si le modèle local n'est pas disponible
def query_huggingface_api(model_path, inputs, api_key=None):
    """Interroge l'API HuggingFace pour obtenir des prédictions"""
    api_url = f"https://api-inference.huggingface.co/models/{model_path}"

    headers = {
        "Content-Type": "application/json"
    }

    # Utiliser la clé API globale si aucune clé n'est fournie
    if not api_key and HUGGINGFACE_API_KEY:
        api_key = HUGGINGFACE_API_KEY

    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    data = {
        "inputs": inputs,
        "options": {
            "wait_for_model": True,
            "use_cache": True
        }
    }

    try:
        response = requests.post(api_url, headers=headers, json=data)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Erreur API HuggingFace: {response.status_code}, {response.text}")

            # Si l'erreur est due à un modèle en cours de chargement, attendre et réessayer
            if response.status_code == 503 and "loading" in response.text.lower():
                print("Le modèle est en cours de chargement, attente de 10 secondes...")
                import time
                time.sleep(10)
                return query_huggingface_api(model_path, inputs, api_key)

            return None
    except Exception as e:
        print(f"Erreur lors de la requête à l'API HuggingFace: {str(e)}")
        return None

# Fonction pour générer une requête SQL à partir d'une description en langage naturel
def generate_sql_query(description):
    """Génère une requête SQL à partir d'une description en langage naturel en utilisant un modèle pré-entraîné"""
    # Définir les tables et schémas fictifs pour l'exemple
    # Dans une application réelle, ces informations proviendraient de la base de données
    schema = """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        name TEXT,
        email TEXT,
        age INTEGER,
        created_at TIMESTAMP
    );

    CREATE TABLE orders (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        product_name TEXT,
        amount DECIMAL(10, 2),
        order_date TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE products (
        id INTEGER PRIMARY KEY,
        name TEXT,
        price DECIMAL(10, 2),
        category TEXT,
        stock INTEGER
    );
    """

    # Traduire la description en anglais
    english_description = translate_fr_to_en(description)
    print(f"Description originale: {description}")
    print(f"Description traduite: {english_description}")

    # Préparer l'entrée pour le modèle
    input_text = f"Schema: {schema}\nQuestion: {english_description}\nSQL:"

    try:
        # Utiliser l'API HuggingFace
        result = query_huggingface_api(MODEL_PATHS["text-to-sql"], input_text)

        if result:
            # Extraire la requête SQL générée
            if isinstance(result, list) and len(result) > 0:
                if "generated_text" in result[0]:
                    sql_query = result[0]["generated_text"]
                else:
                    sql_query = result[0].get("text", "SELECT * FROM users LIMIT 10; -- Requête générée par défaut")
            else:
                sql_query = str(result)
        else:
            # Fallback simple si l'API échoue
            sql_query = "SELECT * FROM users LIMIT 10; -- Requête générée par défaut"

        # Déterminer le type de requête
        sql_type = detect_sql_type(sql_query)

        # Ajouter une explication
        explanation = generate_explanation(sql_query)

        # Formater la requête pour une meilleure lisibilité
        formatted_query = sqlparse.format(sql_query, reindent=True, keyword_case='upper')

        return formatted_query + explanation, sql_type, {}

    except Exception as e:
        print(f"Erreur lors de la génération de la requête SQL: {str(e)}")
        return f"Erreur: {str(e)}", "ERROR", {}

# Fonction pour détecter le type de requête SQL
def detect_sql_type(query):
    """Détecte le type de requête SQL"""
    query = query.strip().upper()

    if query.startswith("SELECT"):
        return "SELECT"
    elif query.startswith("INSERT"):
        return "INSERT"
    elif query.startswith("UPDATE"):
        return "UPDATE"
    elif query.startswith("DELETE"):
        return "DELETE"
    elif query.startswith("CREATE"):
        return "CREATE"
    elif query.startswith("ALTER"):
        return "ALTER"
    elif query.startswith("DROP"):
        return "DROP"
    elif query.startswith("TRUNCATE"):
        return "TRUNCATE"
    else:
        return "UNKNOWN"

# Fonction pour générer une explication de la requête SQL
def generate_explanation(query):
    """Génère une explication détaillée de la requête SQL"""
    explanation = "\n\n-- Explication de la requête :\n"

    # Détecter le type de requête
    sql_type = detect_sql_type(query)

    if sql_type == "SELECT":
        explanation += "-- Cette requête sélectionne des données de la base de données.\n"

        # Détecter les tables
        from_match = re.search(r'FROM\s+([a-zA-Z0-9_,\s]+)(?:\s+WHERE|\s+GROUP|\s+ORDER|\s+LIMIT|\s*$)', query, re.IGNORECASE)
        if from_match:
            tables = [table.strip() for table in from_match.group(1).split(',')]
            explanation += f"-- Tables utilisées: {', '.join(tables)}\n"

        # Détecter les conditions WHERE
        where_match = re.search(r'WHERE\s+(.+?)(?:\s+GROUP|\s+ORDER|\s+LIMIT|\s*$)', query, re.IGNORECASE | re.DOTALL)
        if where_match:
            explanation += f"-- Filtres appliqués: {where_match.group(1).strip()}\n"

        # Détecter GROUP BY
        group_match = re.search(r'GROUP\s+BY\s+(.+?)(?:\s+HAVING|\s+ORDER|\s+LIMIT|\s*$)', query, re.IGNORECASE | re.DOTALL)
        if group_match:
            explanation += f"-- Groupement par: {group_match.group(1).strip()}\n"

        # Détecter ORDER BY
        order_match = re.search(r'ORDER\s+BY\s+(.+?)(?:\s+LIMIT|\s*$)', query, re.IGNORECASE | re.DOTALL)
        if order_match:
            explanation += f"-- Tri par: {order_match.group(1).strip()}\n"

        # Détecter LIMIT
        limit_match = re.search(r'LIMIT\s+(\d+)', query, re.IGNORECASE)
        if limit_match:
            explanation += f"-- Limite de résultats: {limit_match.group(1)}\n"

    elif sql_type == "INSERT":
        explanation += "-- Cette requête insère de nouvelles données dans la base de données.\n"

        # Détecter la table
        table_match = re.search(r'INSERT\s+INTO\s+([a-zA-Z0-9_]+)', query, re.IGNORECASE)
        if table_match:
            explanation += f"-- Table cible: {table_match.group(1)}\n"

    elif sql_type == "UPDATE":
        explanation += "-- Cette requête met à jour des données existantes dans la base de données.\n"

        # Détecter la table
        table_match = re.search(r'UPDATE\s+([a-zA-Z0-9_]+)', query, re.IGNORECASE)
        if table_match:
            explanation += f"-- Table modifiée: {table_match.group(1)}\n"

        # Détecter les conditions WHERE
        where_match = re.search(r'WHERE\s+(.+?)(?:\s*$)', query, re.IGNORECASE | re.DOTALL)
        if where_match:
            explanation += f"-- Filtres appliqués: {where_match.group(1).strip()}\n"

    elif sql_type == "DELETE":
        explanation += "-- Cette requête supprime des données de la base de données.\n"

        # Détecter la table
        table_match = re.search(r'DELETE\s+FROM\s+([a-zA-Z0-9_]+)', query, re.IGNORECASE)
        if table_match:
            explanation += f"-- Table cible: {table_match.group(1)}\n"

        # Détecter les conditions WHERE
        where_match = re.search(r'WHERE\s+(.+?)(?:\s*$)', query, re.IGNORECASE | re.DOTALL)
        if where_match:
            explanation += f"-- Filtres appliqués: {where_match.group(1).strip()}\n"
        else:
            explanation += "-- ATTENTION: Cette requête supprime TOUTES les lignes de la table!\n"

    return explanation

# Fonction pour corriger une requête SQL
def correct_sql_query(query):
    """Corrige une requête SQL en utilisant un modèle pré-entraîné"""
    # Nettoyer la requête
    query = query.strip()

    # Initialiser les listes d'erreurs et de suggestions
    errors = []
    suggestions = []

    # Vérifier si la requête est vide
    if not query:
        errors.append("La requête est vide.")
        return {
            "original": query,
            "corrected_query": None,
            "errors": errors,
            "suggestions": suggestions
        }

    # Afficher la requête originale pour le débogage
    print(f"Requête à corriger: {query}")

    try:
        # Utiliser l'API HuggingFace
        result = query_huggingface_api(MODEL_PATHS["sql-correction"], f"correct: {query}")

        if result:
            # Extraire la requête SQL corrigée
            if isinstance(result, list) and len(result) > 0:
                if "generated_text" in result[0]:
                    corrected_query = result[0]["generated_text"]
                else:
                    corrected_query = result[0].get("text", query)
            else:
                corrected_query = str(result)
        else:
            # Fallback: utiliser sqlparse pour formater la requête
            try:
                corrected_query = sqlparse.format(query, reindent=True, keyword_case='upper')
            except:
                corrected_query = query
                errors.append("Impossible de corriger la requête automatiquement.")

        # Analyser les différences pour générer des erreurs et suggestions
        if corrected_query != query:
            # Comparer les requêtes pour détecter les erreurs
            errors, suggestions = analyze_query_differences(query, corrected_query)

        # Ajouter des suggestions générales
        add_general_suggestions(query, suggestions)

        return {
            "original": query,
            "corrected_query": corrected_query,
            "errors": errors,
            "suggestions": suggestions
        }

    except Exception as e:
        print(f"Erreur lors de la correction de la requête SQL: {str(e)}")
        errors.append(f"Erreur lors de la correction: {str(e)}")

        # Fallback: utiliser sqlparse pour formater la requête
        try:
            corrected_query = sqlparse.format(query, reindent=True, keyword_case='upper')
        except:
            corrected_query = query

        return {
            "original": query,
            "corrected_query": corrected_query,
            "errors": errors,
            "suggestions": suggestions
        }

# Fonction pour analyser les différences entre deux requêtes
def analyze_query_differences(original, corrected):
    """Analyse les différences entre la requête originale et corrigée pour générer des erreurs et suggestions"""
    errors = []
    suggestions = []

    # Convertir en minuscules pour la comparaison
    original_lower = original.lower()

    # Vérifier les mots-clés SQL courants
    sql_keywords = {
        "select": "SELECT",
        "from": "FROM",
        "where": "WHERE",
        "group by": "GROUP BY",
        "order by": "ORDER BY",
        "having": "HAVING",
        "join": "JOIN",
        "inner join": "INNER JOIN",
        "left join": "LEFT JOIN",
        "right join": "RIGHT JOIN",
        "full join": "FULL JOIN",
        "insert into": "INSERT INTO",
        "values": "VALUES",
        "update": "UPDATE",
        "set": "SET",
        "delete from": "DELETE FROM",
        "create table": "CREATE TABLE",
        "alter table": "ALTER TABLE",
        "drop table": "DROP TABLE"
    }

    for keyword_lower, keyword_upper in sql_keywords.items():
        # Vérifier si le mot-clé est mal orthographié dans l'original
        if keyword_lower not in original_lower and keyword_upper not in original:
            # Chercher des variantes proches
            for i in range(1, len(keyword_lower)):
                variant = keyword_lower[:i] + keyword_lower[i+1:]
                if variant in original_lower:
                    errors.append(f"Le mot-clé {keyword_upper} est mal orthographié.")
                    break

    # Vérifier les erreurs de syntaxe courantes
    if "select" in original_lower and "from" not in original_lower:
        errors.append("La requête SELECT doit avoir une clause FROM.")
        suggestions.append("Ajouter une clause FROM à la requête SELECT.")

    if "update" in original_lower and "set" not in original_lower:
        errors.append("La requête UPDATE doit avoir une clause SET.")
        suggestions.append("Ajouter une clause SET à la requête UPDATE.")

    if "insert into" in original_lower and "values" not in original_lower and "select" not in original_lower:
        errors.append("La requête INSERT INTO doit avoir une clause VALUES ou SELECT.")
        suggestions.append("Ajouter une clause VALUES ou SELECT à la requête INSERT INTO.")

    # Vérifier les parenthèses non équilibrées
    if original.count('(') != original.count(')'):
        errors.append("Les parenthèses ne sont pas équilibrées.")
        suggestions.append("Vérifier que chaque parenthèse ouvrante a une parenthèse fermante correspondante.")

    # Vérifier les guillemets non équilibrés
    single_quotes = original.count("'")
    if single_quotes % 2 != 0:
        errors.append("Les guillemets simples ne sont pas équilibrés.")
        suggestions.append("Vérifier que chaque guillemet simple ouvrant a un guillemet simple fermant correspondant.")

    double_quotes = original.count('"')
    if double_quotes % 2 != 0:
        errors.append("Les guillemets doubles ne sont pas équilibrés.")
        suggestions.append("Vérifier que chaque guillemet double ouvrant a un guillemet double fermant correspondant.")

    # Vérifier le point-virgule final
    if not original.rstrip().endswith(';') and corrected.rstrip().endswith(';'):
        suggestions.append("Ajouter un point-virgule à la fin de la requête.")

    return errors, suggestions

# Fonction pour ajouter des suggestions générales
def add_general_suggestions(query, suggestions):
    """Ajoute des suggestions générales pour améliorer la requête"""
    query_lower = query.lower()

    # Suggestions pour les requêtes SELECT
    if query_lower.startswith("select"):
        # Suggérer d'utiliser des alias pour les tables
        if "from" in query_lower and "as" not in query_lower:
            suggestions.append("Utiliser des alias pour les tables pour améliorer la lisibilité.")

        # Suggérer d'utiliser des jointures explicites
        if "from" in query_lower and "," in query_lower.split("from")[1].split("where")[0]:
            suggestions.append("Utiliser des jointures explicites (INNER JOIN, LEFT JOIN, etc.) au lieu des jointures implicites.")

        # Suggérer d'utiliser LIMIT pour limiter les résultats
        if "limit" not in query_lower:
            suggestions.append("Ajouter une clause LIMIT pour limiter le nombre de résultats retournés.")

    # Suggestions pour les requêtes UPDATE et DELETE
    if query_lower.startswith("update") or query_lower.startswith("delete"):
        # Suggérer d'ajouter une clause WHERE
        if "where" not in query_lower:
            suggestions.append("Ajouter une clause WHERE pour limiter les lignes affectées par l'opération.")

    # Suggestions pour les requêtes CREATE TABLE
    if "create table" in query_lower:
        # Suggérer d'ajouter des contraintes
        if "primary key" not in query_lower:
            suggestions.append("Ajouter une contrainte PRIMARY KEY pour identifier de manière unique chaque enregistrement.")

        if "foreign key" not in query_lower and "references" not in query_lower:
            suggestions.append("Envisager d'ajouter des contraintes FOREIGN KEY pour maintenir l'intégrité référentielle.")

# Fonction pour ajouter une requête à l'historique
def add_to_history(description, query, sql_type, advanced_options=None):
    """Ajoute une requête à l'historique des requêtes"""
    if 'query_history' not in session:
        session['query_history'] = []

    # Créer un nouvel enregistrement d'historique
    history_entry = {
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'description': description,
        'query': query,
        'type': sql_type,
        'advanced_options': advanced_options or {}
    }

    # Ajouter l'enregistrement à l'historique
    session['query_history'].insert(0, history_entry)  # Ajouter au début pour avoir les plus récents en premier

    # Limiter l'historique à 50 entrées
    if len(session['query_history']) > 50:
        session['query_history'] = session['query_history'][:50]

    # Sauvegarder la session
    session.modified = True

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

    # Traduire la description en anglais pour le débogage
    english_text = translate_fr_to_en(text)

    # Générer la requête SQL
    result, sql_type, advanced_options = generate_sql_query(text)

    # Ajouter la requête à l'historique
    add_to_history(text, result, sql_type, advanced_options)

    # Déterminer si des options avancées ont été détectées
    has_advanced_options = any(advanced_options.values()) if advanced_options else False

    return jsonify({
        'result': result,
        'detected_type': sql_type,
        'advanced_options': advanced_options,
        'has_advanced_options': has_advanced_options,
        'history': session.get('query_history', []),
        'original_text': text,
        'translated_text': english_text
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

    return jsonify(correction_result)

@app.route('/load_models', methods=['GET'])
def load_models_route():
    """Route pour charger les modèles pré-entraînés"""
    try:
        # Charger les modèles
        for model_type in MODEL_PATHS:
            load_model(model_type)

        return jsonify({
            'success': True,
            'models_loaded': list(models.keys()),
            'message': "Modèles chargés avec succès"
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': "Erreur lors du chargement des modèles"
        })

if __name__ == '__main__':
    print("Démarrage de l'application SQL Bot avec modèles pré-entraînés...")
    print("L'application utilisera l'API HuggingFace pour générer les requêtes SQL.")

    # Vérifier si une clé API HuggingFace est disponible
    if HUGGINGFACE_API_KEY:
        print("Clé API HuggingFace détectée.")
    else:
        print("Aucune clé API HuggingFace détectée. L'application utilisera l'API sans authentification.")
        print("Note: Sans clé API, les requêtes peuvent être limitées ou plus lentes.")

    app.run(debug=True)
