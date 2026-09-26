// =====================================================
// CONFIGURACIÓN DE ENDPOINTS
// =====================================================

const URL_DATOS = "/datos";
const URL_HISTORIAL = "/historial";


// =====================================================
// DATOS DE NODO PARA GRÁFICAS
// =====================================================

const datosNodos = {

    nodo1: {
        horarios: [],
        temperatura: [],
        puntoRocio: []
    },

    nodo2: {
        horarios: [],
        temperatura: [],
        puntoRocio: []
    }

};


// =====================================================
// INICIALIZACIÓN DE CHART.JS
// =====================================================

const ctx = document.getElementById(
    "graficaTemperatura"
);

const graficaTemperatura = new Chart(
    ctx,
    {
        type: "line",

        data: {

            labels: [],

            datasets: [

                {
                    label: "Temperatura DS18B20",

                    data: [],

                    borderColor: "#2563eb",

                    backgroundColor:
                        "rgba(37, 99, 235, 0.1)",

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

    }
);


// =====================================================
// ACTUALIZAR HISTORIAL
// =====================================================

async function actualizarHistorial() {

    try {

        const respuesta = await fetch(
            URL_HISTORIAL
        );

        if (!respuesta.ok) {

            throw new Error(
                `Error HTTP ${respuesta.status}`
            );

        }

        const historial =
            await respuesta.json();


        // =================================================
        // LIMPIAR DATOS DE LOS DOS NODOS
        // =================================================

        datosNodos.nodo1 = {

            horarios: [],

            temperatura: [],

            puntoRocio: []

        };


        datosNodos.nodo2 = {

            horarios: [],

            temperatura: [],

            puntoRocio: []

        };


        // =================================================
        // SEPARAR LOS DATOS SEGÚN EL NODO
        // =================================================

        historial.forEach(
            dato => {

                const nodo =
                    "nodo" + dato.nodo;


                if (
                    !datosNodos[nodo]
                ) {

                    return;

                }


                if (
                    !dato.fechaHora
                ) {

                    return;

                }


                const hora =
                    dato.fechaHora.substring(
                        11,
                        16
                    );


                datosNodos[nodo]
                    .horarios
                    .push(hora);


                datosNodos[nodo]
                    .temperatura
                    .push(
                        dato.temperaturaDS
                    );


                datosNodos[nodo]
                    .puntoRocio
                    .push(
                        dato.puntoRocio
                    );

            }
        );


        // =================================================
        // ACTUALIZAR GRÁFICA
        // =================================================

        actualizarGrafica();


    }

    catch (error) {

        console.error(
            "Error obteniendo historial:",
            error
        );

    }

}


// =====================================================
// ACTUALIZAR GRÁFICA
// =====================================================

function actualizarGrafica() {

    const selector =
        document.getElementById(
            "seleccionNodo"
        );


    if (!selector) {

        return;

    }


    const nodoSeleccionado =
        selector.value;


    const datos =
        datosNodos[nodoSeleccionado];


    if (!datos) {

        return;

    }


    const contenedorScroll =
        document.querySelector(
            ".contenedor-grafico-scroll"
        );


    const areaGrafica =
        document.querySelector(
            ".area-grafica"
        );


    if (
        contenedorScroll &&
        areaGrafica &&
        datos.horarios.length > 0
    ) {

        const anchoMinimoContainer =
            areaGrafica.clientWidth;


        const anchoCalculado =
            Math.max(
                anchoMinimoContainer,
                datos.horarios.length * 35
            );


        contenedorScroll.style.width =
            `${anchoCalculado}px`;

    }


    // =================================================
    // DATOS DE LA GRÁFICA
    // =================================================

    graficaTemperatura.data.labels =
        datos.horarios;


    graficaTemperatura.data.datasets[0].data =
        datos.temperatura;


    graficaTemperatura.data.datasets[1].data =
        datos.puntoRocio;


    // =================================================
    // ACTUALIZAR CHART.JS
    // =================================================

    graficaTemperatura.resize();

    graficaTemperatura.update();


    // =================================================
    // IR AL FINAL DEL GRÁFICO
    // =================================================

    if (areaGrafica) {

        areaGrafica.scrollLeft =
            areaGrafica.scrollWidth;

    }

}


// =====================================================
// ACTUALIZAR DATOS EN TIEMPO REAL
// =====================================================

async function actualizarDatos() {

    try {

        const respuesta =
            await fetch(
                URL_DATOS
            );


        if (!respuesta.ok) {

            throw new Error(
                `Error HTTP ${respuesta.status}`
            );

        }


        const datos =
            await respuesta.json();


        // =================================================
        // ACTUALIZAR NODO 1 Y NODO 2
        // =================================================

        [1, 2].forEach(
            num => {

                if (
                    datos[num]
                ) {

                    actualizarNodo(
                        num,
                        datos[num]
                    );

                }

                else {

                    marcarDesconectado(
                        num
                    );

                }

            }
        );


        // =================================================
        // ACTUALIZAR ESTADO GENERAL
        // =================================================

        actualizarEstado(
            datos
        );


    }

    catch (error) {

        console.error(
            "Error obteniendo datos:",
            error
        );

    }

}


// =====================================================
// ACTUALIZAR INFORMACIÓN DE UN NODO
// =====================================================

function actualizarNodo(
    numeroNodo,
    dato
) {

    const elConexion =
        document.getElementById(
            `nodo${numeroNodo}-conexion`
        );


    if (!elConexion) {

        return;

    }


    // =================================================
    // SI ESTÁ DESCONECTADO
    // =================================================

    if (
        dato.conectado === false
    ) {

        marcarDesconectado(
            numeroNodo
        );

        return;

    }


    // =================================================
    // MARCAR COMO CONECTADO
    // =================================================

    elConexion.className =
        "conexion conectado";


    elConexion
        .querySelector(
            ".texto-conexion"
        )
        .textContent =
        "Conectado";


    // =================================================
    // TEMPERATURA DS18B20
    // =================================================

    const elementoDS =
        document.getElementById(
            `nodo${numeroNodo}-temperaturaDS`
        );


    if (
        elementoDS &&
        dato.temperaturaDS !== undefined
    ) {

        elementoDS.textContent =
            Number(
                dato.temperaturaDS
            ).toFixed(2)
            + " °C";

    }


    // =================================================
    // TEMPERATURA DHT22
    // =================================================

    const elementoDHT =
        document.getElementById(
            `nodo${numeroNodo}-temperaturaDHT`
        );


    if (
        elementoDHT &&
        dato.temperaturaDHT !== undefined
    ) {

        elementoDHT.textContent =
            Number(
                dato.temperaturaDHT
            ).toFixed(2)
            + " °C";

    }


    // =================================================
    // HUMEDAD
    // =================================================

    const elementoHumedad =
        document.getElementById(
            `nodo${numeroNodo}-humedad`
        );


    if (
        elementoHumedad &&
        dato.humedad !== undefined
    ) {

        elementoHumedad.textContent =
            Number(
                dato.humedad
            ).toFixed(2)
            + " %";

    }


    // =================================================
    // PUNTO DE ROCÍO
    // =================================================

    const elementoRocio =
        document.getElementById(
            `nodo${numeroNodo}-puntoRocio`
        );


    if (
        elementoRocio &&
        dato.puntoRocio !== undefined &&
        dato.puntoRocio !== null
    ) {

        elementoRocio.textContent =
            Number(
                dato.puntoRocio
            ).toFixed(2)
            + " °C";

    }


    // =================================================
    // FECHA DE ACTUALIZACIÓN
    // =================================================

    const elementoActualizacion =
        document.getElementById(
            `nodo${numeroNodo}-actualizacion`
        );


    if (
        elementoActualizacion &&
        dato.fechaHora
    ) {

        elementoActualizacion.textContent =
            "Última medición: "
            + dato.fechaHora;

    }

}


// =====================================================
// MARCAR NODO COMO DESCONECTADO
// =====================================================

function marcarDesconectado(
    numeroNodo
) {

    const elConexion =
        document.getElementById(
            `nodo${numeroNodo}-conexion`
        );


    if (!elConexion) {

        return;

    }


    elConexion.className =
        "conexion desconectado";


    const textoConexion =
        elConexion.querySelector(
            ".texto-conexion"
        );


    if (textoConexion) {

        textoConexion.textContent =
            "Desconectado";

    }

}


// =====================================================
// ACTUALIZAR ESTADO INTELIGENTE
// =====================================================

function actualizarEstado(
    datos
) {

    let estadoGeneral =
        "NORMAL";


    let nodosEnAlerta =
        [];


    let cantidadNodosConectados =
        0;


    // =================================================
    // RECORRER NODOS
    // =================================================

    for (
        const numNodo in datos
    ) {

        const infoNodo =
            datos[numNodo];


        if (
            infoNodo &&
            infoNodo.conectado !== false
        ) {

            cantidadNodosConectados++;


            // =============================================
            // EVALUAR ALERTA
            // =============================================

            if (
                infoNodo.estado &&
                infoNodo.estado !== "NORMAL"
            ) {

                estadoGeneral =
                    infoNodo.estado;


                if (
                    numNodo == 1
                ) {

                    nodosEnAlerta.push(
                        "Nodo 1 (Manzana 1)"
                    );

                }


                if (
                    numNodo == 2
                ) {

                    nodosEnAlerta.push(
                        "Nodo 2 (Ciruela 1)"
                    );

                }

            }

        }

    }


    const elementoEstado =
        document.getElementById(
            "estadoGeneral"
        );


    const mensajeEstado =
        document.getElementById(
            "mensajeEstado"
        );


    if (
        !elementoEstado ||
        !mensajeEstado
    ) {

        return;

    }


    // =================================================
    // NINGÚN NODO CONECTADO
    // =================================================

    if (
        cantidadNodosConectados === 0
    ) {

        elementoEstado.textContent =
            "DESCONECTADO";


        mensajeEstado.textContent =
            "⚠ Sin comunicación con los nodos de la chacra.";


        elementoEstado.style.color =
            "#64748b";


        return;

    }


    // =================================================
    // HAY AL MENOS UN NODO CONECTADO
    // =================================================

    elementoEstado.textContent =
        estadoGeneral;


    if (
        nodosEnAlerta.length === 0
    ) {

        mensajeEstado.textContent =
            "Sin indicios de helada en este momento.";


        elementoEstado.style.color =
            "#16a34a";

    }

    else if (
        nodosEnAlerta.length === 1
    ) {

        mensajeEstado.textContent =
            `⚠ ¡Alerta de helada detectada en ${nodosEnAlerta[0]}!`;


        elementoEstado.style.color =
            "#dc2626";

    }

    else {

        mensajeEstado.textContent =
            `⚠ ¡ALERTA GENERAL DE HELADA! Afecta a: ${nodosEnAlerta.join(" y ")}.`;


        elementoEstado.style.color =
            "#dc2626";

    }

}


// =====================================================
// INICIALIZACIÓN Y EVENTOS
// =====================================================

const selectorNodo =
    document.getElementById(
        "seleccionNodo"
    );


if (selectorNodo) {

    selectorNodo.addEventListener(
        "change",
        actualizarGrafica
    );

}


actualizarDatos();

actualizarHistorial();


setInterval(
    actualizarDatos,
    2000
);


setInterval(
    actualizarHistorial,
    5000
);


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


let mapaInicializado =
    false;


let mapa;


function inicializarMapa() {

    if (
        mapaInicializado
    ) {

        return;

    }


    mapa =
        L.map(
            "mapa"
        ).setView(
            coordenadasNodo1,
            18
        );


    L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        {

            attribution:
                "Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS"

        }
    ).addTo(
        mapa
    );


    // =================================================
    // MARCADOR NODO 1
    // =================================================

    const marcadorNodo1 =
        L.marker(
            coordenadasNodo1
        )
        .addTo(
            mapa
        )
        .bindPopup(
            "<b>Nodo 1 (Manzana 1)</b><br>Chacra Experimental FACA"
        );


    // =================================================
    // MARCADOR NODO 2
    // =================================================

    const marcadorNodo2 =
        L.marker(
            coordenadasNodo2
        )
        .addTo(
            mapa
        )
        .bindPopup(
            "<b>Nodo 2 (Ciruela 1)</b><br>Chacra Experimental FACA"
        );


    // =================================================
    // AJUSTAR MAPA A LOS DOS NODOS
    // =================================================

    const grupoNodos =
        L.featureGroup(
            [
                marcadorNodo1,
                marcadorNodo2
            ]
        );


    mapa.fitBounds(
        grupoNodos
            .getBounds()
            .pad(0.4)
    );


    mapaInicializado =
        true;

}


// =====================================================
// DESPLEGABLE DEL MAPA
// =====================================================

const desplegableMapa =
    document.getElementById(
        "desplegableMapa"
    );


if (
    desplegableMapa
) {

    desplegableMapa.addEventListener(
        "toggle",
        function() {

            if (
                desplegableMapa.open
            ) {

                inicializarMapa();


                setTimeout(
                    function() {

                        if (mapa) {

                            mapa.invalidateSize();

                        }

                    },
                    100
                );

            }

        }
    );

}


// =====================================================
// LÓGICA DEL DESPLEGABLE DE HISTORIAL CSV MENSUAL
// =====================================================

const desplegableHistorial =
    document.getElementById(
        "desplegableHistorial"
    );


let historialCargado =
    false;


if (
    desplegableHistorial
) {

    desplegableHistorial.addEventListener(
        "toggle",
        async function() {

            // =================================================
            // SOLO CARGAR CUANDO SE ABRE
            // =================================================

            if (
                !desplegableHistorial.open ||
                historialCargado
            ) {

                return;

            }


            try {

                // =================================================
                // PEDIR LISTA DE CSV AL SERVIDOR
                // =================================================

                const respuesta =
                    await fetch(
                        "/api/archivos-csv"
                    );


                // =================================================
                // COMPROBAR RESPUESTA DEL SERVIDOR
                // =================================================

                if (
                    !respuesta.ok
                ) {

                    throw new Error(
                        `El servidor respondió con HTTP ${respuesta.status}`
                    );

                }


                // =================================================
                // CONVERTIR RESPUESTA A JSON
                // =================================================

                const archivos =
                    await respuesta.json();


                // =================================================
                // CONTENEDOR DE LA LISTA
                // =================================================

                const contenedorLista =
                    document.getElementById(
                        "listaArchivosCsv"
                    );


                if (!contenedorLista) {

                    throw new Error(
                        "No existe el elemento HTML listaArchivosCsv"
                    );

                }


                contenedorLista.innerHTML =
                    "";


                // =================================================
                // COMPROBAR SI HAY ARCHIVOS
                // =================================================

                if (
                    !Array.isArray(archivos) ||
                    archivos.length === 0
                ) {

                    contenedorLista.innerHTML =
                        "<li>No hay registros mensuales guardados todavía.</li>";


                    historialCargado =
                        true;


                    return;

                }


                // =================================================
                // NOMBRES DE LOS MESES
                // =================================================

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


                // =================================================
                // PROCESAR CADA ARCHIVO
                // =================================================

                archivos.forEach(
                    function(archivo) {

                        let nodo =
                            "";

                        let anio =
                            "";

                        let mesNum =
                            "";


                        // =========================================
                        // ARCHIVO DEL NODO 1
                        // =========================================

                        if (
                            archivo.startsWith(
                                "historial_nodo1_"
                            )
                        ) {

                            nodo =
                                "Nodo 1";


                            const parteFecha =
                                archivo
                                    .replace(
                                        "historial_nodo1_",
                                        ""
                                    )
                                    .replace(
                                        ".csv",
                                        ""
                                    );


                            const partesFecha =
                                parteFecha.split(
                                    "-"
                                );


                            anio =
                                partesFecha[0];


                            mesNum =
                                partesFecha[1];

                        }


                        // =========================================
                        // ARCHIVO DEL NODO 2
                        // =========================================

                        else if (
                            archivo.startsWith(
                                "historial_nodo2_"
                            )
                        ) {

                            nodo =
                                "Nodo 2";


                            const parteFecha =
                                archivo
                                    .replace(
                                        "historial_nodo2_",
                                        ""
                                    )
                                    .replace(
                                        ".csv",
                                        ""
                                    );


                            const partesFecha =
                                parteFecha.split(
                                    "-"
                                );


                            anio =
                                partesFecha[0];


                            mesNum =
                                partesFecha[1];

                        }


                        // =========================================
                        // ARCHIVO ANTIGUO
                        // =========================================

                        else if (
                            archivo.startsWith(
                                "historial_"
                            )
                        ) {

                            /*
                             * Esto permite que los archivos
                             * antiguos sigan apareciendo.
                             *
                             * Ejemplo:
                             *
                             * historial_2026-09.csv
                             */

                            nodo =
                                "Historial";


                            const parteFecha =
                                archivo
                                    .replace(
                                        "historial_",
                                        ""
                                    )
                                    .replace(
                                        ".csv",
                                        ""
                                    );


                            const partesFecha =
                                parteFecha.split(
                                    "-"
                                );


                            anio =
                                partesFecha[0];


                            mesNum =
                                partesFecha[1];

                        }


                        // =========================================
                        // FORMATO DESCONOCIDO
                        // =========================================

                        else {

                            console.warn(
                                "Archivo CSV con formato desconocido:",
                                archivo
                            );


                            return;

                        }


                        // =========================================
                        // OBTENER NOMBRE DEL MES
                        // =========================================

                        const nombreMes =
                            meses[mesNum] ||
                            mesNum;


                        // =========================================
                        // CREAR ELEMENTO DE LISTA
                        // =========================================

                        const li =
                            document.createElement(
                                "li"
                            );


                        li.style.marginBottom =
                            "10px";


                        li.innerHTML = `

                            <a
                                href="/descargar/${encodeURIComponent(archivo)}"
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
                                📥 Descargar ${nodo} -
                                ${nombreMes} ${anio}
                            </a>

                        `;


                        contenedorLista.appendChild(
                            li
                        );

                    }
                );


                // =================================================
                // MARCAR COMO CARGADO
                // =================================================

                historialCargado =
                    true;


            }

            catch (error) {

                // =================================================
                // MOSTRAR ERROR REAL EN CONSOLA
                // =================================================

                console.error(
                    "Error cargando la lista de CSV:",
                    error
                );


                const contenedorLista =
                    document.getElementById(
                        "listaArchivosCsv"
                    );


                if (
                    contenedorLista
                ) {

                    contenedorLista.innerHTML =
                        "<li>Error al cargar los registros históricos.</li>";

                }

            }

        }
    );

}
