// Sidebar Navigation
const navLinks = document.querySelectorAll(".nav-links li");
const sections = document.querySelectorAll(".section");
const themeToggle = document.getElementById("themeToggle");
const body = document.body;

// Main Elements
const urlInput = document.getElementById("urlInput");
const generateBtn = document.getElementById("generateBtn");
const loadingAnimation = document.getElementById("loadingAnimation");
const resultsContainer = document.getElementById("resultsContainer");
const keywordsList = document.getElementById("keywordsList");
const generatedContent = document.getElementById("generatedContent");
const copyContentBtn = document.getElementById("copyContent");
const downloadContentBtn = document.getElementById("downloadContent");

// History and Analytics
const historyList = document.getElementById("historyList");
const historySearch = document.getElementById("historySearch");
const historySort = document.getElementById("historySort");
const totalGenerations = document.getElementById("totalGenerations");
const popularKeywords = document.getElementById("popularKeywords");
const generationChart = document.getElementById("generationChart");

// Toast Notifications
const toastContainer = document.getElementById("toastContainer");

// Navigation
navLinks.forEach(link => {
    link.addEventListener("click", () => {
        document.querySelector(".nav-links li.active").classList.remove("active");
        link.classList.add("active");

        const target = link.getAttribute("data-section");
        sections.forEach(section => {
            section.classList.remove("active");
            if (section.id === target) {
                section.classList.add("active");

                // Load data for specific tabs
                if (target === "history") loadHistory();
                if (target === "analytics") loadAnalytics();
            }
        });
    });
});

// Theme Toggle
themeToggle.addEventListener("click", () => {
    if (body.getAttribute("data-theme") === "dark") {
        body.removeAttribute("data-theme");
    } else {
        body.setAttribute("data-theme", "dark");
    }
});

// Generate Content
generateBtn.addEventListener("click", async () => {
    const url = urlInput.value.trim();
    if (!url) {
        showToast("Please enter a valid URL", "error");
        return;
    }

    loadingAnimation.classList.remove("hidden");
    resultsContainer.classList.add("hidden");

    try {
        const response = await fetch("/generate_content", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url }),
        });

        if (!response.ok) throw new Error("Failed to generate content");

        const data = await response.json();
        if (data.error) {
            throw new Error(data.error);
        }

        displayResults(data);
        showToast("Content generated successfully", "success");
    } catch (error) {
        showToast(error.message, "error");
    } finally {
        loadingAnimation.classList.add("hidden");
    }
});

// Display Results
function displayResults(data) {
    // Keywords
    keywordsList.innerHTML = "";
    data.keywords.forEach(keyword => {
        const span = document.createElement("span");
        span.className = "keyword-tag";
        span.textContent = keyword;
        keywordsList.appendChild(span);
    });

    // Generated Content
    generatedContent.textContent = data.generated_content;

    resultsContainer.classList.remove("hidden");
}

// Load History
async function loadHistory() {
    try {
        const response = await fetch("/history");
        if (!response.ok) throw new Error("Failed to load history");

        const history = await response.json();
        historyList.innerHTML = "";

        if (history.length === 0) {
            historyList.innerHTML = "<p>No history available.</p>";
            return;
        }

        history.forEach(item => {
            const div = document.createElement("div");
            div.className = "history-item";
            div.innerHTML = `
                <p><strong>URL:</strong> ${item.url}</p>
                <p><strong>Generated Content:</strong></p>
                <p>${item.generated_content}</p>
            `;
            historyList.appendChild(div);
        });
    } catch (error) {
        showToast("Error loading history", "error");
    }
}

// Load Analytics
async function loadAnalytics() {
    try {
        const response = await fetch("/api/analytics");
        if (!response.ok) throw new Error("Failed to load analytics");

        const analytics = await response.json();

        // Total Generations
        totalGenerations.textContent = analytics.total_generations;

        // Popular Keywords
        popularKeywords.innerHTML = "";
        analytics.popular_keywords.forEach(keyword => {
            const li = document.createElement("li");
            li.textContent = keyword;
            popularKeywords.appendChild(li);
        });

        // Generation Timeline Chart
        const ctx = generationChart.getContext("2d");
        new Chart(ctx, {
            type: "line",
            data: {
                labels: analytics.generation_timeline.labels,
                datasets: [{
                    label: "Generations",
                    data: analytics.generation_timeline.data,
                    borderColor: "rgba(75, 192, 192, 1)",
                    backgroundColor: "rgba(75, 192, 192, 0.2)",
                }]
            }
        });
    } catch (error) {
        showToast("Error loading analytics", "error");
    }
}

// Copy Content
copyContentBtn.addEventListener("click", () => {
    navigator.clipboard.writeText(generatedContent.textContent)
        .then(() => showToast("Content copied to clipboard", "success"))
        .catch(() => showToast("Failed to copy content", "error"));
});

// Download Content
downloadContentBtn.addEventListener("click", () => {
    const blob = new Blob([generatedContent.textContent], { type: "text/plain" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "generated-content.txt";
    link.click();
});
// Assuming you have a script.js file linked in your HTML
document.addEventListener("DOMContentLoaded", () => {
    loadHistory();

    // Search functionality
    document.getElementById("historySearch").addEventListener("input", filterHistory);
    
    // Sort functionality (implement sort logic here)
    document.getElementById("historySort").addEventListener("click", sortHistory);
});

// Function to load history from the backend
async function loadHistory() {
    try {
        const response = await fetch("/history");
        if (!response.ok) throw new Error("Failed to load history");

        const history = await response.json();
        const historyList = document.getElementById("historyList");
        historyList.innerHTML = "";

        if (history.length === 0) {
            historyList.innerHTML = "<p>No history available.</p>";
            return;
        }

        history.forEach(item => {
            const div = document.createElement("div");
            div.className = "history-item";
            div.innerHTML = `
                <p><strong>URL:</strong> ${item.url}</p>
                <p><strong>Generated Content:</strong></p>
                <p>${item.generated_content}</p>
            `;
            historyList.appendChild(div);
        });
    } catch (error) {
        showToast("Error loading history", "error");
    }
}

// Function to filter history based on search input
function filterHistory() {
    const searchValue = document.getElementById("historySearch").value.toLowerCase();
    const historyItems = document.querySelectorAll(".history-item");

    historyItems.forEach(item => {
        const urlText = item.querySelector("strong").nextSibling.textContent.toLowerCase();
        item.style.display = urlText.includes(searchValue) ? "block" : "none";
    });
}

// Function to sort history (implement the logic as needed)
function sortHistory() {
    // Sorting logic goes here
}


// Toast Notifications
function showToast(message, type) {
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;

    toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}
