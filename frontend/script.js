document.addEventListener('DOMContentLoaded', function() {
    const ipForm = document.getElementById('ipForm');
    const ipTable = document.getElementById('ipTable').getElementsByTagName('tbody')[0];

    // Функция для обновления таблицы
    function updateTable(data) {
        ipTable.innerHTML = ''; // Очищаем таблицу
        data.forEach(ipInfo => {
            const row = ipTable.insertRow();
            // Добавляем класс в зависимости от статуса
            if (ipInfo.packet_loss === 100) {
                row.classList.add('red'); // Красный, если нет ответа
            } else {
                row.classList.add('green'); // Зеленый, если есть ответ
            }
            row.insertCell().textContent = ipInfo.ip;
            row.insertCell().textContent = ipInfo.ping || 'N/A';
            row.insertCell().textContent = ipInfo.packet_loss || 'N/A';
            row.insertCell().textContent = ipInfo.packet_received || 'N/A';
            row.insertCell().textContent = ipInfo.last_successful_ping || 'N/A';
            const actionsCell = row.insertCell();
            actionsCell.innerHTML = `
                <button onclick="editIP('${ipInfo.ip}')">Edit</button>
                <button onclick="deleteIP('${ipInfo.ip}')">Delete</button>
            `;
        });
    }

    // Подключение к WebSocket
    const ws = new WebSocket(`ws://${window.location.host}/ws`);

    ws.onopen = function() {
        console.log("WebSocket connection established");
    };

    ws.onmessage = function(event) {
        console.log("Data received:", event.data);  // Логирование
        const data = JSON.parse(event.data);
        updateTable(data);
    };

    ws.onerror = function(error) {
        console.error("WebSocket error:", error);
    };

    ws.onclose = function() {
        console.log("WebSocket connection closed");
    };

// Функция для валидации IP-адреса
function validateIP(ip) {
    const ipRegex = /^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)\.?\b){4}$/;
    return ipRegex.test(ip);
}

// Добавление нового IP-адреса
ipForm.addEventListener('submit', function(event) {
    event.preventDefault();
    const ip = document.getElementById('ipInput').value;

    if (!validateIP(ip)) {
        alert("Invalid IP address format");
        return;
    }

    fetch('/ip/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ip: ip }),
    })
    .then(response => response.json())
    .then(() => {
        document.getElementById('ipInput').value = ''; // Очищаем поле ввода
    });
});

    // Функция для редактирования IP-адреса
    window.editIP = function(old_ip) {
        const new_ip = prompt("Enter new IP address:", old_ip);
        if (!validateIP(new_ip)) {
            alert("Invalid IP address format");
            return;
            }
        if (new_ip) {
            fetch(`/ip/${old_ip}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ ip: new_ip, ping: null, packet_loss: null, packet_received: null, last_successful_ping: null }),
            })
            .then(response => response.json())
            .then(() => {
                alert("IP address updated successfully!");
            });
        }
    };

    // Функция для удаления IP-адреса
    window.deleteIP = function(ip) {
        if (confirm("Are you sure you want to delete this IP address?")) {
            fetch(`/ip/${ip}`, {
                method: 'DELETE',
            })
            .then(() => {
                alert("IP address deleted successfully!");
            });
        }
    };

    // Экспорт данных в CSV
    window.exportCSV = function() {
        window.location.href = '/export-csv/';
    };

    // Импорт данных из CSV
    document.getElementById('csvFileInput').addEventListener('change', function(event) {
        const file = event.target.files[0];
        if (file) {
            const formData = new FormData();
            formData.append('file', file);

            fetch('/import-csv/', {
                method: 'POST',
                body: formData,
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
                window.location.reload();  // Перезагружаем страницу для обновления данных
            });
        }
    });

    // Сортировка таблицы
    let sortDirection = {};  // Хранит направление сортировки для каждого столбца

    window.sortTable = function(column) {
        const table = document.getElementById('ipTable');
        const tbody = table.getElementsByTagName('tbody')[0];
        const rows = Array.from(tbody.getElementsByTagName('tr'));

        // Определяем направление сортировки
        if (!sortDirection[column]) {
            sortDirection[column] = 'asc';
        } else {
            sortDirection[column] = sortDirection[column] === 'asc' ? 'desc' : 'asc';
        }

        rows.sort((a, b) => {
            const aValue = a.getElementsByTagName('td')[getColumnIndex(column)].textContent;
            const bValue = b.getElementsByTagName('td')[getColumnIndex(column)].textContent;

            if (column === 'ip' || column === 'last_successful_ping') {
                // Сортировка по строке
                return sortDirection[column] === 'asc' ? aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
            } else {
                // Сортировка по числу
                return sortDirection[column] === 'asc' ? parseFloat(aValue) - parseFloat(bValue) : parseFloat(bValue) - parseFloat(aValue);
            }
        });

        // Очищаем таблицу и добавляем отсортированные строки
        tbody.innerHTML = '';
        rows.forEach(row => tbody.appendChild(row));
    };

    // Получение индекса столбца по его названию
    function getColumnIndex(column) {
        const headers = Array.from(document.querySelectorAll('#ipTable th'));
        return headers.findIndex(header => header.getAttribute('onclick').includes(column));
    }
});