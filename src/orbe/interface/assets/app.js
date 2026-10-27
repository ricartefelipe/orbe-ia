const fileInput = document.querySelector("#file");
const fileName = document.querySelector("#file-name");
const uploadForm = document.querySelector("#upload-form");
const uploadStatus = document.querySelector("#upload-status");
const queryForm = document.querySelector("#query-form");
const questionInput = document.querySelector("#question");
const answer = document.querySelector("#answer");
const citations = document.querySelector("#citations");
const documentsList = document.querySelector("#documents");
const documentsEmpty = document.querySelector("#documents-empty");

fileInput.addEventListener("change", () => {
  const chosen = fileInput.files && fileInput.files[0];
  fileName.textContent = chosen ? chosen.name : "Nenhum arquivo escolhido";
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clear(citations);
  answer.textContent = "";
  const chosen = fileInput.files && fileInput.files[0];
  if (!chosen) {
    uploadStatus.textContent = "Escolha um arquivo.";
    return;
  }
  const body = new FormData();
  body.append("file", chosen, chosen.name);
  uploadStatus.textContent = "Indexando…";
  const response = await fetch("/api/v1/documents", { method: "POST", body });
  const payload = await readJson(response);
  if (!response.ok) {
    uploadStatus.textContent = detailOf(payload);
    return;
  }
  const duplicate = payload.duplicate ? " Arquivo já indexado." : "";
  uploadStatus.textContent = "Indexado: " + payload.filename + "." + duplicate;
  void loadDocuments();
});

queryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clear(citations);
  answer.textContent = "Consultando…";
  const response = await fetch("/api/v1/queries", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: questionInput.value }),
  });
  const payload = await readJson(response);
  if (!response.ok) {
    answer.textContent = detailOf(payload);
    return;
  }
  answer.textContent = payload.answer || "";
  const items = Array.isArray(payload.citations) ? payload.citations : [];
  items.forEach((item) => {
    const block = document.createElement("article");
    block.className = "citation";
    const title = document.createElement("h3");
    title.textContent = item.filename || "";
    const where = document.createElement("p");
    where.className = "where";
    where.textContent = "posição " + String(item.position) + " · distância " + String(item.distance);
    const excerpt = document.createElement("p");
    excerpt.textContent = item.content || "";
    block.append(title, where, excerpt);
    citations.append(block);
  });
});

async function loadDocuments() {
  const response = await fetch("/api/v1/documents");
  const payload = await readJson(response);
  const items = Array.isArray(payload) ? payload : [];
  clear(documentsList);
  documentsEmpty.hidden = items.length > 0;
  items.forEach((item) => {
    const row = document.createElement("li");
    row.className = "document";
    const name = document.createElement("span");
    name.className = "doc-name";
    name.textContent = item.filename || "";
    const count = document.createElement("span");
    count.className = "doc-count";
    count.textContent = String(item.chunk_count) + " trechos";
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "doc-remove";
    remove.textContent = "Excluir";
    remove.addEventListener("click", () => void deleteDocument(item.id, item.filename));
    row.append(name, count, remove);
    documentsList.append(row);
  });
}

async function deleteDocument(id, name) {
  if (!window.confirm('Excluir "' + name + '" do índice?')) {
    return;
  }
  const response = await fetch("/api/v1/documents/" + encodeURIComponent(id), {
    method: "DELETE",
  });
  if (!response.ok) {
    const payload = await readJson(response);
    uploadStatus.textContent = detailOf(payload);
    return;
  }
  uploadStatus.textContent = "Excluído: " + name + ".";
  void loadDocuments();
}

function clear(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

void loadDocuments();

async function readJson(response) {
  const text = await response.text();
  if (!text) {
    return {};
  }
  try {
    return JSON.parse(text);
  } catch (_error) {
    return {};
  }
}

function detailOf(payload) {
  if (payload && typeof payload.detail === "string" && payload.detail) {
    return payload.detail;
  }
  return "A mesa não conseguiu concluir a operação.";
}
