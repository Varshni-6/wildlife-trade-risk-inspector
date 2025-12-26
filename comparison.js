fetch("http://localhost:5000/get_comparison_data")
    .then(res => res.json())
    .then(data => {
        if (!data || data.length === 0) return;

        const headerRow = document.getElementById("tableHeader");
        const body = document.getElementById("tableBody");

        const columns = Object.keys(data[0]);

        // Build table header
        columns.forEach(col => {
            const th = document.createElement("th");
            th.textContent = col.replace(/_/g, " ").toUpperCase();
            headerRow.appendChild(th);
        });

        // Build table body
        data.forEach(row => {
            const tr = document.createElement("tr");
            columns.forEach(col => {
                const td = document.createElement("td");
                td.textContent = row[col];
                tr.appendChild(td);
            });
            body.appendChild(tr);
        });
    })
    .catch(err => console.error("Comparison fetch error:", err));
