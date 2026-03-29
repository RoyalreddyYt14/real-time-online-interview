const searchInput = document.getElementById("searchInput");
const statusFilter = document.getElementById("statusFilter");

function filterCandidates() {
  const searchTerm = (searchInput.value || "").toLowerCase();
  const status = statusFilter ? statusFilter.value : "all";

  document.querySelectorAll("#candidateTable tbody tr").forEach(function(row){
    const name = (row.cells[1].textContent || "").toLowerCase();
    const statusCell = row.cells[8];
    const rowStatus = statusCell ? (statusCell.textContent || "").trim().toLowerCase() : "";

    const matchesSearch = name.includes(searchTerm);
    const matchesStatus = (status === "all") ||
      (status === "completed" && rowStatus === "completed") ||
      (status === "in-progress" && rowStatus === "in progress");

    row.style.display = (matchesSearch && matchesStatus) ? "" : "none";
  });
}

if (searchInput) {
  searchInput.addEventListener("keyup", filterCandidates);
}

if (statusFilter) {
  statusFilter.addEventListener("change", filterCandidates);
}

function exportTable(){
  let table = document.getElementById("candidateTable").outerHTML;
  let data = new Blob([table], {type:"application/vnd.ms-excel"});
  let url = URL.createObjectURL(data);
  let a = document.createElement("a");
  a.href = url;
  a.download = "candidate_list.xls";
  a.click();
  URL.revokeObjectURL(url);
}

const exportBtn = document.getElementById("exportButton");
if (exportBtn) {
  exportBtn.addEventListener("click", exportTable);
}

function sortTable(columnIndex, numeric) {
  const table = document.getElementById("candidateTable");
  const tbody = table.querySelector("tbody");
  const rows = Array.from(tbody.querySelectorAll("tr"));

  const header = table.querySelector(`th[data-sort='${columnIndex}']`);
  const currentOrder = header.classList.contains("asc") ? "asc" : header.classList.contains("desc") ? "desc" : null;
  const nextOrder = currentOrder === "asc" ? "desc" : "asc";

  table.querySelectorAll("th.sortable").forEach((th) => th.classList.remove("asc", "desc"));
  header.classList.add(nextOrder);

  const sortedRows = rows.sort((a, b) => {
    const aText = (a.cells[columnIndex].textContent || "").trim();
    const bText = (b.cells[columnIndex].textContent || "").trim();

    if (numeric) {
      const aVal = parseFloat(aText) || 0;
      const bVal = parseFloat(bText) || 0;
      return nextOrder === "asc" ? aVal - bVal : bVal - aVal;
    }

    if (aText.toLowerCase() === bText.toLowerCase()) {
      return 0;
    }
    return nextOrder === "asc" ? aText.localeCompare(bText) : bText.localeCompare(aText);
  });

  sortedRows.forEach((row) => tbody.appendChild(row));
}

const sortableHeaders = document.querySelectorAll("#candidateTable th.sortable");
sortableHeaders.forEach((header) => {
  const idx = Number(header.dataset.sort);
  const numeric = [0, 4, 5, 6, 7].includes(idx);
  header.addEventListener("click", function() {
    sortTable(idx, numeric);
  });
});

