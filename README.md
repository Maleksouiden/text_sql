# SQL Bot - Assistant SQL Intelligent

SQL Bot est une application web qui permet de générer des requêtes SQL à partir de descriptions en langage naturel (français). L'application utilise des modèles pré-entraînés pour comprendre les intentions de l'utilisateur et générer des requêtes SQL précises et optimisées.

## Fonctionnalités

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

> "Sélectionne tous les utilisateurs dont l'âge est supérieur à 30 ans et qui ont passé au moins une commande"

L'application traduira automatiquement votre description en anglais et générera la requête SQL correspondante :

```sql
SELECT u.*
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE u.age > 30
GROUP BY u.id
HAVING COUNT(o.id) >= 1;

-- Explication de la requête :
-- Cette requête sélectionne tous les utilisateurs dont l'âge est supérieur à 30 ans
-- Tables utilisées: users, orders
-- Filtres appliqués: u.age > 30
-- Groupement par: u.id
-- Condition HAVING: COUNT(o.id) >= 1
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
