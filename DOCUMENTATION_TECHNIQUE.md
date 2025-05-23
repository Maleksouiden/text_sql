# Documentation Technique - SQL Bot

## Vue d'ensemble

SQL Bot est une application web qui permet de générer des requêtes SQL à partir de descriptions en langage naturel (français). L'application utilise des modèles pré-entraînés pour comprendre les intentions de l'utilisateur et générer des requêtes SQL précises et optimisées.

Cette documentation technique détaille l'architecture, les composants et le fonctionnement interne de l'application.

## Architecture

### Stack technologique

- **Backend** : Flask (Python 3.7+)
- **Frontend** : HTML5, CSS3, JavaScript (vanilla)
- **Modèles IA** : Modèles pré-entraînés via l'API HuggingFace
- **Visualisation** : Chart.js
- **Stockage** : Sessions Flask (stockage temporaire côté serveur)

### Structure du projet

```
sql_bot/
├── app_sql_pretrained.py     # Application principale (Flask)
├── static/                   # Ressources statiques
│   ├── css/                  # Feuilles de style
│   │   └── style.css         # Styles de l'application
│   └── js/                   # Scripts JavaScript
│       └── script.js         # Logique frontend
├── templates/                # Templates HTML
│   └── index.html            # Page principale
├── requirements.txt          # Dépendances Python
└── README.md                 # Documentation utilisateur
```

## Composants principaux

### 1. Traduction français → anglais

Le système de traduction est un composant clé qui permet à l'application de comprendre les requêtes en français. Il utilise deux approches complémentaires :

#### 1.1 API HuggingFace (Modèle Helsinki-NLP/opus-mt-fr-en)

```python
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
```

#### 1.2 Système de secours basé sur des règles

Un dictionnaire de traduction pour les termes SQL courants est utilisé comme solution de secours en cas d'échec de l'API :

```python
def fallback_translate_fr_to_en(text):
    """Traduit un texte du français vers l'anglais en utilisant des règles simples"""
    # Dictionnaire de traduction pour les mots-clés SQL courants
    translation_dict = {
        "sélectionner": "select",
        "afficher": "select",
        "montrer": "select",
        "insérer": "insert",
        "ajouter": "insert",
        "mettre à jour": "update",
        "modifier": "update",
        "supprimer": "delete",
        "effacer": "delete",
        "créer": "create",
        "où": "where",
        # ... autres traductions ...
    }
    
    # Remplacer les mots-clés français par leurs équivalents anglais
    translated_text = text.lower()
    for fr_word, en_word in translation_dict.items():
        translated_text = translated_text.replace(fr_word, en_word)
    
    # Ajouter un préfixe pour indiquer au modèle qu'il s'agit d'une requête SQL
    translated_text = "Generate SQL query: " + translated_text
    
    return translated_text
```

### 2. Génération de requêtes SQL

Le système de génération de requêtes SQL utilise le modèle pré-entraîné `juierror/text-to-sql-with-table-schema` via l'API HuggingFace :

```python
def generate_sql_query(description):
    """Génère une requête SQL à partir d'une description en langage naturel"""
    # Définir les tables et schémas fictifs pour l'exemple
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
    
    # Préparer l'entrée pour le modèle
    input_text = f"Schema: {schema}\nQuestion: {english_description}\nSQL:"
    
    # Utiliser l'API HuggingFace
    result = query_huggingface_api(MODEL_PATHS["text-to-sql"], input_text)
    
    # ... traitement du résultat ...
    
    # Ajouter une explication
    explanation = generate_explanation(sql_query)
    
    # Formater la requête pour une meilleure lisibilité
    formatted_query = sqlparse.format(sql_query, reindent=True, keyword_case='upper')
    
    return formatted_query + explanation, sql_type, {}
```

### 3. Correction de requêtes SQL

Le système de correction de requêtes SQL utilise le modèle pré-entraîné `mrm8488/t5-base-finetuned-sql-correction` et une analyse basée sur des règles :

```python
def correct_sql_query(query):
    """Corrige une requête SQL en utilisant un modèle pré-entraîné"""
    # ... initialisation ...
    
    try:
        # Utiliser l'API HuggingFace
        result = query_huggingface_api(MODEL_PATHS["sql-correction"], f"correct: {query}")
        
        # ... traitement du résultat ...
        
        # Analyser les différences pour générer des erreurs et suggestions
        if corrected_query != query:
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
        # ... gestion des erreurs ...
```

### 4. Interface utilisateur

L'interface utilisateur est construite avec HTML, CSS et JavaScript. Elle est organisée en onglets pour les différentes fonctionnalités :

- **Générateur SQL** : Pour générer des requêtes SQL à partir de descriptions en langage naturel
- **Correcteur SQL** : Pour corriger des requêtes SQL existantes
- **Historique** : Pour consulter l'historique des requêtes générées
- **Visualisation** : Pour visualiser les données avec des graphiques

Le JavaScript gère les interactions utilisateur, les appels AJAX vers le serveur Flask et l'affichage des résultats.

## Modèles d'IA utilisés

### Modèle de traduction

- **Nom** : Helsinki-NLP/opus-mt-fr-en
- **Type** : Seq2Seq (Transformer)
- **Taille** : ~298M paramètres
- **Entraînement** : Entraîné sur le corpus OPUS, qui contient des textes parallèles français-anglais de diverses sources (documents officiels de l'UE, sous-titres de films, documentation technique, etc.)
- **Performances** : Score BLEU de ~38 sur le jeu de test WMT14 fr-en
- **Forces** : Excellente qualité de traduction pour les textes techniques et formels
- **Faiblesses** : Peut avoir des difficultés avec les expressions idiomatiques ou le langage très informel

### Modèle de génération SQL

- **Nom** : juierror/text-to-sql-with-table-schema
- **Type** : T5 (Text-to-Text Transfer Transformer)
- **Base** : t5-base fine-tuné
- **Taille** : ~220M paramètres
- **Entraînement** : Fine-tuné sur des paires de descriptions en langage naturel et requêtes SQL correspondantes, avec schémas de tables
- **Jeux de données** : Spider, WikiSQL et autres jeux de données de text-to-SQL
- **Performances** : Précision d'environ 80% sur des requêtes SQL simples à modérément complexes
- **Forces** : Bonne compréhension des intentions et génération de requêtes SQL valides
- **Faiblesses** : Peut avoir des difficultés avec des requêtes très complexes ou des schémas de base de données non standard

### Modèle de correction SQL

- **Nom** : mrm8488/t5-base-finetuned-sql-correction
- **Type** : T5 fine-tuné
- **Base** : t5-base
- **Taille** : ~220M paramètres
- **Entraînement** : Fine-tuné sur des paires de requêtes SQL incorrectes et leurs versions corrigées
- **Performances** : Détection efficace des erreurs courantes et suggestions pertinentes
- **Forces** : Bonne capacité à corriger les erreurs de syntaxe et à suggérer des améliorations
- **Faiblesses** : Peut avoir des difficultés avec des erreurs très subtiles ou des dialectes SQL spécifiques

## Flux de données

1. **Entrée utilisateur** : L'utilisateur entre une description en français de la requête SQL souhaitée
2. **Requête AJAX** : Le frontend envoie la description au serveur Flask via une requête AJAX
3. **Traduction** : Le serveur traduit la description en anglais
4. **Génération SQL** : La description traduite est envoyée à l'API HuggingFace pour générer la requête SQL
5. **Post-traitement** : Le serveur ajoute des explications et des suggestions à la requête générée
6. **Réponse** : Le résultat est renvoyé au frontend sous forme de JSON
7. **Affichage** : Le frontend affiche la requête générée, la traduction utilisée et les explications
8. **Historique** : La requête est ajoutée à l'historique dans la session Flask

## API et endpoints

### `/process` (POST)

Endpoint principal pour générer des requêtes SQL à partir de descriptions en langage naturel.

**Entrée** :
```json
{
  "text": "Sélectionne tous les utilisateurs dont l'âge est supérieur à 30"
}
```

**Sortie** :
```json
{
  "result": "SELECT * FROM users WHERE age > 30;\n\n-- Explication de la requête :\n-- Cette requête sélectionne tous les utilisateurs dont l'âge est supérieur à 30",
  "detected_type": "SELECT",
  "advanced_options": {},
  "has_advanced_options": false,
  "history": [...],
  "original_text": "Sélectionne tous les utilisateurs dont l'âge est supérieur à 30",
  "translated_text": "Select all users where age is greater than 30"
}
```

### `/correct_query` (POST)

Endpoint pour corriger des requêtes SQL existantes.

**Entrée** :
```json
{
  "query": "SLECT * FORM users WEHRE age > 30"
}
```

**Sortie** :
```json
{
  "original": "SLECT * FORM users WEHRE age > 30",
  "corrected_query": "SELECT * FROM users WHERE age > 30;",
  "errors": [
    "Le mot-clé SELECT est mal orthographié.",
    "Le mot-clé FROM est mal orthographié.",
    "Le mot-clé WHERE est mal orthographié."
  ],
  "suggestions": [
    "Ajouter un point-virgule à la fin de la requête.",
    "Utiliser des alias pour les tables pour améliorer la lisibilité.",
    "Ajouter une clause LIMIT pour limiter le nombre de résultats retournés."
  ]
}
```

## Performances et optimisations

### Optimisations côté serveur

- **Mise en cache des traductions** : Les traductions fréquentes sont mises en cache pour éviter des appels API répétés
- **Système de secours** : Un système de traduction basé sur des règles est utilisé en cas d'échec de l'API
- **Gestion des erreurs** : Des mécanismes de gestion des erreurs robustes pour assurer la continuité du service

### Optimisations côté client

- **Debouncing** : Les requêtes sont envoyées après un délai pour éviter des appels API inutiles pendant la frappe
- **Mise en cache locale** : Les résultats récents sont stockés localement pour une réutilisation rapide
- **Interface réactive** : L'interface utilisateur reste réactive même pendant les appels API

## Limites et améliorations futures

### Limites actuelles

- **Dépendance à l'API HuggingFace** : L'application nécessite une connexion Internet pour fonctionner pleinement
- **Schéma de base de données fixe** : Le modèle utilise un schéma de base de données prédéfini
- **Support limité des dialectes SQL** : Principalement orienté vers SQL standard (PostgreSQL/MySQL)

### Améliorations futures

- **Modèles locaux** : Intégration de modèles plus légers pouvant fonctionner localement
- **Schéma personnalisable** : Permettre aux utilisateurs de définir leur propre schéma de base de données
- **Support de plus de dialectes SQL** : Ajouter le support pour MS SQL, Oracle, SQLite, etc.
- **Apprentissage continu** : Améliorer les modèles en fonction des corrections des utilisateurs
- **Export des requêtes** : Ajouter des fonctionnalités d'export vers différents formats

## Conclusion

SQL Bot est une application web puissante qui combine des modèles d'IA pré-entraînés avec une interface utilisateur intuitive pour générer des requêtes SQL à partir de descriptions en langage naturel. L'architecture modulaire et l'utilisation de l'API HuggingFace permettent une grande flexibilité et des performances élevées, tout en offrant une expérience utilisateur fluide et intuitive.
