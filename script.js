// =============================================================================
//  script.js — Portfolio Renderer
//
//  Project data is stored inline in PROJECT_DATA below AND in projects.json.
//  The portfolio agent updates both files simultaneously.
//
//  Why inline? So the site works when opened as a local file (file:// protocol),
//  without needing a web server. GitHub Pages serves over HTTP so both work.
// =============================================================================

// --- PROJECT DATA (updated by portfolio agent — do not edit manually) ---
// AGENT_DATA_START
const PROJECT_DATA = {
    "weather": {
        "title": "Automated Weather ML Pipeline (MLOps)",
        "short_desc": "Production-style ML workflow with automated retraining using GitHub Actions.",
        "full_desc": "Designed a production-style ML workflow with automated retraining using GitHub Actions. Includes data ingestion, preprocessing, model training, evaluation, and CI/CD automation across the full MLOps lifecycle.",
        "github": "https://github.com/Drylegend/mlops-weather-pipeline",
        "cover": "assets/weather_cover.jpg",
        "images": ["assets/weather_img1.jpg", "assets/weather_img2.jpg", "assets/weather_img3.jpg"],
        "tech_tags": ["Python", "GitHub Actions", "MLOps", "Scikit-learn", "CI/CD"],
        "category": "ML",
        "year": 2025
    },
    "spark": {
        "title": "Global Temperature Analysis (Apache Spark)",
        "short_desc": "Big Data analysis on 160+ years of climate data using PySpark.",
        "full_desc": "Big Data analysis on 160+ years of climate data using PySpark. Includes trend detection, anomaly analysis, and statistical insights across global temperature records. Research paper currently in progress.",
        "github": "https://github.com/Drylegend/Global_Temperature_Analysis_Apache_Spark",
        "cover": "assets/spark_cover.jpg",
        "images": ["assets/spark_img1.jpg", "assets/spark_img2.jpg", "assets/spark_img3.jpg", "assets/spark_img4.jpg", "assets/spark_img5.jpg"],
        "tech_tags": ["Python", "PySpark", "Apache Spark", "Big Data", "Climate Analysis"],
        "category": "Data",
        "year": 2025
    },
    "crime": {
        "title": "Big Data Crime Analytics Dashboard",
        "short_desc": "Interactive Power BI dashboard with slicers, KPIs, and multi-page crime insights.",
        "full_desc": "Power BI dashboard analyzing crime datasets using KPIs, slicers, and multi-page insights. Visualizes state-level pattern changes and yearly trends across large-scale crime data records.",
        "github": "https://github.com/Drylegend/cybercrime-dashboard",
        "cover": "assets/crime_cover.jpg",
        "images": ["assets/crime_img1.jpg", "assets/crime_img2.jpg", "assets/crime_img3.jpg", "assets/crime_img4.jpg", "assets/crime_img5.jpg"],
        "tech_tags": ["Power BI", "DAX", "Big Data", "Data Visualisation", "Analytics"],
        "category": "Data",
        "year": 2025
    },
    "speakapp": {
        "title": "SpeakApp – AI Speech & Pronunciation Assistant",
        "short_desc": "Cross-platform pronunciation evaluator using ASR and ML scoring.",
        "full_desc": "Cross-platform pronunciation evaluator using automatic speech recognition (ASR), phoneme analysis, and ML-based accuracy scoring. Provides real-time feedback and a UI for structured speech practice sessions.",
        "github": "https://github.com/Drylegend/SpeakApp",
        "cover": "assets/speakapp_cover.jpg",
        "images": ["assets/speakapp_img1.jpg", "assets/speakapp_img2.jpg"],
        "tech_tags": ["Python", "ASR", "NLP", "Machine Learning", "Speech Recognition"],
        "category": "ML",
        "year": 2025
    },
    "invest": {
        "title": "S&P 500 Neural Network Price Predictor",
        "short_desc": "Forecast S&P 500 closing prices 5 days ahead using a stacked LSTM network trained on Yahoo Finance historical data.",
        "full_desc": "A stacked LSTM neural network was built in Python with TensorFlow to forecast S&P 500 closing prices using historical daily OHLCV data sourced from Yahoo Finance. The architecture stacks two LSTM layers with dropout regularisation over a 60-day sequence window, trained with the Adam optimiser and mean squared error loss. The model achieves a mean absolute percentage error (MAPE) of less than 2% across held-out testing periods, delivering reliable 5-day-ahead price forecasts.",
        "github": "https://github.com/Drylegend/Smart-Investment-Advisor.git",
        "cover": "assets/invest_cover.jpg",
        "images": ["assets/invest_cover.jpg", "assets/invest_img1.jpg"],
        "tech_tags": ["Python", "TensorFlow", "Keras", "LSTM", "Matplotlib", "pandas", "Yahoo Finance API"],
        "category": "ML",
        "year": 2024
    }
};
// AGENT_DATA_END

// --- STATE ---
let projectDetails = {};
let slideIndex     = 0;
let slideInterval;
let autoScroll     = true;

// --- BOOTSTRAP ---
document.addEventListener("DOMContentLoaded", async () => {
    // Always use inline data first (works on file:// and HTTP)
    projectDetails = PROJECT_DATA;

    // Try to load projects.json for any updates not yet embedded
    // (e.g. when served via HTTP on GitHub Pages)
    try {
        const res = await fetch("projects.json?t=" + new Date().getTime());
        if (res.ok) {
            const data = await res.json();
            if (data.projects) {
                projectDetails = data.projects;
            }
        }
    } catch (_) {
        // fetch failed (file:// or offline) — use inline data, that's fine
    }

    renderCards(projectDetails);
    initFadeIn();
});

// --- CARD RENDERING ---
function renderCards(projects) {
    const container = document.querySelector(".project-container");
    if (!container) return;
    container.innerHTML = "";

    Object.entries(projects).forEach(([key, project]) => {
        const card = document.createElement("div");
        card.className = "project-card";
        card.innerHTML = `
            <img src="${project.cover}" alt="${escapeHtml(project.title)}" loading="lazy" />
            <h3>${escapeHtml(project.title)}</h3>
            <p>${escapeHtml(project.short_desc)}</p>
            <button onclick="openModal('${key}')">View More</button>
        `;
        container.appendChild(card);
    });
}

// --- MODAL ---
function openModal(projectKey) {
    clearInterval(slideInterval);
    autoScroll = true;

    const modal        = document.getElementById("modal");
    const modalContent = document.getElementById("modal-content");
    const project      = projectDetails[projectKey] || PROJECT_DATA[projectKey];
    if (!project) return;

    const images = project.images || (project.cover ? [project.cover] : []);

    let html = `
        <h2>${escapeHtml(project.title)}</h2>
        <p>${escapeHtml(project.full_desc || project.short_desc)}</p>
        ${project.github
            ? `<a class="modal-link" href="${project.github}" target="_blank" rel="noopener">GitHub Repo</a>`
            : ""}
        <div class="slideshow-container">
    `;

    images.forEach(img => {
        html += `<div class="mySlide fade-slide"><img src="${img}" loading="lazy"></div>`;
    });

    html += `
        <a class="prev" onclick="plusSlides(-1)">&#10094;</a>
        <a class="next" onclick="plusSlides(1)">&#10095;</a>
        </div>
        <br>
        <div class="dots-container">
    `;

    images.forEach((_, i) => {
        html += `<span class="dot" onclick="currentSlide(${i})"></span>`;
    });

    html += "</div>";

    modalContent.innerHTML = html;
    modal.style.display    = "block";
    initSlides();
}

// --- SLIDESHOW ---
function initSlides() {
    slideIndex = 0;
    showSlides();
    slideInterval = setInterval(() => {
        if (autoScroll) { slideIndex++; showSlides(); }
    }, 3000);
}

function plusSlides(n) { autoScroll = false; slideIndex += n; showSlides(); }
function currentSlide(n) { autoScroll = false; slideIndex = n; showSlides(); }

function showSlides() {
    const slides = document.getElementsByClassName("mySlide");
    const dots   = document.getElementsByClassName("dot");
    if (!slides.length) return;
    if (slideIndex >= slides.length) slideIndex = 0;
    if (slideIndex < 0) slideIndex = slides.length - 1;

    Array.from(slides).forEach(s => s.style.display = "none");
    Array.from(dots).forEach(d => d.classList.remove("active-dot"));

    slides[slideIndex].style.display = "block";
    if (dots[slideIndex]) dots[slideIndex].classList.add("active-dot");
}

// --- MODAL CONTROLS ---
function closeModal() {
    clearInterval(slideInterval);
    document.getElementById("modal").style.display = "none";
}

function openResume() {
    document.getElementById("resumeModal").style.display = "block";
}

function closeResume() {
    document.getElementById("resumeModal").style.display = "none";
}

// Close modal on backdrop click
window.addEventListener("click", e => {
    const modal = document.getElementById("modal");
    if (e.target === modal) closeModal();
});

// --- FADE-IN ANIMATION ---
function initFadeIn() {
    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) entry.target.classList.add("visible");
        });
    }, { threshold: 0.1 });

    document.querySelectorAll(".fade-in").forEach(el => observer.observe(el));
}

// --- UTILITY ---
function escapeHtml(str) {
    if (!str) return "";
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}