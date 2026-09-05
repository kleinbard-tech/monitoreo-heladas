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
                fill: true
            },
            {
                label: "Punto de rocío",
                data: [],
                borderColor: "#0891b2",
                borderDash: [5, 5],
                tension: 0.3
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: { title: { display: true, text: "Temperatura (°C)" } },
            x: { title: { display: true, text: "Hora" } }
        }
    }
});

// =====================================================
// ACTUALIZAR HISTORIAL Y DESPLAZAMIENTO DEL GRÁFICO
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

    // Calcula el ancho expandido para que aparezca la barra al acumular lecturas
    const contenedorScroll = document.querySelector(".contenedor-grafico-scroll");
    if (contenedorScroll && datos.horarios.length > 0) {
        // Se otorgan 35px por cada medición registrada en el historial (mínimo 800px)
        const anchoDinamico = Math.max(800, datos.horarios.length * 35);
        ctx.style.width = `${anchoDinamico}px`;
    }

    graficaTemperatura.data.labels = datos.horarios;
    graficaTemperatura.data.datasets[0].data = datos.temperatura;
    graficaTemperatura.data.datasets[1].data = datos.puntoRocio;
    graficaTemperatura.update();

    // Desplaza la barra automáticamente hacia la derecha para mostrar la lectura más reciente
    if (contenedorScroll) {
        contenedorScroll.scrollLeft = contenedorScroll.scrollWidth;
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

function actualizarEstado(datos) {
    let estado = "NORMAL";

    for (const nodo in datos) {
        if (datos[nodo].estado && datos[nodo].estado !== "NORMAL") {
            estado = datos[nodo].estado;
        }
    }

    const elementoEstado = document.getElementById("estadoGeneral");
    const mensajeEstado = document.getElementById("mensajeEstado");

    elementoEstado.textContent = estado;

    if (estado === "NORMAL") {
        mensajeEstado.textContent = "Sin indicios de helada en este momento.";
    } else {
        mensajeEstado.textContent = "Se ha detectado una condición de posible helada.";
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
const coordenadasNodo1 = [-38.845769, -68.071461]; // Manzana 1
const coordenadasNodo2 = [-38.845947, -68.071986]; // Ciruela 1

let mapaInicializado = false;
let mapa;

function inicializarMapa() {
    if (mapaInicializado) return;

    mapa = L.map('mapa').setView(coordenadasNodo1, 18);

    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS'
    }).addTo(mapa);

    const marcadorNodo1 = L.marker(coordenadasNodo1).addTo(mapa)
        .bindPopup('<b>Nodo 1</b><br>Manzana 1');

    const marcadorNodo2 = L.marker(coordenadasNodo2).addTo(mapa)
        .bindPopup('<b>Nodo 2</b><br>Ciruela 1');

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