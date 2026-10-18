const API_BASE_URL = "http://127.0.0.1:8000";

document.getElementById("login-form").addEventListener("submit", async (event) => {
  // Stop the browser's default behavior of reloading the page on form submit.
  // We want to handle the submission ourselves with fetch() instead.
  event.preventDefault();

  const username = document.getElementById("username").value;
  const password = document.getElementById("password").value;
  const errorMsg = document.getElementById("login-error");
  errorMsg.style.display = "none";

  try {
    // IMPORTANT: OAuth2PasswordRequestForm (FastAPI's standard login form)
    // expects data as "application/x-www-form-urlencoded", NOT JSON.
    // URLSearchParams builds exactly that format for us.
    const body = new URLSearchParams();
    body.append("username", username);
    body.append("password", password);

    const response = await fetch(`${API_BASE_URL}/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: body,
    });

    if (!response.ok) {
      throw new Error("Invalid credentials");
    }

    const data = await response.json();
    // data looks like: { "access_token": "eyJhbGciOi...", "token_type": "bearer" }

    // Store the token in the browser so other pages (like index.html)
    // can reuse it without asking the user to log in again on every page.
    localStorage.setItem("access_token", data.access_token);

    // Redirect to the dashboard now that we're authenticated.
    window.location.href = "index.html";

  } catch (error) {
    console.error("Login failed:", error);
    errorMsg.style.display = "block";
  }
});
