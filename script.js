// --- PROJECT DETAILS ---
const projectDetails = {
    weather: {
        title: "Automated Weather ML Pipeline (MLOps)",
        description: `
            Designed a production-style ML workflow with automated retraining using GitHub Actions.
            Includes data ingestion, preprocessing, model training, evaluation, and CI/CD automation.
        `,
        github: "https://github.com/Drylegend/mlops-weather-pipeline",
        images: [
            "assets/weather_img1.jpg",
            "assets/weather_img2.jpg",
            "assets/weather_img3.jpg"
            
            
        ]
    },

    spark: {
        title: "Global Temperature Analysis (Apache Spark)",
        description: `
            Big Data Analysis on 160+ years of climate data using PySpark. 
            Includes trend detection, anomaly analysis, and statistical insights.
            Research paper is in progress.
        `,
        github: "https://github.com/Drylegend/Global_Temperature_Analysis_Apache_Spark",
        images: [
            "assets/spark_img1.jpg",
            "assets/spark_img2.jpg",
            "assets/spark_img3.jpg",
            "assets/spark_img4.jpg",
            "assets/spark_img5.jpg"
        ]
    },

    crime: {
        title: "Big Data Crime Analytics Dashboard",
        description: `
            Power BI dashboard analyzing crime datasets using KPIs, slicers, and multi-page insights.
            Visualizes state-level pattern changes and yearly trends.
        `,
        github: "https://github.com/Drylegend/cybercrime-dashboard",
        images: [
            "assets/crime_img1.jpg",
            "assets/crime_img2.jpg",
            "assets/crime_img3.jpg",
            "assets/crime_img4.jpg",
            "assets/crime_img5.jpg"
        ]
    },

    speakapp: {
        title: "SpeakApp – AI Speech & Pronunciation Assistant",
        description: `
            Cross-platform pronunciation evaluator using ASR, phoneme analysis, and ML scoring.
            Provides accuracy results, feedback, and UI for speech practice.
        `,
        github: "https://github.com/Drylegend/SpeakApp",
        images: [
            "assets/speakapp_img1.jpg",
            "assets/speakapp_img2.jpg"
        ]
    }
};

// --- MODAL FUNCTION ---
let slideIndex = 0;
let slideInterval;
let autoScroll = true;

function openModal(projectKey) {
    clearInterval(slideInterval);
    autoScroll = true;

    const modal = document.getElementById("modal");
    const modalContent = document.getElementById("modal-content");
    const project = projectDetails[projectKey];

    // Build modal structure
    let html = `
        <h2>${project.title}</h2>
        <p>${project.description}</p>
        ${project.github ? `<a class="modal-link" href="${project.github}" target="_blank">GitHub Repo</a>` : ""}
        
        <div class="slideshow-container">
    `;

    // Slides
    project.images.forEach((img, i) => {
        html += `
            <div class="mySlide fade-slide">
                <img src="${img}">
            </div>
        `;
    });

    // Arrows
    html += `
        <a class="prev" onclick="plusSlides(-1)">&#10094;</a>
        <a class="next" onclick="plusSlides(1)">&#10095;</a>
        </div>
        <br>
        <div class="dots-container">
    `;

    // Dot indicators
    project.images.forEach((_, i) => {
        html += `<span class="dot" onclick="currentSlide(${i})"></span>`;
    });

    html += `</div>`;

    modalContent.innerHTML = html;
    modal.style.display = "block";

    initSlides();
}

function initSlides() {
    slideIndex = 0;
    showSlides();

    slideInterval = setInterval(() => {
        if (autoScroll) {
            slideIndex++;
            showSlides();
        }
    }, 3000);
}

function plusSlides(n) {
    autoScroll = false;  
    slideIndex += n;
    showSlides();
}

function currentSlide(n) {
    autoScroll = false;  
    slideIndex = n;
    showSlides();
}

function showSlides() {
    const slides = document.getElementsByClassName("mySlide");
    const dots = document.getElementsByClassName("dot");

    if (!slides.length) return;

    if (slideIndex >= slides.length) slideIndex = 0;
    if (slideIndex < 0) slideIndex = slides.length - 1;

    // Hide all slides
    Array.from(slides).forEach(slide => slide.style.display = "none");

    // Remove active class from dots
    Array.from(dots).forEach(dot => dot.classList.remove("active-dot"));

    // Show current slide
    slides[slideIndex].style.display = "block";
    dots[slideIndex].classList.add("active-dot");
}

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