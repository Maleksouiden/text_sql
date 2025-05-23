# SQL Bot - Assistant SQL Intelligent

SQL Bot est une application web qui permet de générer des requêtes SQL à partir de descriptions en langage naturel (français). L'application utilise des modèles pré-entraînés pour comprendre les intentions de l'utilisateur et générer des requêtes SQL précises et optimisées.

## Fonctionnalités

- **Analyse des intentions utilisateur** avec des modèles pré-entraînés pour mieux comprendre les besoins
- **Génération de requêtes SQL** à partir de descriptions en langage naturel
- **Support multilingue** avec traduction automatique français → anglais
- **Support de tous les types de requêtes SQL** (SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP)
- **Correction automatique** des requêtes SQL avec suggestions d'amélioration
- **Visualisation des données** avec des graphiques personnalisables
- **Historique des requêtes** pour faciliter la réutilisation
- **Interface utilisateur intuitive** avec des onglets pour les différentes fonctionnalités

## Architecture technique

L'application est construite avec les technologies suivantes :

- **Backend** : Flask (Python)
- **Frontend** : HTML, CSS, JavaScript (vanilla)
- **Modèles IA** : Modèles pré-entraînés via l'API HuggingFace
- **Visualisation** : Chart.js

Pour plus de détails sur l'architecture technique, consultez le fichier [DOCUMENTATION_TECHNIQUE.md](DOCUMENTATION_TECHNIQUE.md).

## Modèles d'IA utilisés

### Modèle de compréhension des intentions

- **Modèle** : facebook/bart-large-mnli
- **Type** : BART (Bidirectional and Auto-Regressive Transformers)
- **Fonction** : Analyse des requêtes utilisateur pour déterminer leurs intentions

### Modèle de reformulation

- **Modèle** : facebook/bart-large-cnn
- **Type** : BART (Bidirectional and Auto-Regressive Transformers)
- **Fonction** : Reformulation des requêtes pour les rendre plus claires et précises

### Modèle de traduction

- **Modèle** : Helsinki-NLP/opus-mt-fr-en
- **Type** : Seq2Seq (Transformer)
- **Fonction** : Traduction du français vers l'anglais

### Modèle de génération SQL

- **Modèle** : juierror/text-to-sql-with-table-schema
- **Type** : T5 (Text-to-Text Transfer Transformer)
- **Fonction** : Génération de requêtes SQL à partir de descriptions en anglais

### Modèle de correction SQL

- **Modèle** : mrm8488/t5-base-finetuned-sql-correction
- **Type** : T5 fine-tuné
- **Fonction** : Correction des erreurs de syntaxe dans les requêtes SQL

## Installation

1. Clonez ce dépôt :

```bash
git clone https://github.com/Maleksouiden/text_sql.git
cd text_sql
```

2. Créez un environnement virtuel Python et activez-le :

```bash
python -m venv venv
source venv/bin/activate  # Sur Windows : venv\Scripts\activate
```

3. Installez les dépendances :

```bash
pip install -r requirements.txt
```

## Utilisation

1. Lancez l'application :

```bash
python app_sql_pretrained.py
```

2. Ouvrez votre navigateur à l'adresse : http://127.0.0.1:5000

3. Utilisez les différentes fonctionnalités :
   - **Générateur SQL** : Décrivez en français la requête SQL que vous souhaitez générer
   - **Correcteur SQL** : Collez une requête SQL à corriger
   - **Visualisation** : Configurez et générez des graphiques basés sur vos requêtes
   - **Historique** : Consultez et réutilisez vos requêtes précédentes

### Exemple d'utilisation

Pour générer une requête SQL, entrez simplement une description en français :

> "Montre-moi les clients qui ont acheté plus de 3 produits le mois dernier"

L'application analysera vos intentions, reformulera votre demande, la traduira en anglais et générera la requête SQL correspondante :

1. **Analyse des intentions** : "Cette requête concerne la sélection de données avec filtrage et agrégation."
2. **Reformulation** : "Sélectionner les clients qui ont commandé plus de 3 produits au cours du dernier mois"
3. **Traduction** : "Select customers who ordered more than 3 products in the last month"
4. **Génération SQL** :

```sql
SELECT u.id, u.name, COUNT(o.id) as total_orders
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE o.order_date >= DATE_SUB(CURRENT_DATE, INTERVAL 1 MONTH)
GROUP BY u.id, u.name
HAVING COUNT(o.id) > 3;

-- Explication de la requête :
-- Cette requête sélectionne les clients qui ont passé plus de 3 commandes au cours du dernier mois
-- Tables utilisées: users, orders
-- Filtres appliqués: o.order_date >= DATE_SUB(CURRENT_DATE, INTERVAL 1 MONTH)
-- Groupement par: u.id, u.name
-- Condition HAVING: COUNT(o.id) > 3
```

## Configuration avancée

Pour améliorer les performances, vous pouvez configurer une clé API HuggingFace :

1. Créez un compte sur [HuggingFace](https://huggingface.co/)
2. Générez une clé API dans les paramètres du compte
3. Ajoutez la clé dans le fichier `app_sql_pretrained.py` :
   ```python
   HUGGINGFACE_API_KEY = "votre_clé_api"
   ```

## Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

## Auteur

Malek Souiden - [GitHub](https://github.com/Maleksouiden)
