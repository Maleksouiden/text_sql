from flask import Flask, render_template, request, jsonify
import re
import nltk

app = Flask(__name__)

# Téléchargement des ressources NLTK nécessaires (si elles ne sont pas déjà téléchargées)
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

# Dictionnaire de corrections françaises courantes
french_corrections = {
    "a": "à",
    "ou": "où",
    "la": "là",
    "ca": "ça",
    "voila": "voilà",
    "tres": "très",
    "etre": "être",
    "meme": "même",
    "deja": "déjà",
    "apres": "après",
    "plutot": "plutôt",
    "grace": "grâce",
    "francais": "français",
    "different": "différent",
    "etait": "était",
    "cest": "c'est",
    "sil": "s'il",
    "quil": "qu'il",
    "jusqua": "jusqu'à",
    "na": "n'a",
    "ny": "n'y",
    "nest": "n'est",
    "daccord": "d'accord",
    "lorsquil": "lorsqu'il",
    "puisquil": "puisqu'il",
    "parceque": "parce que",
    "peut etre": "peut-être",
    "aujourdhui": "aujourd'hui"
}

def generate_sql_query(description):
    """Génère une requête SQL avancée basée sur une description en langage naturel"""
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

    # Liste des fonctions d'agrégation pour référence dans les commentaires
    # ["count", "sum", "avg", "max", "min", "moyenne", "total", "somme", "maximum", "minimum"]

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

    # Ajout d'exemples de données fictives pour aider à la visualisation
    explanation += "\n-- Exemple de résultats possibles :\n"
    explanation += "-- -----------------------------\n"

    # Générer des exemples de données en fonction des champs sélectionnés
    if champs:
        # En-tête
        header = "-- | " + " | ".join(champs) + " |"
        explanation += header + "\n"
        explanation += "-- | " + " | ".join(["-" * len(champ) for champ in champs]) + " |\n"

        # Données d'exemple (3 lignes)
        sample_data = {
            "id": [1, 2, 3],
            "nom": ["Dupont", "Martin", "Durand"],
            "prenom": ["Jean", "Marie", "Pierre"],
            "email": ["jean.dupont@example.com", "marie.martin@example.com", "pierre.durand@example.com"],
            "date": ["2023-01-15", "2023-02-20", "2023-03-10"],
            "montant": [1250.50, 980.75, 1500.00],
            "quantite": [5, 3, 7],
            "categorie": ["A", "B", "A"],
            "statut": ["Actif", "Inactif", "Actif"]
        }

        for i in range(3):
            row = []
            for champ in champs:
                champ_lower = champ.lower().replace("(", "").replace(")", "")
                # Extraire le nom du champ sans fonction d'agrégation
                base_field = champ_lower
                for func in ["count", "sum", "avg", "max", "min"]:
                    if func in champ_lower:
                        parts = champ_lower.split(func)
                        if len(parts) > 1:
                            base_field = parts[1].strip("() ")

                # Trouver une valeur d'exemple pour ce champ
                for key in sample_data:
                    if key in base_field or base_field in key:
                        row.append(str(sample_data[key][i]))
                        break
                else:
                    # Si aucune correspondance n'est trouvée, utiliser une valeur générique
                    if "count" in champ_lower:
                        row.append(str(10 + i))
                    elif "sum" in champ_lower or "total" in champ_lower:
                        row.append(str(1000 + i * 500))
                    elif "avg" in champ_lower or "moyenne" in champ_lower:
                        row.append(str(100 + i * 25))
                    elif "max" in champ_lower:
                        row.append(str(200 + i * 50))
                    elif "min" in champ_lower:
                        row.append(str(50 + i * 10))
                    else:
                        row.append(f"Valeur{i+1}")

            explanation += "-- | " + " | ".join(row) + " |\n"

    return query + explanation

def correct_french_text(text):
    """Corrige et améliore un texte en français de manière professionnelle"""
    if not text:
        return "Veuillez fournir un texte à corriger."

    # Dictionnaire étendu de corrections françaises
    extended_corrections = {
        # Accents manquants
        "a": "à",
        "ou": "où",
        "la": "là",
        "ca": "ça",
        "voila": "voilà",
        "tres": "très",
        "etre": "être",
        "meme": "même",
        "deja": "déjà",
        "apres": "après",
        "plutot": "plutôt",
        "grace": "grâce",
        "francais": "français",
        "different": "différent",
        "etait": "était",
        "theatre": "théâtre",
        "hotel": "hôtel",
        "foret": "forêt",
        "hopital": "hôpital",
        "etude": "étude",
        "ecole": "école",
        "eleve": "élève",
        "etat": "État",
        "evenement": "événement",
        "etrange": "étrange",
        "etranger": "étranger",
        "etrangere": "étrangère",
        "education": "éducation",
        "economie": "économie",
        "economique": "économique",
        "episode": "épisode",
        "equipe": "équipe",
        "equipement": "équipement",

        # Apostrophes manquantes
        "cest": "c'est",
        "sil": "s'il",
        "quil": "qu'il",
        "quelle": "qu'elle",
        "jusqua": "jusqu'à",
        "na": "n'a",
        "ny": "n'y",
        "nest": "n'est",
        "daccord": "d'accord",
        "lorsquil": "lorsqu'il",
        "puisquil": "puisqu'il",
        "quils": "qu'ils",
        "quelles": "qu'elles",
        "lorsquon": "lorsqu'on",
        "puisquon": "puisqu'on",
        "presquil": "presqu'il",
        "presquelle": "presqu'elle",
        "presquils": "presqu'ils",
        "presquelles": "presqu'elles",
        "jusquen": "jusqu'en",
        "jusquau": "jusqu'au",
        "jusquaux": "jusqu'aux",
        "dautre": "d'autre",
        "dautres": "d'autres",
        "lun": "l'un",
        "lune": "l'une",
        "lautre": "l'autre",
        "lorsque": "lorsqu'",
        "puisque": "puisqu'",

        # Espaces et tirets
        "parceque": "parce que",
        "peut etre": "peut-être",
        "aujourdhui": "aujourd'hui",
        "cest a dire": "c'est-à-dire",
        "vis a vis": "vis-à-vis",
        "rendez vous": "rendez-vous",
        "tout a fait": "tout à fait",
        "a peu pres": "à peu près",
        "a propos": "à propos",
        "a cote": "à côté",
        "a cause": "à cause",
        "a travers": "à travers",
        "a partir": "à partir",
        "a condition": "à condition",
        "a moins": "à moins",
        "a peine": "à peine",

        # Confusions courantes
        "sa": "ça",  # Contexte spécifique, à utiliser avec précaution
        "ses": "ces",  # Contexte spécifique, à utiliser avec précaution
        "ces": "ses",  # Contexte spécifique, à utiliser avec précaution
        "et": "est",  # Contexte spécifique, à utiliser avec précaution
        "est": "et",  # Contexte spécifique, à utiliser avec précaution
        "son": "sont",  # Contexte spécifique, à utiliser avec précaution
        "sont": "son",  # Contexte spécifique, à utiliser avec précaution
        "peu": "peut",  # Contexte spécifique, à utiliser avec précaution
        "peut": "peu",  # Contexte spécifique, à utiliser avec précaution
        "mais": "mes",  # Contexte spécifique, à utiliser avec précaution
        "mes": "mais",  # Contexte spécifique, à utiliser avec précaution
        "ce": "se",  # Contexte spécifique, à utiliser avec précaution
        "se": "ce",  # Contexte spécifique, à utiliser avec précaution

        # Erreurs de pluriel/singulier
        "tout les": "tous les",
        "toute les": "toutes les",
        "tout le monde": "tous le monde",
        "tout ces": "tous ces",
        "toute ces": "toutes ces",
    }

    # Fusionner les dictionnaires de correction
    all_corrections = {**french_corrections, **extended_corrections}

    # Tokenisation du texte
    words = nltk.word_tokenize(text, language='french')

    # Correction des mots
    corrected_words = []
    corrections_made = []

    for word in words:
        word_lower = word.lower()
        if word_lower in all_corrections:
            # Préserver la casse si le mot original commence par une majuscule
            if word[0].isupper():
                corrected = all_corrections[word_lower].capitalize()
            else:
                corrected = all_corrections[word_lower]

            # Enregistrer la correction si elle est différente du mot original
            if corrected.lower() != word_lower:
                corrections_made.append((word, corrected))

            corrected_words.append(corrected)
        else:
            corrected_words.append(word)

    # Reconstruction du texte avec gestion avancée de la ponctuation française
    corrected_text = ""
    i = 0
    while i < len(corrected_words):
        word = corrected_words[i]

        # Gestion spécifique de la ponctuation française
        if word in [':', ';', '!', '?']:
            # Espace insécable avant ces signes de ponctuation en français
            corrected_text = corrected_text.rstrip() + ' ' + word + ' '
        elif word in ['.', ',']:
            # Pas d'espace avant, espace après
            corrected_text = corrected_text.rstrip() + word + ' '
        elif word in ['(', '[', '{', '«']:
            # Espace avant, pas d'espace après
            corrected_text = corrected_text.rstrip() + ' ' + word
        elif word in [')', ']', '}', '»']:
            # Pas d'espace avant, espace après
            corrected_text = corrected_text.rstrip() + word + ' '
        elif word == "'":
            # Apostrophe: pas d'espace avant ni après
            corrected_text = corrected_text.rstrip() + word
        elif i > 0 and corrected_words[i-1] in ['(', '[', '{', '«', "'"]:
            # Pas d'espace après une parenthèse ouvrante
            corrected_text += word
        else:
            # Cas général: ajouter un espace après le mot
            corrected_text += word + ' '

        i += 1

    # Corrections supplémentaires
    corrected_text = corrected_text.strip()

    # Correction des espaces multiples
    corrected_text = re.sub(r'\s+', ' ', corrected_text)

    # Correction des espaces avant/après la ponctuation française
    corrected_text = re.sub(r'\s+([.,])', r'\1', corrected_text)  # Pas d'espace avant la ponctuation simple
    corrected_text = re.sub(r'\s+([;:!?])', r' \1', corrected_text)  # Espace insécable avant la ponctuation double
    corrected_text = re.sub(r'([.,;:!?])([^\s])', r'\1 \2', corrected_text)  # Espace après la ponctuation

    # Correction des guillemets français
    corrected_text = re.sub(r'"([^"]*)"', r'« \1 »', corrected_text)

    # Correction des apostrophes
    corrected_text = re.sub(r'\s\'', r'\'', corrected_text)

    # Correction des majuscules en début de phrase
    corrected_text = re.sub(r'(^|[.!?]\s+)([a-zàáâäæçèéêëìíîïòóôöœùúûüÿ])', lambda m: m.group(1) + m.group(2).upper(), corrected_text)

    # Correction des espaces avant/après les parenthèses et crochets
    corrected_text = re.sub(r'\s+\)', r')', corrected_text)
    corrected_text = re.sub(r'\(\s+', r'(', corrected_text)
    corrected_text = re.sub(r'\s+\]', r']', corrected_text)
    corrected_text = re.sub(r'\[\s+', r'[', corrected_text)

    # Correction des tirets pour les dialogues
    corrected_text = re.sub(r'- ', r'— ', corrected_text)

    # Ajout d'une explication détaillée des corrections
    if corrections_made:
        explanation = "\n\n--- Corrections effectuées ---\n"

        # Regrouper les corrections par type
        correction_types = {
            "Accents manquants": [],
            "Apostrophes manquantes": [],
            "Espaces et tirets": [],
            "Confusions courantes": [],
            "Autres corrections": []
        }

        for original, corrected in corrections_made:
            if any(c in "àáâäæçèéêëìíîïòóôöœùúûüÿ" for c in corrected) and not any(c in "àáâäæçèéêëìíîïòóôöœùúûüÿ" for c in original):
                correction_types["Accents manquants"].append(f"'{original}' → '{corrected}'")
            elif "'" in corrected and "'" not in original:
                correction_types["Apostrophes manquantes"].append(f"'{original}' → '{corrected}'")
            elif ("-" in corrected and "-" not in original) or (" " in corrected and " " not in original):
                correction_types["Espaces et tirets"].append(f"'{original}' → '{corrected}'")
            elif original.lower() in ["sa", "ses", "ces", "et", "est", "son", "sont", "peu", "peut", "mais", "mes", "ce", "se"]:
                correction_types["Confusions courantes"].append(f"'{original}' → '{corrected}'")
            else:
                correction_types["Autres corrections"].append(f"'{original}' → '{corrected}'")

        # Ajouter les corrections par catégorie
        for category, corrections in correction_types.items():
            if corrections:
                explanation += f"\n{category}:\n"
                explanation += "\n".join(corrections) + "\n"

        # Ajouter des conseils d'amélioration
        explanation += "\n--- Conseils d'amélioration ---\n"

        # Détecter les phrases trop longues
        sentences = re.split(r'[.!?]+', text)
        long_sentences = [s.strip() for s in sentences if len(s.split()) > 25]
        if long_sentences:
            explanation += "\n• Phrases trop longues détectées. Envisagez de diviser ces phrases pour améliorer la lisibilité:\n"
            for i, sentence in enumerate(long_sentences[:3]):  # Limiter à 3 exemples
                explanation += f"  - \"{sentence[:100]}...\"\n"
            if len(long_sentences) > 3:
                explanation += f"  (et {len(long_sentences) - 3} autres phrases longues)\n"

        # Détecter les répétitions de mots
        word_counts = {}
        for word in [w.lower() for w in words if len(w) > 3 and w.isalpha()]:
            word_counts[word] = word_counts.get(word, 0) + 1

        repeated_words = [(word, count) for word, count in word_counts.items() if count > 3]
        if repeated_words:
            explanation += "\n• Mots fréquemment répétés (envisagez d'utiliser des synonymes):\n"
            for word, count in sorted(repeated_words, key=lambda x: x[1], reverse=True)[:5]:  # Top 5
                explanation += f"  - \"{word}\" (utilisé {count} fois)\n"

        return corrected_text + explanation
    else:
        # Même si aucune correction de mot n'a été faite, vérifier d'autres aspects
        explanation = "\n\n--- Analyse du texte ---\n"

        # Détecter les phrases trop longues
        sentences = re.split(r'[.!?]+', text)
        long_sentences = [s.strip() for s in sentences if len(s.split()) > 25]
        if long_sentences:
            explanation += "\n• Phrases trop longues détectées. Envisagez de diviser ces phrases pour améliorer la lisibilité:\n"
            for i, sentence in enumerate(long_sentences[:3]):  # Limiter à 3 exemples
                explanation += f"  - \"{sentence[:100]}...\"\n"
            if len(long_sentences) > 3:
                explanation += f"  (et {len(long_sentences) - 3} autres phrases longues)\n"

        # Détecter les répétitions de mots
        word_counts = {}
        for word in [w.lower() for w in words if len(w) > 3 and w.isalpha()]:
            word_counts[word] = word_counts.get(word, 0) + 1

        repeated_words = [(word, count) for word, count in word_counts.items() if count > 3]
        if repeated_words:
            explanation += "\n• Mots fréquemment répétés (envisagez d'utiliser des synonymes):\n"
            for word, count in sorted(repeated_words, key=lambda x: x[1], reverse=True)[:5]:  # Top 5
                explanation += f"  - \"{word}\" (utilisé {count} fois)\n"

        if long_sentences or repeated_words:
            return corrected_text + explanation
        else:
            return corrected_text + "\n\n--- Aucune correction nécessaire ---\nLe texte est grammaticalement correct."

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    data = request.json
    mode = data.get('mode', 'sql')
    text = data.get('text', '')

    if mode == 'sql':
        # Récupérer le type de requête SQL
        sql_type = data.get('sqlType', 'SELECT')

        # Récupérer les options avancées si présentes
        advanced_options = data.get('advancedOptions', {})

        # Générer la requête SQL en fonction du type
        if sql_type == 'SELECT':
            result = generate_sql_query(text)
        elif sql_type == 'DML':
            result = generate_dml_query(text)
        elif sql_type == 'DDL':
            result = generate_ddl_query(text)
        elif sql_type == 'ADVANCED':
            result = generate_advanced_sql_query(text, advanced_options)
        else:
            result = "Type de requête SQL non pris en charge."
    else:  # mode == 'correction'
        result = correct_french_text(text)

    return jsonify({'result': result})

if __name__ == '__main__':
    app.run(debug=True)
