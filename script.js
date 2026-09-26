// ============================================================
// CONFIGURACIÓN
// ============================================================

const URL_DATOS = "/datos";
const URL_HISTORIAL = "/historial";


// ============================================================
// DATOS DE LOS NODOS
// ============================================================

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


// ============================================================
// GRÁFICO
// ============================================================

let graficoTemperatura = null;


// ============================================================
// INICIO
// ============================================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        inicializarGrafico();

        actualizarDatos();
        actualizarHistorial();
        cargarListaCSV();

        setInterval(
            actualizarDatos,
            2000
        );

        setInterval(
            actualizarHistorial,
            5000
        );

    }
);


// ============================================================
// INICIALIZAR GRÁFICO
// ============================================================

function inicializarGrafico() {

    const canvas = document.getElementById(
        "graficoTemperatura"
    );

    if (!canvas) {
        console.warn(
            "No se encontró el canvas graficoTemperatura"
        );

        return;
    }

    const ctx = canvas.getContext("2d");

    graficoTemperatura = new Chart(
        ctx,
        {
            type: "line",

            data: {
                labels: [],

                datasets: [
                    {
                        label: "Nodo 1 - Temperatura",
                        data: [],
                        tension: 0.2,
                        borderWidth: 2,
                        pointRadius: 2
                    },

                    {
                        label: "Nodo 1 - Punto de rocío",
                        data: [],
                        tension: 0.2,
                        borderWidth: 2,
                        pointRadius: 2
                    },

                    {
                        label: "Nodo 2 - Temperatura",
                        data: [],
                        tension: 0.2,
                        borderWidth: 2,
                        pointRadius: 2
                    },

                    {
                        label: "Nodo 2 - Punto de rocío",
                        data: [],
                        tension: 0.2,
                        borderWidth: 2,
                        pointRadius: 2
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
                    x: {
                        title: {
                            display: true,
                            text: "Hora"
                        }
                    },

                    y: {
                        title: {
                            display: true,
                            text: "Temperatura (°C)"
                        }
                    }
                }
            }
        }
    );
}


// ============================================================
// ACTUALIZAR HISTORIAL
// ============================================================

async function actualizarHistorial() {

    try {

        const respuesta = await fetch(
            URL_HISTORIAL
        );

        if (!respuesta.ok) {

            throw new Error(
                "Error HTTP " + respuesta.status
            );

        }

        const historial = await respuesta.json();


        // ----------------------------------------------------
        // Limpiar datos anteriores
        // ----------------------------------------------------

        datosNodos.nodo1.horarios = [];
        datosNodos.nodo1.temperatura = [];
        datosNodos.nodo1.puntoRocio = [];

        datosNodos.nodo2.horarios = [];
        datosNodos.nodo2.temperatura = [];
        datosNodos.nodo2.puntoRocio = [];


        // ----------------------------------------------------
        // Procesar historial
        // ----------------------------------------------------

        historial.forEach(
            function (dato) {

                if (
                    dato.nodo !== 1 &&
                    dato.nodo !== 2
                ) {
                    return;
                }


                const nodo = "nodo" + dato.nodo;


                let fechaHora = dato.fecha_hora;


                if (!fechaHora) {
                    return;
                }


                let hora = fechaHora;


                if (fechaHora.length >= 16) {

                    hora = fechaHora.substring(
                        11,
                        16
                    );

                }


                datosNodos[nodo].horarios.push(
                    hora
                );


                datosNodos[nodo].temperatura.push(
                    dato.temperaturaDS
                );


                datosNodos[nodo].puntoRocio.push(
                    dato.puntoRocio
                );

            }
        );


        actualizarGrafica();

    }
    catch (error) {

        console.error(
            "Error cargando historial:",
            error
        );

    }
}


// ============================================================
// ACTUALIZAR GRÁFICA
// ============================================================

function actualizarGrafica() {

    if (!graficoTemperatura) {
        return;
    }


    const nodo1 = datosNodos.nodo1;
    const nodo2 = datosNodos.nodo2;


    // --------------------------------------------------------
    // Crear conjunto de horarios
    // --------------------------------------------------------

    const horarios = [];


    nodo1.horarios.forEach(
        function (hora) {

            if (!horarios.includes(hora)) {
                horarios.push(hora);
            }

        }
    );


    nodo2.horarios.forEach(
        function (hora) {

            if (!horarios.includes(hora)) {
                horarios.push(hora);
            }

        }
    );


    horarios.sort();


    // --------------------------------------------------------
    // Función para buscar un valor según horario
    // --------------------------------------------------------

    function obtenerValor(
        horariosNodo,
        valoresNodo,
        hora
    ) {

        const indice = horariosNodo.indexOf(
            hora
        );


        if (indice === -1) {
            return null;
        }


        return valoresNodo[indice];

    }


    // --------------------------------------------------------
    // Datos para los cuatro conjuntos
    // --------------------------------------------------------

    const temperaturaNodo1 = [];
    const puntoRocioNodo1 = [];

    const temperaturaNodo2 = [];
    const puntoRocioNodo2 = [];


    horarios.forEach(
        function (hora) {

            temperaturaNodo1.push(
                obtenerValor(
                    nodo1.horarios,
                    nodo1.temperatura,
                    hora
                )
            );


            puntoRocioNodo1.push(
                obtenerValor(
                    nodo1.horarios,
                    nodo1.puntoRocio,
                    hora
                )
            );


            temperaturaNodo2.push(
                obtenerValor(
                    nodo2.horarios,
                    nodo2.temperatura,
                    hora
                )
            );


            puntoRocioNodo2.push(
                obtenerValor(
                    nodo2.horarios,
                    nodo2.puntoRocio,
                    hora
                )
            );

        }
    );


    // --------------------------------------------------------
    // Actualizar gráfico
    // --------------------------------------------------------

    graficoTemperatura.data.labels = horarios;


    graficoTemperatura.data.datasets[0].data =
        temperaturaNodo1;

    graficoTemperatura.data.datasets[1].data =
        puntoRocioNodo1;

    graficoTemperatura.data.datasets[2].data =
        temperaturaNodo2;

    graficoTemperatura.data.datasets[3].data =
        puntoRocioNodo2;


    graficoTemperatura.update();

}


// ============================================================
// ACTUALIZAR DATOS ACTUALES
// ============================================================

async function actualizarDatos() {

    try {

        const respuesta = await fetch(
            URL_DATOS
        );


        if (!respuesta.ok) {

            throw new Error(
                "Error HTTP " + respuesta.status
            );

        }


        const datos = await respuesta.json();


        // ----------------------------------------------------
        // Nodo 1
        // ----------------------------------------------------

        if (datos["1"]) {

            actualizarNodo(
                1,
                datos["1"]
            );

        }
        else {

            marcarDesconectado(
                1
            );

        }


        // ----------------------------------------------------
        // Nodo 2
        // ----------------------------------------------------

        if (datos["2"]) {

            actualizarNodo(
                2,
                datos["2"]
            );

        }
        else {

            marcarDesconectado(
                2
            );

        }


        actualizarEstado();

    }
    catch (error) {

        console.error(
            "Error actualizando datos:",
            error
        );

    }
}


// ============================================================
// ACTUALIZAR INFORMACIÓN DE UN NODO
// ============================================================

function actualizarNodo(
    numeroNodo,
    datos
) {

    const prefijo =
        "nodo" + numeroNodo;


    // --------------------------------------------------------
    // Estado
    // --------------------------------------------------------

    const estado = document.getElementById(
        prefijo + "-estado"
    );

    if (estado) {

        estado.textContent =
            "Conectado";

    }


    // --------------------------------------------------------
    // Temperatura DS18B20
    // --------------------------------------------------------

    const temperaturaDS =
        document.getElementById(
            prefijo + "-temperatura"
        );


    if (temperaturaDS) {

        temperaturaDS.textContent =
            datos.temperaturaDS + " °C";

    }


    // --------------------------------------------------------
    // Temperatura DHT22
    // --------------------------------------------------------

    const temperaturaDHT =
        document.getElementById(
            prefijo + "-temperatura-dht"
        );


    if (temperaturaDHT) {

        temperaturaDHT.textContent =
            datos.temperaturaDHT + " °C";

    }


    // --------------------------------------------------------
    // Humedad
    // --------------------------------------------------------

    const humedad =
        document.getElementById(
            prefijo + "-humedad"
        );


    if (humedad) {

        humedad.textContent =
            datos.humedad + " %";

    }


    // --------------------------------------------------------
    // Punto de rocío
    // --------------------------------------------------------

    const puntoRocio =
        document.getElementById(
            prefijo + "-punto-rocio"
        );


    if (puntoRocio) {

        puntoRocio.textContent =
            datos.puntoRocio + " °C";

    }


    // --------------------------------------------------------
    // Última actualización
    // --------------------------------------------------------

    const actualizacion =
        document.getElementById(
            prefijo + "-actualizacion"
        );


    if (actualizacion) {

        if (datos.fecha_hora) {

            actualizacion.textContent =
                datos.fecha_hora;

        }
        else if (datos.ultima_actualizacion) {

            actualizacion.textContent =
                datos.ultima_actualizacion;

        }

    }

}


// ============================================================
// MARCAR NODO COMO DESCONECTADO
// ============================================================

function marcarDesconectado(
    numeroNodo
) {

    const prefijo =
        "nodo" + numeroNodo;


    const estado =
        document.getElementById(
            prefijo + "-estado"
        );


    if (estado) {

        estado.textContent =
            "Desconectado";

    }

}


// ============================================================
// ACTUALIZAR ESTADO GENERAL
// ============================================================

function actualizarEstado() {

    const estados = [];


    for (
        let numeroNodo = 1;
        numeroNodo <= 2;
        numeroNodo++
    ) {

        const elemento =
            document.getElementById(
                "nodo" +
                numeroNodo +
                "-estado"
            );


        if (elemento) {

            estados.push(
                elemento.textContent
            );

        }

    }


    const conectados =
        estados.filter(
            function (estado) {
                return estado === "Conectado";
            }
        ).length;


    const elementoGeneral =
        document.getElementById(
            "estado-general"
        );


    if (elementoGeneral) {

        if (conectados === 2) {

            elementoGeneral.textContent =
                "Todos los nodos conectados";

        }
        else if (conectados === 1) {

            elementoGeneral.textContent =
                "1 nodo conectado";

        }
        else {

            elementoGeneral.textContent =
                "Ningún nodo conectado";

        }

    }

}


// ============================================================
// LISTA DE ARCHIVOS CSV
// ============================================================

async function cargarListaCSV() {

    try {

        const respuesta = await fetch(
            "/api/archivos-csv"
        );


        if (!respuesta.ok) {

            throw new Error(
                "Error HTTP " +
                respuesta.status
            );

        }


        const datos =
            await respuesta.json();


        console.log(
            "Respuesta de /api/archivos-csv:",
            datos
        );


        // ----------------------------------------------------
        // Buscar el contenedor
        // ----------------------------------------------------

        const contenedor =
            document.getElementById(
                "lista-csv"
            );


        if (!contenedor) {

            console.warn(
                "No se encontró el elemento #lista-csv"
            );

            return;

        }


        // ----------------------------------------------------
        // Limpiar contenido anterior
        // ----------------------------------------------------

        contenedor.innerHTML = "";


        // ----------------------------------------------------
        // Recorrer archivos
        // ----------------------------------------------------

        datos.forEach(
            function (archivo) {

                let nombreArchivo = null;


                // ------------------------------------------------
                // Caso 1: el servidor devuelve directamente
                // el nombre como texto
                // ------------------------------------------------

                if (
                    typeof archivo === "string"
                ) {

                    nombreArchivo =
                        archivo;

                }


                // ------------------------------------------------
                // Caso 2: el servidor devuelve un objeto
                // ------------------------------------------------

                else if (
                    typeof archivo === "object" &&
                    archivo !== null
                ) {

                    nombreArchivo =
                        archivo.nombre ||
                        archivo.archivo ||
                        archivo.filename ||
                        archivo.name ||
                        archivo.file ||
                        null;

                }


                // ------------------------------------------------
                // Si no encontramos nombre, ignorar
                // ------------------------------------------------

                if (!nombreArchivo) {

                    console.warn(
                        "No se pudo determinar el nombre del archivo:",
                        archivo
                    );

                    return;

                }


                // ------------------------------------------------
                // Determinar nodo
                // ------------------------------------------------

                let numeroNodo = null;


                if (
                    nombreArchivo.includes(
                        "historial_nodo1_"
                    )
                ) {

                    numeroNodo = 1;

                }
                else if (
                    nombreArchivo.includes(
                        "historial_nodo2_"
                    )
                ) {

                    numeroNodo = 2;

                }


                // ------------------------------------------------
                // Determinar año y mes
                // ------------------------------------------------

                let anio = "";
                let mes = "";


                const coincidencia =
                    nombreArchivo.match(
                        /_(\d{4})-(\d{2})\.csv$/
                    );


                if (coincidencia) {

                    anio =
                        coincidencia[1];

                    mes =
                        coincidencia[2];

                }


                // ------------------------------------------------
                // Nombre del mes
                // ------------------------------------------------

                const nombresMeses = [
                    "",
                    "Enero",
                    "Febrero",
                    "Marzo",
                    "Abril",
                    "Mayo",
                    "Junio",
                    "Julio",
                    "Agosto",
                    "Septiembre",
                    "Octubre",
                    "Noviembre",
                    "Diciembre"
                ];


                let nombreMes = mes;


                const numeroMes =
                    parseInt(
                        mes,
                        10
                    );


                if (
                    numeroMes >= 1 &&
                    numeroMes <= 12
                ) {

                    nombreMes =
                        nombresMeses[
                            numeroMes
                        ];

                }


                // ------------------------------------------------
                // Texto visible
                // ------------------------------------------------

                let textoArchivo;


                if (
                    numeroNodo === 1
                ) {

                    textoArchivo =
                        "Descargar Historial - Nodo 1 - " +
                        nombreMes +
                        " " +
                        anio;

                }
                else if (
                    numeroNodo === 2
                ) {

                    textoArchivo =
                        "Descargar Historial - Nodo 2 - " +
                        nombreMes +
                        " " +
                        anio;

                }
                else {

                    textoArchivo =
                        "Descargar Historial - " +
                        nombreMes +
                        " " +
                        anio;

                }


                // ------------------------------------------------
                // Crear enlace
                // ------------------------------------------------

                const enlace =
                    document.createElement(
                        "a"
                    );


                enlace.href =
                    "/descargar/" +
                    encodeURIComponent(
                        nombreArchivo
                    );


                enlace.textContent =
                    textoArchivo;


                enlace.target =
                    "_blank";


                enlace.download =
                    nombreArchivo;


                enlace.className =
                    "enlace-csv";


                // ------------------------------------------------
                // Agregar al contenedor
                // ------------------------------------------------

                contenedor.appendChild(
                    enlace
                );


                contenedor.appendChild(
                    document.createElement(
                        "br"
                    )
                );

            }
        );


    }
    catch (error) {

        console.error(
            "Error cargando la lista de CSV:",
            error
        );


        const contenedor =
            document.getElementById(
                "lista-csv"
            );


        if (contenedor) {

            contenedor.textContent =
                "Error al cargar los registros históricos";

        }

    }

}


// ============================================================
// MAPA
// ============================================================

let mapa = null;

let marcadorNodo1 = null;
let marcadorNodo2 = null;


// ============================================================
// INICIALIZAR MAPA
// ============================================================

function inicializarMapa() {

    const elementoMapa =
        document.getElementById(
            "mapa"
        );


    if (!elementoMapa) {
        return;
    }


    mapa = L.map(
        "mapa"
    ).setView(
        [
            -38.84585,
            -68.07172
        ],
        17
    );


    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            maxZoom: 19,
            attribution:
                "&copy; OpenStreetMap"
        }
    ).addTo(
        mapa
    );


    marcadorNodo1 =
        L.marker(
            [
                -38.845769,
                -68.071461
            ]
        )
        .addTo(
            mapa
        )
        .bindPopup(
            "<b>Nodo 1</b><br>Manzana 1"
        );


    marcadorNodo2 =
        L.marker(
            [
                -38.845947,
                -68.071986
            ]
        )
        .addTo(
            mapa
        )
        .bindPopup(
            "<b>Nodo 2</b><br>Ciruela 1"
        );

}


// ============================================================
// INICIAR MAPA
// ============================================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        inicializarMapa();

    }
);
