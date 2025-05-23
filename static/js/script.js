document.addEventListener("DOMContentLoaded", function () {
  // Éléments DOM - Interface principale
  const generateSqlBtn = document.getElementById("generate-sql");
  const sqlInput = document.getElementById("sql-input");
  const resultBox = document.getElementById("result");
  const copyResultBtn = document.getElementById("copy-result");
  const saveResultBtn = document.getElementById("save-result");
  const detectedTypeSpan = document.getElementById("detected-type");

  // Éléments DOM - Types de requêtes SQL
  const sqlTypeButtons = document.querySelectorAll(".sql-type-btn") || [];
  const sqlTypeInfo = document.getElementById("sql-type-info");
  const sqlAdvancedOptions = document.getElementById("sql-advanced-options");
  const advancedCheckboxes =
    document.querySelectorAll(".advanced-checkbox") || [];

  // Éléments DOM - Section graphiques
  const chartSection = document.getElementById("chart-section");
  const generateChartBtn = document.getElementById("generate-chart");
  const updateChartDataBtn = document.getElementById("update-chart-data");
  const chartTypeSelect = document.getElementById("chart-type");
  const chartLabelsInput = document.getElementById("chart-labels");
  const chartValuesInput = document.getElementById("chart-values");
  const chartTitleInput = document.getElementById("chart-title");
  const chartColorSchemeSelect = document.getElementById("chart-color-scheme");
  const chartDataInput = document.getElementById("chart-data");
  const chartCanvas = document.getElementById("data-chart");

  // Éléments DOM - Section historique
  const historySection = document.getElementById("history-section");
  const historyList = document.getElementById("history-list");
  const clearHistoryBtn = document.getElementById("clear-history");

  // Éléments DOM - Section correcteur SQL
  const correctorSection = document.getElementById("corrector-section");
  const sqlToCorrect = document.getElementById("sql-to-correct");
  const correctSqlBtn = document.getElementById("correct-sql");
  const correctionResult = document.getElementById("correction-result");
  const errorsList = document.getElementById("errors-list");
  const suggestionsList = document.getElementById("suggestions-list");
  const correctedQuery = document.getElementById("corrected-query");
  const copyCorrectedBtn = document.getElementById("copy-corrected");
  const useCorrectedBtn = document.getElementById("use-corrected");

  // Éléments DOM - Onglets
  const tabButtons = document.querySelectorAll(".tab-button");
  const tabContents = document.querySelectorAll(".tab-content");

  // Variables globales
  let currentMode = "sql"; // Mode actuel (par défaut: SQL)
  let currentChart = null; // Instance du graphique actuel
  let sqlResult = ""; // Résultat de la dernière requête SQL
  let currentSqlType = "SELECT"; // Type de requête SQL actuel (par défaut: SELECT)

  // Schémas de couleurs pour les graphiques
  const colorSchemes = {
    default: [
      "#4e79a7",
      "#f28e2c",
      "#e15759",
      "#76b7b2",
      "#59a14f",
      "#edc949",
      "#af7aa1",
      "#ff9da7",
      "#9c755f",
      "#bab0ab",
    ],
    pastel: [
      "#a6cee3",
      "#b2df8a",
      "#fb9a99",
      "#fdbf6f",
      "#cab2d6",
      "#ffff99",
      "#1f78b4",
      "#33a02c",
      "#e31a1c",
      "#ff7f00",
    ],
    vibrant: [
      "#1f77b4",
      "#ff7f0e",
      "#2ca02c",
      "#d62728",
      "#9467bd",
      "#8c564b",
      "#e377c2",
      "#7f7f7f",
      "#bcbd22",
      "#17becf",
    ],
    monochrome: [
      "#08306b",
      "#08519c",
      "#2171b5",
      "#4292c6",
      "#6baed6",
      "#9ecae1",
      "#c6dbef",
      "#deebf7",
      "#f7fbff",
      "#fff",
    ],
    corporate: [
      "#003f5c",
      "#2f4b7c",
      "#665191",
      "#a05195",
      "#d45087",
      "#f95d6a",
      "#ff7c43",
      "#ffa600",
      "#7d8491",
      "#bfbfbf",
    ],
  };

  // Initialisation du mode SQL par défaut
  currentMode = "sql";

  // Gestionnaires d'événements pour les boutons de type SQL
  if (sqlTypeButtons.length > 0) {
    sqlTypeButtons.forEach((button) => {
      button.addEventListener("click", function () {
        const sqlType = this.getAttribute("data-type");
        setActiveSqlType(sqlType);
      });
    });
  }

  // Fonction pour définir le mode actif (conservée pour compatibilité)
  function setActiveMode(mode) {
    currentMode = mode;

    // Afficher/masquer la section de graphiques
    chartSection.style.display = mode === "sql" ? "block" : "none";

    // Réinitialisation du résultat
    resultBox.textContent = "";
  }

  // Fonction pour définir le type de requête SQL actif
  function setActiveSqlType(sqlType) {
    currentSqlType = sqlType;

    // Mise à jour des classes actives pour les boutons
    if (sqlTypeButtons.length > 0) {
      sqlTypeButtons.forEach((button) => {
        button.classList.toggle(
          "active",
          button.getAttribute("data-type") === sqlType
        );
      });
    }

    // Mise à jour des informations et options en fonction du type
    if (sqlTypeInfo) {
      updateSqlTypeInfo(sqlType);
    }

    // Afficher/masquer les options avancées
    if (sqlAdvancedOptions) {
      sqlAdvancedOptions.style.display =
        sqlType === "ADVANCED" ? "block" : "none";
    }

    // Mettre à jour le placeholder du textarea
    updateSqlInputPlaceholder(sqlType);
  }

  // Fonction pour mettre à jour les informations sur le type de requête SQL
  function updateSqlTypeInfo(sqlType) {
    if (!sqlTypeInfo) return;

    let title = "";
    let description = "";
    let example = "";

    switch (sqlType) {
      case "SELECT":
        title = "Requête SELECT (DQL)";
        description =
          "Utilisez ce mode pour interroger des données existantes.";
        example =
          "Je veux une requête qui sélectionne les champs nom, prénom, email des tables utilisateurs et commandes où la date est supérieure à '2023-01-01'";
        break;
      case "DML":
        title = "Requêtes INSERT/UPDATE/DELETE (DML)";
        description = "Utilisez ce mode pour manipuler des données existantes.";
        example =
          "Je veux insérer dans la table utilisateurs les valeurs (1, 'Jean Dupont', 'jean@example.com') pour les champs id, nom, email";
        break;
      case "DDL":
        title = "Requêtes CREATE/ALTER/DROP (DDL)";
        description =
          "Utilisez ce mode pour définir ou modifier la structure des données.";
        example =
          "Je veux créer une table clients avec les champs id (entier), nom (texte 100), email (texte 100) et date_inscription (date)";
        break;
      case "ADVANCED":
        title = "Fonctionnalités SQL avancées";
        description =
          "Utilisez ce mode pour générer des requêtes SQL avancées. Sélectionnez les options ci-dessous.";
        example =
          "Je veux une requête avec CTE qui calcule le total des ventes par client et qui affiche uniquement les clients dont le total est supérieur à la moyenne";
        break;
    }

    // Mettre à jour le contenu
    sqlTypeInfo.innerHTML = `
      <h3>${title}</h3>
      <p>${description}</p>
      <div class="example">
        <p><strong>Exemple :</strong> "${example}"</p>
      </div>
    `;
  }

  // Fonction pour mettre à jour le placeholder du textarea
  function updateSqlInputPlaceholder(sqlType) {
    if (!sqlInput) return;

    switch (sqlType) {
      case "SELECT":
        sqlInput.placeholder =
          "Décrivez votre requête SELECT en langage naturel...";
        break;
      case "DML":
        sqlInput.placeholder =
          "Décrivez votre requête INSERT, UPDATE ou DELETE en langage naturel...";
        break;
      case "DDL":
        sqlInput.placeholder =
          "Décrivez votre requête CREATE, ALTER ou DROP en langage naturel...";
        break;
      case "ADVANCED":
        sqlInput.placeholder =
          "Décrivez votre requête SQL avancée en langage naturel...";
        break;
      default:
        sqlInput.placeholder =
          "Décrivez votre requête SQL en langage naturel...";
        break;
    }
  }

  // Gestionnaire pour le bouton de génération SQL
  generateSqlBtn.addEventListener("click", function () {
    const text = sqlInput.value.trim();
    if (!text) {
      alert("Veuillez entrer une description pour votre requête SQL.");
      return;
    }

    processRequest(text);
  });

  // Fonction pour envoyer la requête au serveur
  function processRequest(text) {
    // Afficher un indicateur de chargement
    resultBox.textContent = "Traitement en cours...";

    // Préparer les données à envoyer
    const requestData = { text };

    // Récupérer les options avancées si nécessaire
    const advancedOptions = {};
    advancedCheckboxes.forEach((checkbox) => {
      advancedOptions[checkbox.id.replace("option-", "")] = checkbox.checked;
    });

    // Ajouter les options avancées si au moins une est cochée
    if (Object.values(advancedOptions).some((value) => value)) {
      requestData.advancedOptions = advancedOptions;
    }

    fetch("/process", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(requestData),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Erreur réseau");
        }
        return response.json();
      })
      .then((data) => {
        // Afficher le résultat
        resultBox.textContent = data.result;

        // Afficher le type détecté
        if (data.detected_type) {
          detectedTypeSpan.innerHTML = `Type détecté : <strong>${data.detected_type}</strong>`;
        }

        // Afficher la traduction si disponible
        if (data.translated_text) {
          // Créer ou récupérer le conteneur de traduction
          let translationContainer = document.getElementById(
            "translation-container"
          );
          if (!translationContainer) {
            translationContainer = document.createElement("div");
            translationContainer.id = "translation-container";
            translationContainer.className = "translation-container";

            // Insérer avant la zone de résultat
            resultBox.parentNode.insertBefore(translationContainer, resultBox);
          }

          // Afficher la traduction
          translationContainer.innerHTML = `
            <div class="translation-info">
              <h4>Traduction utilisée:</h4>
              <div class="translation-text">${data.translated_text}</div>
            </div>
          `;
        }

        // Stocker le résultat SQL pour une utilisation ultérieure avec les graphiques
        sqlResult = data.result;

        // Afficher la section de graphiques uniquement pour les requêtes SELECT
        if (data.detected_type === "SELECT") {
          extractFieldsFromSQL(sqlResult);
          chartSection.style.display = "block";
        } else {
          // Masquer la section de graphiques pour les autres types de requêtes
          chartSection.style.display = "none";
        }

        // Mettre à jour l'historique
        if (data.history) {
          updateHistoryList(data.history);
        }

        // Afficher les suggestions basées sur l'apprentissage
        if (data.suggestion) {
          // Supprimer l'ancienne suggestion si elle existe
          const oldSuggestion = document.getElementById(
            "learning-suggestion-container"
          );
          if (oldSuggestion) {
            oldSuggestion.remove();
          }

          // Créer un conteneur pour la suggestion
          const suggestionContainer = document.createElement("div");
          suggestionContainer.id = "learning-suggestion-container";
          suggestionContainer.className = "learning-suggestion-container";

          // Créer la suggestion avec une icône
          suggestionContainer.innerHTML = `
            <div class="learning-suggestion">
              <span class="suggestion-icon" title="Suggestion basée sur vos requêtes précédentes">🧠</span>
              <span>${data.suggestion}</span>
            </div>
          `;

          // Insérer après la zone de résultat
          const resultContainer =
            resultBox.closest(".result-container") || resultBox.parentNode;
          resultContainer.insertBefore(
            suggestionContainer,
            resultBox.nextSibling
          );
        }

        // Afficher les informations sur l'intention utilisateur si disponibles
        if (data.user_intent && data.user_intent.confidence > 0.5) {
          // Créer ou mettre à jour le badge d'intention
          let intentBadge = document.getElementById("intent-badge");
          if (!intentBadge) {
            intentBadge = document.createElement("div");
            intentBadge.id = "intent-badge";
            intentBadge.className = "intent-badge";

            // Insérer près du badge de type détecté
            if (detectedTypeSpan) {
              detectedTypeSpan.parentNode.insertBefore(
                intentBadge,
                detectedTypeSpan.nextSibling
              );
            }
          }

          // Déterminer l'intention principale
          let intentText = "";
          if (data.user_intent.purpose) {
            intentText = `Intention: ${data.user_intent.purpose}`;
          } else if (data.user_intent.format) {
            intentText = `Format souhaité: ${data.user_intent.format}`;
          } else if (data.user_intent.priority) {
            intentText = `Priorité: ${data.user_intent.priority}`;
          }

          if (intentText) {
            intentBadge.textContent = intentText;
            intentBadge.style.display = "inline-block";
          } else {
            intentBadge.style.display = "none";
          }
        }
      })
      .catch((error) => {
        resultBox.textContent = `Erreur: ${error.message}`;
      });
  }

  // Fonction pour mettre à jour l'historique des requêtes
  function updateHistoryList(history) {
    // Vider la liste d'historique
    historyList.innerHTML = "";

    if (history.length === 0) {
      // Afficher un message si l'historique est vide
      historyList.innerHTML =
        '<div class="empty-history">Aucune requête dans l\'historique</div>';
      return;
    }

    // Ajouter chaque élément d'historique à la liste
    history.forEach((item, index) => {
      const historyItem = document.createElement("div");
      historyItem.className = "history-item";
      historyItem.dataset.index = index;

      // Limiter la longueur de la requête pour l'aperçu
      const queryPreview =
        item.query.split("\n")[0].substring(0, 50) +
        (item.query.length > 50 ? "..." : "");

      historyItem.innerHTML = `
        <div class="history-item-header">
          <span class="history-item-type">${item.type}</span>
          <span class="history-item-time">${item.timestamp}</span>
        </div>
        <div class="history-item-description">${item.description}</div>
        <div class="history-item-preview">${queryPreview}</div>
      `;

      // Ajouter un gestionnaire d'événements pour charger la requête
      historyItem.addEventListener("click", function () {
        // Remplir le champ de texte avec la description
        sqlInput.value = item.description;

        // Afficher la requête dans la zone de résultat
        resultBox.textContent = item.query;

        // Mettre à jour le type détecté
        detectedTypeSpan.innerHTML = `Type détecté : <strong>${item.type}</strong>`;

        // Afficher/masquer la section de graphiques selon le type
        chartSection.style.display = item.type === "SELECT" ? "block" : "none";

        // Si c'est une requête SELECT, extraire les champs pour les graphiques
        if (item.type === "SELECT") {
          extractFieldsFromSQL(item.query);
        }
      });

      historyList.appendChild(historyItem);
    });
  }

  // Fonction pour extraire les champs d'une requête SQL
  function extractFieldsFromSQL(sqlText) {
    // Envoyer la requête SQL au serveur pour extraire les champs
    fetch("/extract_fields", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query: sqlText }),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Erreur réseau");
        }
        return response.json();
      })
      .then((data) => {
        const fields = data.fields;

        // Mettre à jour les champs pour les graphiques
        if (fields && fields.length > 0) {
          // Créer des options pour les sélecteurs de champs
          updateFieldSelectors(fields);

          // Utiliser le premier champ pour les étiquettes
          chartLabelsInput.value = fields[0];

          // Utiliser le deuxième champ pour les valeurs, ou le premier s'il n'y en a qu'un
          chartValuesInput.value = fields[1] || fields[0];

          // Suggérer un titre pour le graphique
          chartTitleInput.value = `Analyse des ${fields[1] || fields[0]} par ${
            fields[0]
          }`;
        }
      })
      .catch((error) => {
        console.error("Erreur lors de l'extraction des champs:", error);
      });
  }

  // Fonction pour mettre à jour les sélecteurs de champs
  function updateFieldSelectors(fields) {
    // Créer des éléments de sélection pour les champs
    if (chartLabelsInput && chartValuesInput) {
      // Créer des listes déroulantes si elles n'existent pas déjà
      createFieldSelector(chartLabelsInput, "chart-labels-select", fields);
      createFieldSelector(chartValuesInput, "chart-values-select", fields);
    }
  }

  // Fonction pour créer un sélecteur de champs
  function createFieldSelector(inputElement, selectId, fields) {
    // Vérifier si le sélecteur existe déjà
    let selectElement = document.getElementById(selectId);

    if (!selectElement) {
      // Créer un nouveau sélecteur
      selectElement = document.createElement("select");
      selectElement.id = selectId;
      selectElement.className = "chart-select";

      // Ajouter le sélecteur après l'input
      inputElement.parentNode.insertBefore(
        selectElement,
        inputElement.nextSibling
      );

      // Ajouter un gestionnaire d'événements pour mettre à jour l'input
      selectElement.addEventListener("change", function () {
        inputElement.value = this.value;
      });
    } else {
      // Vider le sélecteur existant
      selectElement.innerHTML = "";
    }

    // Ajouter les options
    fields.forEach((field) => {
      const option = document.createElement("option");
      option.value = field;
      option.textContent = field;
      selectElement.appendChild(option);
    });

    // Sélectionner la valeur actuelle de l'input
    if (inputElement.value && fields.includes(inputElement.value)) {
      selectElement.value = inputElement.value;
    }
  }

  // Gestionnaire pour le bouton de génération de graphique
  generateChartBtn.addEventListener("click", function () {
    // Vérifier si nous avons des données pour le graphique
    if (!chartDataInput.value.trim()) {
      // Si pas de données, générer des données d'exemple basées sur les champs
      generateSampleChartData();
    } else {
      // Sinon, utiliser les données existantes
      createChart();
    }
  });

  // Gestionnaire pour le bouton de mise à jour des données du graphique
  updateChartDataBtn.addEventListener("click", function () {
    createChart();
  });

  // Fonction pour générer des données d'exemple pour le graphique
  function generateSampleChartData() {
    const labels = chartLabelsInput.value.trim();
    const values = chartValuesInput.value.trim();

    if (!labels || !values) {
      alert(
        "Veuillez spécifier au moins un champ pour les étiquettes et un champ pour les valeurs."
      );
      return;
    }

    // Générer des données d'exemple
    const sampleData = [];
    const categories = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin"];

    for (let i = 0; i < categories.length; i++) {
      sampleData.push({
        label: categories[i],
        value: Math.floor(Math.random() * 1000) + 100,
      });
    }

    // Mettre à jour le champ de données
    chartDataInput.value = JSON.stringify(sampleData, null, 2);

    // Créer le graphique
    createChart();
  }

  // Fonction pour créer ou mettre à jour le graphique
  function createChart() {
    // Récupérer les paramètres du graphique
    const chartType = chartTypeSelect.value;
    const chartTitle = chartTitleInput.value || "Visualisation des données";
    const colorScheme =
      colorSchemes[chartColorSchemeSelect.value] || colorSchemes.default;

    // Récupérer les noms des champs pour les axes
    const xAxisField = chartLabelsInput.value;
    const yAxisField = chartValuesInput.value;

    // Analyser les données
    let chartData;
    try {
      // Essayer de parser les données JSON
      chartData = JSON.parse(chartDataInput.value);
    } catch (e) {
      // Si le parsing JSON échoue, essayer de parser comme CSV
      try {
        chartData = parseCSV(chartDataInput.value);
      } catch (csvError) {
        alert(
          "Format de données invalide. Veuillez utiliser un format JSON ou CSV valide."
        );
        console.error("Erreur de parsing:", e, csvError);
        return;
      }
    }

    // Vérifier que les données sont au bon format
    if (!Array.isArray(chartData) || chartData.length === 0) {
      alert("Les données doivent être un tableau non vide d'objets.");
      return;
    }

    // Extraire les labels et les valeurs
    let labels, values;

    // Si les données sont déjà au format {label, value}
    if (
      chartData[0].hasOwnProperty("label") &&
      chartData[0].hasOwnProperty("value")
    ) {
      labels = chartData.map((item) => item.label);
      values = chartData.map((item) => item.value);
    }
    // Si les données sont au format d'objets avec des propriétés dynamiques
    else if (
      chartData[0].hasOwnProperty(xAxisField) &&
      chartData[0].hasOwnProperty(yAxisField)
    ) {
      labels = chartData.map((item) => item[xAxisField]);
      values = chartData.map((item) => item[yAxisField]);
    }
    // Format inconnu, utiliser les clés et valeurs
    else {
      const keys = Object.keys(chartData[0]);
      if (keys.length >= 2) {
        labels = chartData.map((item) => item[keys[0]]);
        values = chartData.map((item) => item[keys[1]]);
      } else {
        alert(
          "Format de données non reconnu. Veuillez utiliser un format avec au moins deux propriétés."
        );
        return;
      }
    }

    // Détruire le graphique existant s'il y en a un
    if (currentChart) {
      currentChart.destroy();
    }

    // Créer des options avancées selon le type de graphique
    const chartOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: chartTitle,
          font: {
            size: 16,
            weight: "bold",
          },
          padding: {
            top: 10,
            bottom: 20,
          },
        },
        legend: {
          display: chartType !== "bar" && chartType !== "line",
          position: "top",
        },
        tooltip: {
          enabled: true,
          mode: "index",
          intersect: false,
          callbacks: {
            label: function (context) {
              let label = context.dataset.label || "";
              if (label) {
                label += ": ";
              }
              if (context.parsed.y !== null) {
                label += new Intl.NumberFormat("fr-FR").format(
                  context.parsed.y
                );
              }
              return label;
            },
          },
        },
      },
    };

    // Ajouter des options spécifiques selon le type de graphique
    if (chartType === "bar") {
      chartOptions.scales = {
        y: {
          beginAtZero: true,
          title: {
            display: true,
            text: yAxisField,
            font: {
              weight: "bold",
            },
          },
        },
        x: {
          title: {
            display: true,
            text: xAxisField,
            font: {
              weight: "bold",
            },
          },
        },
      };
    } else if (chartType === "line") {
      chartOptions.scales = {
        y: {
          beginAtZero: true,
          title: {
            display: true,
            text: yAxisField,
            font: {
              weight: "bold",
            },
          },
        },
        x: {
          title: {
            display: true,
            text: xAxisField,
            font: {
              weight: "bold",
            },
          },
        },
      };
      // Ajouter des options pour les lignes
      chartOptions.elements = {
        line: {
          tension: 0.3, // Ajoute une courbe aux lignes
          fill: false,
        },
        point: {
          radius: 4,
          hoverRadius: 6,
        },
      };
    } else if (chartType === "pie" || chartType === "doughnut") {
      // Options spécifiques pour les graphiques circulaires
      chartOptions.plugins.tooltip = {
        callbacks: {
          label: function (context) {
            const label = context.label || "";
            const value = context.raw || 0;
            const total = context.chart.data.datasets[0].data.reduce(
              (a, b) => a + b,
              0
            );
            const percentage = Math.round((value / total) * 100);
            return `${label}: ${value} (${percentage}%)`;
          },
        },
      };
    }

    // Configuration du graphique
    const chartConfig = {
      type: chartType,
      data: {
        labels: labels,
        datasets: [
          {
            label: yAxisField,
            data: values,
            backgroundColor: Array.isArray(colorScheme)
              ? chartType === "line"
                ? colorScheme[0]
                : colorScheme
              : colorScheme,
            borderColor: Array.isArray(colorScheme)
              ? chartType === "line"
                ? colorScheme[0]
                : colorScheme.map((c) => c.replace("0.7", "1"))
              : colorScheme,
            borderWidth: chartType === "line" ? 2 : 1,
          },
        ],
      },
      options: chartOptions,
    };

    // Créer le nouveau graphique
    currentChart = new Chart(chartCanvas, chartConfig);
  }

  // Fonction pour parser des données CSV
  function parseCSV(csvText) {
    // Diviser le texte en lignes
    const lines = csvText.trim().split("\n");

    // Extraire les en-têtes (première ligne)
    const headers = lines[0].split(",").map((header) => header.trim());

    // Convertir les lignes en objets
    const data = [];
    for (let i = 1; i < lines.length; i++) {
      const values = lines[i].split(",").map((value) => value.trim());

      // Créer un objet avec les en-têtes comme clés
      const obj = {};
      for (let j = 0; j < headers.length; j++) {
        // Essayer de convertir en nombre si possible
        const numValue = parseFloat(values[j]);
        obj[headers[j]] = isNaN(numValue) ? values[j] : numValue;
      }

      data.push(obj);
    }

    return data;
  }

  // Gestionnaire pour le bouton de copie
  copyResultBtn.addEventListener("click", function () {
    const result = resultBox.textContent;
    if (!result) return;

    navigator.clipboard
      .writeText(result)
      .then(() => {
        // Feedback visuel temporaire
        const originalText = copyResultBtn.textContent;
        copyResultBtn.textContent = "Copié !";
        setTimeout(() => {
          copyResultBtn.textContent = originalText;
        }, 2000);
      })
      .catch((err) => {
        console.error("Erreur lors de la copie: ", err);
      });
  });

  // Gestionnaire pour le bouton de sauvegarde
  if (saveResultBtn) {
    saveResultBtn.addEventListener("click", function () {
      const result = resultBox.textContent;
      if (!result) {
        alert("Aucun résultat à sauvegarder.");
        return;
      }

      // Créer un élément <a> pour le téléchargement
      const element = document.createElement("a");
      const file = new Blob([result], { type: "text/plain" });
      element.href = URL.createObjectURL(file);
      element.download =
        "requete_sql_" +
        new Date().toISOString().slice(0, 19).replace(/:/g, "-") +
        ".sql";

      // Simuler un clic sur l'élément pour déclencher le téléchargement
      document.body.appendChild(element);
      element.click();
      document.body.removeChild(element);
    });
  }

  // Gestionnaire pour le bouton d'effacement de l'historique
  if (clearHistoryBtn) {
    clearHistoryBtn.addEventListener("click", function () {
      if (
        confirm(
          "Êtes-vous sûr de vouloir effacer tout l'historique des requêtes ?"
        )
      ) {
        fetch("/clear_history", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        })
          .then((response) => response.json())
          .then((data) => {
            if (data.success) {
              // Mettre à jour l'affichage de l'historique
              historyList.innerHTML =
                '<div class="empty-history">Aucune requête dans l\'historique</div>';
            }
          })
          .catch((error) => {
            console.error(
              "Erreur lors de l'effacement de l'historique:",
              error
            );
          });
      }
    });
  }

  // Gestionnaire pour les onglets
  tabButtons.forEach((button) => {
    button.addEventListener("click", function () {
      const tabName = this.getAttribute("data-tab");

      // Mettre à jour les classes actives des boutons
      tabButtons.forEach((btn) => {
        btn.classList.toggle("active", btn === this);
      });

      // Afficher le contenu de l'onglet correspondant
      tabContents.forEach((content) => {
        if (content.getAttribute("data-tab") === tabName) {
          content.classList.add("active");
        } else {
          content.classList.remove("active");
        }
      });
    });
  });

  // Gestionnaire pour le bouton de correction SQL
  if (correctSqlBtn) {
    correctSqlBtn.addEventListener("click", function () {
      const query = sqlToCorrect.value.trim();
      if (!query) {
        alert("Veuillez entrer une requête SQL à corriger.");
        return;
      }

      // Envoyer la requête au serveur pour correction
      fetch("/correct_query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query }),
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error("Erreur réseau");
          }
          return response.json();
        })
        .then((data) => {
          // Afficher les résultats de la correction
          displayCorrectionResults(data);
        })
        .catch((error) => {
          console.error("Erreur lors de la correction:", error);
          alert("Une erreur est survenue lors de la correction de la requête.");
        });
    });
  }

  // Fonction pour afficher les résultats de la correction
  function displayCorrectionResults(data) {
    // Afficher le conteneur de résultats
    if (correctionResult) {
      correctionResult.style.display = "block";

      // Afficher les erreurs
      if (errorsList) {
        errorsList.innerHTML = "";
        if (data.errors && data.errors.length > 0) {
          data.errors.forEach((error) => {
            const li = document.createElement("li");
            li.textContent = error;
            li.className = "error-item";
            errorsList.appendChild(li);
          });
        } else {
          errorsList.innerHTML = "<li>Aucune erreur détectée</li>";
        }
      }

      // Afficher les suggestions
      if (suggestionsList) {
        suggestionsList.innerHTML = "";
        if (data.suggestions && data.suggestions.length > 0) {
          data.suggestions.forEach((suggestion) => {
            const li = document.createElement("li");

            // Détecter si c'est une suggestion basée sur l'apprentissage
            if (
              suggestion.startsWith("Modèle fréquent:") ||
              suggestion.startsWith("Tables fréquemment utilisées:") ||
              suggestion.startsWith("Champs spécifiques fréquemment utilisés:")
            ) {
              li.className = "suggestion-item learning-suggestion";

              // Ajouter une icône pour les suggestions d'apprentissage
              const icon = document.createElement("span");
              icon.className = "suggestion-icon";
              icon.innerHTML = "🧠";
              icon.title = "Suggestion basée sur vos requêtes précédentes";
              li.appendChild(icon);

              // Ajouter le texte de la suggestion
              const text = document.createElement("span");
              text.textContent = suggestion;
              li.appendChild(text);
            } else {
              li.className = "suggestion-item";
              li.textContent = suggestion;
            }

            suggestionsList.appendChild(li);
          });
        } else {
          suggestionsList.innerHTML = "<li>Aucune suggestion disponible</li>";
        }
      }

      // Afficher la requête corrigée
      if (correctedQuery) {
        correctedQuery.textContent = data.corrected_query || data.original;

        // Supprimer l'ancien conteneur de différences s'il existe
        const oldDiffContainer = document.querySelector(".query-diff");
        if (oldDiffContainer) {
          oldDiffContainer.remove();
        }

        // Mettre en évidence les différences entre la requête originale et corrigée
        if (
          data.original &&
          data.corrected_query &&
          data.original !== data.corrected_query
        ) {
          // Créer un élément pour montrer les différences
          const diffContainer = document.createElement("div");
          diffContainer.className = "query-diff";
          diffContainer.innerHTML = "<h4>Modifications apportées:</h4>";

          // Créer une liste des modifications
          const diffList = document.createElement("ul");

          // Comparer les requêtes mot par mot
          const originalWords = data.original.split(/\s+/);
          const correctedWords = data.corrected_query.split(/\s+/);

          // Trouver les mots qui ont changé
          const changes = [];
          for (
            let i = 0;
            i < Math.max(originalWords.length, correctedWords.length);
            i++
          ) {
            if (i >= originalWords.length) {
              // Mot ajouté
              changes.push({
                type: "added",
                text: `Ajout de "${correctedWords[i]}"`,
              });
            } else if (i >= correctedWords.length) {
              // Mot supprimé
              changes.push({
                type: "removed",
                text: `Suppression de "${originalWords[i]}"`,
              });
            } else if (originalWords[i] !== correctedWords[i]) {
              // Mot modifié
              changes.push({
                type: "modified",
                text: `Remplacement de "${originalWords[i]}" par "${correctedWords[i]}"`,
              });
            }
          }

          // Limiter à 5 changements pour ne pas surcharger l'interface
          const displayChanges = changes.slice(0, 5);

          // Ajouter les changements à la liste
          displayChanges.forEach((change) => {
            const diffItem = document.createElement("li");
            diffItem.textContent = change.text;
            diffItem.className = `diff-${change.type}`;
            diffList.appendChild(diffItem);
          });

          // Indiquer s'il y a plus de changements
          if (changes.length > 5) {
            const moreItem = document.createElement("li");
            moreItem.textContent = `... et ${
              changes.length - 5
            } autres modifications`;
            moreItem.className = "diff-more";
            diffList.appendChild(moreItem);
          }

          // Ajouter la liste des différences si elle contient des éléments
          if (diffList.children.length > 0) {
            diffContainer.appendChild(diffList);

            // Ajouter le conteneur des différences après la requête corrigée
            correctedQuery.parentNode.insertBefore(
              diffContainer,
              correctedQuery.nextElementSibling
            );
          }
        }
      }
    }
  }

  // Gestionnaire pour le bouton de copie de la requête corrigée
  if (copyCorrectedBtn) {
    copyCorrectedBtn.addEventListener("click", function () {
      if (correctedQuery && correctedQuery.textContent) {
        navigator.clipboard
          .writeText(correctedQuery.textContent)
          .then(() => {
            // Changer temporairement le texte du bouton pour indiquer le succès
            const originalText = this.textContent;
            this.textContent = "Copié !";
            setTimeout(() => {
              this.textContent = originalText;
            }, 1500);
          })
          .catch((err) => {
            console.error("Erreur lors de la copie: ", err);
          });
      }
    });
  }

  // Gestionnaire pour le bouton d'utilisation de la requête corrigée
  if (useCorrectedBtn) {
    useCorrectedBtn.addEventListener("click", function () {
      if (correctedQuery && correctedQuery.textContent) {
        // Passer à l'onglet générateur
        tabButtons.forEach((btn) => {
          if (btn.getAttribute("data-tab") === "generator") {
            btn.click();
          }
        });

        // Remplir le champ de texte avec une description de la requête corrigée
        if (sqlInput) {
          sqlInput.value =
            "Voici la requête SQL que je souhaite utiliser : " +
            correctedQuery.textContent;

          // Déclencher la génération
          if (generateSqlBtn) {
            generateSqlBtn.click();
          }
        }
      }
    });
  }
});
