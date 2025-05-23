from flask import Flask, render_template, request, jsonify, session
import re
import datetime
import os
import json
import sqlparse
import requests
import html
import tempfile
import sqlite3
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'sql_bot_secret_key'  # Clé secrète pour les sessions

# Configuration pour l'upload de fichiers
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    # S'assurer que le dossier a les bonnes permissions
    try:
        os.chmod(UPLOAD_FOLDER, 0o755)  # Permissions rwxr-xr-x
    except Exception as e:
        print(f"Avertissement: Impossible de définir les permissions du dossier uploads: {str(e)}")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB max (augmenté)
ALLOWED_EXTENSIONS = {'sql', 'json', 'txt', 'csv'}  # Ajout de formats supplémentaires

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

# Modèles pré-entraînés
TRANSLATION_MODEL = "Helsinki-NLP/opus-mt-fr-en"
UNDERSTANDING_MODEL = "facebook/bart-large-mnli"  # Modèle pour la compréhension des intentions
REFORMULATION_MODEL = "facebook/bart-large-cnn"   # Modèle pour la reformulation des requêtes
SCHEMA_EXTRACTION_MODEL = "google/flan-t5-large"  # Modèle pour l'extraction de schéma
LANGUAGE_UNDERSTANDING_MODEL = "google/flan-t5-xl"  # Modèle pour la compréhension du langage naturel

# Fonction pour vérifier si un fichier a une extension autorisée
def allowed_file(filename):
    """Vérifie si le fichier a une extension autorisée"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Fonction pour analyser un fichier SQL et extraire le schéma
def extract_schema_from_sql_file(file_path):
    """Analyse un fichier SQL et extrait le schéma de la base de données"""
    try:
        # Lire le contenu du fichier SQL
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            sql_content = f.read()

        # Analyser le contenu SQL
        tables = {}
        relations = []

        # Méthode 1: Extraire les CREATE TABLE standards
        create_table_pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"\[]?(\w+)[`"\]]?\s*\((.*?)\);'
        create_table_matches = re.findall(create_table_pattern, sql_content, re.IGNORECASE | re.DOTALL)

        for table_name, table_content in create_table_matches:
            # Extraire les colonnes
            columns = []
            # Pattern plus flexible pour les définitions de colonnes
            column_pattern = r'[`"\[]?(\w+)[`"\]]?\s+([A-Za-z0-9_\(\)]+)'
            column_matches = re.findall(column_pattern, table_content)

            for column_name, _ in column_matches:  # Ignorer le type pour l'instant
                if column_name.lower() not in ['primary', 'foreign', 'key', 'constraint', 'check', 'unique', 'index']:
                    columns.append(column_name.lower())

            tables[table_name.lower()] = columns

            # Extraire les clés étrangères
            fk_pattern = r'FOREIGN\s+KEY\s*\(\s*[`"\[]?(\w+)[`"\]]?\s*\)\s*REFERENCES\s+[`"\[]?(\w+)[`"\]]?\s*\(\s*[`"\[]?(\w+)[`"\]]?\s*\)'
            fk_matches = re.findall(fk_pattern, table_content, re.IGNORECASE)

            for fk_column, ref_table, ref_column in fk_matches:
                relations.append({
                    'table1': table_name.lower(),
                    'column1': fk_column.lower(),
                    'table2': ref_table.lower(),
                    'column2': ref_column.lower()
                })

        # Méthode 2: Si aucune table n'est trouvée, essayer un autre pattern (format phpMyAdmin)
        if not tables:
            # Pattern pour les exports phpMyAdmin
            create_table_pattern2 = r'CREATE TABLE `(\w+)`\s*\(([\s\S]*?)\)\s*ENGINE'
            create_table_matches2 = re.findall(create_table_pattern2, sql_content)

            for table_name, table_content in create_table_matches2:
                columns = []
                # Pattern pour les colonnes dans les exports phpMyAdmin
                column_pattern2 = r'`(\w+)`\s+([^,\n]+)'
                column_matches2 = re.findall(column_pattern2, table_content)

                for column_name, _ in column_matches2:
                    columns.append(column_name.lower())

                tables[table_name.lower()] = columns

                # Extraire les clés étrangères
                fk_pattern2 = r'CONSTRAINT\s+`[^`]+`\s+FOREIGN\s+KEY\s*\(`(\w+)`\)\s*REFERENCES\s+`(\w+)`\s*\(`(\w+)`\)'
                fk_matches2 = re.findall(fk_pattern2, table_content, re.IGNORECASE)

                for fk_column, ref_table, ref_column in fk_matches2:
                    relations.append({
                        'table1': table_name.lower(),
                        'column1': fk_column.lower(),
                        'table2': ref_table.lower(),
                        'column2': ref_column.lower()
                    })

        # Méthode 3: Rechercher les noms de tables dans les commentaires ou autres parties du fichier
        if not tables:
            # Chercher des mentions de tables dans les commentaires
            table_mentions = re.findall(r'--\s*Table\s+structure\s+for\s+(?:table\s+)?[`"\']?(\w+)[`"\']?', sql_content, re.IGNORECASE)
            table_mentions += re.findall(r'--\s*Data\s+for\s+(?:table\s+)?[`"\']?(\w+)[`"\']?', sql_content, re.IGNORECASE)

            # Chercher des INSERT INTO qui peuvent révéler des noms de tables
            insert_mentions = re.findall(r'INSERT\s+INTO\s+[`"\']?(\w+)[`"\']?', sql_content, re.IGNORECASE)

            # Combiner et dédupliquer
            all_tables = set(table_mentions + insert_mentions)

            for table_name in all_tables:
                # Pour chaque table mentionnée, essayer de trouver les colonnes dans les INSERT
                columns = []
                insert_columns_pattern = r'INSERT\s+INTO\s+[`"\']?' + re.escape(table_name) + r'[`"\']?\s*\(([^)]+)\)'
                insert_columns_matches = re.findall(insert_columns_pattern, sql_content, re.IGNORECASE)

                for columns_str in insert_columns_matches:
                    # Extraire les noms de colonnes
                    col_names = re.findall(r'[`"\']?(\w+)[`"\']?', columns_str)
                    columns.extend([col.lower() for col in col_names])

                # Dédupliquer les colonnes
                columns = list(set(columns))

                # Si aucune colonne n'est trouvée, ajouter des colonnes par défaut
                if not columns:
                    columns = ['id', 'name']

                tables[table_name.lower()] = columns

        # Si toujours aucune table n'est trouvée, créer une table par défaut basée sur le nom du fichier
        if not tables:
            file_name = os.path.basename(file_path)
            table_name = os.path.splitext(file_name)[0].replace('-', '_').replace(' ', '_').lower()

            # Ajouter une table par défaut
            tables[table_name] = ['id', 'name', 'description', 'created_at']

            print(f"Aucune table trouvée dans le fichier SQL. Création d'une table par défaut: {table_name}")

        # Générer le schéma SQL
        schema_sql = ""
        for table, columns in tables.items():
            schema_sql += f"CREATE TABLE {table} (\n"

            # Ajouter les colonnes
            for i, column in enumerate(columns):
                # Déterminer le type de données en fonction du nom de la colonne
                if column.endswith("_id") or column == "id":
                    data_type = "INTEGER"
                elif column.endswith("_date") or column.endswith("_at") or column == "date":
                    data_type = "TIMESTAMP"
                elif column.endswith("_price") or column.endswith("_amount") or column.endswith("_cost"):
                    data_type = "DECIMAL(10, 2)"
                else:
                    data_type = "TEXT"

                primary_key = " PRIMARY KEY" if column == "id" else ""
                comma = "," if i < len(columns) - 1 else ""
                schema_sql += f"    {column} {data_type}{primary_key}{comma}\n"

            schema_sql += ");\n\n"

        # Ajouter les contraintes de clé étrangère
        for relation in relations:
            table1 = relation['table1']
            column1 = relation['column1']
            table2 = relation['table2']
            column2 = relation['column2']

            schema_sql += f"-- Relation: {table1}.{column1} = {table2}.{column2}\n"
            schema_sql += f"-- ALTER TABLE {table1} ADD FOREIGN KEY ({column1}) REFERENCES {table2}({column2});\n\n"

        return {
            'tables': tables,
            'relations': relations,
            'schema_sql': schema_sql
        }
    except Exception as e:
        print(f"Erreur lors de l'analyse du fichier SQL: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'tables': {},
            'relations': [],
            'schema_sql': "",
            'error': str(e)
        }

# Fonction pour analyser un fichier JSON et extraire le schéma
def extract_schema_from_json_file(file_path):
    """Analyse un fichier JSON et extrait le schéma de la base de données"""
    try:
        # Lire le contenu du fichier JSON
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            try:
                json_content = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Erreur de décodage JSON: {str(e)}")
                # Essayer de réparer le JSON
                f.seek(0)  # Retourner au début du fichier
                content = f.read()
                # Remplacer les caractères problématiques
                content = content.replace("'", '"').replace('\n', ' ').replace('\r', '')
                try:
                    json_content = json.loads(content)
                except:
                    # Si toujours pas possible, créer une structure par défaut
                    file_name = os.path.basename(file_path)
                    table_name = os.path.splitext(file_name)[0].replace('-', '_').replace(' ', '_').lower()
                    return create_default_schema(table_name)

        # Méthode 1: Vérifier si le JSON contient un schéma de base de données explicite
        if isinstance(json_content, dict) and 'tables' in json_content:
            # Format attendu: {"tables": {"table1": ["col1", "col2"], ...}, "relations": [{"table1": "t1", "column1": "c1", "table2": "t2", "column2": "c2"}, ...]}
            tables = json_content.get('tables', {})
            relations = json_content.get('relations', [])

            # Générer le schéma SQL
            schema_sql = ""
            for table, columns in tables.items():
                schema_sql += f"CREATE TABLE {table} (\n"

                # Ajouter les colonnes
                for i, column in enumerate(columns):
                    # Déterminer le type de données en fonction du nom de la colonne
                    if column.endswith("_id") or column == "id":
                        data_type = "INTEGER"
                    elif column.endswith("_date") or column.endswith("_at") or column == "date":
                        data_type = "TIMESTAMP"
                    elif column.endswith("_price") or column.endswith("_amount") or column.endswith("_cost"):
                        data_type = "DECIMAL(10, 2)"
                    else:
                        data_type = "TEXT"

                    primary_key = " PRIMARY KEY" if column == "id" else ""
                    comma = "," if i < len(columns) - 1 else ""
                    schema_sql += f"    {column} {data_type}{primary_key}{comma}\n"

                schema_sql += ");\n\n"

            # Ajouter les contraintes de clé étrangère
            for relation in relations:
                table1 = relation.get('table1', '')
                column1 = relation.get('column1', '')
                table2 = relation.get('table2', '')
                column2 = relation.get('column2', '')

                if table1 and column1 and table2 and column2:
                    schema_sql += f"-- Relation: {table1}.{column1} = {table2}.{column2}\n"
                    schema_sql += f"-- ALTER TABLE {table1} ADD FOREIGN KEY ({column1}) REFERENCES {table2}({column2});\n\n"

            return {
                'tables': tables,
                'relations': relations,
                'schema_sql': schema_sql
            }

        # Méthode 2: Analyser une liste d'objets (données)
        elif isinstance(json_content, list) and len(json_content) > 0:
            # Format attendu: liste d'objets représentant des données
            tables = {}

            # Analyser le premier objet pour déterminer la structure
            sample_object = json_content[0]

            if isinstance(sample_object, dict):
                # Créer une table pour ce type d'objet
                file_name = os.path.basename(file_path)
                table_name = os.path.splitext(file_name)[0].replace('-', '_').replace(' ', '_').lower()

                # Analyser tous les objets pour trouver toutes les colonnes possibles
                all_columns = set()
                column_types = {}

                for obj in json_content[:100]:  # Limiter à 100 objets pour l'analyse
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            all_columns.add(key)

                            # Déterminer le type de données
                            if key not in column_types:
                                if isinstance(value, int):
                                    column_types[key] = "INTEGER"
                                elif isinstance(value, float):
                                    column_types[key] = "REAL"
                                elif isinstance(value, bool):
                                    column_types[key] = "BOOLEAN"
                                elif isinstance(value, dict):
                                    column_types[key] = "JSON"
                                elif isinstance(value, list):
                                    column_types[key] = "JSON"
                                else:
                                    column_types[key] = "TEXT"

                # Convertir en liste et s'assurer que 'id' est en premier si présent
                columns = list(all_columns)
                if 'id' in columns:
                    columns.remove('id')
                    columns.insert(0, 'id')

                tables[table_name] = columns

                # Générer le schéma SQL
                schema_sql = f"CREATE TABLE {table_name} (\n"

                # Ajouter les colonnes
                for i, column in enumerate(columns):
                    # Utiliser le type détecté ou un type par défaut basé sur le nom
                    if column in column_types:
                        data_type = column_types[column]
                    elif column.endswith("_id") or column == "id":
                        data_type = "INTEGER"
                    elif column.endswith("_date") or column.endswith("_at") or column == "date":
                        data_type = "TIMESTAMP"
                    elif column.endswith("_price") or column.endswith("_amount") or column.endswith("_cost"):
                        data_type = "DECIMAL(10, 2)"
                    else:
                        data_type = "TEXT"

                    primary_key = " PRIMARY KEY" if column == "id" else ""
                    comma = "," if i < len(columns) - 1 else ""
                    schema_sql += f"    {column} {data_type}{primary_key}{comma}\n"

                schema_sql += ");\n\n"

                return {
                    'tables': tables,
                    'relations': [],
                    'schema_sql': schema_sql
                }

        # Méthode 3: Analyser un objet unique (peut-être une structure de base de données)
        elif isinstance(json_content, dict):
            # Essayer de détecter si c'est une structure de base de données
            tables = {}
            relations = []

            # Vérifier si les clés de premier niveau pourraient être des noms de tables
            for key, value in json_content.items():
                if isinstance(value, dict):
                    # Pourrait être une table avec des colonnes comme clés
                    columns = list(value.keys())
                    tables[key] = columns
                elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                    # Pourrait être une liste d'enregistrements
                    columns = set()
                    for item in value[:100]:  # Limiter à 100 items
                        if isinstance(item, dict):
                            columns.update(item.keys())
                    tables[key] = list(columns)

            # Si des tables ont été détectées, générer le schéma SQL
            if tables:
                schema_sql = ""
                for table, columns in tables.items():
                    schema_sql += f"CREATE TABLE {table} (\n"

                    # Ajouter les colonnes
                    for i, column in enumerate(columns):
                        # Déterminer le type de données en fonction du nom de la colonne
                        if column.endswith("_id") or column == "id":
                            data_type = "INTEGER"
                        elif column.endswith("_date") or column.endswith("_at") or column == "date":
                            data_type = "TIMESTAMP"
                        elif column.endswith("_price") or column.endswith("_amount") or column.endswith("_cost"):
                            data_type = "DECIMAL(10, 2)"
                        else:
                            data_type = "TEXT"

                        primary_key = " PRIMARY KEY" if column == "id" else ""
                        comma = "," if i < len(columns) - 1 else ""
                        schema_sql += f"    {column} {data_type}{primary_key}{comma}\n"

                    schema_sql += ");\n\n"

                # Essayer de détecter les relations
                for table, columns in tables.items():
                    for column in columns:
                        if column.endswith("_id") and column != "id":
                            # Essayer de deviner la table référencée
                            ref_table = column[:-3]  # Enlever "_id"
                            if ref_table in tables:
                                relations.append({
                                    'table1': table,
                                    'column1': column,
                                    'table2': ref_table,
                                    'column2': 'id'
                                })

                                schema_sql += f"-- Relation: {table}.{column} = {ref_table}.id\n"
                                schema_sql += f"-- ALTER TABLE {table} ADD FOREIGN KEY ({column}) REFERENCES {ref_table}(id);\n\n"

                return {
                    'tables': tables,
                    'relations': relations,
                    'schema_sql': schema_sql
                }

        # Si aucun format n'est reconnu, créer une structure par défaut
        file_name = os.path.basename(file_path)
        table_name = os.path.splitext(file_name)[0].replace('-', '_').replace(' ', '_').lower()
        return create_default_schema(table_name)

    except Exception as e:
        print(f"Erreur lors de l'analyse du fichier JSON: {str(e)}")
        import traceback
        traceback.print_exc()

        # Créer une structure par défaut en cas d'erreur
        file_name = os.path.basename(file_path)
        table_name = os.path.splitext(file_name)[0].replace('-', '_').replace(' ', '_').lower()
        return create_default_schema(table_name)

# Fonction pour créer un schéma par défaut
def create_default_schema(table_name):
    """Crée un schéma par défaut pour une table donnée"""
    tables = {table_name: ['id', 'name', 'description', 'created_at']}
    schema_sql = f"""CREATE TABLE {table_name} (
    id INTEGER PRIMARY KEY,
    name TEXT,
    description TEXT,
    created_at TIMESTAMP
);
"""

    print(f"Création d'un schéma par défaut pour la table: {table_name}")

    return {
        'tables': tables,
        'relations': [],
        'schema_sql': schema_sql
    }

# Fonction pour extraire le schéma de la base de données à partir du texte
def extract_schema_from_text(text):
    """Extrait les informations de schéma (tables, colonnes, relations) à partir du texte"""
    try:
        # Utiliser des expressions régulières pour détecter les mentions de tables et colonnes
        tables = {}
        relations = []

        # Détecter les mentions de tables
        table_pattern = r'(?:table|tableau|tables|tableaux)\s+(\w+)'
        table_matches = re.findall(table_pattern, text, re.IGNORECASE)

        # Détecter les mentions de colonnes avec leur table
        column_pattern = r'(\w+)\.(\w+)'
        column_matches = re.findall(column_pattern, text)

        # Détecter les relations entre tables
        relation_pattern = r'(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)'
        relation_matches = re.findall(relation_pattern, text)

        # Ajouter les tables détectées
        for table in table_matches:
            tables[table.lower()] = []

        # Ajouter les tables mentionnées dans les colonnes
        for table, column in column_matches:
            table = table.lower()
            column = column.lower()
            if table not in tables:
                tables[table] = []
            if column not in tables[table]:
                tables[table].append(column)

        # Ajouter les relations détectées
        for table1, column1, table2, column2 in relation_matches:
            relations.append({
                'table1': table1.lower(),
                'column1': column1.lower(),
                'table2': table2.lower(),
                'column2': column2.lower()
            })

            # S'assurer que les tables et colonnes sont ajoutées
            for table, column in [(table1.lower(), column1.lower()), (table2.lower(), column2.lower())]:
                if table not in tables:
                    tables[table] = []
                if column not in tables[table]:
                    tables[table].append(column)

        # Si aucune table n'a été détectée, essayer d'utiliser le modèle d'IA
        if not tables:
            # Préparer le prompt pour le modèle
            prompt = f"Extrait les tables, colonnes et relations de cette phrase: {text}\nFormat: Tables: [table1(colonne1, colonne2), table2(colonne1, colonne2)], Relations: [table1.colonne1=table2.colonne2]"

            # Appeler l'API HuggingFace
            result = query_huggingface_api(SCHEMA_EXTRACTION_MODEL, prompt)

            if result:
                # Traiter le résultat
                if isinstance(result, list) and len(result) > 0:
                    schema_text = result[0].get("generated_text", "")

                    # Extraire les tables et colonnes
                    tables_pattern = r'Tables:\s*\[(.*?)\]'
                    tables_match = re.search(tables_pattern, schema_text)
                    if tables_match:
                        tables_str = tables_match.group(1)
                        table_entries = re.findall(r'(\w+)\(([^)]+)\)', tables_str)
                        for table, columns_str in table_entries:
                            columns = [col.strip() for col in columns_str.split(',')]
                            tables[table.lower()] = [col.lower() for col in columns]

                    # Extraire les relations
                    relations_pattern = r'Relations:\s*\[(.*?)\]'
                    relations_match = re.search(relations_pattern, schema_text)
                    if relations_match:
                        relations_str = relations_match.group(1)
                        relation_entries = re.findall(r'(\w+)\.(\w+)=(\w+)\.(\w+)', relations_str)
                        for table1, column1, table2, column2 in relation_entries:
                            relations.append({
                                'table1': table1.lower(),
                                'column1': column1.lower(),
                                'table2': table2.lower(),
                                'column2': column2.lower()
                            })

        # Générer le schéma SQL
        schema_sql = ""
        for table, columns in tables.items():
            schema_sql += f"CREATE TABLE {table} (\n"

            # Ajouter un ID par défaut si aucune colonne n'est spécifiée
            if not columns:
                schema_sql += "    id INTEGER PRIMARY KEY,\n"
                schema_sql += "    name TEXT\n"
            else:
                for i, column in enumerate(columns):
                    # Déterminer le type de données en fonction du nom de la colonne
                    data_type = "INTEGER" if column.endswith("_id") or column == "id" else "TEXT"
                    primary_key = " PRIMARY KEY" if column == "id" else ""
                    comma = "," if i < len(columns) - 1 else ""
                    schema_sql += f"    {column} {data_type}{primary_key}{comma}\n"

            schema_sql += ");\n\n"

        # Ajouter les contraintes de clé étrangère
        for relation in relations:
            table1 = relation['table1']
            column1 = relation['column1']
            table2 = relation['table2']
            column2 = relation['column2']

            schema_sql += f"-- Relation: {table1}.{column1} = {table2}.{column2}\n"
            schema_sql += f"-- ALTER TABLE {table1} ADD FOREIGN KEY ({column1}) REFERENCES {table2}({column2});\n\n"

        return {
            'tables': tables,
            'relations': relations,
            'schema_sql': schema_sql
        }
    except Exception as e:
        print(f"Erreur lors de l'extraction du schéma: {str(e)}")
        return {
            'tables': {},
            'relations': [],
            'schema_sql': ""
        }

# Fonction pour comprendre le langage naturel et extraire les intentions
def understand_natural_language(text, schema_info=None):
    """Comprend le langage naturel et extrait les intentions précises"""
    try:
        # Préparer le prompt pour le modèle
        prompt = f"Comprends cette requête et reformule-la en langage SQL clair: {text}"

        # Ajouter les informations de schéma si disponibles
        if schema_info and schema_info['tables']:
            prompt += "\n\nSchéma de la base de données:"
            for table, columns in schema_info['tables'].items():
                prompt += f"\nTable {table}: "
                if columns:
                    prompt += ", ".join(columns)
                else:
                    prompt += "id, name"

            if schema_info['relations']:
                prompt += "\n\nRelations:"
                for relation in schema_info['relations']:
                    prompt += f"\n{relation['table1']}.{relation['column1']} = {relation['table2']}.{relation['column2']}"

        # Ajouter des instructions spécifiques
        prompt += "\n\nReformule cette requête en langage SQL clair, en précisant les tables et colonnes à utiliser, les conditions de jointure, les filtres, etc."

        # Appeler l'API HuggingFace
        result = query_huggingface_api(LANGUAGE_UNDERSTANDING_MODEL, prompt)

        if result:
            # Extraire le texte reformulé
            if isinstance(result, list) and len(result) > 0:
                if "generated_text" in result[0]:
                    reformulated = result[0]["generated_text"]
                    print(f"Requête reformulée par le modèle de langage: {reformulated}")
                    return reformulated

        # En cas d'échec, retourner le texte original
        return text
    except Exception as e:
        print(f"Erreur lors de la compréhension du langage naturel: {str(e)}")
        return text

# Fonction pour comprendre et reformuler les requêtes utilisateur
def understand_user_intent(text):
    """Analyse et reformule la requête utilisateur pour mieux comprendre ses intentions"""
    try:
        # Étape 1: Extraire les informations de schéma du texte
        schema_info = extract_schema_from_text(text)
        print(f"Schéma extrait: {len(schema_info['tables'])} tables, {len(schema_info['relations'])} relations")

        # Étape 2: Utiliser le modèle de compréhension du langage naturel avec le schéma
        nl_understood_text = understand_natural_language(text, schema_info)
        print(f"Texte compris par le modèle de langage: {nl_understood_text}")

        # Étape 3: Utiliser le modèle de compréhension des intentions
        # Nous envoyons la requête avec des hypothèses pour voir laquelle correspond le mieux
        hypotheses = [
            "Cette requête concerne la sélection de données.",
            "Cette requête concerne l'insertion de données.",
            "Cette requête concerne la mise à jour de données.",
            "Cette requête concerne la suppression de données.",
            "Cette requête concerne la création de structures de données.",
            "Cette requête concerne la modification de structures de données.",
            "Cette requête concerne la suppression de structures de données.",
            "Cette requête concerne l'agrégation de données.",
            "Cette requête concerne le filtrage de données.",
            "Cette requête concerne le tri de données.",
            "Cette requête concerne la jointure de tables.",
            "Cette requête concerne des statistiques sur les données."
        ]

        # Préparer les paires pour le modèle NLI (Natural Language Inference)
        pairs = []
        for hypothesis in hypotheses:
            pairs.append({"text": nl_understood_text, "hypothesis": hypothesis})

        # Appeler l'API HuggingFace pour la classification
        result = query_huggingface_api(UNDERSTANDING_MODEL, pairs)

        # Analyser les résultats pour déterminer l'intention principale
        if result:
            # Trouver l'hypothèse avec le score d'entailment le plus élevé
            best_match = None
            best_score = -1

            for i, item in enumerate(result):
                if isinstance(item, dict) and "entailment" in item:
                    entailment_score = item["entailment"]
                    if entailment_score > best_score:
                        best_score = entailment_score
                        best_match = hypotheses[i]

            if best_match:
                print(f"Intention détectée: {best_match} (score: {best_score})")

                # Étape 4: Reformuler la requête en fonction de l'intention détectée et du schéma
                reformulated_text = reformulate_query_with_schema(nl_understood_text, best_match, schema_info)
                return reformulated_text

        # Si aucune intention claire n'est détectée, utiliser directement le texte compris par le modèle de langage
        return nl_understood_text
    except Exception as e:
        print(f"Erreur lors de l'analyse des intentions: {str(e)}")
        return text

# Fonction pour reformuler la requête en fonction de l'intention détectée et du schéma
def reformulate_query_with_schema(text, intention, schema_info):
    """Reformule la requête en fonction de l'intention détectée et du schéma de la base de données"""
    try:
        # Préparer l'entrée pour le modèle de reformulation
        prompt = f"Intention: {intention}\nRequête originale: {text}\n"

        # Ajouter les informations de schéma
        if schema_info and schema_info['tables']:
            prompt += "\nSchéma de la base de données:\n"
            for table, columns in schema_info['tables'].items():
                prompt += f"Table {table}: "
                if columns:
                    prompt += ", ".join(columns)
                else:
                    prompt += "id, name"
                prompt += "\n"

            if schema_info['relations']:
                prompt += "\nRelations:\n"
                for relation in schema_info['relations']:
                    prompt += f"{relation['table1']}.{relation['column1']} = {relation['table2']}.{relation['column2']}\n"

        prompt += "\nReformulation claire et précise pour générer une requête SQL avec les tables et colonnes spécifiées:"

        # Appeler l'API HuggingFace pour la reformulation
        result = query_huggingface_api(REFORMULATION_MODEL, prompt)

        if result:
            # Extraire le texte reformulé
            if isinstance(result, list) and len(result) > 0:
                if "summary_text" in result[0]:
                    reformulated = result[0]["summary_text"]
                    print(f"Requête reformulée avec schéma: {reformulated}")
                    return reformulated
                elif "generated_text" in result[0]:
                    reformulated = result[0]["generated_text"]
                    print(f"Requête reformulée avec schéma: {reformulated}")
                    return reformulated

        # En cas d'échec, utiliser la méthode de reformulation standard
        return reformulate_query(text, intention)
    except Exception as e:
        print(f"Erreur lors de la reformulation avec schéma: {str(e)}")
        # En cas d'erreur, utiliser la méthode de reformulation standard
        return reformulate_query(text, intention)

# Fonction pour reformuler la requête en fonction de l'intention détectée
def reformulate_query(text, intention):
    """Reformule la requête en fonction de l'intention détectée"""
    try:
        # Préparer l'entrée pour le modèle de reformulation
        prompt = f"Intention: {intention}\nRequête originale: {text}\nReformulation claire et précise pour générer une requête SQL:"

        # Appeler l'API HuggingFace pour la reformulation
        result = query_huggingface_api(REFORMULATION_MODEL, prompt)

        if result:
            # Extraire le texte reformulé
            if isinstance(result, list) and len(result) > 0:
                if "summary_text" in result[0]:
                    reformulated = result[0]["summary_text"]
                    print(f"Requête reformulée: {reformulated}")
                    return reformulated
                elif "generated_text" in result[0]:
                    reformulated = result[0]["generated_text"]
                    print(f"Requête reformulée: {reformulated}")
                    return reformulated

        # En cas d'échec, enrichir la requête avec des mots-clés basés sur l'intention
        keywords = {
            "sélection": ["sélectionner", "afficher", "montrer", "lister", "obtenir"],
            "insertion": ["insérer", "ajouter", "créer une entrée"],
            "mise à jour": ["mettre à jour", "modifier", "changer"],
            "suppression": ["supprimer", "effacer", "enlever"],
            "création": ["créer", "définir", "établir"],
            "agrégation": ["compter", "somme", "moyenne", "minimum", "maximum", "grouper"],
            "filtrage": ["où", "condition", "filtre", "limiter à"],
            "tri": ["trier", "ordonner", "classer"],
            "jointure": ["joindre", "combiner", "relier"]
        }

        # Identifier les mots-clés pertinents en fonction de l'intention
        relevant_keywords = []
        for key, words in keywords.items():
            if key.lower() in intention.lower():
                relevant_keywords.extend(words)

        # Si des mots-clés pertinents sont trouvés, les ajouter à la requête
        if relevant_keywords:
            # Vérifier si ces mots-clés sont déjà présents dans la requête
            missing_keywords = [kw for kw in relevant_keywords if kw.lower() not in text.lower()]

            if missing_keywords:
                # Ajouter les mots-clés manquants à la requête
                enhanced_text = f"{text} (Intention: {', '.join(missing_keywords[:2])})"
                return enhanced_text

        # Si aucune reformulation n'est possible, retourner le texte original
        return text
    except Exception as e:
        print(f"Erreur lors de la reformulation: {str(e)}")
        return text

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
    # Vérifier si un schéma personnalisé est disponible en session
    custom_schema = session.get('custom_schema', None)

    # Extraire le schéma de la base de données à partir du texte
    extracted_schema_info = extract_schema_from_text(description)

    # Déterminer quel schéma utiliser (priorité: schéma personnalisé > schéma extrait > schéma par défaut)
    if custom_schema and custom_schema.get('schema_sql'):
        schema = custom_schema['schema_sql']
        print(f"Utilisation du schéma personnalisé importé: {len(custom_schema['tables'])} tables")
        # Fusionner les relations extraites du texte avec le schéma personnalisé
        if extracted_schema_info['relations']:
            for relation in extracted_schema_info['relations']:
                if relation not in custom_schema['relations']:
                    custom_schema['relations'].append(relation)
            print(f"Ajout de {len(extracted_schema_info['relations'])} relations extraites du texte")
    elif extracted_schema_info['schema_sql']:
        schema = extracted_schema_info['schema_sql']
        print(f"Utilisation du schéma extrait du texte: {len(extracted_schema_info['tables'])} tables")
    else:
        # Schéma par défaut
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
        print("Utilisation du schéma par défaut")

    # Analyser et reformuler la requête pour mieux comprendre les intentions
    understood_description = understand_user_intent(description)
    print(f"Description originale: {description}")
    print(f"Description analysée: {understood_description}")

    # Traduire la description reformulée en anglais
    english_description = translate_fr_to_en(understood_description)
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

    # Extraire le schéma de la base de données à partir du texte
    schema_info = extract_schema_from_text(text)

    # Analyser et reformuler la requête pour mieux comprendre les intentions
    understood_text = understand_user_intent(text)

    # Traduire la description en anglais pour le débogage
    english_text = translate_fr_to_en(understood_text)

    # Générer la requête SQL
    result, sql_type, advanced_options = generate_sql_query(text)

    # Ajouter la requête à l'historique
    add_to_history(text, result, sql_type, advanced_options)

    # Déterminer si des options avancées ont été détectées
    has_advanced_options = any(advanced_options.values()) if advanced_options else False

    # Préparer les informations de schéma pour l'affichage
    schema_display = {
        'tables': list(schema_info['tables'].keys()),
        'columns': {table: columns for table, columns in schema_info['tables'].items()},
        'relations': [f"{r['table1']}.{r['column1']} = {r['table2']}.{r['column2']}" for r in schema_info['relations']]
    }

    return jsonify({
        'result': result,
        'detected_type': sql_type,
        'advanced_options': advanced_options,
        'has_advanced_options': has_advanced_options,
        'history': session.get('query_history', []),
        'original_text': text,
        'understood_text': understood_text,
        'translated_text': english_text,
        'schema_info': schema_display,
        'has_schema': len(schema_info['tables']) > 0
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

@app.route('/upload_schema', methods=['POST'])
def upload_schema():
    """Route pour uploader un fichier de schéma (SQL ou JSON)"""
    try:
        # Vérifier si un fichier a été envoyé
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'Aucun fichier envoyé',
                'message': 'Veuillez sélectionner un fichier à uploader'
            })

        file = request.files['file']

        # Vérifier si un fichier a été sélectionné
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'Aucun fichier sélectionné',
                'message': 'Veuillez sélectionner un fichier à uploader'
            })

        # Vérifier si le fichier a une extension autorisée
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': 'Extension de fichier non autorisée',
                'message': f'Les extensions autorisées sont: {", ".join(ALLOWED_EXTENSIONS)}'
            })

        # Créer le dossier d'upload s'il n'existe pas
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            try:
                os.makedirs(app.config['UPLOAD_FOLDER'])
                os.chmod(app.config['UPLOAD_FOLDER'], 0o755)  # Permissions rwxr-xr-x
            except Exception as e:
                print(f"Erreur lors de la création du dossier uploads: {str(e)}")
                # Continuer malgré l'erreur

        # Sauvegarder le fichier
        try:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Vérifier que le fichier a bien été sauvegardé
            if not os.path.exists(file_path):
                return jsonify({
                    'success': False,
                    'error': 'Erreur de sauvegarde',
                    'message': 'Le fichier n\'a pas pu être sauvegardé sur le serveur'
                })
        except Exception as e:
            print(f"Erreur lors de la sauvegarde du fichier: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': 'Erreur de sauvegarde',
                'message': f'Erreur lors de la sauvegarde du fichier: {str(e)}'
            })

        # Extraire le schéma selon le type de fichier
        schema_info = None
        try:
            if filename.lower().endswith('.sql'):
                schema_info = extract_schema_from_sql_file(file_path)
            elif filename.lower().endswith('.json'):
                schema_info = extract_schema_from_json_file(file_path)
            elif filename.lower().endswith('.txt') or filename.lower().endswith('.csv'):
                # Pour les fichiers texte, essayer d'abord comme SQL puis comme JSON
                schema_info = extract_schema_from_sql_file(file_path)
                if not schema_info or not schema_info.get('tables'):
                    schema_info = extract_schema_from_json_file(file_path)
            else:
                # Essayer de deviner le format en fonction du contenu
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read(1000)  # Lire les 1000 premiers caractères
                    if 'CREATE TABLE' in content or 'INSERT INTO' in content:
                        schema_info = extract_schema_from_sql_file(file_path)
                    elif '{' in content or '[' in content:
                        schema_info = extract_schema_from_json_file(file_path)
                    else:
                        # Format non reconnu, créer un schéma par défaut
                        table_name = os.path.splitext(filename)[0].replace('-', '_').replace(' ', '_').lower()
                        schema_info = create_default_schema(table_name)
        except Exception as e:
            print(f"Erreur lors de l'extraction du schéma: {str(e)}")
            import traceback
            traceback.print_exc()

            # Créer un schéma par défaut en cas d'erreur
            table_name = os.path.splitext(filename)[0].replace('-', '_').replace(' ', '_').lower()
            schema_info = create_default_schema(table_name)

        # Vérifier si le schéma a été extrait avec succès
        if not schema_info or not schema_info.get('tables'):
            # Créer un schéma par défaut
            table_name = os.path.splitext(filename)[0].replace('-', '_').replace(' ', '_').lower()
            schema_info = create_default_schema(table_name)

        # Stocker le schéma en session
        try:
            session['custom_schema'] = schema_info
            session.modified = True
        except Exception as e:
            print(f"Erreur lors du stockage du schéma en session: {str(e)}")
            # Continuer malgré l'erreur

        # Préparer les informations de schéma pour l'affichage
        schema_display = {
            'tables': list(schema_info['tables'].keys()),
            'columns': {table: columns for table, columns in schema_info['tables'].items()},
            'relations': [f"{r['table1']}.{r['column1']} = {r['table2']}.{r['column2']}" for r in schema_info['relations']]
        }

        return jsonify({
            'success': True,
            'message': 'Schéma importé avec succès',
            'schema_info': schema_display,
            'has_schema': True
        })
    except Exception as e:
        print(f"Erreur globale lors de l'upload du fichier: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'message': f'Erreur lors de l\'upload du fichier: {str(e)}'
        })

@app.route('/get_custom_schema', methods=['GET'])
def get_custom_schema():
    """Route pour récupérer le schéma personnalisé stocké en session"""
    schema_info = session.get('custom_schema', {})

    if not schema_info or not schema_info.get('tables'):
        return jsonify({
            'success': False,
            'error': 'Aucun schéma personnalisé',
            'message': 'Aucun schéma personnalisé n\'a été importé'
        })

    # Préparer les informations de schéma pour l'affichage
    schema_display = {
        'tables': list(schema_info['tables'].keys()),
        'columns': {table: columns for table, columns in schema_info['tables'].items()},
        'relations': [f"{r['table1']}.{r['column1']} = {r['table2']}.{r['column2']}" for r in schema_info['relations']]
    }

    return jsonify({
        'success': True,
        'schema_info': schema_display,
        'has_schema': True
    })

@app.route('/clear_custom_schema', methods=['POST'])
def clear_custom_schema():
    """Route pour effacer le schéma personnalisé stocké en session"""
    if 'custom_schema' in session:
        del session['custom_schema']
        session.modified = True

    return jsonify({
        'success': True,
        'message': 'Schéma personnalisé effacé avec succès'
    })

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
