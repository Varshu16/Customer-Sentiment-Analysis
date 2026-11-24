
const navButtons = document.querySelectorAll(".nav-button");
const sections = document.querySelectorAll(".section");

let sentimentChart = null;

// Switch between Single Review and Dataset Analysis
navButtons.forEach(button => {
    button.addEventListener("click", () => {
        navButtons.forEach(item => item.classList.remove("active"));
        sections.forEach(item => item.classList.remove("active"));

        button.classList.add("active");
        document.getElementById(button.dataset.tab).classList.add("active");
    });
});


// Single review prediction
document.getElementById("predictButton").addEventListener("click", async () => {
    const review = document.getElementById("reviewInput").value.trim();
    const resultBox = document.getElementById("singleResult");

    resultBox.classList.remove("hidden");

    if (!review) {
        resultBox.textContent = "Please enter a review.";
        return;
    }

    resultBox.textContent = "Predicting...";

    try {
        const response = await fetch("/predict", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ review })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Prediction failed");
        }

        resultBox.textContent =
            "Predicted Sentiment: " + data.predicted_sentiment;

    } catch (error) {
        resultBox.textContent = error.message;
    }
});


// Select All and Deselect All
document.getElementById("selectAll").addEventListener("click", () => {
    document.querySelectorAll(".options input").forEach(box => {
        box.checked = true;
    });
});

document.getElementById("deselectAll").addEventListener("click", () => {
    document.querySelectorAll(".options input").forEach(box => {
        box.checked = false;
    });
});


// Upload dataset and display its columns
document.getElementById("loadColumns").addEventListener("click", async () => {
    const file = document.getElementById("datasetFile").files[0];
    const error = document.getElementById("errorMessage");

    error.textContent = "";

    if (!file) {
        error.textContent = "Please select a CSV or Excel file.";
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch("/columns", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Could not read file");
        }

        const select = document.getElementById("reviewColumn");
        select.innerHTML = "";

        data.columns.forEach(column => {
            const option = document.createElement("option");
            option.value = column;
            option.textContent = column;
            select.appendChild(option);
        });

        document.getElementById("columnSection").classList.remove("hidden");

    } catch (err) {
        error.textContent = err.message;
    }
});


// Generate selected dataset analysis
document.getElementById("analyzeButton").addEventListener("click", async () => {
    const file = document.getElementById("datasetFile").files[0];
    const column = document.getElementById("reviewColumn").value;

    const options = [...document.querySelectorAll(".options input:checked")]
        .map(box => box.value);

    const error = document.getElementById("errorMessage");
    error.textContent = "";

    if (!file || !column || options.length === 0) {
        error.textContent =
            "Upload a file, select a review column and choose at least one option.";
        return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("review_column", column);

    options.forEach(option => formData.append("options", option));

    const analyzeButton = document.getElementById("analyzeButton");
    analyzeButton.textContent = "Analyzing...";
    analyzeButton.disabled = true;

    try {
        const response = await fetch("/analyze", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Analysis failed");
        }

        showResults(data);

    } catch (err) {
        error.textContent = err.message;
    } finally {
        analyzeButton.textContent = "Generate Analysis";
        analyzeButton.disabled = false;
    }
});


// Custom Chart.js plugin: count labels outside the donut
const outsideCountLabels = {
    id: "outsideCountLabels",

    afterDatasetsDraw(chart) {
        const { ctx } = chart;
        const dataset = chart.data.datasets[0];
        const meta = chart.getDatasetMeta(0);

        ctx.save();

        meta.data.forEach((arc, index) => {
            const value = dataset.data[index];

            if (value === 0) return;

            const angle = (arc.startAngle + arc.endAngle) / 2;

            const centerX = arc.x;
            const centerY = arc.y;

            const startRadius = arc.outerRadius + 3;
            const endRadius = arc.outerRadius + 22;

            const startX = centerX + Math.cos(angle) * startRadius;
            const startY = centerY + Math.sin(angle) * startRadius;

            const endX = centerX + Math.cos(angle) * endRadius;
            const endY = centerY + Math.sin(angle) * endRadius;

            const direction = Math.cos(angle) >= 0 ? 1 : -1;
            const lineEndX = endX + direction * 24;

            // Connector line
            ctx.beginPath();
            ctx.moveTo(startX, startY);
            ctx.lineTo(endX, endY);
            ctx.lineTo(lineEndX, endY);

            ctx.strokeStyle = "#392D43";
            ctx.lineWidth = 1.5;
            ctx.stroke();

            // Count label
            ctx.fillStyle = "#392D43";
            ctx.font = "bold 15px Arial";
            ctx.textAlign = direction === 1 ? "left" : "right";
            ctx.textBaseline = "middle";

            ctx.fillText(
                value,
                lineEndX + direction * 5,
                endY
            );
        });

        ctx.restore();
    }
};


// Display selected analysis results
function showResults(data) {
    const results = document.getElementById("results");
    results.classList.remove("hidden");

    document.getElementById("totalResult").classList.add("hidden");
    document.getElementById("countResult").classList.add("hidden");
    document.getElementById("chartResult").classList.add("hidden");

    // Total reviews
    if (data.total !== undefined) {
        document.getElementById("totalResult").classList.remove("hidden");
        document.getElementById("totalValue").textContent = data.total;
    }

    // Sentiment counts
    if (data.counts) {
        document.getElementById("countResult").classList.remove("hidden");

        document.getElementById("positiveCount").textContent =
            data.counts.Positive;

        document.getElementById("neutralCount").textContent =
            data.counts.Neutral;

        document.getElementById("negativeCount").textContent =
            data.counts.Negative;
    }

    // Donut chart
    if (data.chart) {
        document.getElementById("chartResult").classList.remove("hidden");

        if (sentimentChart) {
            sentimentChart.destroy();
        }

        const chartCanvas = document.getElementById("sentimentChart");

        sentimentChart = new Chart(chartCanvas, {
            type: "doughnut",

            data: {
                labels: ["Positive", "Neutral", "Negative"],

                datasets: [{
                    data: [
                        data.chart.Positive,
                        data.chart.Neutral,
                        data.chart.Negative
                    ],

                    backgroundColor: [
                        "#B9A7D8",
                        "#E9A5A0",
                        "#8E7DB5"
                    ],

                    borderColor: "#FFFFFF",
                    borderWidth: 3,
                    hoverOffset: 8
                }]
            },

            plugins: [outsideCountLabels],

            options: {
                responsive: true,
                maintainAspectRatio: false,

                // Space for labels outside the donut
                layout: {
                    padding: {
                        top: 35,
                        bottom: 35,
                        left: 45,
                        right: 45
                    }
                },

                cutout: "55%",

                plugins: {
                    legend: {
                        display: true,
                        position: "top",

                        labels: {
                            usePointStyle: true,
                            pointStyle: "rectRounded",
                            padding: 22,
                            color: "#392D43",
                            font: {
                                size: 14,
                                weight: "600"
                            }
                        }
                    },

                    tooltip: {
                        callbacks: {
                            label(context) {
                                return `${context.label}: ${context.raw} reviews`;
                            }
                        }
                    }
                }
            }
        });
    }

    results.scrollIntoView({ behavior: "smooth" });
}
