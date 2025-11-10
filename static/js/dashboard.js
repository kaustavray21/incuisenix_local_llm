document.addEventListener("DOMContentLoaded", function () {
  const courseLinks = document.querySelectorAll(".course-link");
  const welcomeContainer = document.getElementById("welcome-message-container");
  const roadmapContainer = document.getElementById("roadmap-container");

  courseLinks.forEach((link) => {
    link.addEventListener("click", async function (event) {
      event.preventDefault();

      // Deactivate other links
      courseLinks.forEach((l) => l.classList.remove("active"));
      // Activate clicked link
      this.classList.add("active");

      const courseId = this.getAttribute("data-course-id");

      // Hide welcome, show roadmap with loading indicator
      welcomeContainer.style.display = "none";
      roadmapContainer.style.display = "block";
      roadmapContainer.innerHTML = `
            <div class="d-flex justify-content-center p-5">
                <div class="spinner-border" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
            `;

      try {
        // Fetch roadmap data
        const response = await fetch(`api/engine/roadmap/${courseId}/`);
        if (!response.ok) {
          throw new Error("Failed to load course data.");
        }
        const data = await response.json();

        // Build roadmap HTML (link to the first video)
        const firstVideoUrl = `/courses/${courseId}/`;
        let roadmapHTML = `
                <div class="row justify-content-center mb-4"> 
                    <div class="col-lg-8">
                        <div class="card shadow border-0 text-center">
                            <div class="card-body p-5">
                                <h2 class="display-5 fw-bold">Roadmap to ${data.title}</h2>
                                <p class="lead text-muted mt-3">Your learning journey for this course is ready. Press the button below to begin.</p>
                                <a href="${firstVideoUrl}" class="btn btn-custom-in btn-lg mt-4">Start Learning</a>
                            </div>
                        </div>
                    </div>
                </div>
                `; // Note: Fixed typo 'classrow' to 'class="row ..."'

        // Display roadmap
        roadmapContainer.innerHTML = roadmapHTML;
      } catch (error) {
        console.error("Error fetching roadmap:", error);
        roadmapContainer.innerHTML =
          '<div class="alert alert-danger">Could not load the course roadmap. Please try again.</div>';
      }
    });
  });
});