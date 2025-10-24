import { getCookie } from "./assistant-utils.js";

async function fetchAPI(url, options = {}) {
  const csrftoken = getCookie("csrftoken");

  const headers = {
    "X-CSRFToken": csrftoken,
    ...options.headers,
  };

  if (options.body instanceof FormData) {
  } else if (
    typeof options.body === "object" &&
    options.body !== null &&
    !(options.body instanceof FormData)
  ) {
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

  if (response.status === 204 || options.method === "POST") {
    const text = await response.text();
    return text ? JSON.parse(text) : { ok: true, status: response.status };
  }

  return response.json();
}

export function addNote(videoId, formData) {
  return fetchAPI(`/api/notes/add/${videoId}/`, {
    method: "POST",
    body: formData,
  });
}

export function editNote(noteId, formData) {
  return fetchAPI(`/api/notes/edit/${noteId}/`, {
    method: "POST",
    body: formData,
  });
}

export function deleteNote(noteId) {
  return fetchAPI(`/api/notes/delete/${noteId}/`, {
    method: "POST",
  });
}
