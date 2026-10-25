// =====================================================
// CONFIGURACIÓN DE ENDPOINTS
// =====================================================
const URL_DATOS = "/datos";
const URL_HISTORIAL = "/historial";
const URL_VIENTO = "/viento";

// =====================================================
// CONTROL DEL DESPLAZAMIENTO DE LA GRÁFICA
// =====================================================
let seguirUltimasMediciones = true;

// =====================================================
// DATOS DE NODO PARA GRÁFICAS
// =====================================================
const datosNodos = {
    nodo1: {
        horarios: [],
        temperaturaDS: [],
        temperaturaDHT: [],
        puntoRocio: []
    },
    nodo2: {
        horarios: [],
        temperaturaDS: [],
        temperaturaDHT: [],
        puntoRocio: []
    }
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
                label: "Temperatura DS18B20 (≈ 2 m, abrigo meteorológico)",
                data: [],
                borderColor: "#2563eb",
                backgroundColor: "rgba(37, 99, 235, 0.1)",
                tension: 0.3,
                fill: true,
                pointRadius: 4,
                pointHoverRadius: 6
            },
            {
                label: "Temperatura DHT22 (≈ 70 cm, abrigo meteorológico)",
                data: [],
                borderColor: "#16a34a",
                backgroundColor: "rgba(22, 163, 74, 0.08)",
                tension: 0.3,
                fill: false,
                pointRadius: 4,
                pointHoverRadius: 6
            },
            {
                label: "Punto de rocío (calculado con DHT22 y humedad)",
                data: [],
                borderColor: "#0891b2",
                borderDash: [5, 5],
                tension: 0.3,
                fill: false,
                pointRadius: 4,
                pointHoverRadius: 6
            }
        ]
    },

    options: {
        responsive: true,
        maintainAspectRatio: false,

        interaction: {
            mode: "index",
            intersect: false
        },

        scales: {
            y: {
                title: {
                    display: true,
                    text: "Temperatura (°C)"
                }
            },

            x: {
                title: {
                    display: true,
                    text: "Hora"
                }
            }
        }
    }
});

// =====================================================
// ACTUALIZAR REFERENCIA METEOROLÓGICA DEL INTA
// =====================================================
async function actualizarVientoINTA() {

    try {

        const respuesta = await fetch(URL_VIENTO);

        if (!respuesta.ok) {
            throw new Error("Error HTTP: " + respuesta.status);
        }

        const viento = await respuesta.json();

        const elementoDireccion =
            document.getElementById("viento-direccion");

        const elementoVelocidad =
            document.getElementById("viento-velocidad");

        const elementoActualizacion =
            document.getElementById("viento-actualizacion");

        // Comprobar si el INTA entregó datos válidos
        if (
            viento.disponible &&
            viento.velocidad !== null &&
            viento.direccion
        ) {

            elementoDireccion.textContent = viento.direccion;

            // Mostrar velocidad con coma decimal
            const velocidad = Number(viento.velocidad);

            elementoVelocidad.textContent =
                velocidad.toLocaleString("es-AR", {
                    minimumFractionDigits: 1,
                    maximumFractionDigits: 2
                }) + " " + (viento.unidad || "km/h");

            // Mostrar fecha y hora publicadas por el INTA
            if (viento.fecha && viento.hora) {

                elementoActualizacion.textContent =
                    "Último dato publicado por INTA: " +
                    viento.fecha + " " +
                    viento.hora;

            } else {

                elementoActualizacion.textContent =
                    "Datos recibidos correctamente desde INTA.";
            }

        } else {

            elementoDireccion.textContent = "--";
            elementoVelocidad.textContent = "-- km/h";

            elementoActualizacion.textContent =
                viento.mensaje ||
                "No hay datos disponibles de la estación del INTA.";
        }

    } catch (error) {

        console.error(
            "Error obteniendo datos del viento del INTA:",
            error
        );

        document.getElementById(
            "viento-actualizacion"
        ).textContent =
            "No se pudo actualizar la referencia meteorológica.";
    }
}

// =====================================================
// ACTUALIZAR HISTORIAL
// =====================================================
async function actualizarHistorial() {

    try {

        const respuesta = await fetch(URL_HISTORIAL);

        if (!respuesta.ok) {
            throw new Error("Error HTTP: " + respuesta.status);
        }

        const historial = await respuesta.json();

        // Reiniciar los datos de ambos nodos
        datosNodos.nodo1 = {
            horarios: [],
            temperaturaDS: [],
            temperaturaDHT: [],
            puntoRocio: []
        };

        datosNodos.nodo2 = {
            horarios: [],
            temperaturaDS: [],
            temperaturaDHT: [],
            puntoRocio: []
        };

        historial.forEach(dato => {

            const nodo = "nodo" + dato.nodo;

            if (!datosNodos[nodo]) {
                return;
            }

            const hora = dato.fechaHora.substring(11, 16);

            datosNodos[nodo].horarios.push(hora);

            // Temperatura del sensor DS18B20
            datosNodos[nodo].temperaturaDS.push(
                dato.temperaturaDS
            );

            // Temperatura del sensor DHT22
            datosNodos[nodo].temperaturaDHT.push(
                dato.temperaturaDHT
            );

            // Punto de rocío
            datosNodos[nodo].puntoRocio.push(
                dato.puntoRocio
            );
        });

        actualizarGrafica();

    } catch (error) {

        console.error(
            "Error obteniendo historial:",
            error
        );
    }
}

// =====================================================
// ACTUALIZAR GRÁFICA SEGÚN EL NODO SELECCIONADO
// =====================================================
function actualizarGrafica() {

    const nodoSeleccionado =
        document.getElementById("seleccionNodo").value;

    const datos = datosNodos[nodoSeleccionado];

    const contenedorScroll =
        document.querySelector(".contenedor-grafico-scroll");

    const areaGrafica =
        document.querySelector(".area-grafica");

    // Guardar la posición actual y comprobar si estaba al final
    let posicionAnterior = 0;
    let estabaAlFinal = true;

    if (areaGrafica) {

        posicionAnterior = areaGrafica.scrollLeft;

        const distanciaAlFinal =
            areaGrafica.scrollWidth -
            areaGrafica.clientWidth -
            areaGrafica.scrollLeft;

        estabaAlFinal = distanciaAlFinal <= 10;
    }

    // Ajustar el ancho del gráfico según la cantidad de mediciones
    if (
        contenedorScroll &&
        areaGrafica &&
        datos.horarios.length > 0
    ) {

        const anchoMinimoContainer =
            areaGrafica.clientWidth;

        const anchoCalculado = Math.max(
            anchoMinimoContainer,
            datos.horarios.length * 35
        );

        contenedorScroll.style.width =
            `${anchoCalculado}px`;
    }

    // Actualizar las etiquetas del eje horizontal
    graficaTemperatura.data.labels = datos.horarios;

    // CURVA 1: Temperatura DS18B20
    graficaTemperatura.data.datasets[0].data =
        datos.temperaturaDS;

    // CURVA 2: Temperatura DHT22
    graficaTemperatura.data.datasets[1].data =
        datos.temperaturaDHT;

    // CURVA 3: Punto de rocío
    graficaTemperatura.data.datasets[2].data =
        datos.puntoRocio;

    graficaTemperatura.resize();
    graficaTemperatura.update("none");

    // Mantener el comportamiento del desplazamiento horizontal
    if (areaGrafica) {

        if (seguirUltimasMediciones && estabaAlFinal) {

            // Seguir automáticamente las mediciones recientes
            areaGrafica.scrollLeft =
                areaGrafica.scrollWidth;

        } else {

            // Mantener la posición de consulta del usuario
            areaGrafica.scrollLeft = Math.min(
                posicionAnterior,
                areaGrafica.scrollWidth -
                areaGrafica.clientWidth
            );

            seguirUltimasMediciones = false;
        }
    }
}

// =====================================================
// DETECTAR SI EL USUARIO SE DESPLAZA HACIA ATRÁS
// =====================================================
const areaGraficaScroll =
    document.querySelector(".area-grafica");

if (areaGraficaScroll) {

    areaGraficaScroll.addEventListener("scroll", function () {

        const distanciaAlFinal =
            this.scrollWidth -
            this.clientWidth -
            this.scrollLeft;

        // Si está cerca del extremo derecho,
        // activar nuevamente el seguimiento automático
        if (distanciaAlFinal <= 10) {

            seguirUltimasMediciones = true;

        } else {

            seguirUltimasMediciones = false;
        }
    });
}

// =====================================================
// ACTUALIZAR DATOS EN TIEMPO REAL
// =====================================================
async function actualizarDatos() {

    try {

        const respuesta = await fetch(URL_DATOS);

        if (!respuesta.ok) {
            throw new Error("Error HTTP: " + respuesta.status);
        }

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

        console.error(
            "Error obteniendo datos:",
            error
        );
    }
}

// =====================================================
// ACTUALIZAR TARJETAS DE CADA NODO
// =====================================================
function actualizarNodo(numeroNodo, dato) {

    const elConexion =
        document.getElementById(`nodo${numeroNodo}-conexion`);

    if (dato.conectado === false) {

        marcarDesconectado(numeroNodo);
        return;
    }

    elConexion.className = "conexion conectado";

    elConexion
        .querySelector(".texto-conexion")
        .textContent = "Conectado";

    // Temperatura DS18B20
    document.getElementById(
        `nodo${numeroNodo}-temperaturaDS`
    ).textContent =
        dato.temperaturaDS.toFixed(2) + " °C";

    // Temperatura DHT22
    document.getElementById(
        `nodo${numeroNodo}-temperaturaDHT`
    ).textContent =
        dato.temperaturaDHT.toFixed(2) + " °C";

    // Humedad relativa
    document.getElementById(
        `nodo${numeroNodo}-humedad`
    ).textContent =
        dato.humedad.toFixed(2) + " %";

    // Punto de rocío
    document.getElementById(
        `nodo${numeroNodo}-puntoRocio`
    ).textContent =
        dato.puntoRocio.toFixed(2) + " °C";

    // Fecha y hora de la última medición
    document.getElementById(
        `nodo${numeroNodo}-actualizacion`
    ).textContent =
        "Última medición: " + dato.fechaHora;
}

// =====================================================
// MARCAR NODO COMO DESCONECTADO
// =====================================================
function marcarDesconectado(numeroNodo) {

    const elConexion =
        document.getElementById(`nodo${numeroNodo}-conexion`);

    elConexion.className = "conexion desconectado";

    elConexion
        .querySelector(".texto-conexion")
        .textContent = "Desconectado";
}

// =====================================================
// ACTUALIZAR ESTADO GENERAL
// =====================================================
function actualizarEstado(datos) {

    let estadoGeneral = "NORMAL";
    let nodosEnAlerta = [];
    let cantidadNodosConectados = 0;

    // Recorrer los datos recibidos
    for (const numNodo in datos) {

        const infoNodo = datos[numNodo];

        if (
            infoNodo &&
            infoNodo.conectado !== false
        ) {

            cantidadNodosConectados++;

            if (
                infoNodo.estado &&
                infoNodo.estado !== "NORMAL"
            ) {

                estadoGeneral = infoNodo.estado;

                if (numNodo == 1) {
                    nodosEnAlerta.push("Nodo 1 (Manzana 1)");
                }

                if (numNodo == 2) {
                    nodosEnAlerta.push("Nodo 2 (Ciruela 1)");
                }
            }
        }
    }

    const elementoEstado =
        document.getElementById("estadoGeneral");

    const mensajeEstado =
        document.getElementById("mensajeEstado");

    // CASO 1: ningún nodo reporta conexión activa
    if (cantidadNodosConectados === 0) {

        elementoEstado.textContent = "DESCONECTADO";

        mensajeEstado.textContent =
            "⚠ Sin comunicación con los nodos de la chacra.";

        elementoEstado.style.color = "#64748b";

        return;
    }

    // CASO 2: hay nodos conectados
    elementoEstado.textContent = estadoGeneral;

    if (nodosEnAlerta.length === 0) {

        mensajeEstado.textContent =
            "Sin indicios de helada en este momento.";

        elementoEstado.style.color = "#16a34a";

    } else if (nodosEnAlerta.length === 1) {

        mensajeEstado.textContent =
            `⚠ ¡Alerta de helada detectada en ${nodosEnAlerta[0]}!`;

        elementoEstado.style.color = "#dc2626";

    } else {

        mensajeEstado.textContent =
            `⚠ ¡ALERTA GENERAL DE HELADA! Afecta a: ${nodosEnAlerta.join(" y ")}.`;

        elementoEstado.style.color = "#dc2626";
    }
}

// =====================================================
// INICIALIZACIÓN Y ACTUALIZACIÓN AUTOMÁTICA
// =====================================================

// Actualizar los dos nodos
actualizarDatos();

// Actualizar el historial de temperaturas
actualizarHistorial();

// Consultar los datos meteorológicos del INTA
actualizarVientoINTA();

// Actualización de los nodos cada 2 segundos
setInterval(actualizarDatos, 2000);

// Actualización del historial cada 5 segundos
setInterval(actualizarHistorial, 5000);

// Actualización de la referencia del INTA cada 60 segundos
setInterval(actualizarVientoINTA, 60000);

// =====================================================
// LÓGICA DEL MAPA DESPLEGABLE
// =====================================================
const coordenadasNodo1 = [
    -38.845769,
    -68.071461
];

const coordenadasNodo2 = [
    -38.845947,
    -68.071986
];

let mapaInicializado = false;
let mapa;

function inicializarMapa() {

    if (mapaInicializado) {
        return;
    }

    mapa = L.map("mapa").setView(
        coordenadasNodo1,
        18
    );

    L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        {
            attribution:
                "Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS"
        }
    ).addTo(mapa);

    const marcadorNodo1 = L.marker(coordenadasNodo1)
        .addTo(mapa)
        .bindPopup(
            "<b>Nodo 1 (Manzana 1)</b><br>Chacra Experimental FACA"
        );

    const marcadorNodo2 = L.marker(coordenadasNodo2)
        .addTo(mapa)
        .bindPopup(
            "<b>Nodo 2 (Ciruela 1)</b><br>Chacra Experimental FACA"
        );

    const grupoNodos = L.featureGroup([
        marcadorNodo1,
        marcadorNodo2
    ]);

    mapa.fitBounds(
        grupoNodos.getBounds().pad(0.4)
    );

    mapaInicializado = true;
}

// Inicializar el mapa al desplegar su sección
const desplegableMapa =
    document.getElementById("desplegableMapa");

if (desplegableMapa) {

    desplegableMapa.addEventListener("toggle", function () {

        if (desplegableMapa.open) {

            inicializarMapa();

            setTimeout(() => {

                if (mapa) {
                    mapa.invalidateSize();
                }

            }, 100);
        }
    });
}

// =====================================================
// LÓGICA DEL DESPLEGABLE DE HISTORIAL CSV MENSUAL
// =====================================================
const desplegableHistorial =
    document.getElementById("desplegableHistorial");

let historialCargado = false;

if (desplegableHistorial) {

    desplegableHistorial.addEventListener(
        "toggle",
        async function () {

            if (
                desplegableHistorial.open &&
                !historialCargado
            ) {

                try {

                    const respuesta = await fetch(
                        "/api/archivos-csv"
                    );

                    if (!respuesta.ok) {
                        throw new Error(
                            "Error HTTP: " + respuesta.status
                        );
                    }

                    const archivos = await respuesta.json();

                    console.log(
                        "Archivos CSV recibidos:",
                        archivos
                    );

                    const contenedorLista =
                        document.getElementById("listaArchivosCsv");

                    contenedorLista.innerHTML = "";

                    if (archivos.length === 0) {

                        contenedorLista.innerHTML =
                            "<li>No hay registros mensuales guardados todavía.</li>";

                        return;
                    }

                    archivos.forEach(archivo => {

                        // Obtener el nombre del archivo
                        let nombreArchivo = "";

                        if (typeof archivo === "string") {

                            nombreArchivo = archivo;

                        } else if (
                            typeof archivo === "object" &&
                            archivo !== null
                        ) {

                            nombreArchivo =
                                archivo.archivo ||
                                archivo.nombre ||
                                archivo.filename ||
                                archivo.name ||
                                archivo.file ||
                                "";
                        }

                        if (!nombreArchivo) {

                            console.warn(
                                "No se pudo obtener el nombre del archivo:",
                                archivo
                            );

                            return;
                        }

                        // Obtener el número de nodo
                        let numeroNodo = null;

                        if (
                            typeof archivo === "object" &&
                            archivo !== null &&
                            archivo.nodo !== undefined
                        ) {

                            numeroNodo = Number(archivo.nodo);
                        }

                        // Si no viene el nodo, intentar obtenerlo del nombre
                        if (
                            numeroNodo === null ||
                            Number.isNaN(numeroNodo)
                        ) {

                            if (
                                nombreArchivo.startsWith(
                                    "historial_nodo1_"
                                )
                            ) {

                                numeroNodo = 1;

                            } else if (
                                nombreArchivo.startsWith(
                                    "historial_nodo2_"
                                )
                            ) {

                                numeroNodo = 2;
                            }
                        }

                        // Extraer año y mes
                        const partes = nombreArchivo
                            .replace(/^historial_nodo[12]_/, "")
                            .replace(".csv", "")
                            .split("-");

                        const anio = partes[0];
                        const mesNum = partes[1];

                        // Nombres de los meses
                        const meses = {
                            "01": "Enero",
                            "02": "Febrero",
                            "03": "Marzo",
                            "04": "Abril",
                            "05": "Mayo",
                            "06": "Junio",
                            "07": "Julio",
                            "08": "Agosto",
                            "09": "Septiembre",
                            "10": "Octubre",
                            "11": "Noviembre",
                            "12": "Diciembre"
                        };

                        const nombreMes = meses[mesNum] || mesNum;

                        // Nombre del nodo
                        let nombreNodo = "Nodo";

                        if (numeroNodo === 1) {

                            nombreNodo = "Nodo 1 (Manzana 1)";

                        } else if (numeroNodo === 2) {

                            nombreNodo = "Nodo 2 (Ciruela 1)";
                        }

                        // Crear elemento de lista
                        const li = document.createElement("li");

                        // Crear enlace de descarga
                        li.innerHTML = `
                            <a
                                href="/descargar/${numeroNodo}/${encodeURIComponent(nombreArchivo)}"
                                target="_blank"
                                style="
                                    display: inline-block;
                                    background-color: #0284c7;
                                    color: white;
                                    padding: 6px 14px;
                                    border-radius: 6px;
                                    text-decoration: none;
                                    font-size: 13px;
                                    font-weight: 600;
                                "
                            >
                                📥 Descargar registro mensual - ${nombreNodo} - ${nombreMes} ${anio}
                            </a>
                        `;

                        contenedorLista.appendChild(li);
                    });

                    historialCargado = true;

                } catch (error) {

                    console.error(
                        "Error cargando la lista de CSV:",
                        error
                    );

                    const contenedorLista =
                        document.getElementById("listaArchivosCsv");

                    contenedorLista.innerHTML =
                        "<li>Error al cargar los registros históricos.</li>";
                }
            }
        }
    );
}
