// =====================================================
// CONFIGURACIÓN DE ENDPOINTS
// =====================================================
const URL_DATOS = "/datos";
const URL_HISTORIAL = "/historial";

// =====================================================
// DATOS DE NODO PARA GRÁFICAS
// =====================================================
const datosNodos = {
    nodo1: { horarios: [], temperatura: [], puntoRocio: [] },
    nodo2: { horarios: [], temperatura: [], puntoRocio: [] }
};

// =====================================================
// INICIALIZACIÓN DE CHART.JS
// =====================================================
const ctx = document.getElementById("graficaTemperatura");

const graficaTemperatura = new Chart(ctx, {
    type: "line",
    data: {
        labels: [],
        datasets: [
            {
                label: "Temperatura DS18B20",
                data: [],
                borderColor: "#2563eb",
                backgroundColor: "rgba(37, 99, 235, 0.1)",
                tension: 0.3,
                fill: true,
                pointRadius: 4,
                pointHoverRadius: 6
            },
            {
                label: "Punto de rocío",
                data: [],
                borderColor: "#0891b2",
                borderDash: [5, 5],
                tension: 0.3,
                pointRadius: 4,
                pointHoverRadius: 6
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
            mode: 'index',
            intersect: false
        },
        scales: {
            y: { title: { display: true, text: "Temperatura (°C)" } },
            x: { title: { display: true, text: "Hora" } }
        }
    }
});

// =====================================================
// ACTUALIZAR HISTORIAL
// =====================================================
async function actualizarHistorial() {
    try {
        const respuesta = await fetch(URL_HISTORIAL);
        const historial = await respuesta.json();

        datosNodos.nodo1 = { horarios: [], temperatura: [], puntoRocio: [] };
        datosNodos.nodo2 = { horarios: [], temperatura: [], puntoRocio: [] };

        historial.forEach(dato => {
            const nodo = "nodo" + dato.nodo;
            if (!datosNodos[nodo]) return;

            const hora = dato.fechaHora.substring(11, 16);
            datosNodos[nodo].horarios.push(hora);
            datosNodos[nodo].temperatura.push(dato.temperaturaDS);
            datosNodos[nodo].puntoRocio.push(dato.puntoRocio);
        });

        actualizarGrafica();
    } catch (error) {
        console.error("Error obteniendo historial:", error);
    }
}

function actualizarGrafica() {
    const nodoSeleccionado = document.getElementById("seleccionNodo").value;
    const datos = datosNodos[nodoSeleccionado];

    const contenedorScroll = document.querySelector(".contenedor-grafico-scroll");
    const areaGrafica = document.querySelector(".area-grafica");

    if (contenedorScroll && datos.horarios.length > 0) {
        const anchoMinimoContainer = areaGrafica.clientWidth;
        const anchoCalculado = Math.max(anchoMinimoContainer, datos.horarios.length * 35);
        contenedorScroll.style.width = `${anchoCalculado}px`;
    }

    graficaTemperatura.data.labels = datos.horarios;
    graficaTemperatura.data.datasets[0].data = datos.temperatura;
    graficaTemperatura.data.datasets[1].data = datos.puntoRocio;
    
    graficaTemperatura.resize();
    graficaTemperatura.update();

    if (areaGrafica) {
        areaGrafica.scrollLeft = areaGrafica.scrollWidth;
    }
}

// =====================================================
// ACTUALIZAR DATOS EN TIEMPO REAL
// =====================================================
async function actualizarDatos() {
    try {
        const respuesta = await fetch(URL_DATOS);
        const datos = await respuesta.json();

        [1, 2].forEach(num => {
            if (datos[num]) {
                actualizarNodo(num, datos[num]);
            } else {
                marcarDesconectado(num);
            }
        });

        actualizarEstado(datos);
    } catch (error) {
        console.error("Error obteniendo datos:", error);
    }
}

function actualizarNodo(numeroNodo, dato) {
    const elConexion = document.getElementById(`nodo${numeroNodo}-conexion`);

    if (dato.conectado === false) {
        marcarDesconectado(numeroNodo);
        return;
    }

    elConexion.className = "conexion conectado";
    elConexion.querySelector(".texto-conexion").textContent = "Conectado";

    document.getElementById(`nodo${numeroNodo}-temperaturaDS`).textContent = dato.temperaturaDS.toFixed(2) + " °C";
    document.getElementById(`nodo${numeroNodo}-temperaturaDHT`).textContent = dato.temperaturaDHT.toFixed(2) + " °C";
    document.getElementById(`nodo${numeroNodo}-humedad`).textContent = dato.humedad.toFixed(2) + " %";
    document.getElementById(`nodo${numeroNodo}-puntoRocio`).textContent = dato.puntoRocio.toFixed(2) + " °C";
    document.getElementById(`nodo${numeroNodo}-actualizacion`).textContent = "Última medición: " + dato.fechaHora;
}

function marcarDesconectado(numeroNodo) {
    const elConexion = document.getElementById(`nodo${numeroNodo}-conexion`);
    elConexion.className = "conexion desconectado";
    elConexion.querySelector(".texto-conexion").textContent = "Desconectado";
}

// =====================================================
// ACTUALIZAR ESTADO INTELIGENTE (GENERAL POR NODOS)
// =====================================================
function actualizarEstado(datos) {
    let estadoGeneral = "NORMAL";
    let mensaje = "Sin indicios de helada en este momento.";
    let claseColor = "estado-normal"; // Asumimos verde por defecto

    // Recorremos los datos recibidos de los nodos (ej: nodo 1 y nodo 2)
    for (const numNodo in datos) {
        const infoNodo = datos[numNodo];
        
        // Si el nodo mandó un estado que NO es NORMAL (ej: ALERTA, PELIGRO, etc.)
        if (infoNodo.estado && infoNodo.estado !== "NORMAL") {
            estadoGeneral = infoNodo.estado;
            
            // Personalizamos el mensaje según qué nodo esté en riesgo
            if (numNodo == 1) {
                mensaje = "⚠ ¡Alerta de helada detectada en Nodo 1 (Manzana 1)!";
            } else if (numNodo == 2) {
                mensaje = "⚠ ¡Alerta de helada detectada en Nodo 2 (Ciruela 1)!";
            } else {
                mensaje = `⚠ ¡Alerta de helada detectada en Nodo ${numNodo}!`;
            }
            
            claseColor = "estado-alerta"; // Cambia a rojo/alerta
            break; // Si hay al menos uno en alerta, priorizamos mostrarlo
        }
    }

    const elementoEstado = document.getElementById("estadoGeneral");
    const mensajeEstado = document.getElementById("mensajeEstado");
    const contenedorEstado = document.querySelector(".estado-general");

    elementoEstado.textContent = estadoGeneral;
    mensajeEstado.textContent = mensaje;

    // Actualizamos dinámicamente el color del texto principal
    if (estadoGeneral === "NORMAL") {
        elementoEstado.style.color = "#16a34a"; // Verde
    } else {
        elementoEstado.style.color = "#dc2626"; // Rojo alerta
    }
}

// =====================================================
// INICIALIZACIÓN Y EVENTOS
// =====================================================
document.getElementById("seleccionNodo").addEventListener("change", actualizarGrafica);

actualizarDatos();
actualizarHistorial();

setInterval(actualizarDatos, 2000);
setInterval(actualizarHistorial, 5000);

// =====================================================
// LÓGICA DEL MAPA DESPLEGABLE
// =====================================================
const coordenadasNodo1 = [-38.845769, -68.071461];
const coordenadasNodo2 = [-38.845947, -68.071986];

let mapaInicializado = false;
let mapa;

function inicializarMapa() {
    if (mapaInicializado) return;

    mapa = L.map('mapa').setView(coordenadasNodo1, 18);

    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS'
    }).addTo(mapa);

    const marcadorNodo1 = L.marker(coordenadasNodo1).addTo(mapa)
        .bindPopup('<b>Nodo 1 (Manzana 1)</b><br>Chacra Experimental FACA');

    const marcadorNodo2 = L.marker(coordenadasNodo2).addTo(mapa)
        .bindPopup('<b>Nodo 2 (Ciruela 1)</b><br>Chacra Experimental FACA');

    const grupoNodos = L.featureGroup([marcadorNodo1, marcadorNodo2]);
    mapa.fitBounds(grupoNodos.getBounds().pad(0.4));

    mapaInicializado = true;
}

const desplegableMapa = document.getElementById('desplegableMapa');

if (desplegableMapa) {
    desplegableMapa.addEventListener('toggle', function() {
        if (desplegableMapa.open) {
            inicializarMapa();
            setTimeout(() => {
                if (mapa) mapa.invalidateSize();
            }, 100);
        }
    });
}

// =====================================================
// LÓGICA DEL DESPLEGABLE DE HISTORIAL CSV MENSUAL
// =====================================================
const desplegableHistorial = document.getElementById('desplegableHistorial');
let historialCargado = false;

if (desplegableHistorial) {
    desplegableHistorial.addEventListener('toggle', async function() {
        if (desplegableHistorial.open && !historialCargado) {
            try {
                const respuesta = await fetch('/api/archivos-csv');
                const archivos = await respuesta.json();
                
                const contenedorLista = document.getElementById('listaArchivosCsv');
                contenedorLista.innerHTML = '';

                if (archivos.length === 0) {
                    contenedorLista.innerHTML = '<li>No hay registros mensuales guardados todavía.</li>';
                    return;
                }

                archivos.forEach(archivo => {
                    // Extraer año y mes (ej: historial_2026-09.csv -> 2026 y 09)
                    const partes = archivo.replace('historial_', '').replace('.csv', '').split('-');
                    const anio = partes[0];
                    const mesNum = partes[1];
                    
                    const meses = {
                        "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
                        "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
                        "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
                    };
                    const nombreMes = meses[mesNum] || mesNum;

                    const li = document.createElement('li');
                    li.innerHTML = `
                        <a href="/descargar/${archivo}" target="_blank" style="display: inline-block; background-color: #0284c7; color: white; padding: 6px 14px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 600;">
                            📥 Descargar registro mensual de ${nombreMes} ${anio}
                        </a>
                    `;
                    contenedorLista.appendChild(li);
                });

                historialCargado = true;
            } catch (error) {
                console.error("Error cargando la lista de CSV:", error);
                const contenedorLista = document.getElementById('listaArchivosCsv');
                contenedorLista.innerHTML = '<li>Error al cargar los registros históricos.</li>';
            }
        }
    });
}
