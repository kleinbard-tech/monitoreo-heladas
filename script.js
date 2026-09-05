let grafico = null;

// Ejecutar al cargar la página
document.addEventListener("DOMContentLoaded", () => {
    obtenerDatosServidor();
    // Consultar nuevos datos cada 5 segundos
    setInterval(obtenerDatosServidor, 5000);
});

async function obtenerDatosServidor() {
    try {
        // Obtener datos actuales
        const resDatos = await fetch("/datos");
        const datosActuales = await resDatos.json();

        // Obtener historial completo
        const resHistorial = await fetch("/historial");
        const historial = await resHistorial.json();

        actualizarTarjetas(datosActuales);
        actualizarTabla(historial);
        actualizarGrafico(historial);

    } catch (error) {
        console.error("Error al obtener datos del servidor:", error);
    }
}

function actualizarTarjetas(datos) {
    const contenedor = document.getElementById("tarjetas-nodos");
    const nodosKeys = Object.keys(datos);

    if (nodosKeys.length === 0) {
        contenedor.innerHTML = `<p class="cargando">Esperando primera lectura de los sensores...</p>`;
        return;
    }

    contenedor.innerHTML = "";

    nodosKeys.forEach(nodoId => {
        const reg = datos[nodoId];
        const esAlerta = reg.estado && reg.estado.toUpperCase().includes("ALERTA");
        const claseEstado = esAlerta ? "alerta" : "normal";

        const html = `
            <div class="tarjeta-nodo ${claseEstado}">
                <div class="nodo-titulo">Nodo #${reg.nodo} - ${reg.estado}</div>
                <div class="metricas">
                    <div><strong>T. DS18B20:</strong> ${reg.temperaturaDS} °C</div>
                    <div><strong>T. DHT22:</strong> ${reg.temperaturaDHT} °C</div>
                    <div><strong>Humedad:</strong> ${reg.humedad} %</div>
                    <div><strong>Punto Rocío:</strong> ${reg.puntoRocio} °C</div>
                </div>
                <div style="font-size: 0.75rem; color: #666; margin-top: 10px;">
                    Última act: ${reg.fechaHora}
                </div>
            </div>
        `;
        contenedor.innerHTML += html;
    });
}

function actualizarTabla(historial) {
    const tbody = document.getElementById("tabla-historial");

    if (historial.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="cargando">Sin datos registrados aún.</td></tr>`;
        return;
    }

    // Mostrar los registros ordenados desde el más reciente arriba
    const historialInvertido = [...historial].reverse();

    tbody.innerHTML = historialInvertido.map(reg => {
        const esAlerta = reg.estado && reg.estado.toUpperCase().includes("ALERTA");
        const badgeClass = esAlerta ? "badge-alerta" : "badge-normal";

        return `
            <tr>
                <td>${reg.fechaHora}</td>
                <td>#${reg.nodo}</td>
                <td>${reg.medicion}</td>
                <td>${reg.temperaturaDS} °C</td>
                <td>${reg.temperaturaDHT} °C</td>
                <td>${reg.humedad} %</td>
                <td>${reg.puntoRocio} °C</td>
                <td><span class="${badgeClass}">${reg.estado}</span></td>
            </tr>
        `;
    }).join("");
}

function actualizarGrafico(historial) {
    if (historial.length === 0) return;

    // Ajustar dinámicamente el ancho del canvas: 40px por cada punto (mínimo 600px)
    const anchoDinamico = Math.max(600, historial.length * 40);
    const canvas = document.getElementById("graficoTemperatura");
    canvas.style.width = `${anchoDinamico}px`;

    const etiquetas = historial.map(r => r.fechaHora.split(" ")[1] || r.fechaHora);
    const tempDS = historial.map(r => r.temperaturaDS);
    const puntoRocio = historial.map(r => r.puntoRocio);

    if (!grafico) {
        const ctx = canvas.getContext("2d");
        grafico = new Chart(ctx, {
            type: "line",
            data: {
                labels: etiquetas,
                datasets: [
                    {
                        label: "Temp. DS18B20 (°C)",
                        data: tempDS,
                        borderColor: "#d9534f",
                        backgroundColor: "rgba(217, 83, 79, 0.1)",
                        fill: true,
                        tension: 0.3
                    },
                    {
                        label: "Punto de Rocío (°C)",
                        data: puntoRocio,
                        borderColor: "#0275d8",
                        backgroundColor: "rgba(2, 117, 216, 0.1)",
                        fill: true,
                        tension: 0.3
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        ticks: { maxRotation: 45, minRotation: 45 }
                    },
                    y: {
                        title: { display: true, text: "Temperatura (°C)" }
                    }
                }
            }
        });
    } else {
        grafico.data.labels = etiquetas;
        grafico.data.datasets[0].data = tempDS;
        grafico.data.datasets[1].data = puntoRocio;
        grafico.update();
    }

    // Scroll automático del contenedor hacia la derecha para mostrar la lectura más reciente
    const contenedorScroll = document.querySelector(".contenedor-grafico");
    contenedorScroll.scrollLeft = contenedorScroll.scrollWidth;
}