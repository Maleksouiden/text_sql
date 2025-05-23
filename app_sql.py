from flask import Flask, render_template, request, jsonify, session
import re
import random
import datetime
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Clé secrète pour les sessions

# Fonction pour détecter automatiquement le type de requête SQL
def detect_sql_type(description):
    """Détecte automatiquement le type de requête SQL à partir de la description"""
    description_lower = description.lower()

    # Mots-clés pour les requêtes SELECT
    select_keywords = ["sélectionner", "select", "afficher", "montrer", "lister", "obtenir", "récupérer", "chercher", "trouver"]

    # Mots-clés pour les requêtes INSERT
    insert_keywords = ["insérer", "insert", "ajouter", "créer une ligne", "créer un enregistrement"]

    # Mots-clés pour les requêtes UPDATE
    update_keywords = ["mettre à jour", "update", "modifier", "changer"]

    # Mots-clés pour les requêtes DELETE
    delete_keywords = ["supprimer", "delete", "effacer", "enlever", "retirer"]

    # Mots-clés pour les requêtes CREATE TABLE
    create_table_keywords = ["créer une table", "create table", "nouvelle table"]

    # Mots-clés pour les requêtes ALTER TABLE
    alter_table_keywords = ["modifier une table", "alter table", "changer une table", "ajouter une colonne", "supprimer une colonne"]

    # Mots-clés pour les requêtes DROP
    drop_keywords = ["supprimer une table", "drop table", "effacer une table", "supprimer une vue", "drop view"]

    # Vérifier les mots-clés dans la description
    for keyword in select_keywords:
        if keyword in description_lower:
            return "SELECT"

    for keyword in insert_keywords:
        if keyword in description_lower:
            return "INSERT"

    for keyword in update_keywords:
        if keyword in description_lower:
            return "UPDATE"

    for keyword in delete_keywords:
        if keyword in description_lower:
            return "DELETE"

    for keyword in create_table_keywords:
        if keyword in description_lower:
            return "CREATE_TABLE"

    for keyword in alter_table_keywords:
        if keyword in description_lower:
            return "ALTER_TABLE"

    for keyword in drop_keywords:
        if keyword in description_lower:
            return "DROP"

    # Par défaut, on suppose que c'est une requête SELECT
    return "SELECT"

# Fonction pour ajouter une requête à l'historique
def add_to_history(description, query, query_type):
    """Ajoute une requête à l'historique des requêtes"""
    if 'query_history' not in session:
        session['query_history'] = []

    # Créer un nouvel enregistrement d'historique
    history_entry = {
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'description': description,
        'query': query,
        'type': query_type
    }

    # Ajouter l'enregistrement à l'historique
    session['query_history'].insert(0, history_entry)  # Ajouter au début pour avoir les plus récents en premier

    # Limiter l'historique à 50 entrées
    if len(session['query_history']) > 50:
        session['query_history'] = session['query_history'][:50]

    # Sauvegarder la session
    session.modified = True

def generate_sql_query(description):
    """Génère une requête SQL SELECT basée sur une description en langage naturel"""
    # Extraction des informations clés de la description
    tables_pattern = r"tables?\s+(\w+(?:,\s*\w+)*)"
    champs_pattern = r"champs?\s+(\w+(?:,\s*\w+)*)"

    tables_match = re.search(tables_pattern, description, re.IGNORECASE)
    champs_match = re.search(champs_pattern, description, re.IGNORECASE)

    tables = tables_match.group(1).split(',') if tables_match else []
    champs = champs_match.group(1).split(',') if champs_match else []

    # Nettoyage des espaces
    tables = [t.strip() for t in tables]
    champs = [c.strip() for c in champs]

    # Génération avancée de requête SQL
    if not tables:
        return "Erreur: Aucune table spécifiée dans la description.\n\nExemple de format: 'Je veux une requête qui sélectionne les champs nom, prénom des tables utilisateurs où id > 100'\n\nPour des requêtes plus avancées, vous pouvez spécifier:\n- Des fonctions d'agrégation (COUNT, SUM, AVG, MAX, MIN)\n- Des groupements (GROUP BY)\n- Des sous-requêtes\n- Des jointures complexes\n- Des conditions avancées (HAVING, IN, EXISTS)"

    # Construction de la clause SELECT
    if not champs:
        select_clause = "SELECT *"
    else:
        # Vérifier si des fonctions d'agrégation sont demandées
        processed_champs = []
        for champ in champs:
            # Détecter si une fonction d'agrégation est demandée pour ce champ
            if "count" in description.lower() and champ in description.lower().split("count")[1][:20]:
                processed_champs.append(f"COUNT({champ})")
            elif "sum" in description.lower() and champ in description.lower().split("sum")[1][:20]:
                processed_champs.append(f"SUM({champ})")
            elif "avg" in description.lower() and champ in description.lower().split("avg")[1][:20]:
                processed_champs.append(f"AVG({champ})")
            elif "moyenne" in description.lower() and champ in description.lower().split("moyenne")[1][:20]:
                processed_champs.append(f"AVG({champ})")
            elif "max" in description.lower() and champ in description.lower().split("max")[1][:20]:
                processed_champs.append(f"MAX({champ})")
            elif "min" in description.lower() and champ in description.lower().split("min")[1][:20]:
                processed_champs.append(f"MIN({champ})")
            elif "total" in description.lower() and champ in description.lower().split("total")[1][:20]:
                processed_champs.append(f"SUM({champ})")
            else:
                processed_champs.append(champ)

        select_clause = f"SELECT {', '.join(processed_champs)}"

    # Construction de la clause FROM
    from_clause = f"FROM {tables[0]}"

    # Détection du type de jointure demandé
    join_type = "INNER JOIN"  # Par défaut
    if "left join" in description.lower() or "jointure externe gauche" in description.lower():
        join_type = "LEFT JOIN"
    elif "right join" in description.lower() or "jointure externe droite" in description.lower():
        join_type = "RIGHT JOIN"
    elif "full join" in description.lower() or "jointure complète" in description.lower():
        join_type = "FULL JOIN"

    # Ajout de jointures si plusieurs tables
    joins = ""
    if len(tables) > 1:
        for i in range(1, len(tables)):
            # Recherche d'une condition de jointure spécifique
            custom_join_condition = None

            for join_keyword in ["joindre", "join", "relier", "lier"]:
                if join_keyword in description.lower():
                    parts = description.lower().split(join_keyword)
                    if len(parts) > 1 and tables[i].lower() in parts[1]:
                        # Extraire la condition après le nom de la table
                        condition_text = parts[1].split(tables[i].lower())[1].strip()
                        # Chercher des mots clés comme "sur", "on", "avec", "using"
                        for cond_keyword in ["sur", "on", "avec", "using", "where", "où"]:
                            if cond_keyword in condition_text:
                                join_cond = condition_text.split(cond_keyword)[1].strip()
                                # Extraire jusqu'au prochain point ou fin de phrase
                                end_cond = join_cond.find('.')
                                if end_cond != -1:
                                    join_cond = join_cond[:end_cond]

                                # Nettoyer la condition
                                join_cond = join_cond.strip()
                                if join_cond:
                                    custom_join_condition = join_cond
                                    break

            # Si une condition personnalisée est trouvée, l'utiliser
            if custom_join_condition:
                joins += f"\n{join_type} {tables[i]} ON {custom_join_condition}"
            else:
                # Sinon, utiliser la jointure par défaut
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

                where_clause = f"\nWHERE {condition_text}"
                break

    # Recherche de GROUP BY
    group_by_clause = ""
    group_keywords = ["group by", "grouper par", "grouper", "regrouper"]

    for keyword in group_keywords:
        if keyword in description.lower():
            parts = description.lower().split(keyword)
            if len(parts) > 1:
                group_text = parts[1].strip()
                # Extraction du groupe jusqu'au prochain point ou fin de phrase
                end_group = group_text.find('.')
                if end_group != -1:
                    group_text = group_text[:end_group]

                # Recherche des champs de groupement
                group_fields = []
                for champ in champs:
                    if champ.lower() in group_text:
                        group_fields.append(champ)

                if group_fields:
                    group_by_clause = f"\nGROUP BY {', '.join(group_fields)}"
                    break

    # Recherche de HAVING
    having_clause = ""
    having_keywords = ["having", "ayant", "avec condition", "avec filtre"]

    for keyword in having_keywords:
        if keyword in description.lower():
            parts = description.lower().split(keyword)
            if len(parts) > 1:
                having_text = parts[1].strip()
                # Extraction de la condition jusqu'au prochain point ou fin de phrase
                end_having = having_text.find('.')
                if end_having != -1:
                    having_text = having_text[:end_having]

                having_clause = f"\nHAVING {having_text}"
                break

    # Recherche d'instructions de tri
    order_clause = ""
    order_keywords = ["trier", "ordonner", "ordre", "order by", "sort"]

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
                if "desc" in order_text.lower() or "décroissant" in order_text.lower():
                    direction = "DESC"
                else:
                    direction = "ASC"

                # Extraction du champ de tri
                order_field = None
                for champ in champs:
                    if champ.lower() in order_text:
                        order_field = champ
                        break

                if order_field:
                    order_clause = f"\nORDER BY {order_field} {direction}"
                elif champs:
                    # Si aucun champ spécifique n'est trouvé, utiliser le premier champ
                    order_clause = f"\nORDER BY {champs[0]} {direction}"

                break

    # Recherche de limite
    limit_clause = ""
    limit_keywords = ["limite", "limiter", "limit", "maximum", "max"]

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

    # Assemblage de la requête
    query = f"{select_clause}\n{from_clause}{joins}{where_clause}{group_by_clause}{having_clause}{order_clause}{limit_clause};"

    # Ajout d'une explication détaillée
    explanation = "\n\n-- Explication de la requête :\n"
    explanation += f"-- Cette requête sélectionne {'tous les champs (*)' if not champs else 'les champs: ' + ', '.join(champs)}\n"
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

    return query + explanation

@app.route('/')
def index():
    """Route principale pour afficher la page d'accueil"""
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    """Route pour traiter les requêtes de génération SQL"""
    data = request.json
    text = data.get('text', '')

    # Détecter automatiquement le type de requête SQL
    sql_type = detect_sql_type(text)

    # Récupérer les options avancées si présentes
    advanced_options = data.get('advancedOptions', {})

    # Générer la requête SQL en fonction du type détecté
    result = generate_sql_query(text)

    # Ajouter la requête à l'historique
    add_to_history(text, result, sql_type)

    return jsonify({
        'result': result,
        'detected_type': sql_type,
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

if __name__ == '__main__':
    app.run(debug=True)
