// static/js/modules/note-api.js

// Import the correct getCookie function
import { getCookie } from "./assistant-utils.js";

/**
 * A reusable fetch wrapper that adds the CSRF token.
 * @param {string} url - The API endpoint URL.
 * @param {object} options - The options for the fetch call (method, body, etc.)
 * @returns {Promise<object>} - The JSON response from the server.
 */
async function fetchAPI(url, options = {}) {
  // Get a fresh token for every request
  const csrftoken = getCookie("csrftoken");

  const headers = {
    "X-CSRFToken": csrftoken,
    ...options.headers,
  };

  // Do not set Content-Type for FormData; the browser does it.
  if (options.body instanceof FormData) {
    // Let the browser set the Content-Type with the correct boundary
  } else if (
    typeof options.body === "object" &&
    options.body !== null &&
    !(options.body instanceof FormData)
  ) {
    // Default to JSON if it's an object but not FormData
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    let error;
    try {
      error = await response.json();
    } catch (e) {
      error = { message: response.statusText };
    }
    throw new Error(error.message || "Something went wrong");
  }

  // Handle successful deletion (which might not return JSON)
  if (response.status === 204 || options.method === "POST") {
    // For delete, response.ok is enough. For edit/add, we expect JSON.
    // Let's try to parse JSON, but gracefully handle no content.
    const text = await response.text();
    return text ? JSON.parse(text) : { ok: true, status: response.status };
  }

  return response.json();
}

/**
 * Saves a new note to the server.
 * @param {string} videoId - The ID of the video.
 * @param {FormData} formData - The form data containing the note.
 * @returns {Promise<object>}
 */
export function addNote(videoId, formData) {
  return fetchAPI(`/api/notes/add/${videoId}/`, {
    method: "POST",
    body: formData,
  });
}

/**
 * Updates an existing note on the server.
 * @param {string} noteId - The ID of the note to edit.
 * @param {string} newTitle - The updated title.
 *.
 * @param {string} newContent - The updated content.
 * @returns {Promise<object>}
 */
export function editNote(noteId, newTitle, newContent) {
  // *** THIS IS THE FIX ***
  // The backend view expects FormData, just like the add_note view.
  const formData = new FormData();
  formData.append("title", newTitle);
  formData.append("content", newContent);

  return fetchAPI(`/api/notes/edit/${noteId}/`, {
    method: "POST",
    body: formData,
  });
}

/**
 * Deletes a note from the server.
 * @param {string} noteId - The ID of the note to delete.
 * @returns {Promise<object>}
 */
export function deleteNote(noteId) {
  return fetchAPI(`/api/notes/delete/${noteId}/`, {
    method: "POST",
  });
}